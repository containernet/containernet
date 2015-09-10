#!/usr/bin/python

"""
This example shows how to create a simple network and
how to create docker containers (based on existing images)
to it.
"""

from mininet.net import Mininet
from mininet.node import Controller, Docker
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def dockerNet():

    "Create a network with some docker containers acting as hosts."

    net = Mininet( controller=Controller )

    info( '*** Adding controller\n' )
    net.addController( 'c0' )

    info( '*** Adding hosts\n' )
    h1 = net.addHost( 'h1', ip='10.0.0.1' )
    h2 = net.addHost( 'h2', ip='10.0.0.2' )

    info( '*** Adding docker containers\n' )
    d1 = net.addHost( 'd1', ip='10.0.0.253', cls=Docker, dimage="ubuntu", dcmd="/bin/sleep 180" )
    d2 = net.addHost( 'd2', ip='10.0.0.254', cls=Docker, dimage="ubuntu" )

    info( '*** Adding switch\n' )
    s1 = net.addSwitch( 's1' )
    s2 = net.addSwitch( 's2' )

    info( '*** Creating links\n' )
    net.addLink( h1, s1 )
    net.addLink( d1, s1 )
    net.addLink( h2, s2 )
    net.addLink( d2, s2 )
    net.addLink( s1, s2 )

    info( '*** Starting network\n')
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )

    info( '*** Stopping network' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    dockerNet()