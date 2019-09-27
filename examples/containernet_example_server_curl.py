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
server = net.addDocker('server', ip='10.0.0.251', dcmd="python app.py",
                       dimage="server_example:latest")
client = net.addDocker('client', ip='10.0.0.252', dimage="curl_example:latest")
info('*** Adding switches\n')
s1 = net.addSwitch('s1')
s2 = net.addSwitch('s2')
info('*** Creating links\n')
net.addLink(server, s1)
net.addLink(s1, s2, cls=TCLink, delay='100ms', bw=1)
net.addLink(s2, client)
info('*** Starting network\n')
net.start()
info('\nclient.cmd("time curl 10.0.0.251/9999"):\n')
info(client.cmd("time curl 10.0.0.251/9999") + "\n")
info('*** Running CLI\n')
CLI(net)
info('*** Stopping network')
net.stop()
