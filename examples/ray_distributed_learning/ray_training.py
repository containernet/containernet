#!/usr/bin/python
"""
Ray Workers in Containernet.
"""
import os
from pathlib import Path
import argparse

from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
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


def create_links(net, head, workers, delay):
    info('*** Adding switches\n')
    switch = net.addSwitch('s1')

    info('*** Creating links\n')
    net.addLink(head, switch, delay=f'{delay}ms')
    for worker in workers:
        net.addLink(worker, switch, delay=f'{delay}ms')


def parse_args():
    sudo_user = os.environ.get('SUDO_USER')
    parser = argparse.ArgumentParser(description="Ray Workers in Containernet")
    parser.add_argument('--data-dir', default=Path(f'/home/{sudo_user}') / 'data', help="Host directory for data folder")
    parser.add_argument('--results-dir', default=Path(f'/home/{sudo_user}') / 'results', help="Host directory for results folder")
    parser.add_argument('--num_nodes', type=int, default=4, help="Number of nodes (including the head node)")
    parser.add_argument('--delay', type=float, default=0.004, help="Delay between nodes in milliseconds")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    host_data_folder = args.data_dir
    host_results_folder = args.results_dir
    num_nodes = args.num_nodes
    delay = args.delay * 2

    setLogLevel('info')

    net = create_net()
    head, workers = add_docker_containers(net, host_data_folder, host_results_folder, num_nodes)
    create_links(net, head, workers, delay)

    info('*** Starting network\n')
    net.start()
    info('*** Testing connectivity\n')
    net.ping([head, workers[0]])
    info('*** Running CLI\n')
    CLI(net)
    info('*** Stopping network')
    net.stop()


