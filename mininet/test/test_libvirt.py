#!/usr/bin/env python2
import unittest
import os
import time
import subprocess
import docker
from mininet.net import Containernet
from mininet.node import Host, Controller, OVSSwitch, Docker
from mininet.link import TCLink
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup
import libvirt
import xml.dom.minidom as minidom


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
        self.l = []
        self.docker_cli = None
        self.lv_conn_qemu = libvirt.open('qemu:///system')
        self.image_name = "/home/xschlef/no-cow/test-vm1.qcow2"
        super(simpleTestTopology, self).__init__(*args, **kwargs)

    def createNet(
            self,
            nswitches=1, nhosts=0, ndockers=0, nlibvirt=0,
            autolinkswitches=False):
        """
        Creates a Mininet instance and automatically adds some
        nodes to it.
        """
        self.net = Containernet( controller=Controller, mgmt_net={'mac': '00:AA:BB:CC:DD:EE'}, cmd_endpoint="qemu:///system" )
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
            self.d.append(self.net.addDocker('d%d' % i, dimage="ubuntu:trusty"))

        for i in range(0, nlibvirt):
            self.l.append(self.net.addLibvirthost('l%d' % i, disk_image=self.image_name))

    def startNet(self):
        self.net.start()

    def stopNet(self):
        self.net.stop()

    def getDockerCli(self):
        """
        Helper to interact with local docker instance.
        """
        if self.docker_cli is None:
            self.docker_cli = docker.APIClient(
                base_url='unix://var/run/docker.sock')
        return self.docker_cli

    def setUp(self):
        print "\nTesting: ", self._testMethodName

    @staticmethod
    def tearDown():


        cleanup()
        # make sure that all pending docker containers are killed
        with open(os.devnull, 'w') as devnull:
            subprocess.call(
                "docker rm -f $(docker ps --filter 'label=com.containernet' -a -q)",
                stdout=devnull,
                stderr=devnull,
                shell=True)

    def getContainernetContainers(self):
        """
        List the containers managed by containernet
        """
        return self.getDockerCli().containers(filters={"label": "com.containernet"})

    def getContainernetLibvirtHosts(self):
        hosts = 0
        for domain in self.lv_conn_qemu.listAllDomains():
            xml = minidom.parseString(domain.XMLDesc())
            title = xml.getElementsByTagName("title")
            if title and "com.containernet" in title[0].toxml():
                hosts += 1

        return hosts

@unittest.skip("test")
class testContainernetConnectivity( simpleTestTopology ):
    """
    Tests to check connectivity of Docker containers within
    the emulated network.
    """

    def testHostLv( self ):
        """
        l1 -- h1
        """
        # create network
        self.createNet(nswitches=0, nhosts=1, nlibvirt=1)
        # setup links
        self.net.addLink(self.h[0], self.l[0])
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testLvLv( self ):
        """
        l1 -- l2
        """
        # create network
        self.createNet(nswitches=0, nhosts=0, nlibvirt=2)
        # setup links
        self.net.addLink(self.l[0], self.l[1])
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testHostSwitchLv( self ):
        """
        l1 -- s1 -- h1
        """
        # create network
        self.createNet(nswitches=1, nhosts=1, nlibvirt=1)
        # setup links
        self.net.addLink(self.h[0], self.s[0])
        self.net.addLink(self.l[0], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testDockerSwitchLv( self ):
        """
        d1 -- s1 -- l1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=1, nlibvirt=1)
        # setup links
        self.net.addLink(self.d[0], self.s[0])
        self.net.addLink(self.l[0], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testLvSwitchLv( self ):
        """
        l1 -- s1 -- l1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=2)
        # setup links
        self.net.addLink(self.l[0], self.s[0])
        self.net.addLink(self.l[1], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testLvMultipleInterfaces( self ):
        """
        l1 -- s1 -- l2 -- s2 -- l3
        l2 has two interfaces, each with its own subnet
        """
        # create network
        self.createNet(nswitches=2, nhosts=0, nlibvirt=2)
        # add additional Docker with special IP
        self.l.append(self.net.addLibvirthost(
            'd%d' % len(self.d), ip="11.0.0.2", disk_image=self.image_name))
        # setup links
        self.net.addLink(self.s[0], self.s[1])
        self.net.addLink(self.l[0], self.s[0])
        self.net.addLink(self.l[1], self.s[0])
        self.net.addLink(self.l[2], self.s[1])
        # special link that add second interface to d2
        self.net.addLink(
            self.l[1], self.s[1], params1={"ip": "11.0.0.1/8"})

        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(self.getContainernetLibvirtHosts() == 3)
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.l[0], self.l[1]]) <= 0.0)
        self.assertTrue(self.net.ping([self.l[2]], manualdestip="11.0.0.1") <= 0.0)
        self.assertTrue(self.net.ping([self.l[1]], manualdestip="11.0.0.2") <= 0.0)
        # stop Mininet network
        self.stopNet()

