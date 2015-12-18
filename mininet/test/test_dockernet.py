import unittest
import os
import time
import subprocess
import docker
from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import UserSwitch, OVSSwitch, IVSSwitch
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup


class simpleTestTopology( unittest.TestCase ):
    """
        Helper class to do basic test setups.
        s1 -- s2 -- s3 -- ... -- sN
    """

    def __init__(self, *args, **kwargs):
        self.net = None
        self.s = []  # list of switches
        self.h = []  # list of hosts
        self.d = []  # list of docker containers
        self.docker_cli = None
        super(simpleTestTopology, self).__init__(*args, **kwargs)

    def createNet(
            self,
            nswitches=1, nhosts=0, ndockers=0,
            autolinkswitches=False):
        """
        Creates a Mininet instance and automatically adds some
        nodes to it.
        """
        self.net = Mininet( controller=Controller )
        self.net.addController( 'c0' )

        # add some switches
        for i in range(0, nswitches):
            self.s.append(self.net.addSwitch('s%d' % i))
        # if specified, chain all switches
        if autolinkswitches:
            for i in range(0, len(self.s) - 1):
                self.net.addLink(self.s[i], self.s[i + 1])
        # add some hosts
        for i in range(0, nhosts):
            self.h.append(self.net.addHost('h%d' % i))
        # add some dockers
        for i in range(0, ndockers):
            self.d.append(self.net.addDocker('d%d' % i, dimage="ubuntu"))

    def startNet(self):
        self.net.start()

    def stopNet(self):
        self.net.stop()

    def getDockerCli(self):
        """
        Helper to interact with local docker instance.
        """
        if self.docker_cli is None:
            self.docker_cli = docker.Client(
                base_url='unix://var/run/docker.sock')
        return self.docker_cli

    @staticmethod
    def setUp():
        pass

    @staticmethod
    def tearDown():
        cleanup()
        # make sure that all pending docker containers are killed
        with open(os.devnull, 'w') as devnull:
            subprocess.call(
                "sudo docker rm -f $(sudo docker ps -a -q)",
                stdout=devnull,
                stderr=devnull,
                shell=True)


