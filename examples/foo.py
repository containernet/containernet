#!/usr/bin/python
"""
This is the most simple example to showcase Containernet.
"""
from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
setLogLevel('info')

net = Containernet(controller=Controller)
info('*** Adding controller\n')
net.addController('c0')
info('*** Adding docker containers\n')
d2 = net.addDocker('d2', ip='10.0.0.251', rm=True, dimage="ubuntu:trusty")
info('***D2 started\n')
d1 = net.addDockerFromFile('d1', path="./Dockerfile", rm="True")
info('*** Starting network\n')
net.start()
info('*** Testing connectivity\n')
info('*** Running CLI\n')
CLI(net)
info('*** Stopping network')
net.stop()

