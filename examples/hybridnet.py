#!/usr/bin/python

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
    h2 = net.addLibvirthost("test1", cls=LibvirtHost, disk_image="/home/xschlef/no-cow/test-vm1.qcow2")

    info('*** Adding switch\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2', cls=OVSSwitch)
    s3 = net.addSwitch('s3')

    info('*** Creating links\n')
    net.addLink(h1, s1)

    info('*** Starting network\n')
    net.start()


    net.ping([h2], manualdestip="10.0.0.254")

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network')
    net.stop()

if __name__ == '__main__':
    setLogLevel('debug')
    topology()
