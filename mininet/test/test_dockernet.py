import unittest
import os
import time
from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import UserSwitch, OVSSwitch, IVSSwitch
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup


class simpleStarTestTopology( object ):
    """
        Helper class to do basic test setups.
        s1 -- s2 -- s3
    """

    def createNet(self):
        self.net = Mininet( controller=Controller )
        self.net.addController( 'c0' )
        self.s1 = self.net.addSwitch( 's1' )
        self.s2 = self.net.addSwitch( 's2' )
        self.s3 = self.net.addSwitch( 's3' )
        self.net.addLink( self.s1, self.s2 )
        self.net.addLink( self.s2, self.s3 )

    def startNet(self):
        self.net.start()

    def stopNet(self):
        self.net.stop()

    @staticmethod
    def setUp():
        pass

    @staticmethod
    def tearDown():
        # TODO kill all docker containers!!!!!!!
        cleanup()


class testDockernet( simpleStarTestTopology, unittest.TestCase ):

    def testSingleDockerConnection( self ):
        """
        Create one host and one Docker container, connect them to s1
        and let them ping each other.
        """
        self.createNet()
        h1 = self.net.addHost( 'h1', ip='10.0.0.1' )
        d1 = self.net.addDocker( 'd1', ip='10.0.0.254', dimage="ubuntu" )
        self.net.addLink( h1, self.s1 )
        self.net.addLink( self.s1, d1 )

        self.startNet()

        assert(self.net.ping([h1, d1]) <= 0.0)

        self.stopNet()

    def testSingleDocker2( self ):
        print "Dockernet TEST2"


if __name__ == '__main__':
    unittest.main()