@unittest.skip("test")
class testContainernetLibvirtCommandExecution( simpleTestTopology ):
    """
    Test to check the command execution inside Libvirt containers by
    using the Mininet API.
    """

    def testCommandSimple( self ):
        """
        d1 ls
        d1 ifconfig -a
        d1 ping 127.0.0.1 -c 3
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=1)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(self.l[0], self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue("etc" in self.l[0].cmd("ls /"))
        self.assertTrue("l0-eth0" in self.l[0].cmd("ifconfig -a"))
        self.assertTrue("0%" in self.l[0].cmd("ping 127.0.0.1 -c 3"))
        # stop Mininet network
        self.stopNet()

@unittest.skip("test")
class testContainernetDynamicTopologies( simpleTestTopology ):
    """
    Tests to check dynamic topology support which allows to add
    and remove containers to/from a running Mininet network instance.
    """

    def testSimpleAdd( self ):
        """
        start: l0 -- s0
        add l1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=1)
        # setup links
        self.net.addLink(self.s[0], self.l[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue(len(self.net.hosts) == 1)
        l1 = self.net.addLibvirthost('l1', disk_image=self.image_name)
        self.net.addLink(l1, self.s[0], params1={"ip": "10.0.0.254/8"})
        # check number of running hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.l[0]], manualdestip="10.0.0.254") <= 0.0)
        # stop Mininet network
        self.stopNet()

    # @unittest.skip("test")
    def testSimpleRemove( self ):
        """
        start: l0 -- s0 -- l1
        remove d1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=2)
        # setup links
        self.net.addLink(self.s[0], self.l[0])
        self.net.addLink(self.s[0], self.l[1])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(self.getContainernetLibvirtHosts() == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        self.assertTrue(len(self.net.links) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.l[0]], manualdestip="10.0.0.2") <= 0.0)
        # remove d2 on-the-fly
        self.net.removeLink(node1=self.l[1], node2=self.s[0])
        self.net.removeDocker(self.l[1])
        # check number of running hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        # check connectivity by using ping (now it should be broken)
        self.assertTrue(self.net.ping(
            [self.l[0]], manualdestip="10.0.0.2", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()

    # @unittest.skip("test")
    def testFullyDynamic( self ):
        """
        start: s1 -- h1 (for ping tests)
        add d0, d1, l0, l1
        remove d0, l0
        add l3
        remove d0, l1, l3
        """
        # create network
        self.createNet(nswitches=1, nhosts=1)
        # setup links
        self.net.addLink(self.s[0], self.h[0])
        # start Mininet network
        self.startNet()
        # check number of running hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 0)
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        ### add some hosts: d0, d1, l0, l1
        d0 = self.net.addDocker('d0', dimage="ubuntu:trusty")
        self.net.addLink(d0, self.s[0], params1={"ip": "10.0.0.200/8"})
        d1 = self.net.addDocker('d1', dimage="ubuntu:trusty")
        self.net.addLink(d1, self.s[0], params1={"ip": "10.0.0.201/8"})
        l0 = self.net.addLibvirthost('l0', disk_image=self.image_name)
        self.net.addLink(l0, self.s[0], params1={"ip": "10.0.0.202/8"})
        l1 = self.net.addLibvirthost('l1', disk_image=self.image_name)
        self.net.addLink(l1, self.s[0], params1={"ip": "10.0.0.203/8"})
        # check number of running hosts
        self.assertTrue(len(self.getContainernetContainers()) == 2)
        self.assertTrue(self.getContainernetLibvirtHosts() == 2)
        self.assertTrue(len(self.net.hosts) == 5)
        self.assertTrue(len(self.net.links) == 5)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.200") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.201") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.202") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.203") <= 0.0)
        ### remove d0, l0
        self.net.removeLink(node1=d0, node2=self.s[0])
        self.net.removeDocker(d0)
        self.net.removeLink(node1=l0, node2=self.s[0])
        self.net.removeLibvirthost(l0)
        # check number of running hosts
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(self.getContainernetLibvirtHosts() == 1)
        self.assertTrue(len(self.net.hosts) == 3)
        self.assertTrue(len(self.net.links) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.200", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.202", timeout=1) >= 100.0)
        ### add libvirt: l3
        l3 = self.net.addLibvirthost('l3', disk_image=self.image_name)
        self.net.addLink(l3, self.s[0], params1={"ip": "10.0.0.204/8"})
        # check number of running docker containers
        self.assertTrue(self.getContainernetLibvirtHosts() == 2)
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(len(self.net.hosts) == 4)
        self.assertTrue(len(self.net.links) == 4)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.204") <= 0.0)
        ### remove all containers
        self.net.removeLink(node1=l1, node2=self.s[0])
        self.net.removeLibvirthost(l1)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.204") <= 0.0)
        self.net.removeLink(node1=l3, node2=self.s[0])
        self.net.removeLibvirthost(l3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.201") <= 0.0)
        self.net.removeLink(node1=d1, node2=self.s[0])
        self.net.removeDocker(d1)
        # check number of running hosts
        self.assertTrue(len(self.getContainernetContainers()) == 0)
        self.assertTrue(self.getContainernetLibvirtHosts() == 0)
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        # check connectivity by using ping
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.200", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.201", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.202", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.203", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.204", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()

@unittest.skip("test")
class testContainernetTCLinks( simpleTestTopology ):
    """
    Tests to check TCLinks together with LibvirtHosts
    """

    def testCustomDelay( self ):
        """
        d0,d1 -- s0 --delay-- d2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=3)
        # setup links
        self.net.addLink(self.s[0], self.l[0])
        self.net.addLink(self.s[0], self.l[1])
        self.net.addLink(self.s[0], self.l[2], cls=TCLink, delay="100ms")
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 3)
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping: default link
        _, _, res = self.net.pingFull([self.l[0]], manualdestip="10.0.0.2")[0]
        self.assertTrue(res[3] <= 20)
        # check connectivity by using ping: delayed TCLink
        _, _, res = self.net.pingFull([self.l[0]], manualdestip="10.0.0.3")[0]
        self.assertTrue(res[3] > 200 and res[3] < 500)
        # stop Mininet network
        self.stopNet()

    def testCustomLoss( self ):
        """
        d0,d1 -- s0 --loss-- d2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=3)
        # setup links
        self.net.addLink(self.s[0], self.l[0])
        self.net.addLink(self.s[0], self.l[1])
        self.net.addLink(
            self.s[0], self.l[2], cls=TCLink, loss=100)  # 100% loss
        # start Mininet network
        self.startNet()
        # check number of hosts
        self.assertTrue(self.getContainernetLibvirtHosts() == 3)
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping(
               [self.l[0]], manualdestip="10.0.0.2", timeout=1) <= 0.0)
        # check connectivity by using ping: lossy TCLink (100%)
        self.assertTrue(self.net.ping(
               [self.l[0]], manualdestip="10.0.0.3", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()


class testContainernetLibvirtResourceLimitAPI( simpleTestTopology ):
    """
    Test to check the resource limitation API of the Docker integration.
    TODO: Also check if values are set correctly in the guest VMs
    """

    def testCPUShare( self ):
        """
        l0, l1 with CPU share limits
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=0)
        # add dockers
        l0 = self.net.addLibvirthost('l0', ip='10.0.0.1', disk_image=self.image_name, cpu_shares=10)
        l1 = self.net.addLibvirthost('l1', ip='10.0.0.2', disk_image=self.image_name, cpu_shares=90)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(l0, self.s[0])
        self.net.addLink(l1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([l0, l1]) <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testCPULimitCFSBased( self ):
        """
        l0, l1 with CPU share limits
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        l0 = self.net.addLibvirthost('l0', ip='10.0.0.1', disk_image=self.image_name,
                                     vcpu_period=50000, vcpu_quota=10000)
        l1 = self.net.addLibvirthost('l1', ip='10.0.0.2', disk_image=self.image_name,
                                     vcpu_period=50000, vcpu_quota=10000)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(l0, self.s[0])
        self.net.addLink(l1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([l0, l1]) <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testMemLimits( self ):
        """
        l0, l1 with CPU share limits
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        l0 = self.net.addLibvirthost('l0', ip='10.0.0.1', disk_image=self.image_name,
                                     mem_limit=512)
        l1 = self.net.addLibvirthost('l1', ip='10.0.0.2', disk_image=self.image_name,
                                     mem_limit=768)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(l0, self.s[0])
        self.net.addLink(l1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([l0, l1]) <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testRuntimeCPULimitUpdate(self):
        """
        Test CPU limit update at runtime
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        l0 = self.net.addLibvirthost('l0', ip='10.0.0.1', disk_image=self.image_name,
                                     cpu_shares=50)
        l1 = self.net.addLibvirthost('l1', ip='10.0.0.2', disk_image=self.image_name,
                                     vcpu_period=50000, vcpu_quota=10000)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(l0, self.s[0])
        self.net.addLink(l1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([l0, l1]) <= 0.0)
        # update limits
        l0.updateCpuLimit(cpu_shares=512)
        self.assertEqual(l0.resources['cpu_shares'], 512)
        l1.updateCpuLimit(vcpu_period=50001, vcpu_quota=20000)
        self.assertEqual(l1.resources['vcpu_period'], 50001)
        self.assertEqual(l1.resources['vcpu_quota'], 20000)
        # stop Mininet network
        self.stopNet()

    def testRuntimeMemoryLimitUpdate(self):
        """
        Test mem limit update at runtime
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        l0 = self.net.addLibvirthost('l0', ip='10.0.0.1', disk_image=self.image_name,
                                     mem_limit=512)
        l1 = self.net.addLibvirthost('l1', ip='10.0.0.2', disk_image=self.image_name)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(l0, self.s[0])
        self.net.addLink(l1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([l0, l1]) <= 0.0)
        # update limits
        l0.updateMemoryLimit(mem_limit=1500)
        l1.updateMemoryLimit(mem_limit=512)

        #TODO query libvirt or run cmd inside vm
        # stop Mininet network
        self.stopNet()



if __name__ == '__main__':
    unittest.main()
