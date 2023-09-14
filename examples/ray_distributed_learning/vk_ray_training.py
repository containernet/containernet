#!/usr/bin/python
"""
Ray Workers in Containernet.
"""
import os
import requests
import networkx as nx
from pathlib import Path
import argparse
import itertools
import random

from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCIntf
from mininet.log import info, setLogLevel


def create_net():
    net = Containernet(controller=Controller)
    info('*** Adding controller\n')
    net.addController('c0')
    return net


def add_docker_containers(net, host_data_folder, host_results_folder, num_nodes):
    info('*** Adding docker containers\n')
    head_commands = (
        f"/bin/bash -c 'python ./training_scripts/data/data.py --data all; "
        f"/bin/bash ./utils/edit_hosts.sh;"
        f"ray start --head --node-ip-address 10.0.0.100 --disable-usage-stats;"
        f"exec /bin/bash'"
    )
    worker_commands = (
        f"/bin/bash -c 'python ./training_scripts/data/data.py --data all;"
        f"/bin/bash ./utils/edit_hosts.sh;"
        f"ray start --address 10.0.0.100:6379 --disable-usage-stats;"
        f"exec /bin/bash'"
    )

    workers_data_folder = '/root/data'
    workers_results_folder = '/root/results'

    head = net.addDocker('head', ip='10.0.0.100', dimage="ray:GPU", dcmd=head_commands, cpuset_cpus='0', cpus=1,
                         shm_size="5000mb", dns=["8.8.8.8"], volumes=[f'{host_data_folder}:{workers_data_folder}',
                                                                      f'{host_results_folder}:{workers_results_folder}'])
    workers = []
    for i in range(1, num_nodes):
        workers.append(net.addDocker(f'worker_{i}', ip=f'10.0.0.{i + 100}', dimage="ray:GPU", dcmd=worker_commands,
                                     cpuset_cpus=f'{i}', cpus=1, shm_size="5000mb", dns=["8.8.8.8"],
                                     volumes=[f'{host_data_folder}:{workers_data_folder}',
                                              f'{host_results_folder}:{workers_results_folder}']))

    return head, workers


#VK new
def download_topology(gml_url, file_path):
    """ Download the gml file from gml_url and write it locally to file path if that file doesn't exists yet. 
    Returns the networkx object of that file. """
    if not os.path.exists(file_path):
        with open(file_path, "wb") as file:
            gml = requests.get(gml_url, stream=True)
            gml.raise_for_status()
            for chunk in gml.iter_content(chunk_size=128):
                file.write(chunk)
    return nx.read_gml(file_path)


#VK new
def create_links_from_graph(net, head, workers, graph, bw, mean_latency, stddev_latency, distribution, head_node=None):
    """ Create net from given graph. 
    TODO: Set (other) properties of the links?? """

    assert len(graph.nodes) == len(workers) + 1, "number of ray nodes should equal the number of nodes in the given topology graph"

    info("*** Creating switches with attached ray containers\n")
    nodes = list(graph.nodes)
    switch_dict = {}
    # get index of head node in the graph's node list. random if non given
    if head_node is None:
        index = random.randrange(len(nodes))
    else:
        index = nodes.index(head_node)
    # add ray node to switches
    for ray_container in itertools.chain([head], workers):
        switch = net.addSwitch("s"+str(index))
        switch_dict[nodes[index]] = switch
        net.addLink(ray_container, switch)
        index = (index + 1) % len(nodes)
    
    info("*** Connecting switches via topology of the graph\n")
    if mean_latency:
        mean_latency = f'{mean_latency / 4}us'
    if stddev_latency:
        stddev_latency = f'{stddev_latency / 4}us'
    for v, w in graph.edges:
        # here you could add some additional properties to the links
        net.addLink(switch_dict[v], switch_dict[w], intf=TCIntf, delay=mean_latency, jitter=stddev_latency, distribution=distribution, bw=bw)

# VK changed
def parse_args():
    sudo_user = os.environ.get('SUDO_USER')
    parser = argparse.ArgumentParser(description="Ray Workers in Containernet")
    parser.add_argument('--data-dir', default=Path(f'/home/{sudo_user}') / 'data', help="Host directory for data folder")
    parser.add_argument('--results-dir', default=Path(f'/home/{sudo_user}') / 'results', help="Host directory for results folder")
    parser.add_argument('--topology-file', default=Path(f"topologies/2_star.gml"), help="Path to gml file describing the network topology")
    parser.add_argument('--delay', type=float, default=None, help="Round-trip delay between nodes in microseconds")
    parser.add_argument('--jitter', type=float, default=0., help="Standard deviation of delay between nodes in milliseconds")
    parser.add_argument('--distribution', type=str, default=None, help="Set latency distribution (tc per default offers 'normal', 'pareto', 'paretonormal' but custom distribution files can be created")
    parser.add_argument('--bw', type=float, default=None, help="Bandwidth of the links")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    host_data_folder = args.data_dir
    host_results_folder = args.results_dir
    graph = nx.read_gml(args.topology_file)
    num_nodes = len(graph.nodes) 
    delay = args.delay
    jitter = args.jitter
    bw = args.bw
    distribution = args.distribution

    setLogLevel('info')

    net = create_net()
    head, workers = add_docker_containers(net, host_data_folder, host_results_folder, num_nodes)
    create_links_from_graph(net, head, workers, graph, bw, delay, jitter, distribution, head_node='1')
    info('*** Starting network\n')
    net.start()

    info('*** Running CLI\n')
    CLI(net)
    info('*** Stopping network')
    net.stop()


