import pytest
import unittest
import os
import subprocess
import docker
from mininet.net import Containernet
from mininet.node import Controller
from mininet.link import TCLink
from mininet.topolib import TreeContainerNet
from mininet.clean import cleanup


def find_test_container(filename):
    """
    Returns absolute path to given file in misc/ folder.
    """
    abs_path = os.path.dirname(__file__).replace(
        "mininet/test", "")
    return os.path.join(abs_path,
                        "examples/example-containers/{}".format(filename))


class testImageBuilding( unittest.TestCase ):

    def testaddDocker(self):
        net = Containernet(controller=Controller)
        path = find_test_container("webserver_curl")
        d2 = net.addDocker("d2", ip='10.0.0.252',
                           build_params={"dockerfile": "Dockerfile.server",
                                         "path": path})
        self.assertTrue(d2._check_image_exists(_id=d2.dimage))
        d3 = net.addDocker("d3", ip='10.0.0.253',
                           dimage="webserver_curl_test",
                           build_params={"dockerfile": "Dockerfile.server",
                                         "path": path})
        self.assertTrue(d3._check_image_exists("webserver_curl_test"))
        d4 = net.addDocker("d4", ip='10.0.0.254',
                           build_params={"dockerfile": "Dockerfile.server",
                                         "tag": "webserver_curl_test2",
                                         "path": path})
        self.assertTrue(d4._check_image_exists("webserver_curl_test2"))

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

    @staticmethod
    def setUp():
        pass


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
        self.net = Containernet( controller=Controller )
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

    def startNet(self):
        self.net.start()

    def stopNet(self):
        self.net.stop()
        self.s = []
        self.h = []
        self.d = []

    def getDockerCli(self):
        """
        Helper to interact with local docker instance.
        """
        if self.docker_cli is None:
            self.docker_cli = docker.APIClient(
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
                "docker rm -f $(docker ps --filter 'label=com.containernet' -a -q)",
                stdout=devnull,
                stderr=devnull,
                shell=True)

    def getContainernetContainers(self):
        """
        List the containers managed by containernet
        """
        return self.getDockerCli().containers(filters={"label": "com.containernet"})


#@unittest.skip("disabled connectivity tests for development")
class testContainernetConnectivity( simpleTestTopology ):
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
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
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
        self.assertTrue(len(self.getContainernetContainers()) == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
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
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
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
        self.assertTrue(len(self.getContainernetContainers()) == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.pingAll() <= 0.0)
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
            'd%d' % len(self.d), ip="11.0.0.2", dimage="ubuntu:trusty"))
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
        self.assertTrue(len(self.getContainernetContainers()) == 3)
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.d[0], self.d[1]]) <= 0.0)
        self.assertTrue(self.net.ping([self.d[2]], manualdestip="11.0.0.1") <= 0.0)
        self.assertTrue(self.net.ping([self.d[1]], manualdestip="11.0.0.2") <= 0.0)
        # stop Mininet network
        self.stopNet()


#@unittest.skip("disabled command execution tests for development")
class testContainernetContainerCommandExecution( simpleTestTopology ):
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
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue("etc" in self.d[0].cmd("ls"))
        self.assertTrue("d0-eth0" in self.d[0].cmd("ifconfig -a"))
        self.assertTrue("0%" in self.d[0].cmd("ping 127.0.0.1 -c 3"))
        # stop Mininet network
        self.stopNet()


