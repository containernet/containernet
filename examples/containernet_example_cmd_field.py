#!/usr/bin/python
"""
Example to test the automated CMD field execution feature.
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
# normal container without CMD
d1 = net.addDocker('d1', ip='10.0.0.251', dimage="ubuntu:trusty")
# HTTPD container with CMD that starts httpd in foreground
d2 = net.addDocker('d2', ip='10.0.0.252', dimage="httpd:latest")
info('*** Adding switches\n')
s1 = net.addSwitch('s1')
s2 = net.addSwitch('s2')
info('*** Creating links\n')
net.addLink(d1, s1)
net.addLink(s1, s2, cls=TCLink, delay='100ms', bw=1)
net.addLink(s2, d2)
info('*** Starting network\n')
net.start()
d2.start()
info('*** Running CLI\n')
CLI(net)
info('*** Stopping network')
net.stop()

# Check if things are working:
# 1. Containernet CLI containernet> works after startup
# 2. docker container top mn.d2 shows the running httpd

