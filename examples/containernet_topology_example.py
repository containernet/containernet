#!/usr/bin/python

"""
Create a 1024-host network, and run the CLI on it.
If this fails because of kernel limits, you may have
to adjust them, e.g. by adding entries to /etc/sysctl.conf
and running sysctl -p. Check util/sysctl_addon.
This is a copy of tree1024.py that is using the Containernet
constructor. Containernet overrides the buildFromTopo
functionality and adds Docker hosts instead.
"""

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.node import OVSSwitch
from mininet.topolib import TreeContainerNet

if __name__ == '__main__':
    setLogLevel( 'info' )
    network = TreeContainerNet( depth=2, fanout=100, switch=OVSSwitch )
    network.run( CLI, network )
