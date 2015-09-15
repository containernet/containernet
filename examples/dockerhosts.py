#!/usr/bin/python

"""
This example shows how to create a simple network and
how to create docker containers (based on existing images)
to it.
"""

from mininet.net import Mininet
from mininet.node import Controller, Docker, OVSSwitch
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
    d1 = net.addHost( 'd1', ip='10.0.0.253', cls=Docker, dimage="ubuntu" )
    d2 = net.addHost( 'd2', ip='10.0.0.254', cls=Docker, dimage="ubuntu" )
    d3 = net.addHost( 'd3', ip='11.0.0.253', cls=Docker, dimage="ubuntu" )

    info( '*** Adding switch\n' )
    s1 = net.addSwitch( 's1' )
    s2 = net.addSwitch( 's2', cls=OVSSwitch )
    s3 = net.addSwitch( 's3' )

    info( '*** Creating links\n' )
    net.addLink( h1, s1 )
    net.addLink( s1, d1 )
    net.addLink( h2, s2 )
    net.addLink( d2, s2 )
    net.addLink( s1, s2 )
    # try to add a second interface to a docker container
    net.addLink( d2, s3, params1={"ip": "11.0.0.254/8"})
    net.addLink( d3, s3 )

    info( '*** Starting network\n')
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )

    info( '*** Stopping network' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    dockerNet()
