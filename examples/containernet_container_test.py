#!/usr/bin/python
"""
This topology is used to test the compatibility of different Docker images.
The images to be tested can be found in 'examples/example-containers'.
They are build with './build.sh'
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
d1 = net.addDocker('d1', dimage="ubuntu:trusty")
d2 = net.addDocker('d2', dimage="containernet_example:ubuntu1404")
d3 = net.addDocker('d3', dimage="containernet_example:ubuntu1604")
d4 = net.addDocker('d4', dimage="containernet_example:ubuntu1804")
d5 = net.addDocker('d5', dimage="containernet_example:centos6")
d6 = net.addDocker('d6', dimage="containernet_example:centos7")
d7 = net.addDocker('d7', dimage="containernet_example:alpine3")

info('*** Adding switches\n')
s1 = net.addSwitch('s1')

info('*** Creating links\n')
net.addLink(d1, s1)
net.addLink(d2, s1)
net.addLink(d3, s1)
net.addLink(d4, s1)
net.addLink(d5, s1)
net.addLink(d6, s1)
net.addLink(d7, s1)

info('*** Starting network\n')
net.start()

info('*** Testing connectivity\n')
net.ping([d2, d1])
net.ping([d3, d1])
net.ping([d4, d1])
net.ping([d5, d1])
net.ping([d6, d1])
net.ping([d7, d1])

info('*** Running CLI\n')
CLI(net)

info('*** Stopping network')
net.stop()