#@unittest.skip("disabled dynamic topology tests for development")
class testContainernetDynamicTopologies( simpleTestTopology ):
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
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(len(self.net.hosts) == 1)
        # add d2 and connect it on-the-fly
        d2 = self.net.addDocker('d2', dimage="ubuntu:trusty")
        self.net.addLink(d2, self.s[0], params1={"ip": "10.0.0.254/8"})
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.d[0]], manualdestip="10.0.0.254") <= 0.0)
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
        self.assertTrue(len(self.getContainernetContainers()) == 2)
        self.assertTrue(len(self.net.hosts) == 2)
        self.assertTrue(len(self.net.links) == 2)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.d[0]], manualdestip="10.0.0.2") <= 0.0)
        # remove d2 on-the-fly
        self.net.removeLink(node1=self.d[1], node2=self.s[0])
        self.net.removeDocker(self.d[1])
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 1)
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        # check connectivity by using ping (now it should be broken)
        self.assertTrue(self.net.ping(
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
        self.assertTrue(len(self.getContainernetContainers()) == 0)
        self.assertTrue(len(self.net.hosts) == 1)
        self.assertTrue(len(self.net.links) == 1)
        ### add some containers: d0, d1, d2, d3
        d0 = self.net.addDocker('d0', dimage="ubuntu:trusty")
        self.net.addLink(d0, self.s[0], params1={"ip": "10.0.0.200/8"})
        d1 = self.net.addDocker('d1', dimage="ubuntu:trusty")
        self.net.addLink(d1, self.s[0], params1={"ip": "10.0.0.201/8"})
        d2 = self.net.addDocker('d2', dimage="ubuntu:trusty")
        self.net.addLink(d2, self.s[0], params1={"ip": "10.0.0.202/8"})
        d3 = self.net.addDocker('d3', dimage="ubuntu:trusty")
        self.net.addLink(d3, self.s[0], params1={"ip": "10.0.0.203/8"})
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 4)
        self.assertTrue(len(self.net.hosts) == 5)
        self.assertTrue(len(self.net.links) == 5)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.200") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.201") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.202") <= 0.0)
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.203") <= 0.0)
        ### remove d0, d1
        self.net.removeLink(node1=d0, node2=self.s[0])
        self.net.removeDocker(d0)
        self.net.removeLink(node1=d1, node2=self.s[0])
        self.net.removeDocker(d1)
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 2)
        self.assertTrue(len(self.net.hosts) == 3)
        self.assertTrue(len(self.net.links) == 3)
        # check connectivity by using ping
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.200", timeout=1) >= 100.0)
        self.assertTrue(self.net.ping(
               [self.h[0]], manualdestip="10.0.0.201", timeout=1) >= 100.0)
        ### add container: d4
        d4 = self.net.addDocker('d4', dimage="ubuntu:trusty")
        self.net.addLink(d4, self.s[0], params1={"ip": "10.0.0.204/8"})
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 3)
        self.assertTrue(len(self.net.hosts) == 4)
        self.assertTrue(len(self.net.links) == 4)
        # check connectivity by using ping
        self.assertTrue(self.net.ping([self.h[0]], manualdestip="10.0.0.204") <= 0.0)
        ### remove all containers
        self.net.removeLink(node1=d2, node2=self.s[0])
        self.net.removeDocker(d2)
        self.net.removeLink(node1=d3, node2=self.s[0])
        self.net.removeDocker(d3)
        self.net.removeLink(node1=d4, node2=self.s[0])
        self.net.removeDocker(d4)
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 0)
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


#@unittest.skip("disabled TCLink tests for development")
class testContainernetTCLinks( simpleTestTopology ):
    """
    Tests to check TCLinks together with Docker containers.
    """

    def testCustomDelay( self ):
        """
        d0,d1 -- s0 --delay-- d2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=3)
        # setup links
        self.net.addLink(self.s[0], self.d[0])
        self.net.addLink(self.s[0], self.d[1])
        self.net.addLink(self.s[0], self.d[2], cls=TCLink, delay="100ms")
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 3)
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping: default link
        _, _, res = self.net.pingFull([self.d[0]], manualdestip="10.0.0.2")[0]
        self.assertLessEqual(res[3], 100)
        # check connectivity by using ping: delayed TCLink
        _, _, res = self.net.pingFull([self.d[0]], manualdestip="10.0.0.3")[0]
        self.assertGreaterEqual(res[3], 200)
        self.assertLessEqual(res[3], 500)
        # stop Mininet network
        self.stopNet()

    def testCustomLoss( self ):
        """
        d0,d1 -- s0 --loss-- d2
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=3)
        # setup links
        self.net.addLink(self.s[0], self.d[0])
        self.net.addLink(self.s[0], self.d[1])
        self.net.addLink(
            self.s[0], self.d[2], cls=TCLink, loss=100)  # 100% loss
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.getContainernetContainers()) == 3)
        self.assertTrue(len(self.net.hosts) == 3)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping(
               [self.d[0]], manualdestip="10.0.0.2", timeout=1) <= 0.0)
        # check connectivity by using ping: lossy TCLink (100%)
        self.assertTrue(self.net.ping(
               [self.d[0]], manualdestip="10.0.0.3", timeout=1) >= 100.0)
        # stop Mininet network
        self.stopNet()