#@unittest.skip("disabled connectivity tests for development")
class testDockernetConnectivity( simpleTestTopology ):
    """
    Tests to check connectivity of Docker containers within
    the emulated network.
    """

    def testHostDocker( self ):
        """
        d1 -- h1
        """
        # create network
        self.createNet(nswitches=0, nhosts=1, ndockers=1)
        # setup links
        self.net.addLink(self.h[0], self.d[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 1)
        assert(len(self.net.hosts) == 2)
        # check connectivity by using ping
        assert(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testDockerDocker( self ):
        """
        d1 -- d2
        """
        # create network
        self.createNet(nswitches=0, nhosts=0, ndockers=2)
        # setup links
        self.net.addLink(self.d[0], self.d[1])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 2)
        assert(len(self.net.hosts) == 2)
        # check connectivity by using ping
        assert(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testHostSwtichDocker( self ):
        """
        d1 -- s1 -- h1
        """
        # create network
        self.createNet(nswitches=1, nhosts=1, ndockers=1)
        # setup links
        self.net.addLink(self.h[0], self.s[0])
        self.net.addLink(self.d[0], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 1)
        assert(len(self.net.hosts) == 2)
        # check connectivity by using ping
        assert(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testDockerSwtichDocker( self ):
        """
        d1 -- s1 -- d2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=2)
        # setup links
        self.net.addLink(self.d[0], self.s[0])
        self.net.addLink(self.d[1], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 2)
        assert(len(self.net.hosts) == 2)
        # check connectivity by using ping
        assert(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testDockerMultipleInterfaces( self ):
        """
        d1 -- s1 -- d2 -- s2 -- d3
        d2 has two interfaces, each with its own subnet
        """
        # create network
        self.createNet(nswitches=2, nhosts=0, ndockers=2)
        # add additional Docker with special IP
        self.d.append(self.net.addDocker(
            'd%d' % len(self.d), ip="11.0.0.2", dimage="ubuntu"))
        # setup links
        self.net.addLink(self.s[0], self.s[1])
        self.net.addLink(self.d[0], self.s[0])
        self.net.addLink(self.d[1], self.s[0])
        self.net.addLink(self.d[2], self.s[1])
        # special link that add second interface to d2
        self.net.addLink(
            self.d[1], self.s[1], params1={"ip": "11.0.0.1/8"})

        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 3)
        assert(len(self.net.hosts) == 3)
        # check connectivity by using ping
        assert(self.net.ping([self.d[0], self.d[1]]) <= 0.0)
        assert(self.net.ping([self.d[2]], manualdestip="11.0.0.1") <= 0.0)
        assert(self.net.ping([self.d[1]], manualdestip="11.0.0.2") <= 0.0)
        # stop Mininet network
        self.stopNet()


#@unittest.skip("disabled command execution tests for development")
class testDockernetContainerCommandExecution( simpleTestTopology ):
    """
    Test to check the command execution inside Docker containers by
    using the Mininet API.
    """

    def testCommandSimple( self ):
        """
        d1 ls
        d1 ifconfig -a
        d1 ping 127.0.0.1 -c 3
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=1)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(self.d[0], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 1)
        assert("etc" in self.d[0].cmd("ls"))
        assert("d0-eth0" in self.d[0].cmd("ifconfig -a"))
        assert("0%" in self.d[0].cmd("ping 127.0.0.1 -c 3"))
        # stop Mininet network
        self.stopNet()


#@unittest.skip("disabled dynamic topology tests for development")
class testDockernetDynamicTopologies( simpleTestTopology ):
    """
    Tests to check dynamic topology support which allows to add
    and remove containers to/from a running Mininet network instance.
    """

    def testSimpleAdd( self ):
        """
        start: d0 -- s0
        add d1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=1)
        # setup links
        self.net.addLink(self.s[0], self.d[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 1)
        assert(len(self.net.hosts) == 1)
        # add d2 and connect it on-the-fly
        d2 = self.net.addDocker('d2', dimage="ubuntu")
        self.net.addLink(d2, self.s[0], params1={"ip": "10.0.0.254/8"})
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 2)
        assert(len(self.net.hosts) == 2)
        # check connectivity by using ping
        assert(self.net.ping([self.d[0]], manualdestip="10.0.0.254") <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testSimpleRemove( self ):
        """
        start: d0 -- s0 -- d1
        remove d1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=2)
        # setup links
        self.net.addLink(self.s[0], self.d[0])
        self.net.addLink(self.s[0], self.d[1])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 2)
        assert(len(self.net.hosts) == 2)
        assert(len(self.net.links) == 2)
        # check connectivity by using ping
        assert(self.net.ping([self.d[0]], manualdestip="10.0.0.2") <= 0.0)
        # remove d2 on-the-fly
        self.net.removeLink(node1=self.d[1], node2=self.s[0])
        self.net.removeDocker(self.d[1])
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 1)
        assert(len(self.net.hosts) == 1)
        assert(len(self.net.links) == 1)
        # check connectivity by using ping (now it should be broken)
        assert(self.net.ping(
            [self.d[0]], manualdestip="10.0.0.2", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()

    def testFullyDynamic( self ):
        """
        start: s1 -- h1 (for ping tests)
        add d0, d1, d2, d3
        remove d0, d1
        add d4
        remove d2, d3, d4
        """
        # create network
        self.createNet(nswitches=1, nhosts=1, ndockers=0)
        # setup links
        self.net.addLink(self.s[0], self.h[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 0)
        assert(len(self.net.hosts) == 1)
        assert(len(self.net.links) == 1)
        ### add some containers: d0, d1, d2, d3
        d0 = self.net.addDocker('d0', dimage="ubuntu")
        self.net.addLink(d0, self.s[0], params1={"ip": "10.0.0.200/8"})
        d1 = self.net.addDocker('d1', dimage="ubuntu")
        self.net.addLink(d1, self.s[0], params1={"ip": "10.0.0.201/8"})
        d2 = self.net.addDocker('d2', dimage="ubuntu")
        self.net.addLink(d2, self.s[0], params1={"ip": "10.0.0.202/8"})
        d3 = self.net.addDocker('d3', dimage="ubuntu")
        self.net.addLink(d3, self.s[0], params1={"ip": "10.0.0.203/8"})
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 4)
        assert(len(self.net.hosts) == 5)
        assert(len(self.net.links) == 5)
        # check connectivity by using ping
        assert(self.net.ping([self.h[0]], manualdestip="10.0.0.200") <= 0.0)
        assert(self.net.ping([self.h[0]], manualdestip="10.0.0.201") <= 0.0)
        assert(self.net.ping([self.h[0]], manualdestip="10.0.0.202") <= 0.0)
        assert(self.net.ping([self.h[0]], manualdestip="10.0.0.203") <= 0.0)
        ### remove d0, d1
        self.net.removeLink(node1=d0, node2=self.s[0])
        self.net.removeDocker(d0)
        self.net.removeLink(node1=d1, node2=self.s[0])
        self.net.removeDocker(d1)
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 2)
        assert(len(self.net.hosts) == 3)
        assert(len(self.net.links) == 3)
        # check connectivity by using ping
        assert(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.200", timeout=1) >= 100.0)
        assert(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.201", timeout=1) >= 100.0)
        ### add container: d4
        d4 = self.net.addDocker('d4', dimage="ubuntu")
        self.net.addLink(d4, self.s[0], params1={"ip": "10.0.0.204/8"})
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 3)
        assert(len(self.net.hosts) == 4)
        assert(len(self.net.links) == 4)
        # check connectivity by using ping
        assert(self.net.ping([self.h[0]], manualdestip="10.0.0.204") <= 0.0)
        ### remove all containers
        self.net.removeLink(node1=d2, node2=self.s[0])
        self.net.removeDocker(d2)
        self.net.removeLink(node1=d3, node2=self.s[0])
        self.net.removeDocker(d3)
        self.net.removeLink(node1=d4, node2=self.s[0])
        self.net.removeDocker(d4)
        # check number of running docker containers
        assert(len(self.getDockerCli().containers()) == 0)
        assert(len(self.net.hosts) == 1)
        assert(len(self.net.links) == 1)
        # check connectivity by using ping
        assert(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.202", timeout=1) >= 100.0)
        assert(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.203", timeout=1) >= 100.0)
        assert(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.204", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()


if __name__ == '__main__':
    unittest.main()
