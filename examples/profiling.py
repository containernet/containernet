#!/usr/bin/env python2

import os
import argparse
import itertools as it
import time
import yaml
import copy
import subprocess
import sys
import re
from mininet.net import Containernet
from mininet.clean import cleanup
from mininet.node import Controller, Docker, OVSSwitch, LibvirtHost, Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info, debug, warn, error, output
from mininet.link import TCLink, Link
from mininet.topo import Topo

import MaxiNet
from MaxiNet.Frontend import maxinet
from MaxiNet.Frontend.container import Docker as MaxiDocker
from MaxiNet.Frontend.libvirt import LibvirtHost as MaxiVm


class Profiler:
    def __init__(self, experiment, output_folder, profile_type):
        self.data = experiment
        self.output_folder = output_folder.rstrip("/")

        self.systemd_run_cmd = "/usr/bin/systemd-run"
        self.remote_run = "root@{host}"

        self.nodes = []
        self.configurations = 0
        self.active_configuration = 0
        self.run_nr = 0
        self.outfile_template = "{base}/{ename}-{profile}-{node}-{conf}-{run}.exp"

        self.remove_args = ['systemd_type', 'waitpid']

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

        print("Experiment contains %d different configurations." % self.configurations)

        self.profile_type = profile_type

        # maxinet related stuff

        if self.profile_type == 'maxinet':
            self.topo = Topo()
            self.cluster = maxinet.Cluster()
            self.maxinet_experiment = None

        # containernet
        if self.profile_type == 'containernet':
            self.topo = Topo()
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
            profile=self.profile_type,
            run=self.run_nr
        )

        # insert ip and outfile if needed
        if isinstance(string, basestring):
            return string.format(outdir=self.output_folder, outfile=outfile, target_ip=self.data.get('target_ip'))
        if isinstance(string, list):
            formatted_list = []
            for i in string:
                formatted_list.append(i.format(outdir=self.output_folder,
                                               outfile=outfile,
                                               target_ip=self.data.get('target_ip')))
            return formatted_list

    def get_node(self, nodename):
        if self.profile_type == 'containernet':
            return self.containernet.get(nodename)
        if self.profile_type == 'maxinet':
            return self.maxinet_experiment.get_node(nodename)

    def get_node_command(self, cmd_type, node):
        cmd = node.get(cmd_type)
        if self.profile_type in node and cmd_type in node[self.profile_type]:
            cmd = node[self.profile_type][cmd_type]
        return cmd

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
            info("Updated node %s configuration to: %s\n" % (node['name'], conf))

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

                info("Updated node %s configuration to: %s\n" % (node['name'], conf))
        return True

    def run_command(self, cmd, node=None):
        if isinstance(cmd, list) or isinstance(cmd, basestring):
            cmd = {'args': cmd}
        cmd = copy.deepcopy(cmd)

        if isinstance(cmd['args'], list):
            cmd['args'] = " ".join(cmd['args'])

        # remove args that we don't want to carry over to the subprocess / node call
        for arg in self.remove_args:
            if arg in cmd:
                del cmd[arg]

        if 'shell' not in cmd:
            cmd['shell'] = True

        debug(str(cmd) + "\n")
        # run on host if node is not set
        if node is None:
            return subprocess.check_output(**cmd)

        cmd['args'] = self.format_command(cmd['args'], node)
        create_dir ="mkdir -p %s" % self.output_folder

        if self.profile_type == 'local':
            # add ssh call to our command if we have to run remote
            run_on = self.get_node_command('run_on', node)
            if node and run_on:
                cmd['args'] = "/usr/bin/ssh %s '%s'" % (self.remote_run.format(host=run_on), cmd['args'])
                create_dir = "/usr/bin/ssh %s '%s'" % (self.remote_run.format(host=run_on), create_dir)

        debug("Running cmd {cmd} on {node}.\n".format(cmd=cmd['args'],
                                                    node=node['name']
                                                    )
              )
        if self.profile_type == 'local':
            # local variant has to create the directories
            subprocess.call(create_dir, shell=True)
            return subprocess.check_output(**cmd)
        else:
            n = self.get_node(node['name'])
            if isinstance(cmd['args'], list):
                cmd['args'] = " ".join(cmd['args'])
            return n.cmd(cmd['args'])

    def setup_experiment(self):
        # local profiling will always use hardware, so no need to setup switches
        if self.profile_type != 'local':
            dpid = 2000
            output("Setting up switches\n")
            for switch in self.data.get('switches', []):
                self.topo.addSwitch(switch, dpid=maxinet.Tools.makeMAC(dpid))
                dpid += 1

        output("Setting up nodes\n")
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
        output("Setting up links\n")
        for link in self.data.get('links', {}):
            if self.profile_type != 'local':
                if 'from' not in link or 'to' not in link:
                    warn("Misconfigured Link %s\n" % link)
                    continue

                for p in ['bw', 'loss']:
                    if p in link.get('params', {}):
                        link['params'][p] = float(link['params'][p])

                self.topo.addLink(link['from'], link['to'], **link.get('params', {}))

        if self.profile_type == 'maxinet':
            output("Starting MaxiNet\n")
            self.maxinet_experiment = maxinet.Experiment(self.cluster,
                                                         self.topo,
                                                         switch=OVSSwitch,
                                                         **self.data.get('maxinet', {}))
            self.maxinet_experiment.setup()

        if self.profile_type == 'containernet':
            output("Starting Containernet\n")
            # MaxiNet defaults to TCLink while Containernet defaults to Link so set it here
            self.containernet = Containernet(topo=self.topo, switch=OVSSwitch, link=TCLink)
            self.containernet.start()

        for node in self.nodes:
            # do a deepcopy so modifications don't carry over to the next run
            cmd = copy.deepcopy(self.get_node_command("setup", node))
            if cmd:
                if self.profile_type == 'local':
                    # run it in a slice so we can reference it later if its local
                    # other profile types do not need this
                    cmd['args'] = "%s --slice perf-%s.slice --service-type %s %s" % (
                        self.systemd_run_cmd, node['name'],
                        cmd.get("systemd_type", "oneshot"),
                        cmd['args']
                    )

                self.run_command(cmd, node)

    def start_experiment(self):
        try:
            for index in range(0, self.configurations):
                print("\n\nRun Nr: %d of Exp: %s. Configuration: %d\n\n" % (self.run_nr, self.data['name'], index))
                failed = False
                for node in self.nodes:
                    if not self.apply_configuration(node, index):
                        error(
                        "Failed to configure node %s with conf %d, skipping configuration.\n" % (node['name'], index))
                        failed = True

                if failed:
                    continue
                info("Running start commands\n")

                # will contain the pids of the running processes if the script has to wait for them
                pids = []
                for node in self.nodes:
                    start = copy.deepcopy(self.get_node_command("start", node))
                    if start:
                        # super hack start
                        # echo the pid of the command so we can monitor for it afterwards
                        if start.get('waitpid'):
                            start['args'] = str(start['args']) + "echo pid=$!"
                        try:
                            p = self.run_command(start, node)
                        except subprocess.CalledProcessError as e:
                            error(e + "\n")
                        else:
                            pid = re.search("pid=(\d+)", p)
                            if pid and int(pid.group(1)) > 0 and start.get('waitpid'):
                                pids.append([node, pid.group(1)])

                # other approach to waiting for the processes to finish is to set a maximum duration
                # while possible this does not make sense with waitpid == True
                start_time = time.time()
                if 'duration' in self.data:
                    print("Experiment duration set to %s seconds." % self.data.get('duration'))
                    while start_time + int(self.data.get('duration')) > time.time():
                        time.sleep(0.5)

                info("Waiting for startprocesses to finish\n")
                # super hack continued
                # call ls on the pid in /proc to see if the process actually terminated
                for p in pids:
                    running = True
                    while running:
                        try:
                            output = self.run_command({'args': "ls /proc/%s" % p[1], 'shell': True}, p[0])
                        except subprocess.CalledProcessError:
                            running = False
                        else:
                            if "cannot" in output:
                                running = False
                        time.sleep(0.5)

                for node in self.nodes:
                    stop = self.get_node_command("stop", node)
                    if stop:
                        # stop command can always fail, dont care
                        try:
                            self.run_command(stop, node)
                        except:
                            pass
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
                    run_on = self.get_node_command("run_on", node)
                    if run_on:
                        self.run_command(["rsync", "-avz", "%s:%s/" % (run_on,
                                                                      self.output_folder),
                                          self.output_folder
                                          ])
                except:
                    pass
        elif self.profile_type == "maxinet":
            if self.maxinet_experiment:
                self.maxinet_experiment.stop()
                self.maxinet_experiment = None
            # aggregate all outfiles from all hosts in the mapping
            # and of course rsync has to be passwordless
            if "hostnamemapping" in self.data.get("maxinet", ""):
                for host in self.data['maxinet']['hostnamemapping'].keys():
                    self.run_command(["rsync", "-avz", "%s:%s/" % (host, self.output_folder), self.output_folder])
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
                    error("Error in run %d. %s" % (run, e))
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
        default="containernet",
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
    setLogLevel('info')

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