#@unittest.skip("disabled container resource limit tests for development")
class testContainernetContainerResourceLimitAPI( simpleTestTopology ):
    """
    Test to check the resource limitation API of the Docker integration.
    TODO: Also check if values are set correctly in to running containers,
    e.g., with: docker inspect mn.d1 CLI calls?
    """

    def testCPUShare( self ):
        """
        d1, d2 with CPU share limits
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker('d0', ip='10.0.0.1', dimage="ubuntu:trusty", cpu_shares=10)
        d1 = self.net.addDocker('d1', ip='10.0.0.2', dimage="ubuntu:trusty", cpu_shares=90)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(d0, self.s[0])
        self.net.addLink(d1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([d0, d1]) <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testCPULimitCFSBased( self ):
        """
        d1, d2 with CPU share limits
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker(
            'd0', ip='10.0.0.1', dimage="ubuntu:trusty",
            cpu_period=50000, cpu_quota=10000)
        d1 = self.net.addDocker(
            'd1', ip='10.0.0.2', dimage="ubuntu:trusty",
            cpu_period=50000, cpu_quota=10000)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(d0, self.s[0])
        self.net.addLink(d1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([d0, d1]) <= 0.0)
        # stop Mininet network
        self.stopNet()

    def testMemLimits( self ):
        """
        d1, d2 with CPU share limits
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker(
            'd0', ip='10.0.0.1', dimage="ubuntu:trusty",
            mem_limit=132182016)
        d1 = self.net.addDocker(
            'd1', ip='10.0.0.2', dimage="ubuntu:trusty",
            mem_limit=132182016)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(d0, self.s[0])
        self.net.addLink(d1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([d0, d1]) <= 0.0)
        # stop Mininet network
        self.stopNet()

    @pytest.mark.skipif(os.environ.get("CONTAINERNET_NESTED") is not None,
                        reason="not in nested Docker deployment")
    def testRuntimeCPULimitUpdate(self):
        """
        Test CPU limit update at runtime
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker(
            'd0', ip='10.0.0.1', dimage="ubuntu:trusty",
            cpu_share=0.3)
        d1 = self.net.addDocker(
            'd1', ip='10.0.0.2', dimage="ubuntu:trusty",
            cpu_period=50000, cpu_quota=10000)
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(d0, self.s[0])
        self.net.addLink(d1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([d0, d1]) <= 0.0)
        # update limits
        d0.updateCpuLimit(cpu_shares=512)
        self.assertEqual(d0.resources['cpu_shares'], 512)
        d1.updateCpuLimit(cpu_period=50001, cpu_quota=20000)
        self.assertEqual(d1.resources['cpu_period'], 50001)
        self.assertEqual(d1.resources['cpu_quota'], 20000)
        # stop Mininet network
        self.stopNet()

    @pytest.mark.skipif(os.environ.get("CONTAINERNET_NESTED") is not None,
                        reason="not in nested Docker deployment")
    def testRuntimeMemoryLimitUpdate(self):
        """
        Test mem limit update at runtime
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker(
            'd0', ip='10.0.0.1', dimage="ubuntu:trusty",
            mem_limit=132182016)
        d1 = self.net.addDocker(
            'd1', ip='10.0.0.2', dimage="ubuntu:trusty",
            )
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(d0, self.s[0])
        self.net.addLink(d1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check connectivity by using ping: default link
        self.assertTrue(self.net.ping([d0, d1]) <= 0.0)
        # update limits
        d0.updateMemoryLimit(mem_limit=66093056)
        self.assertEqual(d0.resources['mem_limit'], 66093056)
        d1.updateMemoryLimit(memswap_limit=-1)
        self.assertEqual(d1.resources['memswap_limit'], None)
        # stop Mininet network
        self.stopNet()


#@unittest.skip("disabled container resource limit tests for development")
class testContainernetVolumeAPI( simpleTestTopology ):
    """
    Test the volume API.
    """

    def testContainerVolumes( self ):
        """
        d1, d2 with volumes
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker('d0', ip='10.0.0.1', dimage="ubuntu:trusty", volumes=["/:/mnt/vol1:rw"])
        d1 = self.net.addDocker('d1', ip='10.0.0.2', dimage="ubuntu:trusty", volumes=["/:/mnt/vol1:rw", "/:/mnt/vol2:rw"])
        # start Mininet network
        self.startNet()
        # check if we can see the root file system
        self.assertTrue("etc" in d0.cmd("ls /mnt/vol1"))
        self.assertTrue("etc" in d1.cmd("ls /mnt/vol1"))
        self.assertTrue("etc" in d1.cmd("ls /mnt/vol2"))
        # stop Mininet network
        self.stopNet()


