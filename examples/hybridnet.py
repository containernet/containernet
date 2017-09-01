#!/usr/bin/env python2

"""
This example shows how to create a simple network and
how to create docker containers (based on existing images)
to it.
"""

from mininet.net import Containernet
from mininet.node import Controller, Docker, OVSSwitch, LibvirtHost
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Link

def topology():

    "Create a network with some docker containers acting as hosts."

    net = Containernet(controller=Controller)

    info('*** Adding controller\n')
    net.addController('c0')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1')
    d1 = net.addDocker('d1', ip='10.0.0.251', dimage="ubuntu:trusty")
    v1 = net.addLibvirthost("v1", disk_image="/srv/images/test-vm1.qcow2")

    info('*** Adding switch\n')
    s1 = net.addSwitch('s1')

    info('*** Creating links\n')
    net.addLink(h1, s1)
    net.addLink(v1, s1)
    net.addLink(d1, s1)
    v1.setMAC('00:AA:BB:CC:DD:EF')

    info('*** Starting network\n')
    net.start()

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network')
    net.stop()

if __name__ == '__main__':
    setLogLevel('debug')
    topology()
