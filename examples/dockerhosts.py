#!/usr/bin/python

"""
This example shows how to create a simple network and
how to create docker containers (based on existing images)
to it.
"""

from mininet.net import Containernet
from mininet.node import Controller, Docker, OVSSwitch
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
    h2 = net.addHost('h2')

    info('*** Adding docker containers\n')
    d1 = net.addDocker('d1', ip='10.0.0.251', dimage="ubuntu:trusty")
    d2 = net.addDocker('d2', ip='10.0.0.252', dimage="ubuntu:trusty", cpu_period=50000, cpu_quota=25000)
    d3 = net.addHost(
        'd3', ip='11.0.0.253', cls=Docker, dimage="ubuntu:trusty", cpu_shares=20)
    # using advanced features like volumes and exposed ports
    d5 = net.addDocker('d5', dimage="ubuntu:trusty", volumes=["/:/mnt/vol1:rw"], ports=[9999], port_bindings={9999:9999}, publish_all_ports=True)

    info('*** Adding switch\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2', cls=OVSSwitch)
    s3 = net.addSwitch('s3')

    info('*** Creating links\n')
    net.addLink(h1, s1)
    net.addLink(s1, d1)
    net.addLink(h2, s2)
    net.addLink(d2, s2)
    net.addLink(s1, s2)
    #net.addLink(s1, s2, cls=TCLink, delay="100ms", bw=1, loss=10)
    # try to add a second interface to a docker container
    net.addLink(d2, s3, params1={"ip": "11.0.0.254/8"})
    net.addLink(d3, s3)

    info('*** Starting network\n')
    net.start()

    net.ping([d1, d2])

    # our extended ping functionality
    net.ping([d1], manualdestip="10.0.0.252")
    net.ping([d2, d3], manualdestip="11.0.0.254")

    info('*** Dynamically add a container at runtime\n')
    d4 = net.addDocker('d4', dimage="ubuntu:trusty")
    # we have to specify a manual ip when we add a link at runtime
    net.addLink(d4, s1, params1={"ip": "10.0.0.254/8"})
    # other options to do this
    #d4.defaultIntf().ifconfig("10.0.0.254 up")
    #d4.setIP("10.0.0.254")

    # if this ping keeps failing, use some waiting
    # time.sleep(2)

    net.ping([d1], manualdestip="10.0.0.254")

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()
