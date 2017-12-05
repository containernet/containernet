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
DISK_IMAGE = "/srv/images/ubuntu16.04.qcow2"

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
        self.vm_names = ["vm1", "vm2", "vm3"]
        super(simpleTestTopology, self).__init__(*args, **kwargs)

    def createNet(
            self,
            nswitches=1, nhosts=0, ndockers=0, nlibvirt=0,
            autolinkswitches=False, use_running=False):
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

        for i in range(1, nlibvirt+1):
            self.l.append(self.net.addLibvirthost('vm%d' % i,
                                                  disk_image=DISK_IMAGE,
                                                  use_existing_vm=use_running))

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

#@unittest.skip("test")
class testContainernetConnectivity( simpleTestTopology ):
    """
    Tests to check connectivity of Docker containers within
    the emulated network.
    """

    def testHostLv( self ):
        """
        vm1 -- h1
        """
        # create network
        self.createNet(nswitches=0, nhosts=1, nlibvirt=1)
        # setup links
        self.net.addLink(self.h[0], self.l[0])
        # start Mininet network
        self.startNet()
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testLvLv( self ):
        """
        vm1 -- vm2
        """
        # create network
        self.createNet(nswitches=0, nhosts=0, nlibvirt=2)
        # setup links
        self.net.addLink(self.l[0], self.l[1])
        # start Mininet network
        self.startNet()
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testLvSwitchLv( self ):
        """
        vm1 -- s1 -- vm1
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=2)
        # setup links
        self.net.addLink(self.l[0], self.s[0])
        self.net.addLink(self.l[1], self.s[0])
        # start Mininet network
        self.startNet()
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testLvMultipleInterfaces( self ):
        """
        vm1 -- s1 -- vm2 -- s2 -- vm3
        vm2 has two interfaces, each with its own subnet
        """
        # create network
        self.createNet(nswitches=2, nhosts=0, nlibvirt=2)
        # add additional Docker with special IP
        self.l.append(self.net.addLibvirthost(
            'vm%d' % len(self.d), ip="11.0.0.2", disk_image=DISK_IMAGE))
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
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.l[0], self.l[1]]) <= 0.0)
        self.assertTrue(self.net.ping([self.l[2]], manualdestip="11.0.0.1") <= 0.0)
        self.assertTrue(self.net.ping([self.l[1]], manualdestip="11.0.0.2") <= 0.0)
        # stop Mininet network
        self.stopNet()

#@unittest.skip("test")
class testContainernetDynamicTopologies( simpleTestTopology ):
    """
    Tests to check dynamic topology support which allows to add
    and remove containers to/from a running Mininet network instance.
    """

    def testRunningAdd( self ):
        """
        start: vm1 -- s0
        add vm2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=1)
        # setup links
        self.net.addLink(self.s[0], self.l[0])
        # start Mininet network
        self.startNet()
        self.assertTrue(len(self.net.hosts) == 1)
        vm2 = self.net.addLibvirthost('vm2', disk_image=DISK_IMAGE)
        self.l.append(vm2)
        self.net.addLink(vm2, self.s[0], params1={"ip": "10.0.0.254/8"})
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.l[0]], manualdestip="10.0.0.254") <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testRunningRemove( self ):
        """
        start: vm1 -- s0 -- vm2
        remove vm2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=2)
        # setup links
        self.net.addLink(self.s[0], self.l[0])
        self.net.addLink(self.s[0], self.l[1])
        # start Mininet network
        self.startNet()
        self.assertTrue(len(self.net.hosts) == 2)
        self.assertTrue(len(self.net.links) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.l[0]], manualdestip="10.0.0.2") <= 0.0)
        # remove vm2 on-the-fly
        self.net.removeLink(node1=self.l[1], node2=self.s[0])
        self.net.removeLibvirthost(self.l[1])
        # check number of running hosts
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        # check connectivity by using ping (now it should be broken)
        self.assertTrue(self.net.ping(
            [self.l[0]], manualdestip="10.0.0.2", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()

    def testRunningDynamic( self ):
        """
        start: s1 -- h1 (for ping tests)
        add vm1, vm2
        remove vm1
        add vm3
        remove vm1, vm3
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
        vm1 = self.net.addLibvirthost('vm1', disk_image=DISK_IMAGE)
        self.net.addLink(vm1, self.s[0], params1={"ip": "10.0.0.202/8"})
        vm2 = self.net.addLibvirthost('vm2', disk_image=DISK_IMAGE)
        self.net.addLink(vm2, self.s[0], params1={"ip": "10.0.0.203/8"})
        # check number of running hosts
        self.assertTrue(len(self.net.hosts) == 3)
        self.assertTrue(len(self.net.links) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.202") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.203") <= 0.0)
        self.net.removeLink(node1=vm1, node2=self.s[0])
        self.net.removeLibvirthost(vm1)
        # check number of running hosts
        self.assertTrue(len(self.net.hosts) == 2)
        self.assertTrue(len(self.net.links) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.202", timeout=1) >= 100.0)
        ### add libvirt: vm3
        vm3 = self.net.addLibvirthost('vm3', disk_image=DISK_IMAGE)
        self.net.addLink(vm3, self.s[0], params1={"ip": "10.0.0.204/8"})
        self.assertTrue(len(self.net.hosts) == 3)
        self.assertTrue(len(self.net.links) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.204") <= 0.0)
        ### remove all containers
        self.net.removeLink(node1=vm2, node2=self.s[0])
        self.net.removeLibvirthost(vm2)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.204") <= 0.0)
        self.net.removeLink(node1=vm3, node2=self.s[0])
        self.net.removeLibvirthost(vm3)
        # check number of running hosts
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        # check connectivity by using ping
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.202", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.203", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.204", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()

#@unittest.skip("test")
class testContainernetTCLinks( simpleTestTopology ):
    """
    Tests to check TCLinks together with LibvirtHosts
    """

    def testCustomDelay( self ):
        """
        vm1,vm2 -- s0 --delay-- vm3
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
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping: default link
        _, _, res = self.net.pingFull([self.l[0]], manualdestip="10.0.0.2")[0]
        self.assertTrue(res[3] <= 20)
        # check connectivity by using ping: delayed TCLink
        _, _, res = self.net.pingFull([self.l[0]], manualdestip="10.0.0.3")[0]
        self.assertTrue(res[3] > 200 and res[3] < 500)
        # stop Mininet network
        self.stopNet()

    #@unittest.skip("test")
    def testCustomLoss( self ):
        """
        vm1,vm2 -- s0 --loss-- vm3
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
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping(
               [self.l[0]], manualdestip="10.0.0.2", timeout=1) <= 0.0)
        # check connectivity by using ping: lossy TCLink (100%)
        self.assertTrue(self.net.ping(
               [self.l[0]], manualdestip="10.0.0.3", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()

#@unittest.skip("test")
class testContainernetContainerResourceLimitAPI( simpleTestTopology ):
    """
    Test to check the resource limitation API of the LibvirtHost integration.
    TODO: Also check if values are set correctly in to running containers,
    e.g., with: docker inspect mn.d1 CLI calls?
    """

    def testCPUShare( self ):
        """
        d1, d2 with CPU share limits
        """
        # create network
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=0)
        vm1 = self.net.addLibvirthost('vm1', disk_image=DISK_IMAGE)
        vm2 = self.net.addLibvirthost('vm2', disk_image=DISK_IMAGE)
        self.net.addLink(self.s[0], vm1)
        self.net.addLink(self.s[0], vm2)
        # add dockers
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([vm1], manualdestip="10.0.0.2", timeout=1) <= 0.0)
        vm1.updateCpuLimit(cpu_shares=512, use_libvirt=False)
        params = vm1.domain.schedulerParameters()
        assert(int(params['cpu_shares']) == 512)
        vm2.updateCpuLimit(cpu_quota=500000, cpu_period=100000, use_libvirt=False)
        params = vm2.domain.schedulerParameters()
        assert (int(params['vcpu_quota']) == 500000)
        assert (int(params['vcpu_period']) == 100000)
        self.assertTrue(self.net.ping([vm1], manualdestip="10.0.0.2", timeout=1) <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testMemLimits( self ):
        """
        d1, d2 with CPU share limits
        """
        # create network
        # create network
        self.createNet(nswitches=1, nhosts=0, nlibvirt=0)
        vm1 = self.net.addLibvirthost('vm1', disk_image=DISK_IMAGE)
        self.net.addLink(self.s[0], vm1)
        # add dockers
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        # check connectivity by using ping: default link
        curmem = vm1.domain.memoryStats()['actual']
        vm1.updateMemoryLimit(600)
        time.sleep(5)
        params = vm1.domain.memoryStats()
        assert(long(params['actual']) == 600 * 1024)
        vm1.updateMemoryLimit(curmem / 1024)
        # stop Mininet network
        self.stopNet()

if __name__ == '__main__':
    setLogLevel('info')
    unittest.main()
