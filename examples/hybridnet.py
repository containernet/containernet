#!/bin/env python2

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
import libvirt




def topology():

    "Create a network with some docker containers acting as hosts."

    net = Containernet(controller=Controller, mgmt_net={'mac': '00:AA:BB:CC:DD:EE'}, cmd_endpoint="qemu:///system")

    info('*** Adding controller\n')
    net.addController('c0')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1')
    credentials = {
        'credentials': {
            'username': 'root',
            'password': 'containernet'
        }
    }
    v1 = net.addLibvirthost("test1", cls=LibvirtHost, disk_image="/home/xschlef/no-cow/test-vm1.qcow2", login=credentials)
    v2 = net.addLibvirthost("test2", cls=LibvirtHost, disk_image="/home/xschlef/no-cow/test-vm1.qcow2", login=credentials)

    info('*** Adding switch\n')
    s1 = net.addSwitch('s1')

    info('*** Creating links\n')
    net.addLink(v1, s1)
    net.addLink(v2, s1)

    info('*** Starting network\n')
    net.start()

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network')
    net.stop()

if __name__ == '__main__':
    setLogLevel('debug')
    topology()
