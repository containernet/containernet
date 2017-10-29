#!/usr/bin/env python2

import os
import argparse
import itertools as it
import time
import yaml
import copy
import subprocess
import sys
from mininet.net import Containernet
from mininet.clean import cleanup
from mininet.node import Controller, Docker, OVSSwitch, LibvirtHost, Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Link
from mininet.topo import Topo

from MaxiNet.Frontend import maxinet
from MaxiNet.Frontend.container import Docker as MaxiDocker
from MaxiNet.Frontend.libvirt import LibvirtHost as MaxiVm


class Profiler:
    def __init__(self, experiment, output_folder, profile_type):
        self.data = experiment
        self.output_folder = output_folder.rstrip("/")

        self.systemd_run_cmd = "systemd-run"
        self.remote_run = "root@{host}"

        self.nodes = []
        self.configurations = 0
        self.active_configuration = 0
        self.run_nr = 0
        self.outfile_template = "{base}/{ename}-{node}-{conf}-{run}.exp"

        # compute the possible configurations for the nodes
        for nodename, settings in self.data['nodes'].items():
            node = dict()
            node['name'] = nodename
            node.update(settings)

            if "mem" in settings and "cpu_cores" in settings:
                node['configuration'] = Profiler.compute_cartesian_product(
                    {'mem': settings.get('mem'), 'cpu_cores': settings.get('cpu_cores')})
                if len(node['configuration']) > self.configurations:
                    self.configurations = len(node['configuration'])

            self.nodes.append(node)

        self.profile_type = profile_type

        # maxinet related stuff
        self.topo = Topo()
        if self.profile_type == 'maxinet':
            self.cluster = None
            self.maxinet_experiment = None

        # containernet
        self.containernet = None

    @staticmethod
    def compute_cartesian_product(p_dict):
        p_names = sorted(p_dict)
        return [dict(zip(p_names, prod)) for prod in it.product(*(p_dict[n] for n in p_names))]

    def format_command(self, string, node):
        # name the file correctly
        outfile = self.outfile_template.format(
            base=self.output_folder,
            ename=self.data['name'],
            node=node['name'],
            conf=self.active_configuration,
            run=self.run_nr
        )

        # insert ip and outfile if needed
        if isinstance(string, basestring):
            return string.format(outfile=outfile, target_ip=self.data.get('target_ip'))
        if isinstance(string, list):
            formatted_list = []
            for i in string:
                formatted_list.append(i.format(outfile=outfile, target_ip=self.data.get('target_ip')))
            return formatted_list

    def get_node(self, nodename):
        if self.profile_type == 'containernet':
            return self.containernet.get(nodename)
        if self.profile_type == 'maxinet':
            return self.maxinet_experiment.get_node(nodename)

    def apply_configuration(self, node, index):
        if "configuration" not in node:
            return True
        if len(node['configuration']) <= index or len(node['configuration']) == 1:
            conf = node['configuration'][0]
        else:
            conf = node['configuration'][index]
        self.active_configuration = index

        if self.profile_type == 'local':
            command = ["systemctl", "set-property", "perf-%s.slice" % node['name'], "--runtime"]
            cmd = copy.copy(command)
            for c, value in conf.items():
                if c == "cpu_cores":
                    cmd.append("CPUQuota={}%".format(int(float(value) * 100)))
                if c == "mem":
                    cmd.append("MemoryLimit={}M".format(int(value)))

            self.run_command(cmd, node)
            print("Updated node %s configuration to: %s" % (node['name'], conf))

        else:
            n = self.get_node(node['name'])
            # normal hosts are not profiled so only apply limits to nodes within profiles
            if self.profile_type in node and not type(n) == Host:
                for c, value in conf.items():
                    ret = True
                    if c == "cpu_cores":
                        core_map = {}
                        for i in range(0, int(value)):
                            core_map[i] = str(i)
                        ret = n.updateCpuLimit(cores=core_map)
                    if c == "mem":
                        ret = n.updateMemoryLimit(mem_limit=value)

                    if not ret:
                        return False

                print("Updated node %s configuration to: %s" % (node['name'], conf))
        return True

    def run_command(self, cmd, node, **kwargs):
        if node is None:
            if 'popen' in kwargs:
                del kwargs['popen']
                return subprocess.Popen(cmd, **kwargs)
            else:
                return subprocess.call(cmd, **kwargs)
        cmd = self.format_command(cmd, node)
        print("Running cmd {cmd} on {node}. kwargs={kwargs}".format(cmd=cmd,
                                                                    node=node['name'],
                                                                    kwargs=str(kwargs)
                                                                    )
              )
        if self.profile_type == 'local':
            if node and 'run_on' in node.get(self.profile_type, {}):
                cmd.insert(0, self.remote_run.format(host=node[self.profile_type]['run_on']))
                cmd.insert(0, "ssh")

            if 'popen' in kwargs:
                del kwargs['popen']
                return subprocess.Popen(cmd, **kwargs)
            else:
                return subprocess.call(cmd, **kwargs)
        else:
            n = self.get_node(node['name'])
            # containernet and maxinet nodes do not understand shell=True
            if 'shell' in kwargs:
                del kwargs['shell']

            if kwargs.get('popen', False):
                del kwargs['popen']
                return n.popen(cmd, **kwargs)
            else:
                if isinstance(cmd, list):
                    cmd = " ".join(cmd)
                n.cmd(cmd, **kwargs)
                return

    def setup_experiment(self):
        # local profiling will always use hardware, so no need to setup switches
        if self.profile_type != 'local':
            print("Setting up switches")
            for switch in self.data.get('switches', []):
                self.topo.addSwitch(switch)

        print("Setting up nodes")
        # wrap the nodes correctly and put them in the topology
        for n in self.nodes:
            node = copy.deepcopy(n)
            privateDirs = [(self.output_folder, self.output_folder)]
            mac = maxinet.Tools.makeMAC(self.nodes.index(n))
            if self.profile_type in node:
                if 'mac' not in node[self.profile_type]:
                    node[self.profile_type]['mac'] = mac
                # default to host
                if "type" not in node[self.profile_type]:
                    node[self.profile_type]['type'] = "Host"
                    cls = Host
                if self.profile_type == 'containernet':
                    if node[self.profile_type]['type'] == "LibvirtHost":
                        cls = LibvirtHost
                    if node[self.profile_type]['type'] == "Docker":
                        cls = Docker
                    del node[self.profile_type]['type']
                    self.topo.addHost(node['name'],
                                      cls=cls,
                                      privateDirs=privateDirs,
                                      **node.get('containernet', {}))

                if self.profile_type == 'maxinet':
                    if node[self.profile_type]['type'] == "LibvirtHost":
                        cls = MaxiVm
                    if node[self.profile_type]['type'] == "Docker":
                        cls = MaxiDocker
                    del node[self.profile_type]['type']
                    self.topo.addHost(node['name'],
                                      cls=cls,
                                      privateDirs=privateDirs,
                                      **node.get('maxinet', {}))

            else:
                # add the node as a basic mininet host to the topology
                if self.profile_type == 'containernet' or self.profile_type == "maxinet":
                    if 'mac' not in node:
                        node['mac'] = mac
                    self.topo.addHost(node['name'],
                                      privateDirs=privateDirs,
                                      ip=node['ip'],
                                      mac=node['mac'])

        # TODO: netem calls for local profiling
        print("Setting up links")
        for link in self.data.get('links', {}):
            if self.profile_type != 'local':
                if 'from' not in link or 'to' not in link:
                    print("Misconfigured Link %s " % link)
                    continue

                for p in ['bw', 'loss']:
                    if p in link.get('params'):
                        link['params'][p] = float(link['params'][p])
                self.topo.addLink(link['from'], link['to'], cls=TCLink, **link.get('params', {}))

        if self.profile_type == 'maxinet':
            print("Starting MaxiNet")
            self.cluster = maxinet.Cluster()
            self.cluster.logger.setLevel("DEBUG")
            self.maxinet_experiment = maxinet.Experiment(self.cluster,
                                                         self.topo,
                                                         switch=OVSSwitch,
                                                         **self.data.get('maxinet', {}))
            self.maxinet_experiment.setup()
            # wait for the controller to be set up
            time.sleep(5)

        if self.profile_type == 'containernet':
            print("Starting Containernet")
            self.containernet = Containernet(topo=self.topo, switch=OVSSwitch)
            self.containernet.start()

        for node in self.nodes:
            # run it in a slice so we can reference it later if its local
            # other profile types do not need this
            if self.profile_type == 'local' and "setup_cmd" in node.get(self.profile_type, {}):
                tmp = [self.systemd_run_cmd, '--slice', "perf-%s.slice" % node['name']]
                tmp.extend(["--service-type", node[self.profile_type].get("systemd_type", "oneshot")])
                tmp.extend(node[self.profile_type]['setup_cmd'])
                node['setup_cmd'] = tmp

            # actually run the setup command
            if "setup_cmd" in node:
                self.run_command(node[self.profile_type]['setup_cmd'], node)

    def start_experiment(self):
        try:
            for index in range(0, self.configurations):
                print("\n\nRun Nr: %d of Exp: %s. Configuration: %d\n\n" % (self.run_nr, self.data['name'], index))
                failed = False
                for node in self.nodes:
                    if not self.apply_configuration(node, index):
                        print(
                        "Failed to configure node %s with conf %d, skipping configuration." % (node['name'], index))
                        failed = True

                if failed:
                    continue
                print("Running start commands")
                for node in self.nodes:
                    if "start_cmd" in node:
                        self.run_command(node['start_cmd'],
                                         node,
                                         shell=node.get('start_shell', False),
                                         popen=node.get('popen', False))

                    if "start_cmd" in node.get(self.profile_type, {}):
                        self.run_command(node[self.profile_type]['start_cmd'],
                                         node,
                                         shell=node[self.profile_type].get('start_shell', False),
                                         popen=node[self.profile_type].get('popen', False))
        except Exception as e:
            info("Error while running experiment. %s\n" % e)

    def stop_experiment(self):
        # tear down everything
        if self.profile_type == 'local':
            for node in self.nodes:
                cmd = ["systemctl", "stop", "perf-%s.slice" % node['name']]
                try:
                    self.run_command(cmd, node)
                except:
                    pass
                try:
                    if "run_on" in node:
                        self.run_command(["rsync", "-avz", "%s:%s" % (node['run_on'],
                                                                      self.output_folder),
                                          self.output_folder
                                          ],
                                         None)
                except:
                    pass
        elif self.profile_type == "maxinet":
            if self.maxinet_experiment:
                self.maxinet_experiment.stop()
                self.maxinet_experiment = None
            # aggregate all outfiles from all hosts in the mapping, only works for static mappings
            # and of course rsync has to be passwordless
            if "hostnamemapping" in self.data.get("maxinet"):
                for host in self.data['maxinet']['hostnamemapping'].keys():
                    self.run_command(["rsync", "-avz", "%s:%s/" % (host, self.output_folder), self.output_folder], None)
        elif self.profile_type == "containernet":
            if self.containernet:
                self.containernet.stop()
                self.containernet = None

        self.topo = Topo()

    def clean(self):
        # tear down previous failed runs
        if self.profile_type == "local":
            for node in self.nodes:
                cmd = ["systemctl", "stop", "perf-%s.slice" % node['name']]
                try:
                    self.run_command(cmd, node)
                except:
                    pass

        if self.profile_type == "containernet":
            cleanup()

            # maxinet should not be cleaned up automatically

    def run_experiment(self):
        try:
            self.clean()
            for run in range(0, self.data['repetitions']):
                print("\n\nStart Run Nr: %d of Exp: %s.\n\n" % (run, self.data['name']))
                self.setup_experiment()
                try:
                    self.run_nr = run
                    self.start_experiment()
                except Exception as e:
                    print("Error in run %d. %s" % (run, e))
                print("Run Nr: %d finished.\n\n" % run)
                self.stop_experiment()
        finally:
            print("**** FINISHED ****")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Profiling experiment runner.")

    parser.add_argument(
        "-e",
        help="Experiment file to use.",
        required=True,
        dest="yaml_file")

    parser.add_argument(
        "-t",
        help="type: local, containernet, maxinet",
        required=False,
        default="all",
        dest="exp_type")

    parser.add_argument(
        "--ip",
        help="overwrite experiment target ip, useful for localhost experiments",
        required=False,
        dest="target_ip")

    parser.add_argument(
        "-o",
        help="Output folder",
        required=False,
        default="./output",
        dest="output")

    args = parser.parse_args()

    if not os.path.exists(args.output):
        os.mkdir(args.output)

    args.output = os.path.abspath(args.output)

    experiments = yaml.load(open(args.yaml_file))['experiments']
    setLogLevel('debug')

    types = ['local', 'containernet', 'maxinet']

    if args.exp_type not in types and args.exp_type != 'all':
        print("Not a valid type of experiment.")
        sys.exit(0)

    for exp in experiments:
        if args.target_ip:
            exp['target_ip'] = args.target_ip
        if args.exp_type == 'all':
            for t in types:
                e = Profiler(exp, args.output, profile_type=t)
                e.run_experiment()
        else:
            e = Profiler(exp, args.output, profile_type=args.exp_type)
            e.run_experiment()
