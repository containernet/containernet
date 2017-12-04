#!/usr/bin/env python2

"""
This example shows how to create a simple network with two variants to create Libvirt-based hosts.
"""

from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def topology():
    "Create a network with different node types, also utilizing Libvirt"

    net = Containernet(controller=Controller)

    net.addController("c0")

    n1 = net.addHost("h1", ip='10.0.0.1')
    n2 = net.addLibvirthost("vm1", ip='10.0.0.2', domain_name="ubuntu16.04")
    n3 = net.addDocker('d1', ip='10.0.0.3', dimage="ubuntu:trusty")
    n4 = net.addLibvirthost("vm2", ip='10.0.0.4', disk_image="/var/libvirt/images/ubuntu16.04.qcow2")

    info('*** Starting Switches and Links\n')
    s1 = net.addSwitch("s1")
    net.addLink(n1, s1)
    net.addLink(n2, s1)
    net.addLink(n3, s1)
    net.addLink(n4, s1)

    info('*** Starting network\n')
    net.start()

    CLI(net)

    info('*** Stopping network')
    net.stop()


if __name__ == '__main__':
    setLogLevel('debug')
    topology()
