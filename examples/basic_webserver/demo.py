#!/usr/bin/python
"""
This is an example how to simulate a client server environment.
"""
from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel

setLogLevel('info')

net = Containernet(controller=Controller)
net.addController('c0')

info('*** Adding server and client container\n')
server = net.addDocker('server', ip='10.0.0.251', dcmd="python app.py", dimage="test_server:latest")
client = net.addDocker('client', ip='10.0.0.252', dimage="test_client:latest")

info('*** Setup network\n')
s1 = net.addSwitch('s1')
s2 = net.addSwitch('s2')
net.addLink(server, s1)
net.addLink(s1, s2, cls=TCLink, delay='100ms', bw=1)
net.addLink(s2, client)
net.start()

info('*** Starting to execute commands\n')

info('Execute: client.cmd("time curl 10.0.0.251")\n')
info(client.cmd("time curl 10.0.0.251") + "\n")

info('Execute: client.cmd("time curl 10.0.0.251/hello/42")\n')
info(client.cmd("time curl 10.0.0.251/hello/42") + "\n")

CLI(net)

net.stop()