@unittest.skip("skip since storage_opt is only supported for overlay on XFS filesystems with pquota mount option")
class testContainernetContainerStorageOptAPI( simpleTestTopology ):
    """
    Test to check the storage option/limitation API of the Docker integration.
    """

    def testStorageOpt( self ):
        """
        d1, d2 with storage size limit
        """
        # create network
        self.createNet(nswitches=1, nhosts=0, ndockers=0)
        # add dockers
        d0 = self.net.addDocker(
            'd0', ip='10.0.0.1', dimage="ubuntu:trusty",
            storage_opt={'size': '42m'})
        d1 = self.net.addDocker(
            'd1', ip='10.0.0.2', dimage="ubuntu:trusty",
            storage_opt={'size': '1G'})
        # setup links (we always need one connection to suppress warnings)
        self.net.addLink(d0, self.s[0])
        self.net.addLink(d1, self.s[0])
        # start Mininet network
        self.startNet()
        # check number of running docker containers
        self.assertTrue(len(self.net.hosts) == 2)
        # check size of default docker storage partition (overlay)
        self.assertEqual(d0.cmd("df -h | grep overlay").split()[1], "42M")
        self.assertEqual(d1.cmd("df -h | grep overlay").split()[1], "1.0G")
        # stop Mininet network
        self.stopNet()

class testCustomTopologies( unittest.TestCase ):
    """
    Test the behaviour of custom containernet topologies.
    """

    def testTreeTopology( self ):
        net = TreeContainerNet(2, 2, dimage="ubuntu:trusty")
        dropped = net.run( net.pingAll )
        self.assertEqual( dropped, 0 )

    @pytest.mark.skipif(os.environ.get("CONTAINERNET_NESTED") is not None,
                        reason="not in nested Docker deployment")
    def testNATWithTreeTopology( self ):
        # In order to test the NAT we spin up another network on the host which
        # is only accessible through a NAT in the Mininet network.
        dockerClient = docker.from_env()
        dockerClient.networks.create(
            "test-nat-network",
            driver="bridge",
            labels={"com.containernet": ""}
        )
        otherContainer = dockerClient.containers.run(
            "ubuntu:trusty",
            network="test-nat-network",
            stdin_open=True,
            detach=True,
            tty=True,
            labels=["com.containernet"]
        )
        # Reload the container to fetch all attributes:
        otherContainer.reload()
        otherContainerIp = otherContainer.attrs['NetworkSettings']['Networks']['test-nat-network']['IPAddress']

        net = TreeContainerNet(2, 2, dimage="ubuntu:trusty")
        net.addNAT().configDefault()
        net.start()

        # Assert that we can reach a container in the other network.
        pingResult = net.ping([net.hosts[0]], manualdestip=otherContainerIp)
        self.assertEqual(pingResult, 0)

        # We only stop this network, tearDown will take care of the extra container.
        net.stop()

    @staticmethod
    def tearDown():
        cleanup()
        # make sure that all pending docker containers and networks are killed
        with open(os.devnull, 'w') as devnull:
            subprocess.call(
                "docker rm -f $(docker ps --filter 'label=com.containernet' -a -q)",
                stdout=devnull,
                stderr=devnull,
                shell=True)
            subprocess.call(
                "docker network rm $(docker network ls --filter 'label=com.containernet' -q)",
                stdout=devnull,
                stderr=devnull,
                shell=True)


if __name__ == '__main__':
    unittest.main()
