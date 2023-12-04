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

import docker


def create_net():
    net = Containernet(controller=Controller)
    info("*** Adding controller\n")
    net.addController("c0")
    return net


def add_docker_containers(
    net,
    image,
    host_data_folder,
    host_results_folder,
    num_nodes,
    gpu_instances,
    cpus_per_node,
):
    info("*** Adding docker containers\n")

    # The first ipy gets assigned to the head node
    ips = [f"10.0.0.{i + 100}" for i in range(num_nodes)]
    device_requests = (
        [
            [
                docker.types.DeviceRequest(
                    device_ids=[instance],
                    capabilities=[["gpu", "utility", "compute"]],
                    driver="nvidia",
                )
            ]
            for instance in gpu_instances
        ]
        if gpu_instances
        else [[] for _ in range(num_nodes)]
    )

    commands = [
        (
            f"/bin/bash -c 'python ./training_scripts/data/data.py --data all; "
            f"/bin/bash ./utils/ping_all.sh {' '.join(ips)};"
            f"/bin/bash ./utils/edit_hosts.sh;"
            f"ray start --head --node-ip-address {ips[0]} --disable-usage-stats --num-gpus 1 >/ray.out 2>/ray.err;"
            f"exec /bin/bash'"
        )
    ] + [
        (
            f"/bin/bash -c 'python ./training_scripts/data/data.py --data all;"
            f"/bin/bash ./utils/ping_all.sh {' '.join(ips)};"
            f"/bin/bash ./utils/edit_hosts.sh;"
            f"ray start --address {ips[0]}:6379 --disable-usage-stats --num-gpus 1 >/ray.out 2>/ray.err;"
            f"exec /bin/bash'"
        )
        for i in range(1, num_nodes)
    ]

    workers_data_folder = "/root/data"
    workers_results_folder = "/root/results"

    head = net.addDocker(
        "head",
        ip=ips[0],
        dimage=image,
        dcmd=commands[0],
        cpus=cpus_per_node,
        shm_size="10240mb",
        dns=["8.8.8.8"],
        device_requests=device_requests[0],
        volumes=[
            f"{host_data_folder}:{workers_data_folder}",
            f"{host_results_folder}:{workers_results_folder}",
        ],
    )
    workers = []
    for i in range(1, num_nodes):
        workers.append(
            net.addDocker(
                f"worker_{i}",
                ip=ips[i],
                dimage=image,
                dcmd=commands[i],
                cpus=cpus_per_node,
                shm_size="10240mb",
                dns=["8.8.8.8"],
                device_requests=device_requests[i],
                volumes=[
                    f"{host_data_folder}:{workers_data_folder}",
                    f"{host_results_folder}:{workers_results_folder}",
                ],
            )
        )

    return head, workers


def create_links(net, head, workers, link_delay):
    info("*** Adding switches\n")
    switch = net.addSwitch("s1")

    info("*** Creating links\n")
    net.addLink(head, switch, delay=f"{link_delay}ms")
    for worker in workers:
        net.addLink(worker, switch, delay=f"{link_delay}ms")


def parse_args():
    sudo_user = os.environ.get("SUDO_USER")
    parser = argparse.ArgumentParser(description="Ray Workers in Containernet")
    parser.add_argument(
        "--data-dir",
        default=Path(f"/home/{sudo_user}") / "data",
        help="Host directory for data folder",
    )
    parser.add_argument(
        "--results-dir",
        default=Path(f"/home/{sudo_user}") / "results",
        help="Host directory for results folder",
    )
    parser.add_argument(
        "--num-nodes",
        type=int,
        default=4,
        help="Number of nodes (including the head node)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.0, help="Delay between nodes in milliseconds"
    )
    parser.add_argument(
        "--gpu-instances",
        nargs="+",
        type=str,
        help="Space separated list of nvidia gpu ids. Should be exactly num_nodes many. Use nvidia-smi -L to view ids on your system",
    )
    parser.add_argument(
        "--cpus-per-node",
        type=int,
        default=1,
        help="Number of cpus per node",
    )
    parser.add_argument(
        "--image", type=str, default="ray:gpu", help="The docker image used for hosts"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    image = args.image
    host_data_folder = args.data_dir
    host_results_folder = args.results_dir
    num_nodes = args.num_nodes
    link_delay = args.delay / 2
    gpu_instances = args.gpu_instances
    cpus_per_node = args.cpus_per_node

    if gpu_instances and len(gpu_instances) != num_nodes:
        print(
            f"Received {len(gpu_instances)} gpu ids. This number has to equal num_nodes (currently: {num_nodes})"
        )
        return

    setLogLevel("info")

    net = create_net()
    head, workers = add_docker_containers(
        net,
        image,
        host_data_folder,
        host_results_folder,
        num_nodes,
        gpu_instances,
        cpus_per_node,
    )
    create_links(net, head, workers, link_delay)

    info("*** Starting network\n")
    net.start()
    info("*** Testing connectivity\n")
    net.ping([head, workers[0]])
    info("*** Running CLI\n")
    CLI(net)
    info("*** Stopping network")
    net.stop()


if __name__ == "__main__":
    main()
