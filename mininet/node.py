"""
Node objects for Mininet.

Nodes provide a simple abstraction for interacting with hosts, switches
and controllers. Local nodes are simply one or more processes on the local
machine.

Node: superclass for all (primarily local) network nodes.

Host: a virtual host. By default, a host is simply a shell; commands
    may be sent using Cmd (which waits for output), or using sendCmd(),
    which returns immediately, allowing subsequent monitoring using
    monitor(). Examples of how to run experiments using this
    functionality are provided in the examples/ directory. By default,
    hosts share the root file system, but they may also specify private
    directories.

CPULimitedHost: a virtual host whose CPU bandwidth is limited by
    RT or CFS bandwidth limiting.

Switch: superclass for switch nodes.

UserSwitch: a switch using the user-space switch from the OpenFlow
    reference implementation.

OVSSwitch: a switch using the Open vSwitch OpenFlow-compatible switch
    implementation (openvswitch.org).

OVSBridge: an Ethernet bridge implemented using Open vSwitch.
    Supports STP.

IVSSwitch: OpenFlow switch using the Indigo Virtual Switch.

Controller: superclass for OpenFlow controllers. The default controller
    is controller(8) from the reference implementation.

OVSController: The test controller from Open vSwitch.

NOXController: a controller node using NOX (noxrepo.org).

Ryu: The Ryu controller (https://osrg.github.io/ryu/)

RemoteController: a remote controller node, which may use any
    arbitrary OpenFlow-compatible controller, and which is not
    created or managed by Mininet.

Future enhancements:

- Possibly make Node, Switch and Controller more abstract so that
  they can be used for both local and remote nodes

- Create proxy objects for remote nodes (Mininet: Cluster Edition)
"""

import os
import pty
import re
import signal
import select
import docker
import json
import time
import sys

from subprocess import Popen, PIPE, check_output, list2cmdline
from time import sleep

from mininet.log import info, error, warn, debug
from mininet.util import ( quietRun, errRun, errFail, moveIntf, isShellBuiltin,
                           numCores, retry, mountCgroups, libvirtErrorHandler, numCores )
from mininet.moduledeps import moduleDeps, pathCheck, TUN
from mininet.link import Link, Intf, TCIntf, OVSIntf
from re import findall
from distutils.version import StrictVersion

LIBVIRT_AVAILABLE = False
try:
    import libvirt
    import xml.dom.minidom as minidom
    import paramiko
    import socket
    LIBVIRT_AVAILABLE = True
except ImportError:
    pass

class Node( object ):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""

    portBase = 0  # Nodes always start with eth0/port0, even in OF 1.0

    def __init__( self, name, inNamespace=True, **params ):
        """name: name of node
           inNamespace: in network namespace?
           privateDirs: list of private directory strings or tuples
           params: Node parameters (see config() for details)"""

        # Make sure class actually works
        self.checkSetup()

        self.name = params.get( 'name', name )
        self.privateDirs = params.get( 'privateDirs', [] )
        self.inNamespace = params.get( 'inNamespace', inNamespace )

        # Stash configuration parameters for future reference
        self.params = params

        self.intfs = {}  # dict of port numbers to interfaces
        self.ports = {}  # dict of interfaces to port numbers
                         # replace with Port objects, eventually ?
        self.nameToIntf = {}  # dict of interface names to Intfs

        # Make pylint happy
        ( self.shell, self.execed, self.pid, self.stdin, self.stdout,
            self.lastPid, self.lastCmd, self.pollOut ) = (
                None, None, None, None, None, None, None, None )
        self.waiting = False
        self.readbuf = ''

        # Start command interpreter shell
        self.startShell()
        self.mountPrivateDirs()

    # File descriptor to node mapping support
    # Class variables and methods

    inToNode = {}  # mapping of input fds to nodes
    outToNode = {}  # mapping of output fds to nodes

    @classmethod
    def fdToNode( cls, fd ):
        """Return node corresponding to given file descriptor.
           fd: file descriptor
           returns: node"""
        node = cls.outToNode.get( fd )
        return node or cls.inToNode.get( fd )

    # Command support via shell process in namespace
    def startShell( self, mnopts=None ):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return
        # mnexec: (c)lose descriptors, (d)etach from tty,
        # (p)rint pid, and run in (n)amespace
        opts = '-cd' if mnopts is None else mnopts
        if self.inNamespace:
            opts += 'n'
        # bash -i: force interactive
        # -s: pass $* to shell, and make process easy to find in ps
        # prompt is set to sentinel chr( 127 )
        cmd = [ 'mnexec', opts, 'env', 'PS1=' + chr( 127 ),
                'bash', '--norc', '-is', 'mininet:' + self.name ]
        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
        # in the subprocess and insulate it from signals (e.g. SIGINT)
        # received by the parent
        master, slave = pty.openpty()
        self.shell = self._popen( cmd, stdin=slave, stdout=slave, stderr=slave,
                                  close_fds=False )
        self.stdin = os.fdopen( master, 'rw' )
        self.stdout = self.stdin
        self.pid = self.shell.pid
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        while True:
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
            self.pollOut.poll()
        self.waiting = False
        # +m: disable job control notification
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

    def mountPrivateDirs( self ):
        "mount private directories"
        # Avoid expanding a string into a list of chars
        assert not isinstance( self.privateDirs, basestring )
        for directory in self.privateDirs:
            if isinstance( directory, tuple ):
                # mount given private directory
                privateDir = directory[ 1 ] % self.__dict__
                mountPoint = directory[ 0 ]
                self.cmd( 'mkdir -p %s' % privateDir )
                self.cmd( 'mkdir -p %s' % mountPoint )
                self.cmd( 'mount --bind %s %s' %
                               ( privateDir, mountPoint ) )
            else:
                # mount temporary filesystem on directory
                self.cmd( 'mkdir -p %s' % directory )
                self.cmd( 'mount -n -t tmpfs tmpfs %s' % directory )

    def unmountPrivateDirs( self ):
        "mount private directories"
        for directory in self.privateDirs:
            if isinstance( directory, tuple ):
                self.cmd( 'umount ', directory[ 0 ] )
            else:
                self.cmd( 'umount ', directory )

    def _popen( self, cmd, **params ):
        """Internal method: spawn and return a process
            cmd: command to run (list)
            params: parameters to Popen()"""
        # Leave this is as an instance method for now
        assert self
        return Popen( cmd, **params )

    def cleanup( self ):
        "Help python collect its garbage."
        # We used to do this, but it slows us down:
        # Intfs may end up in root NS
        # for intfName in self.intfNames():
        # if self.name in intfName:
        # quietRun( 'ip link del ' + intfName )
        self.shell = None

    # Subshell I/O, commands and control

    def read( self, maxbytes=1024 ):
        """Buffered read from node, potentially blocking.
           maxbytes: maximum number of bytes to return"""
        count = len( self.readbuf )
        if count < maxbytes:
            data = os.read( self.stdout.fileno(), maxbytes - count )
            self.readbuf += data
        if maxbytes >= len( self.readbuf ):
            result = self.readbuf
            self.readbuf = ''
        else:
            result = self.readbuf[ :maxbytes ]
            self.readbuf = self.readbuf[ maxbytes: ]
        return result

    def readline( self ):
        """Buffered readline from node, potentially blocking.
           returns: line (minus newline) or None"""
        self.readbuf += self.read( 1024 )
        if '\n' not in self.readbuf:
            return None
        pos = self.readbuf.find( '\n' )
        line = self.readbuf[ 0: pos ]
        self.readbuf = self.readbuf[ pos + 1: ]
        return line

    def write( self, data ):
        """Write data to node.
           data: string"""
        os.write( self.stdin.fileno(), data )

    def terminate( self ):
        "Send kill signal to Node and clean up after it."
        self.unmountPrivateDirs()
        if self.shell:
            if self.shell.poll() is None:
                os.killpg( self.shell.pid, signal.SIGHUP )
        self.cleanup()

    def stop( self, deleteIntfs=False ):
        """Stop node.
           deleteIntfs: delete interfaces? (False)"""
        if deleteIntfs:
            self.deleteIntfs()
        self.terminate()

    def waitReadable( self, timeoutms=None ):
        """Wait until node's output is readable.
           timeoutms: timeout in ms or None to wait indefinitely.
           returns: result of poll()"""
        if len( self.readbuf ) == 0:
            return self.pollOut.poll( timeoutms )

    def sendCmd( self, *args, **kwargs ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete.
           args: command and arguments, or string
           printPid: print command's PID? (False)"""
        assert self.shell# and not self.waiting
        printPid = kwargs.get( 'printPid', False )
        # Allow sendCmd( [ list ] )
        if len( args ) == 1 and isinstance( args[ 0 ], list ):
            cmd = args[ 0 ]
        # Allow sendCmd( cmd, arg1, arg2... )
        elif len( args ) > 0:
            cmd = args
        # Convert to string
        if not isinstance( cmd, str ):
            cmd = ' '.join( [ str( c ) for c in cmd ] )
        if not re.search( r'\w', cmd ):
            # Replace empty commands with something harmless
            cmd = 'echo -n'
        self.lastCmd = cmd
        # if a builtin command is backgrounded, it still yields a PID
        if len( cmd ) > 0 and cmd[ -1 ] == '&':
            # print ^A{pid}\n so monitor() can set lastPid
            cmd += ' printf "\\001%d\\012" $! '
        elif printPid and not isShellBuiltin( cmd ):
            cmd = 'mnexec -p ' + cmd
        self.write( cmd + '\n' )
        self.lastPid = None
        self.waiting = True

    def sendInt( self, intr=chr( 3 ) ):
        "Interrupt running command."
        debug( 'sendInt: writing chr(%d)\n' % ord( intr ) )
        self.write( intr )

    def monitor( self, timeoutms=None, findPid=True ):
        """Monitor and return the output of a command.
           Set self.waiting to False if command has completed.
           timeoutms: timeout in ms or None to wait indefinitely
           findPid: look for PID from mnexec -p"""
        ready = self.waitReadable( timeoutms )
        if not ready:
            return ''
        data = self.read( 1024 )
        pidre = r'\[\d+\] \d+\r\n'
        # Look for PID
        marker = chr( 1 ) + r'\d+\r\n'
        if findPid and chr( 1 ) in data:
            # suppress the job and PID of a backgrounded command
            if re.findall( pidre, data ):
                data = re.sub( pidre, '', data )
            # Marker can be read in chunks; continue until all of it is read
            while not re.findall( marker, data ):
                data += self.read( 1024 )
            markers = re.findall( marker, data )
            if markers:
                self.lastPid = int( markers[ 0 ][ 1: ] )
                data = re.sub( marker, '', data )
        # Look for sentinel/EOF
        if len( data ) > 0 and data[ -1 ] == chr( 127 ):
            self.waiting = False
            data = data[ :-1 ]
        elif chr( 127 ) in data:
            self.waiting = False
            data = data.replace( chr( 127 ), '' )
        return data

    def waitOutput( self, verbose=False, findPid=True ):
        """Wait for a command to complete.
           Completion is signaled by a sentinel character, ASCII(127)
           appearing in the output stream.  Wait for the sentinel and return
           the output, including trailing newline.
           verbose: print output interactively"""
        log = info if verbose else debug
        output = ''
        while self.waiting:
            data = self.monitor( findPid=findPid )
            output += data
            log( data )
        return output

    def cmd( self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, args ) )
        if self.shell:
            self.shell.poll()
            if self.shell.returncode is not None:
                print("shell died on ", self.name)
                self.shell = None
                self.startShell()
            self.sendCmd( *args, **kwargs )
            return self.waitOutput( verbose )
        else:
            warn( '(%s exited - ignoring cmd%s)\n' % ( self, args ) )

    def cmdPrint( self, *args):
        """Call cmd and printing its output
           cmd: string"""
        return self.cmd( *args, **{ 'verbose': True } )

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in our namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        defaults = { 'stdout': PIPE, 'stderr': PIPE,
                     'mncmd':
                     [ 'mnexec', '-da', str( self.pid ) ] }
        defaults.update( kwargs )
        if len( args ) == 1:
            if isinstance( args[ 0 ], list ):
                # popen([cmd, arg1, arg2...])
                cmd = args[ 0 ]
            elif isinstance( args[ 0 ], basestring ):
                # popen("cmd arg1 arg2...")
                cmd = args[ 0 ].split()
            else:
                raise Exception( 'popen() requires a string or list' )
        elif len( args ) > 0:
            # popen( cmd, arg1, arg2... )
            cmd = list( args )
        # Attach to our namespace  using mnexec -a
        cmd = defaults.pop( 'mncmd' ) + cmd
        # Shell requires a string, not a list!
        if defaults.get( 'shell', False ):
            cmd = ' '.join( cmd )
        popen = self._popen( cmd, **defaults )
        return popen

    def pexec( self, *args, **kwargs ):
        """Execute a command using popen
           returns: out, err, exitcode"""
        popen = self.popen( *args, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                            **kwargs )
        # Warning: this can fail with large numbers of fds!
        out, err = popen.communicate()
        exitcode = popen.returncode
        return out, err, exitcode

    # Interface management, configuration, and routing

    # BL notes: This might be a bit redundant or over-complicated.
    # However, it does allow a bit of specialization, including
    # changing the canonical interface names. It's also tricky since
    # the real interfaces are created as veth pairs, so we can't
    # make a single interface at a time.

    def newPort( self ):
        "Return the next port number to allocate."
        if len( self.ports ) > 0:
            return max( self.ports.values() ) + 1
        return self.portBase

    def addIntf( self, intf, port=None, moveIntfFn=moveIntf ):
        """Add an interface.
           intf: interface
           port: port number (optional, typically OpenFlow port number)
           moveIntfFn: function to move interface (optional)"""
        if port is None:
            port = self.newPort()
        self.intfs[ port ] = intf
        self.ports[ intf ] = port
        self.nameToIntf[ intf.name ] = intf
        debug( '\n' )
        debug( 'added intf %s (%d) to node %s\n' % (
                intf, port, self.name ) )
        if self.inNamespace:
            debug( 'moving', intf, 'into namespace for', self.name, '\n' )
            moveIntfFn( intf.name, self  )

    def defaultIntf( self ):
        "Return interface for lowest port"
        ports = self.intfs.keys()
        if ports:
            return self.intfs[ min( ports ) ]
        else:
            warn( '*** defaultIntf: warning:', self.name,
                  'has no interfaces\n' )

    def intf( self, intf=None ):
        """Return our interface object with given string name,
           default intf if name is falsy (None, empty string, etc).
           or the input intf arg.

        Having this fcn return its arg for Intf objects makes it
        easier to construct functions with flexible input args for
        interfaces (those that accept both string names and Intf objects).
        """
        if not intf:
            return self.defaultIntf()
        elif isinstance( intf, basestring):
            return self.nameToIntf.get(intf)
        else:
            return intf

    def connectionsTo( self, node):
        "Return [ intf1, intf2... ] for all intfs that connect self to node."
        # We could optimize this if it is important
        connections = []
        for intf in self.intfList():
            link = intf.link
            if link:
                node1, node2 = link.intf1.node, link.intf2.node
                if node1 == self and node2 == node:
                    connections += [ ( intf, link.intf2 ) ]
                elif node1 == node and node2 == self:
                    connections += [ ( intf, link.intf1 ) ]
        return connections

    def deleteIntfs( self, checkName=True ):
        """Delete all of our interfaces.
           checkName: only delete interfaces that contain our name"""
        # In theory the interfaces should go away after we shut down.
        # However, this takes time, so we're better off removing them
        # explicitly so that we won't get errors if we run before they
        # have been removed by the kernel. Unfortunately this is very slow,
        # at least with Linux kernels before 2.6.33
        for intf in self.intfs.values():
            # Protect against deleting hardware interfaces
            if ( self.name in intf.name ) or ( not checkName ):
                intf.delete()
                info( '.' )

    # Routing support

    def setARP( self, ip, mac ):
        """Add an ARP entry.
           ip: IP address as string
           mac: MAC address as string"""
        result = self.cmd( 'arp', '-s', ip, mac )
        return result

    def setHostRoute( self, ip, intf ):
        """Add route to host.
           ip: IP address as dotted decimal
           intf: string, interface name"""
        return self.cmd( 'route add -host', ip, 'dev', intf )

    def setDefaultRoute( self, intf=None ):
        """Set the default route to go through intf.
           intf: Intf or {dev <intfname> via <gw-ip> ...}"""
        # Note setParam won't call us if intf is none
        if isinstance( intf, basestring ) and ' ' in intf:
            params = intf
        else:
            params = 'dev %s' % intf
        # Do this in one line in case we're messing with the root namespace
        self.cmd( 'ip route del default; ip route add default', params )

    # Convenience and configuration methods

    def setMAC( self, mac, intf=None ):
        """Set the MAC address for an interface.
           intf: intf or intf name
           mac: MAC address as string"""
        return self.intf( intf ).setMAC( mac )

    def setIP( self, ip, prefixLen=8, intf=None, **kwargs ):
        """Set the IP address for an interface.
           intf: intf or intf name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs
           kwargs: any additional arguments for intf.setIP"""
        return self.intf( intf ).setIP( ip, prefixLen, **kwargs )

    def IP( self, intf=None ):
        "Return IP address of a node or specific interface."
        return self.intf( intf ).IP()

    def MAC( self, intf=None ):
        "Return MAC address of a node or specific interface."
        return self.intf( intf ).MAC()

    def intfIsUp( self, intf=None ):
        "Check if an interface is up."
        return self.intf( intf ).isUp()

    # The reason why we configure things in this way is so
    # That the parameters can be listed and documented in
    # the config method.
    # Dealing with subclasses and superclasses is slightly
    # annoying, but at least the information is there!

    def setParam( self, results, method, **param ):
        """Internal method: configure a *single* parameter
           results: dict of results to update
           method: config method name
           param: arg=value (ignore if value=None)
           value may also be list or dict"""
        name, value = param.items()[ 0 ]
        if value is None:
            return
        f = getattr( self, method, None )
        if not f:
            return
        if isinstance( value, list ):
            result = f( *value )
        elif isinstance( value, dict ):
            result = f( **value )
        else:
            result = f( value )
        results[ name ] = result
        return result

    def config( self, mac=None, ip=None,
                defaultRoute=None, lo='up', **_params ):
        """Configure Node according to (optional) parameters:
           mac: MAC address for default interface
           ip: IP address for default interface
           ifconfig: arbitrary interface configuration
           Subclasses should override this method and call
           the parent class's config(**params)"""
        # If we were overriding this method, we would call
        # the superclass config method here as follows:
        # r = Parent.config( **_params )
        r = {}
        self.setParam( r, 'setMAC', mac=mac )
        self.setParam( r, 'setIP', ip=ip )
        self.setParam( r, 'setDefaultRoute', defaultRoute=defaultRoute )
        # This should be examined
        self.cmd( 'ifconfig lo ' + lo )
        return r

    def configDefault( self, **moreParams ):
        "Configure with default parameters"
        self.params.update( moreParams )
        self.config( **self.params )

    # This is here for backward compatibility
    def linkTo( self, node, link=Link ):
        """(Deprecated) Link to another node
           replace with Link( node1, node2)"""
        return link( self, node )

    # Other methods

    def intfList( self ):
        "List of our interfaces sorted by port number"
        return [ self.intfs[ p ] for p in sorted( self.intfs.iterkeys() ) ]

    def intfNames( self ):
        "The names of our interfaces sorted by port number"
        return [ str( i ) for i in self.intfList() ]

    def __repr__( self ):
        "More informative string representation"
        intfs = ( ','.join( [ '%s:%s' % ( i.name, i.IP() )
                              for i in self.intfList() ] ) )
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid )

    def __str__( self ):
        "Abbreviated string representation"
        return self.name

    # Automatic class setup support

    isSetup = False

    @classmethod
    def checkSetup( cls ):
        "Make sure our class and superclasses are set up"
        while cls and not getattr( cls, 'isSetup', True ):
            cls.setup()
            cls.isSetup = True
            # Make pylint happy
            cls = getattr( type( cls ), '__base__', None )

    @classmethod
    def setup( cls ):
        "Make sure our class dependencies are available"
        pathCheck( 'mnexec', 'ifconfig', moduleName='Mininet')


class Host( Node ):
    "A host is simply a Node"
    pass


class Docker ( Host ):
    """Node that represents a docker container.
    This part is inspired by:
    http://techandtrains.com/2014/08/21/docker-container-as-mininet-host/
    We use the docker-py client library to control docker.
    """

    def __init__(
            self, name, dimage, dcmd=None, **kwargs):
        """
        Creates a Docker container as Mininet host.

        Resource limitations based on CFS scheduler:
        * cpu.cfs_quota_us: the total available run-time within a period (in microseconds)
        * cpu.cfs_period_us: the length of a period (in microseconds)
        (https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt)

        Default Docker resource limitations:
        * cpu_shares: Relative amount of max. avail CPU for container
            (not a hard limit, e.g. if only one container is busy and the rest idle)
            e.g. usage: d1=4 d2=6 <=> 40% 60% CPU
        * cpuset_cpus: Bind containers to CPU 0 = cpu_1 ... n-1 = cpu_n (string: '0,2')
        * mem_limit: Memory limit (format: <number>[<unit>], where unit = b, k, m or g)
        * memswap_limit: Total limit = memory + swap

        All resource limits can be updated at runtime! Use:
        * updateCpuLimits(...)
        * updateMemoryLimits(...)
        """
        self.dimage = dimage
        self.dnameprefix = "mn"
        self.dcmd = dcmd if dcmd is not None else "/bin/bash"
        self.dc = None  # pointer to the dict containing 'Id' and 'Warnings' keys of the container
        self.dcinfo = None
        self.did = None # Id of running container
        #  let's store our resource limits to have them available through the
        #  Mininet API later on
        defaults = { 'cpu_quota': -1,
                     'cpu_period': None,
                     'cpu_shares': None,
                     'cpuset_cpus': None,
                     'mem_limit': None,
                     'memswap_limit': None,
                     'environment': {},
                     'volumes': [],  # use ["/home/user1/:/mnt/vol2:rw"]
                     'publish_all_ports': True,
                     'port_bindings': {},
                     'dns': [],
                     }

        defaults.update( kwargs )

        # keep resource in a dict for easy update during container lifetime
        self.resources = dict(
            cpu_quota=defaults['cpu_quota'],
            cpu_period=defaults['cpu_period'],
            cpu_shares=defaults['cpu_shares'],
            cpuset_cpus=defaults['cpuset_cpus'],
            mem_limit=defaults['mem_limit'],
            memswap_limit=defaults['memswap_limit']
        )

        self.volumes = defaults['volumes']
        self.environment = {} if defaults['environment'] is None else defaults['environment']
        # setting PS1 at "docker run" may break the python docker api (update_container hangs...)
        # self.environment.update({"PS1": chr(127)})  # CLI support
        self.publish_all_ports = defaults['publish_all_ports']
        self.port_bindings = defaults['port_bindings']
        self.dns = defaults['dns']

        # setup docker client
        # self.dcli = docker.APIClient(base_url='unix://var/run/docker.sock')
        self.dcli = docker.from_env().api

        # pull image if it does not exist
        self._check_image_exists(dimage, True)

        # for DEBUG
        debug("Created docker container object %s\n" % name)
        debug("image: %s\n" % str(self.dimage))
        debug("dcmd: %s\n" % str(self.dcmd))
        debug("kwargs: %s\n" % str(kwargs))

        # creats host config for container
        # see: https://docker-py.readthedocs.org/en/latest/hostconfig/
        hc = self.dcli.create_host_config(
            network_mode=None,
            privileged=True,  # we need this to allow mininet network setup
            binds=self.volumes,
            publish_all_ports=self.publish_all_ports,
            port_bindings=self.port_bindings,
            mem_limit=self.resources.get('mem_limit'),
            cpuset_cpus=self.resources.get('cpuset_cpus'),
            dns=self.dns,
        )

        # create new docker container
        self.dc = self.dcli.create_container(
            name="%s.%s" % (self.dnameprefix, name),
            image=self.dimage,
            command=self.dcmd,
            stdin_open=True,  # keep container open
            tty=True,  # allocate pseudo tty
            environment=self.environment,
            #network_disabled=True,  # docker stats breaks if we disable the default network
            host_config=hc,
            labels=['com.containernet'],
            volumes=[self._get_volume_mount_name(v) for v in self.volumes if self._get_volume_mount_name(v) is not None],
            hostname=name
        )

        # start the container
        self.dcli.start(self.dc)
        debug("Docker container %s started\n" % name)

        # fetch information about new container
        self.dcinfo = self.dcli.inspect_container(self.dc)
        self.did = self.dcinfo.get("Id")

        # call original Node.__init__
        Host.__init__(self, name, **kwargs)

        # let's initially set our resource limits
        self.update_resources(**self.resources)
        # self.updateCpuLimit(cpu_quota=self.resources.get('cpu_quota'),
        #                     cpu_period=self.resources.get('cpu_period'),
        #                     cpu_shares=self.resources.get('cpu_shares'),
        #                     )
        # self.updateMemoryLimit(mem_limit=self.resources.get('mem_limit'),
        #                        memswap_limit=self.resources.get('memswap_limit')
        #                        )

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return
        # mnexec: (c)lose descriptors, (d)etach from tty,
        # (p)rint pid, and run in (n)amespace
        # opts = '-cd' if mnopts is None else mnopts
        # if self.inNamespace:
        #     opts += 'n'
        # bash -i: force interactive
        # -s: pass $* to shell, and make process easy to find in ps
        # prompt is set to sentinel chr( 127 )
        cmd = [ 'docker', 'exec', '-it',  '%s.%s' % ( self.dnameprefix, self.name ), 'env', 'PS1=' + chr( 127 ),
                'bash', '--norc', '-is', 'mininet:' + self.name ]
        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
        # in the subprocess and insulate it from signals (e.g. SIGINT)
        # received by the parent
        master, slave = pty.openpty()
        self.shell = self._popen( cmd, stdin=slave, stdout=slave, stderr=slave,
                                  close_fds=False )
        self.stdin = os.fdopen( master, 'rw' )
        self.stdout = self.stdin
        self.pid = self._get_pid()
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        while True:
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
            self.pollOut.poll()
        self.waiting = False
        # +m: disable job control notification
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

    def _get_volume_mount_name(self, volume_str):
        """ Helper to extract mount names from volume specification strings """
        parts = volume_str.split(":")
        if len(parts) < 3:
            return None
        return parts[1]

    def terminate( self ):
        """ Stop docker container """
        if not self._is_container_running():
            return
        try:
            self.dcli.remove_container(self.dc, force=True, v=True)
        except docker.errors.APIError as e:
            warn("Warning: API error during container removal.\n")
        self.cleanup()

    def sendCmd( self, *args, **kwargs ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete."""
        self._check_shell()
        if not self.shell:
            return
        Host.sendCmd( self, *args, **kwargs )

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in node's namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""

        if not self._is_container_running():
            error( "ERROR: Can't connect to Container \'%s\'' for docker host \'%s\'!\n" % (self.did, self.name) )
            return
        mncmd = ["docker", "exec", "-t", "%s.%s" % (self.dnameprefix, self.name)]

        return Host.popen( self, *args, mncmd=mncmd, **kwargs )

    def cmd(self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, args ) )
        self.sendCmd( *args, **kwargs )
        return self.waitOutput( verbose )

    def _get_pid(self):
        state = self.dcinfo.get("State", None)
        if state:
            return state.get("Pid", -1)
        return -1

    def _check_shell(self):
        """Verify if shell is alive and
           try to restart if needed"""
        if self._is_container_running():
            if self.shell:
                self.shell.poll()
                if self.shell.returncode is not None:
                    debug("*** Shell died for docker host \'%s\'!\n" % self.name )
                    self.shell = None
                    debug("*** Restarting Shell of docker host \'%s\'!\n" % self.name )
                    self.startShell()
            else:
                debug("*** Restarting Shell of docker host \'%s\'!\n" % self.name )
                self.startShell()
        else:
            error( "ERROR: Can't connect to Container \'%s\'' for docker host \'%s\'!\n" % (self.did, self.name) )
            if self.shell:
                self.shell = None

    def _is_container_running(self):
        """Verify if container is alive"""
        container_list = self.dcli.containers(filters={"id": self.did, "status": "running"})
        if len(container_list) == 0:
            return False;
        return True

    def _check_image_exists(self, imagename, pullImage=False):
        # split tag from repository if a tag is specified
        if ":" in imagename:
            repo, tag = imagename.split(":")
        else:
            repo = imagename
            tag = "latest"

        if self._image_exists(repo, tag):
            return True

        # image not found
        if pullImage:
            if self._pull_image(repo, tag):
                info('*** Download of "%s:%s" successful\n' % (repo, tag))
                return True
        # we couldn't find the image
        return False

    def _image_exists(self, repo, tag):
        """
        Checks if the repo:tag image exists locally
        :return: True if the image exists locally. Else false.
        """
        # filter by repository
        images = self.dcli.images(repo)
        imageName = "%s:%s" % (repo, tag)

        for image in images:
            if 'RepoTags' in image:
                if image['RepoTags'] is None:
                    return False
                if imageName in image['RepoTags']:
                    return True
        return False

    def _pull_image(self, repository, tag):
        """
        :return: True if pull was successful. Else false.
        """
        message = ""
        try:
            info('*** Image "%s:%s" not found. Trying to load the image. \n' % (repository, tag))
            info('*** This can take some minutes...\n')

            for line in self.dcli.pull(repository, tag, stream=True):
                # Collect output of the log for enhanced error feedback
                message = message + json.dumps(json.loads(line), indent=4)

        except:
            error('*** error: _pull_image: %s:%s failed.' % (repository, tag)
                  + message)
        if not self._image_exists(repository, tag):
            error('*** error: _pull_image: %s:%s failed.' % (repository, tag)
                  + message)
            return False
        return True

    def update_resources(self, **kwargs):
        """
        Update the container's resources using the docker.update function
        re-using the same parameters:
        Args:
           blkio_weight
           cpu_period, cpu_quota, cpu_shares
           cpuset_cpus
           cpuset_mems
           mem_limit
           mem_reservation
           memswap_limit
           kernel_memory
           restart_policy
        see https://docs.docker.com/engine/reference/commandline/update/
        or API docs: https://docker-py.readthedocs.io/en/stable/api.html#module-docker.api.container
        :return:
        """

        self.resources.update(kwargs)
        # filter out None values to avoid errors
        resources_filtered = {res:self.resources[res] for res in self.resources if self.resources[res] is not None}
        info("{1}: update resources {0}\n".format(resources_filtered, self.name))
        self.dcli.update_container(self.dc, **resources_filtered)


    def updateCpuLimit(self, cpu_quota=-1, cpu_period=-1, cpu_shares=-1, cores=None):
        """
        Update CPU resource limitations.
        This method allows to update resource limitations at runtime by bypassing the Docker API
        and directly manipulating the cgroup options.
        Args:
            cpu_quota: cfs quota us
            cpu_period: cfs period us
            cpu_shares: cpu shares
            cores: specifies which cores should be accessible for the container e.g. "0-2,16" represents
                Cores 0, 1, 2, and 16
        """
        # see https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt

        # also negative values can be set for cpu_quota (uncontrained setting)
        # just check if value is a valid integer
        if isinstance(cpu_quota, (int, long)):
            self.resources['cpu_quota'] = self.cgroupSet("cfs_quota_us", cpu_quota)
        if cpu_period >= 0:
            self.resources['cpu_period'] = self.cgroupSet("cfs_period_us", cpu_period)
        if cpu_shares >= 0:
            self.resources['cpu_shares'] = self.cgroupSet("shares", cpu_shares)
        if cores:
            self.dcli.update_container(self.dc, cpuset_cpus=cores)
            # quota, period ad shares can also be set by this line. Usable for future work.

    def updateMemoryLimit(self, mem_limit=-1, memswap_limit=-1):
        """
        Update Memory resource limitations.
        This method allows to update resource limitations at runtime by bypassing the Docker API
        and directly manipulating the cgroup options.

        Args:
            mem_limit: memory limit in bytes
            memswap_limit: swap limit in bytes

        """
        # see https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt
        if mem_limit >= 0:
            self.resources['mem_limit'] = self.cgroupSet("limit_in_bytes", mem_limit, resource="memory")
        if memswap_limit >= 0:
            self.resources['memswap_limit'] = self.cgroupSet("memsw.limit_in_bytes", memswap_limit, resource="memory")


    def cgroupSet(self, param, value, resource='cpu'):
        """
        Directly manipulate the resource settings of the Docker container's cgrpup.
        Args:
            param: parameter to set, e.g., cfs_quota_us
            value: value to set
            resource: resource name: cpu

        Returns: value that was set

        """
        cmd = 'cgset -r %s.%s=%s docker/%s' % (
            resource, param, value, self.did)
        debug(cmd + "\n")
        try:
            check_output(cmd, shell=True)
        except:
            error("Problem writing cgroup setting %r\n" % cmd)
            return
        nvalue = int(self.cgroupGet(param, resource))
        if nvalue != value:
            error('*** error: cgroupSet: %s set to %s instead of %s\n'
                  % (param, nvalue, value))
        return nvalue

    def cgroupGet(self, param, resource='cpu'):
        """
        Read cgroup values.
        Args:
            param: parameter to read, e.g., cfs_quota_us
            resource: resource name: cpu / memory

        Returns: value

        """
        cmd = 'cgget -r %s.%s docker/%s' % (
            resource, param, self.did)
        try:
            return int(check_output(cmd, shell=True).split()[-1])
        except:
            error("Problem reading cgroup info: %r\n" % cmd)
            return -1


class LibvirtHost( Host ):
    """Base class for controlling a host that is managed by libvirt.

    Args:
        name: name of the node
        disk_image: file that holds a disk image, if empty string is passed
                    an existing domain with name = name will be used
        use_existing_vm: Use an existing VM of name kwargs['name'] if domain_name is not set. Default: False
        domain_name: The domain that is used when using an existing VM. Default: kwargs['name']
        type: the type of domain to instantiate, default: 'kvm'
        login: the dictionary to pass to the management network paramiko ssh session.
                default: {'credentials': { 'username': 'root', 'password': 'containernet'},}
        cmd_endpoint: which endpoint to use. default 'qemu:///system'
        domain_xml: If defined this XML string will be used to instantiate the domain.
                This string will formatted like the default domain_xml in LibvirtHost.
                So you can use placeholders that will be filled by Containernet.
                If a path is specified the file will be read instead. default: None
        disk_target_dev: String. disk device string for domain_xml. Default: 'sda'
        disk_target_driver_name: String. disk device driver string for domain_xml. Default: 'qemu'
        disk_target_driver_type: String. disk device type string for domain_xml. Default: 'qcow2'
        os_arch: String. type of os string for domain_xml. Default: 'x86_64'
        os_machine: String. default 'pc'
        os_type: String. OS type for libvirt. Default: 'hvm'
        emulator: String. Path to the emulator. Default: '/usr/bin/qemu-system-x86_64'
        memory: String. Amount of memory in MB. Defines max memory. Default: '1024'
        currentMemory: String. Amount of memory currently assigned to the domain. Default: '1024'
        features: String containing XML for possible features that need to be added. Default: ""
        vcpu: String containing the amount of VCPUs allocated to this domain. Default: '1'
        transient_disk: Boolean. Defines the domain with a transient disk. Disables Snapshots. Not possible with current
                qemu versions. Default: False
        snapshot: Boolean. if the domain should create a snapshot before being added to the emulated network.
                Default: True
        restore_snapshot: Boolean. if the domain should be restored to its original state if a snapshot exists.
                Default: True
        snapshot_disk_image_path: String. Specify a fixed path for the snapshot. Default: None
        use_sudo: Boolean. Set this to true to let Containernet call sudo su - after logging in.
                Passwordless sudo required. Default False
        keep_running: Boolean. Do not shut down this host when it is removed. Default: False
        mgmt_net_at_start: Boolean. Set this to true for generated domains where the guest does not
                understand hotplugging. Has no effect for predefined domains. Default: False
        mgmt_net_attached: Boolean. Set this to true when you are using a predefined domain that is already attached
                to the mangement network. Default: False
        mgmt_network: String. Contains the libvirt name of the management network. Usually not needed to be specified
                manually. Default: mn.libvirt.mgmt
        mgmt_ip: String. Custom static IP of the host for the management network. Default: None
        mgmt_mac: String. Custom MAC for the host in the management network. Default: None
        mgmt_pci_slot: String. Set a custom pci slot for the management network. Max: "0x1F". Default: "0x1F"
        no_check: Boolean. Overrides check_domain. Use this for non standard domains. Default: False
    """
    def __init__(self, name, disk_image="", use_existing_vm=False, **kwargs):
        # only define these if they are not defined yet to make inheritance viable
        if not hasattr(self, "SNAPSHOT_XML"):
            self.SNAPSHOT_XML = """
                            <domainsnapshot>
                                <description>Mininet snapshot</description>
                                <memory snapshot='external' file='{snapshot_disk_image_path}.mem'/>
                                <disks>
                                    <disk name='{image}'>
                                        <source file='{snapshot_disk_image_path}'/>
                                    </disk>
                                </disks>
                            </domainsnapshot>
                            """

        if not hasattr(self, "SNAPSHOT_XML_RUNNING"):
            self.SNAPSHOT_XML_RUNNING = """
                            <domainsnapshot>
                                <description>Mininet snapshot</description>
                            </domainsnapshot>
                            """
        if not hasattr(self, "INTERFACE_XML"):
            self.INTERFACE_XML = """
                    <interface type='direct' trustGuestRxFilters='yes'>
                        <model type='virtio'/>
                        <source dev='{intfname}' mode='private'/>
                    </interface>
                    """

        if not hasattr(self, "INTERFACE_XML_MGMT"):
            self.INTERFACE_XML_MGMT = """
                    <interface type="network">
                        <mac address="{mgmt_mac}"/>
                        <source network="{mgmt_network}"/>
                        <address bus="0x00" domain="0x0000" slot="{mgmt_pci_slot}" type="pci"/>
                    </interface>
                    """
        if not hasattr(self, "DOMAIN_XML"):
            self.DOMAIN_XML = """
            <domain type="{type}">
              <name>{name}</name>
              <memory unit="MiB">{memory}</memory>
              <currentMemory unit="MiB">{currentMemory}</currentMemory>
              <vcpu current="{vcpu}">{cpumax}</vcpu>
              <os>
                <type arch="{os_arch}" machine="{os_machine}">{os_type}</type>
              </os>
              <features>
                <acpi/>
                {features}
              </features>
              <devices>
                <emulator>{emulator}</emulator>
                <disk device="disk" type="file">
                  <source file="{disk_image}"/>
                  <target dev="{disk_target_dev}"/>
                  <driver name="{disk_target_driver_name}" type="{disk_target_driver_type}"/>
                  {disk_transient_disk}
                </disk>
                {mgmt_interface}
                <console type="pty"/>
                {additional_devices}
              </devices>
            </domain>
            """
        # "private" dict for capabilities property
        self._capabilities = None
        # a lot of defaults
        kwargs.setdefault('type', 'kvm')
        kwargs.setdefault('login', {'credentials': {
                                        'username': 'root',
                                        'password': 'containernet'
                                        },
                                    })
        kwargs.setdefault('cmd_endpoint', 'qemu:///system')
        kwargs.setdefault('domain_xml', None)
        kwargs.setdefault('disk_target_dev', 'sda')
        kwargs.setdefault('disk_target_driver_name', 'qemu')
        kwargs.setdefault('disk_target_driver_type', 'qcow2')
        kwargs.setdefault('os_arch', 'x86_64')
        kwargs.setdefault('os_machine', 'pc')
        kwargs.setdefault('os_type', 'hvm')
        kwargs.setdefault('emulator', "/usr/bin/qemu-system-x86_64")
        kwargs.setdefault('memory', '1024')
        kwargs.setdefault('currentMemory', '1024')
        kwargs.setdefault('features', '')
        kwargs.setdefault('vcpu', '1')
        kwargs.setdefault('snapshot', True)
        kwargs.setdefault('restore_snapshot', True)
        kwargs.setdefault('snapshot_disk_image_path', None)
        kwargs.setdefault('transient_disk', False)
        kwargs.setdefault('use_sudo', False)
        kwargs.setdefault('keep_running', False)
        kwargs.setdefault('mgmt_net_at_start', True)
        kwargs.setdefault('mgmt_net_attached', False)
        kwargs.setdefault('no_check', False)
        kwargs.setdefault('mgmt_pci_slot', '0x1F')
        kwargs.setdefault('additional_devices', "")

        kwargs.setdefault('resources', {
            'cpu_quota': -1,
            'cpu_period': -1,
            'cpu_shares': -1,
        })

        self.lv_conn = libvirt.open(kwargs['cmd_endpoint'])
        if self.lv_conn is None:
            error("LibvirtHost.__init__: Failed to open connection to endpoint: %s\n" % kwargs['cmd_endpoint'])

        self.disk_image = disk_image
        # do not allow snapshots for transient disks
        if kwargs['transient_disk']:
            kwargs['snapshot'] = False

        self.mgmt_net_interface_xml = ""
        # domain object we get from libvirt
        self.domain = None
        # etree we store for domain manipulation
        self.domain_tree = None
        # XML serialization of the domain_tree
        self.domain_xml = None

        if disk_image == "" and kwargs['domain_xml'] is None:
            info("LibvirtHost.__init__: No disk image given. Trying to use an existing domain with name %s.\n" % name)
            use_existing_vm = True

        if use_existing_vm:
            self.domain_name = kwargs.get('domain_name', name)
        else:
            # domain name with prefix
            self.domain_name = "%s.%s" % ("mn", name)
        # contains the libvirt domain snapshot, if we created one
        self.lv_domain_snapshot = None
        # keep track of our main ssh session
        self.ssh_session = paramiko.SSHClient()
        self.shell = None

        # get the maximum amount of physical cpus
        self.maxCpus = numCores()
        self.use_existing_vm = use_existing_vm
        # set resources to empty dict, will update them later
        self.resources = {}

        self.mgmt_net = self.lv_conn.networkLookupByName(kwargs['mgmt_network'])
        if not self.mgmt_net:
            error("LibvirtHost.__init__: Could not find the libvirt management network: %s\n" % kwargs['mgmt_network'])
            return

        if not self.use_existing_vm:
            if kwargs['domain_xml'] is not None:
                # check if we got a path to a file instead of a whole xml representation
                if os.path.isfile(kwargs['domain_xml']):
                    with open(kwargs['domain_xml'], 'r') as xml_file:
                        self.DOMAIN_XML = xml_file.read()
                        info("LibvirtHost.__init__: Using provided domain XML file for domain %s.\n" % self.domain_name)
                else:
                    self.DOMAIN_XML = kwargs['domain_xml']
                    info("LibvirtHost.__init__: Using provided domain XML for domain %s.\n" % self.domain_name)

            self.build_domain(**kwargs)
            if not self.check_domain(**kwargs):
                error("LibvirtHost.__init__: Provided domain XML has errors!\n")

            debug("Created Domain object: %s\n" % self.domain_name)
            debug("image: %s\n" % str(self.disk_image))
            debug("kwargs: %s\n" % str(kwargs))
        else:
            try:
                self.domain = self.lv_conn.lookupByName(self.domain_name)
                self.domain_xml = self.getDomainXML()
            except libvirt.libvirtError:
                error("LibvirtHost.__init__: Domain '%s' does not exist. Cannot use preexisting domain.\n"
                      % self.domain_name)
                return
            debug("Using preexisting domain %s as node %s.\n" % (self.domain_name, name))

        # instantiate the domain in libvirt
        if self.domain is None:
            self.domain = self.lv_conn.createXML(self.domain_xml)

        if kwargs['snapshot']:
            if kwargs['snapshot_disk_image_path'] is None:
                # find a safe new path within the directory
                incr = 1
                dst_image_path = "%s.mininet.snap" % self.disk_image
                if os.path.isfile(dst_image_path):
                    while os.path.isfile("%s.%s" % (dst_image_path, incr)):
                        incr += 1
                    dst_image_path = "%s.%s" % (dst_image_path, incr)

                kwargs['snapshot_disk_image_path'] = dst_image_path

            if self.use_existing_vm:
                snapshot_xml = self.SNAPSHOT_XML_RUNNING
                info("LibvirtHost.__init__: Creating snapshot of existing domain %s.\n" % self.domain_name)
            else:
                snapshot_xml = self.SNAPSHOT_XML.format(image=self.disk_image, **kwargs)
                info("LibvirtHost.__init__: Creating snapshot of domain %s at %s.\n" %
                     (self.domain_name, kwargs['snapshot_disk_image_path']))

            try:
                self.lv_domain_snapshot = self.domain.snapshotCreateXML(snapshot_xml)
            except libvirt.libvirtError as e:
                error("LibvirtHost.__init__: Could not create snapshot for domain '%s'.\n"
                      % self.domain_name)
                raise e

        if not self.use_existing_vm:
            # snapshots are created so now we can set the title so cleanup can remove the domain if something crashes
            self.domain.setMetadata(libvirt.VIR_DOMAIN_METADATA_TITLE,
                                    "com.containernet-%s" % self.domain_name,
                                    key=None,
                                    uri=None)

        # pre-existing domains might still be shut down. so start them
        if not self.domain.isActive():
            # launch
            self.domain.create()

        # if a domain is paused resume it
        if libvirt.VIR_DOMAIN_PAUSED in self.domain.state():
            self.domain.resume()

        # if the management network is not added before starting the domain add it now
        # don't add it if we use an existing vm and mgmt_net_at_start is true
        if self.mgmt_net_interface_xml is "" and not kwargs['mgmt_net_attached']:
            self.attach_management_network(**kwargs)

        # finally update the resource dict to reflect our current configuration
        self.update_resources(**kwargs['resources'])

        # call original Node.__init__
        Host.__init__(self, name, **kwargs)

    @property
    def capabilities(self):
        if self._capabilities is None:
            self._capabilities = minidom.parseString(self.lv_conn.getCapabilities())
        return self._capabilities

    def getDomainXML(self):
        return self.domain.XMLDesc()

    @property
    def isQemu(self):
        return "qemu" in self.params['cmd_endpoint']

    @property
    def isKVM(self):
        return "kvm" in self.params['type']

    @property
    def isLXC(self):
        return "lxc" in self.params['cmd_endpoint']

    def build_domain(self, **params):
        # create a host config from params
        if "mgmt_net_at_start" in params:
            debug("LibvirtHost.buildDomain: Adding management network before starting the domain '%s'\n" %
                  self.domain_name)
            self.mgmt_net_interface_xml = self.INTERFACE_XML_MGMT.format(**params)

        if params['transient_disk']:
            params['disk_transient_disk'] = "<transient/>"
        else:
            params['disk_transient_disk'] = ""

        domain = self.DOMAIN_XML.format(
            name=self.domain_name,
            cpumax=self.maxCpus,
            disk_image=self.disk_image,
            mgmt_interface=self.mgmt_net_interface_xml,
            **params
        )

        # store the domain_xml until we have the real one from libvirt
        self.domain_xml = domain

    def check_domain(self, **kwargs):
        if kwargs.get('no_check'):
            return True
        try:
            if self.lv_conn.lookupByName(self.domain_name):
                error("LibvirtHost.check_domain: Domain '%s' exists already.\n" % self.domain_name)
                return False
        except libvirt.libvirtError:
            # domain does not yet exist. everything is fine
            pass

        # check if acpi is present, as we need it for interface attachment / vcpu management
        dom = minidom.parseString(self.domain_xml)
        if not dom.getElementsByTagName("acpi"):
            error("LibvirtHost.check_domain: Domain '%s' does not have acpi enabled.\n" % self.domain_name)
            return False

        debug("LibvirtHost.check_domain: XML Representation of domain:\n%s\n" % self.domain_xml)

        return True

    def _get_new_ssh_session(self):
        session = paramiko.SSHClient()

        t = time.time()
        while True:
            try:
                if "timeout" not in self.params['login']['credentials']:
                    self.params['login']['credentials']['timeout'] = 60

                if "banner_timeout" not in self.params['login']['credentials']:
                    self.params['login']['credentials']['banner_timeout'] = 60

                session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                session.connect(self.params['mgmt_ip'], **self.params['login']['credentials'])
                debug("LibvirtHost._get_new_ssh_session: Logged in to domain %s using ssh.\n" % self.domain_name)
                return session
            except paramiko.BadHostKeyException as e:
                error("LibvirtHost._get_new_ssh_session: Domain '%s' has login method ssh, "
                      "but has HostKey problems. Error: %s\n" %
                      (self.name, e))
                return False
            except paramiko.AuthenticationException as e:
                error("LibvirtHost._get_new_ssh_session: Domain '%s' has login method ssh, "
                      "but SSH threw an authentication"
                      "Error: %s\n" % (self.name, e))
                return False
            except paramiko.SSHException as e:
                error("LibvirtHost._get_new_ssh_session: Domain '%s' has login method ssh, "
                      "but could not connect to the VM. "
                      "Did you set up the management network correctly?."
                      "Error: %s\n" % (self.name, e))
                return False
            except socket.error as e:
                # if the domain is still starting up, allow connections to it to fail unless timeout is reached
                if time.time() - t > self.params['login']['credentials']['timeout']:
                    error("LibvirtHost._get_new_ssh_session: Domain '%s' has login method ssh, "
                          "but could not connect to the VM. Reached timeout!"
                          "Error: %s\n" % (self.name, e))
                    return False
            except KeyboardInterrupt:
                error("LibvirtHost._get_new_ssh_session: Keyboard Interrupt.\n")
                return False

    def startShell(self, mnopts=None):
        """ Tries to connect to a domain via SSH and exposes a shell that behaves like a normal mininet shell."""
        debug("LibvirtHost.startShell: Trying to SSH into domain %s. This might take a while.\n" %
              self.domain_name)
        sess = self._get_new_ssh_session()
        if sess:
            self.ssh_session = sess
        else:
            error("LibvirtHost.startShell: Could not start the shell for domain %s.\n" % self.domain_name)
            return False
        self.domain_xml = self.getDomainXML()
        self.pid = self.getPid()
        self.pollOut = select.poll()
        # create a new channel
        self.shell = self.ssh_session.invoke_shell()
        # this might not be needed
        self.shell.set_combine_stderr(True)
        self.shell.settimeout(None)
        self.pollOut.register(self.shell, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR)
        self.stdin = self.shell
        self.stdout = self.shell
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # read motd etc.
        while self.shell.recv_ready():
            self.read()
        self.waiting = False

        # set prompt to sentinel
        self.cmd('export PS1="\\177"')

        # call sudo, has to be passwordless and PS1 has to be preserved!
        if self.params['use_sudo']:
            self.cmd("sudo -Es")
        # set the hostname
        self.cmd('hostname %s' % self.name)
        self.cmd('unset HISTFILE; stty -echo; set +m')


    def read( self, maxbytes=1024 ):
        """Buffered read from node, potentially blocking.
           maxbytes: maximum number of bytes to return"""
        count = len( self.readbuf )
        if count < maxbytes:
            data = self.shell.recv(maxbytes - count )
            self.readbuf += data
        if maxbytes >= len( self.readbuf ):
            result = self.readbuf
            self.readbuf = ''
        else:
            result = self.readbuf[ :maxbytes ]
            self.readbuf = self.readbuf[ maxbytes: ]
        return result

    def write( self, data ):
        """Write data to node.
           data: string"""
        if self.shell.send_ready():
            self.shell.sendall(data)
        else:
            raise Exception("Could not write to domain %s" % self.domain_name)

    def addIntf( self, intf, port=None, moveIntfFn=moveIntf ):
        """Add an interface.
           intf: interface
           port: port number (optional, typically OpenFlow port number)
           moveIntfFn: function to move interface (optional)

           Modified version for libvirt hosts.

           Creates a macvtap device on the host machine and then adds the interface to the node.
           """

        # predictable network interface names are not available on every possible domain
        # so we use a different strategy
        # enumerate all interfaces currently available on the node first
        interface_list_cmd = "ls --color=never /sys/class/net"
        before_interfaces = self.cmd(interface_list_cmd).strip().split('  ')
        debug("LibvirtHost.addIntf: Interfaces on node %s before attaching: %s\n" % (self.name,
                                                                                     ' '.join(before_interfaces)))
        interface_xml = self.INTERFACE_XML.format(intfname=intf.name)
        try:
            debug("LibvirtHost.addIntf: Attaching device %s to node %s.\n" % (intf.name, self.name))
            debug(interface_xml + "\n")
            self.domain.attachDevice(interface_xml)
        except libvirt.libvirtError as e:
            error("Could not attach interface %s to node %s. Error: %s\n" % (intf.name, self.name, e))
            raise Exception("Error while attaching a new interface.")

        # be conservative and wait a little for the device to appear
        time.sleep(0.3)

        # we wait until something changes in network devices
        # the device that appears is our new interface
        start = time.time()
        done = False
        debug("LibvirtHost.addIntf: Waiting a maximum amount of 60 Seconds for the interface to appear.\n")
        while not done:
            if start + 60 < time.time():
                raise Exception("Error while attaching a new interface. Could not find the newly attached interface."
                                "Timeout reached.")
            after_interfaces = self.cmd(interface_list_cmd).strip().split('  ')
            if len(before_interfaces) == len(after_interfaces):
                time.sleep(0.5)
                continue

            if len(before_interfaces) > len(after_interfaces):
                raise Exception("Error while attaching a new interface. Could not find the newly attached interface.")

            # get name of the new interface
            new_intf = list(set(after_interfaces) - set(before_interfaces))[0]
            # bail out and say its ok after 10 seconds if the interfaces are named the same
            if str(new_intf).strip() == str(intf).strip() and start + 10 < time.time():
                break
            time.sleep(0.3)

            # rename the interface, if command does not produce output it might be successful
            if not self.cmd("ip link set %s name %s" % (str(new_intf), intf)):
                if not new_intf in self.cmd(interface_list_cmd).strip().split('  '):
                    done = True
            if not done:
                time.sleep(0.5)

        # let the hostobject do the bookkeeping
        Node.addIntf(self, intf, port, moveIntfFn=moveIntf)

    def monitor( self, timeoutms=None, findPid=True ):
        """Monitor and return the output of a command.
           Set self.waiting to False if command has completed.
           timeoutms: timeout in ms or None to wait indefinitely
           findPid: look for PID from mnexec -p"""

        # pruned version for LibvirtHosts
        ready = self.waitReadable( timeoutms )
        if not ready:
            return ''
        data = self.read( 1024 )
        # Look for sentinel/EOF
        if len( data ) > 0 and data[ -1 ] == chr( 127 ):
            self.waiting = False
            data = data[ :-1 ]
        elif chr( 127 ) in data:
            self.waiting = False
            data = data.replace( chr( 127 ), '' )
        return data

    def sendCmd( self, *args, **kwargs ):
        """ Send a string as command to the LibvirtHost
           args: command and arguments, or string"""
        assert self.ssh_session
        # Allow sendCmd( [ list ] )
        if len( args ) == 1 and isinstance( args[ 0 ], list ):
            cmd = args[ 0 ]
        # Allow sendCmd( cmd, arg1, arg2... )
        elif len( args ) > 0:
            cmd = args
        # Convert to string
        if not isinstance( cmd, str ):
            cmd = ' '.join( [ str( c ) for c in cmd ] )
        if not re.search( r'\w', cmd ):
            # Replace empty commands with something harmless
            cmd = 'echo -n'
        self.lastCmd = cmd
        # if a builtin command is backgrounded, it still yields a PID
        if len( cmd ) > 0 and cmd[ -1 ] == '&':
            # print ^A{pid}\n so monitor() can set lastPid
            cmd += ' printf "\\001%d\\012" $! '

        debug("LibvirtHost.sendCmd: Sending command %s over ssh.\n" % cmd)
        self.write( cmd + '\n' )
        self.waiting = True

    def getPid(self):
        """Gets the pid of the libvirt process running the mininet host.
           This is only to keep the behaviour of existing mininet hosts.
        """

        # iterate over all system processes and look for one containing the uuid of the domain in the commandline
        # I don't know if this is completely foolproof for all hypervisors that libvirt supports
        for dirname in os.listdir('/proc'):
            if dirname == 'curproc':
                continue

            try:
                with open('/proc/%s/cmdline' % dirname, mode='rb') as fd:
                    content = fd.read().decode().split('\x00')
            except Exception:
                continue

            if str(self.domain.UUIDString()) in content:
                return dirname

    def mountPrivateDirs(self):
        """ Mounting private dirs of a vm means copying data from the host to the guest at startup.
            The privateDirs list is interpreted as follows:
                tuple( vmpath, hostpath)
        """
        assert not isinstance( self.privateDirs, basestring )
        # ignore everything here if no privateDirs are specified
        if not len(self.privateDirs):
            return

        info("LibvirtHost.mountPrivateDirs: Copying data to guest %s filesystem.\n" % self.name)
        # try to open SFTP
        try:
            sftp = self.ssh_session.open_sftp()
        except:
            error("LibvirtHost.mountPrivateDirs: Could not open SFTP connection for Host %s.\n" % self.name)
            return

        for directory in self.privateDirs:
            if isinstance( directory, tuple ):
                # mount given private directory
                host_dir = directory[ 1 ] % self.__dict__
                vm_dir = directory[ 0 ]

                if not os.path.exists(host_dir):
                    # use exist_ok=True for python3
                    os.makedirs( host_dir )

                # create the directory on the remote machine
                self.cmd("mkdir -p %s" % vm_dir)

                for local_file in os.listdir(host_dir):
                    try:
                        sftp.put("%s/%s" % (host_dir, local_file), "%s/%s" % (vm_dir, local_file))
                    except IOError, OSError:
                        error("LibvirtHost.mountPrivateDirs: Failed to transfer file %s to node directory %s.\n" %
                              (local_file, host_dir))
            else:
                warn("LibvirtHost.mountPrivateDirs: Only tuples are supported in VM context.\n")

    def unmountPrivateDirs(self):
        """ Unmounting should copy the data out of the VM to the host filesystem.
            The privateDirs list is interpreted as follows:
                tuple( vmpath, hostpath)
        """
        assert not isinstance( self.privateDirs, basestring )
        # ignore everything here if no privateDirs are specified
        if not len(self.privateDirs):
            return

        try:
            self.ssh_session.get_transport().sock.settimeout(30.0)
            sftp = self.ssh_session.open_sftp()
        except Exception as e:
            error(e)
            return

        info("LibvirtHost.unmountPrivateDirs: Copying data from Host %s to local filesystem.\n" % self.name)

        for directory in self.privateDirs:
            if isinstance( directory, tuple ):
                # mount given private directory
                host_dir = directory[1] % self.__dict__
                vm_dir = directory[0]

                if not os.path.exists(host_dir):
                    # use exist_ok=True for python3
                    os.makedirs( host_dir )

                if not os.path.isdir(host_dir):
                    error("LibvirtHost.unmountPrivateDirs: Cannot transfer files to host directory %s. "
                          "%s is not a directory.\n" %
                          (host_dir, host_dir))
                    continue

                for remote_file in sftp.listdir(vm_dir):
                    try:
                        sftp.get("%s/%s" % (vm_dir, remote_file), "%s/%s" % (host_dir, remote_file))
                    except IOError, OSError:
                        error("LibvirtHost.unmountPrivateDirs: Failed to transfer file %s to host directory %s.\n" %
                              (remote_file, host_dir))
            else:
                warn("LibvirtHost.unmountPrivateDirs: Only tuples are supported in VM context.\n")

    def cmd( self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, args ) )

        try:
            self.sendCmd( *args, **kwargs )
            return self.waitOutput( verbose )
        except paramiko.SSHException as e:
            info("LibvirtHost.cmd: Exception thrown. Trying to restart SSH session. Error: %s\n" % e)
            self.startShell()

    def popen( self, *args, **kwargs ):
        """Return a Popen() object
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        # TODO: Implement wrapper around exec_command
        popen_session = self._get_new_ssh_session()
        while True:
            try:
                popen_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                popen_session.connect(self.params['mgmt_ip'], **self.params['login']['credentials'])
                break
            except Exception as e:
                error("LibvirtHost.popen: Failed to launch a new ssh connection to the domain %s." % self.domain_name)
                return

        shell = popen_session.invoke_shell()
        return shell.exec_command(list2cmdline(args))

    def pexec( self, *args, **kwargs ):
        """Execute a command using exec_command
           returns: out, err, exitcode"""
        chan = self.ssh_session.get_transport().open_session()
        chan.exec_command(list2cmdline(args))
        exitcode = chan.recv_exit_status()
        out = ''
        err = ''
        while chan.recv_ready():
            out += chan.recv(1024)
        while chan.recv_stderr_ready():
            err += chan.recv_stderr(1024)

        return out, err, exitcode

    def remove_snapshot_file(self):
        """Removes the snapshot associated with the LibvirtHost."""
        # remove the snapshot. The metadata is already cleared by libvirt as the domain is now undefined
        if os.path.isfile(self.params['snapshot_disk_image_path']):
            os.remove(self.params['snapshot_disk_image_path'])
        if os.path.isfile("%s.mem" % self.params['snapshot_disk_image_path']):
            os.remove("%s.mem" % self.params['snapshot_disk_image_path'])

    def attach_management_network(self, **kwargs):
        """Attaches an interfaces to the LibvirtHost. This interfaces is used to SSH into the machine."""
        info("LibvirtHost.attach_management_network: Creating interface for management network.\n")

        self.mgmt_net_interface_xml = self.INTERFACE_XML_MGMT.format(**kwargs)
        try:
            self.domain.attachDevice(self.mgmt_net_interface_xml)
        except libvirt.libvirtError as e:
            error("Could not attach the management interface to node %s. Error: %s\n" %
                  (self.domain_name, e))
            raise Exception("Error while attaching the management interface.")

    def detach_management_network(self):
        """Detaches the previously attached management interface."""
        info("LibvirtHost.detach_management_network: Detaching the management interface for domain %s.\n" %
             self.domain_name)
        try:
            self.domain.detachDevice(self.mgmt_net_interface_xml)
        except libvirt.libvirtError as e:
            error("Could not detach the management interface from domain %s. Error: %s\n" %
                  (self.domain_name, e))

    def terminate( self ):
        """ Stop libvirt host """
        # write data from VM to host if private directories are "mounted"
        self.unmountPrivateDirs()

        if not self.use_existing_vm:
            # just delete temporary VMs and remove their snapshot
            try:
                self.domain.destroy()
            except libvirt.libvirtError as e:
                warn("LibvirtHost.terminate: Could not terminate the domain %s, maybe it is already destroyed? %s" %
                     (self.domain_name, e))
            if self.params['snapshot']:
                self.remove_snapshot_file()
        else:
            # remove the mgmt network so snapshot restore can work
            if not self.params['mgmt_net_attached']:
                self.detach_management_network()
            if self.params['snapshot']:
                if self.params['restore_snapshot']:
                    try:
                        # reverting to the snapshot, contains the previous state
                        # this needs fixing in corner cases, running VMs do not like to be snapshot multiple
                        # times...
                        info("LibvirtHost.terminate: Reverting to earlier snapshot.\n")
                        self.domain.revertToSnapshot(self.lv_domain_snapshot, libvirt.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
                        debug("LibvirtHost.terminate: Deleting earlier snapshot.\n")
                        self.domain.snapshotCurrent().delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_CHILDREN)
                        #self.lv_domain_snapshot.delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_CHILDREN)
                    except libvirt.libvirtError as e:
                        error("LibvirtHost.terminate: Could not restore the snapshot for domain %s. %s" %
                              (self.domain_name, e))
            else:
                if not self.params['keep_running']:
                    try:
                        info("LibvirtHost.terminate: Shutting down domain %s.\n" % self.domain_name)
                        self.domain.shutdown()
                    except libvirt.libvirtError as e:
                        warn("LibvirtHost.terminate: Could not shutdown the domain %s, maybe it is already offline? %s" %
                             (self.domain_name, e))

        self.cleanup()

    def update_resources(self, **kwargs):
        """
        Update the libvirt host's resources using libvirt
        :return:
        """

        self.resources.update(kwargs)
        # filter out None values to avoid errors
        resources_filtered = {res:self.resources[res] for res in self.resources if self.resources[res] is not None}
        info("{1}: update resources {0}\n".format(resources_filtered, self.domain_name))
        self.updateCpuLimit(**kwargs)
        self.updateMemoryLimit(**kwargs)

    def updateCpuLimit(self, cpu_quota=-1, cpu_period=-1, cpu_shares=-1,
                       emulator_period=-1, emulator_quota=-1, cores=None,
                       emulator_cores=None, use_libvirt=True, **kwargs):
        """
        Update CPU resource limitations.
        This method allows to update resource limitations at runtime in the same fashion as docker containers.
        For more control use libvirt directly.
        You can not disable the first core on a running VM!
        Args:
            cpu_quota: cfs quota us, time in microseconds a cgroup can access cpus during one cfs_cpu_period
            cpu_period: cfs period us, time in microseconds when quota should be refreshed
            cpu_shares: cpu shares
            emulator_period: cfs_quota_us assigned to emulator
            emulator_quota: cfs_period_us assigned to emulator
            use_libvirt: boolean. If False, containernet will try to manipulate the cgroups directly and not through
                    libvirt. Sets the limit for the VM as a whole!
                    Only supports cpu_quota, cpu_period, cpu_shares and cores. Default: True
            cores: maps vcpus to physical cores, e.g. {0: "1", 1: "2-3"} maps vcpu 0 to cpu 1 and vcpu 1 to cpu 2 and 3.
                    Offline cores will be brought online. Cores not specified will be set offline.
                    if just a string is used, vcpus will be pinned to their physical counterparts e.g. 0 -> 0, 1 -> 1.
            emulator_cores: tuple. maps emulator to physical cores, (0,1,0,1) maps the emulator to cores 1 and 3.
                    Default: None
        """
        if not use_libvirt:
            def cgroupSet(param, value, resource='cpu'):
                # this one is a hack
                # if we want to change the resource limits for the parent we have to set them for the children as well
                # the problem is that when we restrict the resources we have to do this bottom up
                # when we increase the limits we have to do this top down
                # evaluating if we actually increase or decrease the limits is finicky
                # so just do the brute force approach
                def apply_children():
                    # set limits for all children first!
                    parent = "/sys/fs/cgroup/%s/machine/%s.libvirt-qemu" % (resource, self.domain_name)
                    for d in os.listdir(parent):
                        if os.path.isdir("%s/%s" % (parent, d)):
                            try:
                                check_output('cgset -r %s.%s=%s machine/%s.libvirt-qemu/%s' % (
                                resource, param, value, self.domain_name, d), shell=True)
                            except:
                                pass

                # bottom up for decreasing limits. will fail silently
                apply_children()
                # set limits for parent process
                cmd = 'cgset -r %s.%s=%s machine/%s.libvirt-qemu' % (resource, param, value, self.domain_name)
                debug(cmd + "\n")
                # top down for increasing limits. will fail silently
                try:
                    check_output(cmd, shell=True)
                except:
                    error("Problem writing cgroup setting %r\n" % cmd)
                    return -1
                apply_children()
                return value

            if isinstance(cpu_quota, (int, long)) and cpu_quota > 1000:
                self.resources['cpu_quota'] = cgroupSet("cfs_quota_us", cpu_quota)
            if cpu_period >= 0:
                self.resources['cpu_period'] = cgroupSet("cfs_period_us", cpu_period)
            if cpu_shares >= 0:
                self.resources['cpu_shares'] = cgroupSet("shares", cpu_shares)
            if cores:
                self.resources['cores'] = cgroupSet("cpus", cores, resource="cpuset")
            return True


        # use libvirt to set the limits
        params = {}
        if cpu_quota != -1:
            params['vcpu_quota'] = int(cpu_quota)
        if cpu_period != -1:
            params['vcpu_period'] = int(cpu_period)
        if cpu_shares != -1:
            params['cpu_shares'] = int(cpu_shares)
        if emulator_period != -1:
            params['emulator_period'] = int(emulator_period)
        if emulator_quota != -1:
            params['emulator_quota'] = int(emulator_quota)

        if emulator_cores:
            try:
                debug("LibvirtHost.updateCpuLimit: Pinning the emulator to cores %s.\n" % str(emulator_cores))
                self.domain.pinEmulator(emulator_cores)
            except libvirt.libvirtError:
                error("LibvirtHost.updateCpuLimit: Could not pin the emulator to %s.\n" % str(emulator_cores))
                return False

        try:
            if len(params) > 0:
                self.domain.setSchedulerParameters(params)
                info("LibvirtHost.updateCpuLimit: Set scheduler parameters to %s.\n" % params)
            if cores is not None:
                # if someone is calling this method like the docker version
                if isinstance(cores, basestring):
                    warn("LibvirtHost.updateCpuLimit: "
                         "This method does not behave the same way as with docker containers.\n")
                    cores_dict = {}
                    if "-" in cores:
                        start, end = cores.split("-")
                        for cpu in range(int(start), int(end) + 1):
                            cores_dict[cpu] = str(cpu)
                    else:
                        cores_dict = {int(cores): str(cores)}
                    cores = cores_dict

                # check if set_vcpu method is avaiable
                set_vcpu = getattr(self.domain, "setVcpu", None)
                if not set_vcpu:
                    info("LibvirtHost.updateCpuLimit: You cannot bring up specific cores with this version of libvirt. "
                         "Upgrade to a newer version if you need this feature. "
                         "Setting number of Vcpus instead of managing specific cores.\n")
                    info("LibvirtHost.updateCpuLimit: Setting number of Vcpus to %d\n" % len(cores))
                    try:
                        self.domain.setVcpusFlags(len(cores), libvirt.VIR_DOMAIN_AFFECT_LIVE)
                    except:
                        warn("Could not change the amount of vcpus. Maybe this version of Qemu / libvirt does not "
                             "allow reducing vcpus.\n")
                        return False
                else:
                    if 0 not in cores:
                        info("LibvirtHost.updateCpuLimit: Do not try to bring down the first vcpu of a domain! "
                             "This will not work! Keeping it online.\n")
                        cores[0] = "0-%d" % (int(self.maxCpus) - 1)

                mapping = []
                # calculate the mapping and if available bring up the vcpu
                for vcpu_nr, vcpu_map in cores.items():
                    mapping = [0] * self.maxCpus

                    for inp in vcpu_map.split(","):
                        if "-" in inp:
                            start, end = inp.split("-")
                            for cpu in range(int(start), int(end) + 1):
                                mapping[cpu] = 1
                        else:
                            mapping[int(inp)] = 1

                    if set_vcpu:
                        try:
                            info("LibvirtHost.updateCpuLimit: Setting core %d state to running.\n" % vcpu_nr)
                            set_vcpu(str(vcpu_nr), libvirt.VIR_VCPU_RUNNING)
                        except libvirt.libvirtError:
                            error("LibvirtHost.updateCpuLimit: Could not change state of vcpu %d.\n" % (int(vcpu_nr)))
                            return False

                    try:
                        info("LibvirtHost.updateCpuLimit: Setting vcpu %d pinning to %s.\n" % (int(vcpu_nr),
                                                                                               str(mapping)))
                        self.domain.pinVcpu(vcpu_nr, tuple(mapping))
                    except libvirt.libvirtError:
                        error("LibvirtHost.updateCpuLimit: Could not pin vcpu %d to %s.\n" % (int(vcpu_nr),
                                                                                              str(mapping)))
                        return False

                # bring down the not mentioned cores, but only if set_vcpu is available
                # if set_vcpu is unavailable this was already done by setVcpus
                if set_vcpu:
                    # reverse the mapping to get the offline cores
                    offlinecores = [0 if x == 1 else 1 for x in mapping]
                    for vcpu_nr in offlinecores:
                        try:
                            debug("LibvirtHost.updateCpuLimit: Setting core %d state to offline.\n" % vcpu_nr)
                            self.domain.setVcpu(str(vcpu_nr), libvirt.VIR_VCPU_OFFLINE)
                        except libvirt.libvirtError:
                            error("LibvirtHost.updateCpuLimit: Could not change state of vcpu %d to offline.\n" %
                                  (int(vcpu_nr)))
                            return False

                params['cores'] = cores

            self.resources.update(params)
            return True
        except libvirt.libvirtError as e:
            error("LibvirtHost.updateCpuLimit: Error setting CPU limits. Error: %s\n" % e)
            return False

    def updateMemoryLimit(self, mem_limit=-1, memswap_limit=-1, **kwargs):
        """
        Update Memory resource limitations.
        This method allows to update resource limitations at runtime

        Args:
            mem_limit: memory limit in MiB
            memswap_limit: swap limit in megabytes
            force: force mem_limits less than 512MiB

        """
        try:
            if mem_limit != -1:
                if mem_limit < 512 and 'force' not in kwargs:
                    error("Refusing to set memory_limit to less than 512MiB. Use force=True if you desire to do so.\n")
                    return

                # libvirt seems to default to KiB
                mem_limit = mem_limit * 1024
                self.domain.setMemoryFlags(mem_limit, libvirt.VIR_DOMAIN_AFFECT_LIVE)
                self.resources['mem_limit'] = mem_limit
                info("LibvirtHost.updateMemoryLimit: Set max memory for node %s to %d KiB.\n" % (self.name, mem_limit))

            if memswap_limit != -1:
                error("LibvirtHost.updateMemoryLimit: Setting swap is not yet implemented.\n")
            return True
        except libvirt.libvirtError as e:
            error("LibvirtHost.updateMemoryLimit: Error setting memory limits. Error: %s\n" % e)
            return False


class CPULimitedHost( Host ):

    "CPU limited host"

    def __init__( self, name, sched='cfs', **kwargs ):
        Host.__init__( self, name, **kwargs )
        # Initialize class if necessary
        if not CPULimitedHost.inited:
            CPULimitedHost.init()
        # Create a cgroup and move shell into it
        self.cgroup = 'cpu,cpuacct,cpuset:/' + self.name
        errFail( 'cgcreate -g ' + self.cgroup )
        # We don't add ourselves to a cpuset because you must
        # specify the cpu and memory placement first
        errFail( 'cgclassify -g cpu,cpuacct:/%s %s' % ( self.name, self.pid ) )
        # BL: Setting the correct period/quota is tricky, particularly
        # for RT. RT allows very small quotas, but the overhead
        # seems to be high. CFS has a mininimum quota of 1 ms, but
        # still does better with larger period values.
        self.period_us = kwargs.get( 'period_us', 100000 )
        self.sched = sched
        if sched == 'rt':
            self.checkRtGroupSched()
            self.rtprio = 20

    def cgroupSet( self, param, value, resource='cpu' ):
        "Set a cgroup parameter and return its value"
        cmd = 'cgset -r %s.%s=%s /%s' % (
            resource, param, value, self.name )
        quietRun( cmd )
        nvalue = int( self.cgroupGet( param, resource ) )
        if nvalue != value:
            error( '*** error: cgroupSet: %s set to %s instead of %s\n'
                   % ( param, nvalue, value ) )
        return nvalue

    def cgroupGet( self, param, resource='cpu' ):
        "Return value of cgroup parameter"
        cmd = 'cgget -r %s.%s /%s' % (
            resource, param, self.name )
        return int( quietRun( cmd ).split()[ -1 ] )

    def cgroupDel( self ):
        "Clean up our cgroup"
        # info( '*** deleting cgroup', self.cgroup, '\n' )
        _out, _err, exitcode = errRun( 'cgdelete -r ' + self.cgroup )
        # Sometimes cgdelete returns a resource busy error but still
        # deletes the group; next attempt will give "no such file"
        return exitcode == 0 or ( 'no such file' in _err.lower() )

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in node's namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        # Tell mnexec to execute command in our cgroup
        mncmd = [ 'mnexec', '-g', self.name,
                  '-da', str( self.pid ) ]
        # if our cgroup is not given any cpu time,
        # we cannot assign the RR Scheduler.
        if self.sched == 'rt':
            if int( self.cgroupGet( 'rt_runtime_us', 'cpu' ) ) <= 0:
                mncmd += [ '-r', str( self.rtprio ) ]
            else:
                debug( '*** error: not enough cpu time available for %s.' %
                       self.name, 'Using cfs scheduler for subprocess\n' )
        return Host.popen( self, *args, mncmd=mncmd, **kwargs )

    def cleanup( self ):
        "Clean up Node, then clean up our cgroup"
        super( CPULimitedHost, self ).cleanup()
        retry( retries=3, delaySecs=.1, fn=self.cgroupDel )

    _rtGroupSched = False   # internal class var: Is CONFIG_RT_GROUP_SCHED set?

    @classmethod
    def checkRtGroupSched( cls ):
        "Check (Ubuntu,Debian) kernel config for CONFIG_RT_GROUP_SCHED for RT"
        if not cls._rtGroupSched:
            release = quietRun( 'uname -r' ).strip('\r\n')
            output = quietRun( 'grep CONFIG_RT_GROUP_SCHED /boot/config-%s' %
                               release )
            if output == '# CONFIG_RT_GROUP_SCHED is not set\n':
                error( '\n*** error: please enable RT_GROUP_SCHED '
                       'in your kernel\n' )
                exit( 1 )
            cls._rtGroupSched = True

    def chrt( self ):
        "Set RT scheduling priority"
        quietRun( 'chrt -p %s %s' % ( self.rtprio, self.pid ) )
        result = quietRun( 'chrt -p %s' % self.pid )
        firstline = result.split( '\n' )[ 0 ]
        lastword = firstline.split( ' ' )[ -1 ]
        if lastword != 'SCHED_RR':
            error( '*** error: could not assign SCHED_RR to %s\n' % self.name )
        return lastword

    def rtInfo( self, f ):
        "Internal method: return parameters for RT bandwidth"
        pstr, qstr = 'rt_period_us', 'rt_runtime_us'
        # RT uses wall clock time for period and quota
        quota = int( self.period_us * f )
        return pstr, qstr, self.period_us, quota

    def cfsInfo( self, f ):
        "Internal method: return parameters for CFS bandwidth"
        pstr, qstr = 'cfs_period_us', 'cfs_quota_us'
        # CFS uses wall clock time for period and CPU time for quota.
        quota = int( self.period_us * f * numCores() )
        period = self.period_us
        if f > 0 and quota < 1000:
            debug( '(cfsInfo: increasing default period) ' )
            quota = 1000
            period = int( quota / f / numCores() )
        # Reset to unlimited on negative quota
        if quota < 0:
            quota = -1
        return pstr, qstr, period, quota

    # BL comment:
    # This may not be the right API,
    # since it doesn't specify CPU bandwidth in "absolute"
    # units the way link bandwidth is specified.
    # We should use MIPS or SPECINT or something instead.
    # Alternatively, we should change from system fraction
    # to CPU seconds per second, essentially assuming that
    # all CPUs are the same.

    def setCPUFrac( self, f, sched=None ):
        """Set overall CPU fraction for this host
           f: CPU bandwidth limit (positive fraction, or -1 for cfs unlimited)
           sched: 'rt' or 'cfs'
           Note 'cfs' requires CONFIG_CFS_BANDWIDTH,
           and 'rt' requires CONFIG_RT_GROUP_SCHED"""
        if not sched:
            sched = self.sched
        if sched == 'rt':
            if not f or f < 0:
                raise Exception( 'Please set a positive CPU fraction'
                                 ' for sched=rt\n' )
            pstr, qstr, period, quota = self.rtInfo( f )
        elif sched == 'cfs':
            pstr, qstr, period, quota = self.cfsInfo( f )
        else:
            return
        # Set cgroup's period and quota
        setPeriod = self.cgroupSet( pstr, period )
        setQuota = self.cgroupSet( qstr, quota )
        if sched == 'rt':
            # Set RT priority if necessary
            sched = self.chrt()
        info( '(%s %d/%dus) ' % ( sched, setQuota, setPeriod ) )

    def setCPUs( self, cores, mems=0 ):
        "Specify (real) cores that our cgroup can run on"
        if not cores:
            return
        if isinstance( cores, list ):
            cores = ','.join( [ str( c ) for c in cores ] )
        self.cgroupSet( resource='cpuset', param='cpus',
                        value=cores )
        # Memory placement is probably not relevant, but we
        # must specify it anyway
        self.cgroupSet( resource='cpuset', param='mems',
                        value=mems)
        # We have to do this here after we've specified
        # cpus and mems
        errFail( 'cgclassify -g cpuset:/%s %s' % (
                 self.name, self.pid ) )

    def config( self, cpu=-1, cores=None, **params ):
        """cpu: desired overall system CPU fraction
           cores: (real) core(s) this host can run on
           params: parameters for Node.config()"""
        r = Node.config( self, **params )
        # Was considering cpu={'cpu': cpu , 'sched': sched}, but
        # that seems redundant
        self.setParam( r, 'setCPUFrac', cpu=cpu )
        self.setParam( r, 'setCPUs', cores=cores )
        return r

    inited = False

    @classmethod
    def init( cls ):
        "Initialization for CPULimitedHost class"
        mountCgroups()
        cls.inited = True


# Some important things to note:
#
# The "IP" address which setIP() assigns to the switch is not
# an "IP address for the switch" in the sense of IP routing.
# Rather, it is the IP address for the control interface,
# on the control network, and it is only relevant to the
# controller. If you are running in the root namespace
# (which is the only way to run OVS at the moment), the
# control interface is the loopback interface, and you
# normally never want to change its IP address!
#
# In general, you NEVER want to attempt to use Linux's
# network stack (i.e. ifconfig) to "assign" an IP address or
# MAC address to a switch data port. Instead, you "assign"
# the IP and MAC addresses in the controller by specifying
# packets that you want to receive or send. The "MAC" address
# reported by ifconfig for a switch data port is essentially
# meaningless. It is important to understand this if you
# want to create a functional router using OpenFlow.

class Switch( Node ):
    """A Switch is a Node that is running (or has execed?)
       an OpenFlow switch."""

    portBase = 1  # Switches start with port 1 in OpenFlow
    dpidLen = 16  # digits in dpid passed to switch

    def __init__( self, name, dpid=None, opts='', listenPort=None, **params):
        """dpid: dpid hex string (or None to derive from name, e.g. s1 -> 1)
           opts: additional switch options
           listenPort: port to listen on for dpctl connections"""
        Node.__init__( self, name, **params )
        self.dpid = self.defaultDpid( dpid )
        self.opts = opts
        self.listenPort = listenPort
        if not self.inNamespace:
            self.controlIntf = Intf( 'lo', self, port=0 )

    def defaultDpid( self, dpid=None ):
        "Return correctly formatted dpid from dpid or switch name (s1 -> 1)"
        if dpid:
            # Remove any colons and make sure it's a good hex number
            dpid = dpid.translate( None, ':' )
            assert len( dpid ) <= self.dpidLen and int( dpid, 16 ) >= 0
        else:
            # Use hex of the first number in the switch name
            nums = re.findall( r'\d+', self.name )
            if nums:
                dpid = hex( int( nums[ 0 ] ) )[ 2: ]
            else:
                raise Exception( 'Unable to derive default datapath ID - '
                                 'please either specify a dpid or use a '
                                 'canonical switch name such as s23.' )
        return '0' * ( self.dpidLen - len( dpid ) ) + dpid

    def defaultIntf( self ):
        "Return control interface"
        if self.controlIntf:
            return self.controlIntf
        else:
            return Node.defaultIntf( self )

    def sendCmd( self, *cmd, **kwargs ):
        """Send command to Node.
           cmd: string"""
        kwargs.setdefault( 'printPid', False )
        if not self.execed:
            return Node.sendCmd( self, *cmd, **kwargs )
        else:
            error( '*** Error: %s has execed and cannot accept commands' %
                   self.name )

    def connected( self ):
        "Is the switch connected to a controller? (override this method)"
        # Assume that we are connected by default to whatever we need to
        # be connected to. This should be overridden by any OpenFlow
        # switch, but not by a standalone bridge.
        debug( 'Assuming', repr( self ), 'is connected to a controller\n' )
        return True

    def stop( self, deleteIntfs=True ):
        """Stop switch
           deleteIntfs: delete interfaces? (True)"""
        if deleteIntfs:
            self.deleteIntfs()

    def __repr__( self ):
        "More informative string representation"
        intfs = ( ','.join( [ '%s:%s' % ( i.name, i.IP() )
                              for i in self.intfList() ] ) )
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid )


class UserSwitch( Switch ):
    "User-space switch."

    dpidLen = 12

    def __init__( self, name, dpopts='--no-slicing', **kwargs ):
        """Init.
           name: name for the switch
           dpopts: additional arguments to ofdatapath (--no-slicing)"""
        Switch.__init__( self, name, **kwargs )
        pathCheck( 'ofdatapath', 'ofprotocol',
                   moduleName='the OpenFlow reference user switch' +
                              '(openflow.org)' )
        if self.listenPort:
            self.opts += ' --listen=ptcp:%i ' % self.listenPort
        else:
            self.opts += ' --listen=punix:/tmp/%s.listen' % self.name
        self.dpopts = dpopts

    @classmethod
    def setup( cls ):
        "Ensure any dependencies are loaded; if not, try to load them."
        if not os.path.exists( '/dev/net/tun' ):
            moduleDeps( add=TUN )

    def dpctl( self, *args ):
        "Run dpctl command"
        listenAddr = None
        if not self.listenPort:
            listenAddr = 'unix:/tmp/%s.listen' % self.name
        else:
            listenAddr = 'tcp:127.0.0.1:%i' % self.listenPort
        return self.cmd( 'dpctl ' + ' '.join( args ) +
                         ' ' + listenAddr )

    def connected( self ):
        "Is the switch connected to a controller?"
        status = self.dpctl( 'status' )
        return ( 'remote.is-connected=true' in status and
                 'local.is-connected=true' in status )

    @staticmethod
    def TCReapply( intf ):
        """Unfortunately user switch and Mininet are fighting
           over tc queuing disciplines. To resolve the conflict,
           we re-create the user switch's configuration, but as a
           leaf of the TCIntf-created configuration."""
        if isinstance( intf, TCIntf ):
            ifspeed = 10000000000  # 10 Gbps
            minspeed = ifspeed * 0.001

            res = intf.config( **intf.params )

            if res is None:  # link may not have TC parameters
                return

            # Re-add qdisc, root, and default classes user switch created, but
            # with new parent, as setup by Mininet's TCIntf
            parent = res['parent']
            intf.tc( "%s qdisc add dev %s " + parent +
                     " handle 1: htb default 0xfffe" )
            intf.tc( "%s class add dev %s classid 1:0xffff parent 1: htb rate "
                     + str(ifspeed) )
            intf.tc( "%s class add dev %s classid 1:0xfffe parent 1:0xffff " +
                     "htb rate " + str(minspeed) + " ceil " + str(ifspeed) )

    def start( self, controllers ):
        """Start OpenFlow reference user datapath.
           Log to /tmp/sN-{ofd,ofp}.log.
           controllers: list of controller objects"""
        # Add controllers
        clist = ','.join( [ 'tcp:%s:%d' % ( c.IP(), c.port )
                            for c in controllers ] )
        ofdlog = '/tmp/' + self.name + '-ofd.log'
        ofplog = '/tmp/' + self.name + '-ofp.log'
        intfs = [ str( i ) for i in self.intfList() if not i.IP() ]
        self.cmd( 'ofdatapath -i ' + ','.join( intfs ) +
                  ' punix:/tmp/' + self.name + ' -d %s ' % self.dpid +
                  self.dpopts +
                  ' 1> ' + ofdlog + ' 2> ' + ofdlog + ' &' )
        self.cmd( 'ofprotocol unix:/tmp/' + self.name +
                  ' ' + clist +
                  ' --fail=closed ' + self.opts +
                  ' 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        if "no-slicing" not in self.dpopts:
            # Only TCReapply if slicing is enable
            sleep(1)  # Allow ofdatapath to start before re-arranging qdisc's
            for intf in self.intfList():
                if not intf.IP():
                    self.TCReapply( intf )

    def stop( self, deleteIntfs=True ):
        """Stop OpenFlow reference user datapath.
           deleteIntfs: delete interfaces? (True)"""
        self.cmd( 'kill %ofdatapath' )
        self.cmd( 'kill %ofprotocol' )
        super( UserSwitch, self ).stop( deleteIntfs )


class OVSSwitch( Switch ):
    "Open vSwitch switch. Depends on ovs-vsctl."

    def __init__( self, name, failMode='secure', datapath='kernel',
                  inband=False, protocols=None,
                  reconnectms=1000, stp=False, batch=False, **params ):
        """name: name for switch
           failMode: controller loss behavior (secure|standalone)
           datapath: userspace or kernel mode (kernel|user)
           inband: use in-band control (False)
           protocols: use specific OpenFlow version(s) (e.g. OpenFlow13)
                      Unspecified (or old OVS version) uses OVS default
           reconnectms: max reconnect timeout in ms (0/None for default)
           stp: enable STP (False, requires failMode=standalone)
           batch: enable batch startup (False)"""
        Switch.__init__( self, name, **params )
        self.failMode = failMode
        self.datapath = datapath
        self.inband = inband
        self.protocols = protocols
        self.reconnectms = reconnectms
        self.stp = stp
        self._uuids = []  # controller UUIDs
        self.batch = batch
        self.commands = []  # saved commands for batch startup

        # add a prefix to the name of the deployed switch, to find it back easier later
        prefix = params.get('prefix', '')
        self.deployed_name = prefix + name


    @classmethod
    def setup( cls ):
        "Make sure Open vSwitch is installed and working"
        pathCheck( 'ovs-vsctl',
                   moduleName='Open vSwitch (openvswitch.org)')
        # This should no longer be needed, and it breaks
        # with OVS 1.7 which has renamed the kernel module:
        #  moduleDeps( subtract=OF_KMOD, add=OVS_KMOD )
        out, err, exitcode = errRun( 'ovs-vsctl -t 1 show' )
        if exitcode:
            error( out + err +
                   'ovs-vsctl exited with code %d\n' % exitcode +
                   '*** Error connecting to ovs-db with ovs-vsctl\n'
                   'Make sure that Open vSwitch is installed, '
                   'that ovsdb-server is running, and that\n'
                   '"ovs-vsctl show" works correctly.\n'
                   'You may wish to try '
                   '"service openvswitch-switch start".\n' )
            exit( 1 )
        version = quietRun( 'ovs-vsctl --version' )
        cls.OVSVersion = findall( r'\d+\.\d+', version )[ 0 ]

    @classmethod
    def isOldOVS( cls ):
        "Is OVS ersion < 1.10?"
        return ( StrictVersion( cls.OVSVersion ) <
                 StrictVersion( '1.10' ) )

    def dpctl( self, *args ):
        "Run ovs-ofctl command"
        return self.cmd( 'ovs-ofctl', args[ 0 ], self.deployed_name, *args[ 1: ] )

    def vsctl( self, *args, **kwargs ):
        "Run ovs-vsctl command (or queue for later execution)"
        if self.batch:
            cmd = ' '.join( str( arg ).strip() for arg in args )
            self.commands.append( cmd )
        else:
            return self.cmd( 'ovs-vsctl', *args, **kwargs )

    @staticmethod
    def TCReapply( intf ):
        """Unfortunately OVS and Mininet are fighting
           over tc queuing disciplines. As a quick hack/
           workaround, we clear OVS's and reapply our own."""
        if isinstance( intf, TCIntf ):
            intf.config( **intf.params )

    def attach( self, intf ):
        "Connect a data port"
        self.vsctl( 'add-port', self.deployed_name, intf )
        self.cmd( 'ifconfig', intf, 'up' )
        self.TCReapply( intf )

    def attachInternalIntf(self, intf_name, net):
        """Add an interface of type:internal to the ovs switch
           and add routing entry to host"""
        self.vsctl('add-port', self.deployed_name, intf_name, '--', 'set', ' interface', intf_name, 'type=internal')
        int_intf = Intf(intf_name, node=self.deployed_name)
        #self.addIntf(int_intf, moveIntfFn=None)
        self.cmd('ip route add', net, 'dev', intf_name)

        return self.nameToIntf[intf_name]

    def detach( self, intf ):
        "Disconnect a data port"
        self.vsctl( 'del-port', self.deployed_name, intf )

    def controllerUUIDs( self, update=False ):
        """Return ovsdb UUIDs for our controllers
           update: update cached value"""
        if not self._uuids or update:
            controllers = self.cmd( 'ovs-vsctl -- get Bridge', self.deployed_name,
                                    'Controller' ).strip()
            if controllers.startswith( '[' ) and controllers.endswith( ']' ):
                controllers = controllers[ 1 : -1 ]
                if controllers:
                    self._uuids = [ c.strip()
                                    for c in controllers.split( ',' ) ]
        return self._uuids

    def connected( self ):
        "Are we connected to at least one of our controllers?"
        for uuid in self.controllerUUIDs():
            if 'true' in self.vsctl( '-- get Controller',
                                     uuid, 'is_connected' ):
                return True
        return self.failMode == 'standalone'

    def intfOpts( self, intf ):
        "Return OVS interface options for intf"
        opts = ''
        if not self.isOldOVS():
            # ofport_request is not supported on old OVS
            opts += ' ofport_request=%s' % self.ports[ intf ]
            # Patch ports don't work well with old OVS
            if isinstance( intf, OVSIntf ):
                intf1, intf2 = intf.link.intf1, intf.link.intf2
                peer = intf1 if intf1 != intf else intf2
                opts += ' type=patch options:peer=%s' % peer
        return '' if not opts else ' -- set Interface %s' % intf + opts

    def bridgeOpts( self ):
        "Return OVS bridge options"
        opts = ( ' other_config:datapath-id=%s' % self.dpid +
                 ' fail_mode=%s' % self.failMode )
        if not self.inband:
            opts += ' other-config:disable-in-band=true'
        if self.datapath == 'user':
            opts += ' datapath_type=netdev'
        if self.protocols and not self.isOldOVS():
            opts += ' protocols=%s' % self.protocols
        if self.stp and self.failMode == 'standalone':
            opts += ' stp_enable=true'
        return opts

    def start( self, controllers ):
        "Start up a new OVS OpenFlow switch using ovs-vsctl"
        if self.inNamespace:
            raise Exception(
                'OVS kernel switch does not work in a namespace' )
        int( self.dpid, 16 )  # DPID must be a hex string
        # Command to add interfaces
        intfs = ''.join( ' -- add-port %s %s' % ( self.deployed_name, intf ) +
                         self.intfOpts( intf )
                         for intf in self.intfList()
                         if self.ports[ intf ] and not intf.IP() )
        # Command to create controller entries
        clist = [ ( self.deployed_name + c.name, '%s:%s:%d' %
                  ( c.protocol, c.IP(), c.port ) )
                  for c in controllers ]
        if self.listenPort:
            clist.append( ( self.deployed_name + '-listen',
                            'ptcp:%s' % self.listenPort ) )
        ccmd = '-- --id=@%s create Controller target=\\"%s\\"'
        if self.reconnectms:
            ccmd += ' max_backoff=%d' % self.reconnectms
        cargs = ' '.join( ccmd % ( name, target )
                          for name, target in clist )
        # Controller ID list
        cids = ','.join( '@%s' % name for name, _target in clist )
        # Try to delete any existing bridges with the same name
        if not self.isOldOVS():
            cargs += ' -- --if-exists del-br %s' % self.deployed_name
        # One ovs-vsctl command to rule them all!
        self.vsctl( cargs +
                    ' -- add-br %s' % self.deployed_name +
                    ' -- set bridge %s controller=[%s]' % ( self.deployed_name, cids  ) +
                    self.bridgeOpts() +
                    intfs )
        # If necessary, restore TC config overwritten by OVS
        if not self.batch:
            for intf in self.intfList():
                self.TCReapply( intf )

    # This should be ~ int( quietRun( 'getconf ARG_MAX' ) ),
    # but the real limit seems to be much lower
    argmax = 128000

    @classmethod
    def batchStartup( cls, switches, run=errRun ):
        """Batch startup for OVS
           switches: switches to start up
           run: function to run commands (errRun)"""
        info( '...' )
        cmds = 'ovs-vsctl'
        for switch in switches:
            if switch.isOldOVS():
                # Ideally we'd optimize this also
                run( 'ovs-vsctl del-br %s' % switch )
            for cmd in switch.commands:
                cmd = cmd.strip()
                # Don't exceed ARG_MAX
                if len( cmds ) + len( cmd ) >= cls.argmax:
                    run( cmds, shell=True )
                    cmds = 'ovs-vsctl'
                cmds += ' ' + cmd
                switch.cmds = []
                switch.batch = False
        if cmds:
            run( cmds, shell=True )
        # Reapply link config if necessary...
        for switch in switches:
            for intf in switch.intfs.itervalues():
                if isinstance( intf, TCIntf ):
                    intf.config( **intf.params )
        return switches

    def stop( self, deleteIntfs=True ):
        """Terminate OVS switch.
           deleteIntfs: delete interfaces? (True)"""
        self.cmd( 'ovs-vsctl del-br', self.deployed_name )
        if self.datapath == 'user':
            self.cmd( 'ip link del', self.deployed_name )
        super( OVSSwitch, self ).stop( deleteIntfs )

    @classmethod
    def batchShutdown( cls, switches, run=errRun ):
        "Shut down a list of OVS switches"
        delcmd = 'del-br %s'
        if switches and not switches[ 0 ].isOldOVS():
            delcmd = '--if-exists ' + delcmd
        # First, delete them all from ovsdb
        run( 'ovs-vsctl ' +
             ' -- '.join( delcmd % s.deployed_name for s in switches ), shell=True )
        # Next, shut down all of the processes
        pids = ' '.join( str( switch.pid ) for switch in switches )
        run( 'kill -HUP ' + pids )
        for switch in switches:
            switch.shell = None
        return switches


OVSKernelSwitch = OVSSwitch


class OVSBridge( OVSSwitch ):
    "OVSBridge is an OVSSwitch in standalone/bridge mode"

    def __init__( self, *args, **kwargs ):
        """stp: enable Spanning Tree Protocol (False)
           see OVSSwitch for other options"""
        kwargs.update( failMode='standalone' )
        OVSSwitch.__init__( self, *args, **kwargs )

        # ip address of this bridge (eg. 10.10.0.1/24)
        self.ip = kwargs.get('ip')

    def start( self ):
        "Start bridge, ignoring controllers argument"
        OVSSwitch.start( self, controllers=[] )

        # assign an ip address to this switch, so it can connect to the host
        if self.ip:
            self.cmd('ip address add', self.ip, 'dev', self.deployed_name)
            self.cmd('ip link set', self.deployed_name, 'up')

    def connected( self ):
        "Are we forwarding yet?"
        if self.stp:
            status = self.dpctl( 'show' )
            return 'STP_FORWARD' in status and not 'STP_LEARN' in status
        else:
            return True


class IVSSwitch( Switch ):
    "Indigo Virtual Switch"

    def __init__( self, name, verbose=False, **kwargs ):
        Switch.__init__( self, name, **kwargs )
        self.verbose = verbose

    @classmethod
    def setup( cls ):
        "Make sure IVS is installed"
        pathCheck( 'ivs-ctl', 'ivs',
                   moduleName="Indigo Virtual Switch (projectfloodlight.org)" )
        out, err, exitcode = errRun( 'ivs-ctl show' )
        if exitcode:
            error( out + err +
                   'ivs-ctl exited with code %d\n' % exitcode +
                   '*** The openvswitch kernel module might '
                   'not be loaded. Try modprobe openvswitch.\n' )
            exit( 1 )

    @classmethod
    def batchShutdown( cls, switches ):
        "Kill each IVS switch, to be waited on later in stop()"
        for switch in switches:
            switch.cmd( 'kill %ivs' )
        return switches

    def start( self, controllers ):
        "Start up a new IVS switch"
        args = ['ivs']
        args.extend( ['--name', self.name] )
        args.extend( ['--dpid', self.dpid] )
        if self.verbose:
            args.extend( ['--verbose'] )
        for intf in self.intfs.values():
            if not intf.IP():
                args.extend( ['-i', intf.name] )
        for c in controllers:
            args.extend( ['-c', '%s:%d' % (c.IP(), c.port)] )
        if self.listenPort:
            args.extend( ['--listen', '127.0.0.1:%i' % self.listenPort] )
        args.append( self.opts )

        logfile = '/tmp/ivs.%s.log' % self.name

        self.cmd( ' '.join(args) + ' >' + logfile + ' 2>&1 </dev/null &' )

    def stop( self, deleteIntfs=True ):
        """Terminate IVS switch.
           deleteIntfs: delete interfaces? (True)"""
        self.cmd( 'kill %ivs' )
        self.cmd( 'wait' )
        super( IVSSwitch, self ).stop( deleteIntfs )

    def attach( self, intf ):
        "Connect a data port"
        self.cmd( 'ivs-ctl', 'add-port', '--datapath', self.name, intf )

    def detach( self, intf ):
        "Disconnect a data port"
        self.cmd( 'ivs-ctl', 'del-port', '--datapath', self.name, intf )

    def dpctl( self, *args ):
        "Run dpctl command"
        if not self.listenPort:
            return "can't run dpctl without passive listening port"
        return self.cmd( 'ovs-ofctl ' + ' '.join( args ) +
                         ' tcp:127.0.0.1:%i' % self.listenPort )


class Controller( Node ):
    """A Controller is a Node that is running (or has execed?) an
       OpenFlow controller."""

    def __init__( self, name, inNamespace=False, command='controller',
                  cargs='-v ptcp:%d', cdir=None, ip="127.0.0.1",
                  port=6653, protocol='tcp', **params ):
        self.command = command
        self.cargs = cargs
        self.cdir = cdir
        # Accept 'ip:port' syntax as shorthand
        if ':' in ip:
            ip, port = ip.split( ':' )
            port = int( port )
        self.ip = ip
        self.port = port
        self.protocol = protocol
        Node.__init__( self, name, inNamespace=inNamespace,
                       ip=ip, **params  )
        self.checkListening()

    def checkListening( self ):
        "Make sure no controllers are running on our port"
        # Verify that Telnet is installed first:
        out, _err, returnCode = errRun( "which telnet" )
        if 'telnet' not in out or returnCode != 0:
            raise Exception( "Error running telnet to check for listening "
                             "controllers; please check that it is "
                             "installed." )
        listening = self.cmd( "echo A | telnet -e A %s %d" %
                              ( self.ip, self.port ) )
        if 'Connected' in listening:
            servers = self.cmd( 'netstat -natp' ).split( '\n' )
            pstr = ':%d ' % self.port
            clist = servers[ 0:1 ] + [ s for s in servers if pstr in s ]
            raise Exception( "Please shut down the controller which is"
                             " running on port %d:\n" % self.port +
                             '\n'.join( clist ) )

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        pathCheck( self.command )
        cout = '/tmp/' + self.name + '.log'
        if self.cdir is not None:
            self.cmd( 'cd ' + self.cdir )
        self.cmd( self.command + ' ' + self.cargs % self.port +
                  ' 1>' + cout + ' 2>' + cout + ' &' )
        self.execed = False

    def stop( self, *args, **kwargs ):
        "Stop controller."
        self.cmd( 'kill %' + self.command )
        self.cmd( 'wait %' + self.command )
        super( Controller, self ).stop( *args, **kwargs )

    def IP( self, intf=None ):
        "Return IP address of the Controller"
        if self.intfs:
            ip = Node.IP( self, intf )
        else:
            ip = self.ip
        return ip

    def __repr__( self ):
        "More informative string representation"
        return '<%s %s: %s:%s pid=%s> ' % (
            self.__class__.__name__, self.name,
            self.IP(), self.port, self.pid )

    @classmethod
    def isAvailable( cls ):
        "Is controller available?"
        return quietRun( 'which controller' )


class OVSController( Controller ):
    "Open vSwitch controller"
    def __init__( self, name, command='ovs-controller', **kwargs ):
        if quietRun( 'which test-controller' ):
            command = 'test-controller'
        Controller.__init__( self, name, command=command, **kwargs )

    @classmethod
    def isAvailable( cls ):
        return ( quietRun( 'which ovs-controller' ) or
                 quietRun( 'which test-controller' ) or
                 quietRun( 'which ovs-testcontroller' ) )

class NOX( Controller ):
    "Controller to run a NOX application."

    def __init__( self, name, *noxArgs, **kwargs ):
        """Init.
           name: name to give controller
           noxArgs: arguments (strings) to pass to NOX"""
        if not noxArgs:
            warn( 'warning: no NOX modules specified; '
                  'running packetdump only\n' )
            noxArgs = [ 'packetdump' ]
        elif type( noxArgs ) not in ( list, tuple ):
            noxArgs = [ noxArgs ]

        if 'NOX_CORE_DIR' not in os.environ:
            exit( 'exiting; please set missing NOX_CORE_DIR env var' )
        noxCoreDir = os.environ[ 'NOX_CORE_DIR' ]

        Controller.__init__( self, name,
                             command=noxCoreDir + '/nox_core',
                             cargs='--libdir=/usr/local/lib -v -i ptcp:%s ' +
                             ' '.join( noxArgs ),
                             cdir=noxCoreDir,
                             **kwargs )

class Ryu( Controller ):
    "Controller to run Ryu application"
    def __init__( self, name, *ryuArgs, **kwargs ):
        """Init.
        name: name to give controller.
        ryuArgs: arguments and modules to pass to Ryu"""
        homeDir = quietRun( 'printenv HOME' ).strip( '\r\n' )
        ryuCoreDir = '%s/ryu/ryu/app/' % homeDir
        if not ryuArgs:
            warn( 'warning: no Ryu modules specified; '
                  'running simple_switch only\n' )
            ryuArgs = [ ryuCoreDir + 'simple_switch.py' ]
        elif type( ryuArgs ) not in ( list, tuple ):
            ryuArgs = [ ryuArgs ]

        Controller.__init__( self, name,
                             command='ryu-manager',
                             cargs='--ofp-tcp-listen-port %s ' +
                             ' '.join( ryuArgs ),
                             cdir=ryuCoreDir,
                             **kwargs )


class RemoteController( Controller ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, ip='127.0.0.1',
                  port=None, **kwargs):
        """Init.
           name: name to give controller
           ip: the IP address where the remote controller is
           listening
           port: the port where the remote controller is listening"""
        Controller.__init__( self, name, ip=ip, port=port, **kwargs )

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return

    def checkListening( self ):
        "Warn if remote controller is not accessible"
        if self.port is not None:
            self.isListening( self.ip, self.port )
        else:
            for port in 6653, 6633:
                if self.isListening( self.ip, port ):
                    self.port = port
                    info( "Connecting to remote controller"
                          " at %s:%d\n" % ( self.ip, self.port ))
                    break

        if self.port is None:
            self.port = 6653
            warn( "Setting remote controller"
                  " to %s:%d\n" % ( self.ip, self.port ))

    def isListening( self, ip, port ):
        "Check if a remote controller is listening at a specific ip and port"
        listening = self.cmd( "echo A | telnet -e A %s %d" % ( ip, port ) )
        if 'Connected' not in listening:
            warn( "Unable to contact the remote controller"
                  " at %s:%d\n" % ( ip, port ) )
            return False
        else:
            return True

DefaultControllers = ( Controller, OVSController )

def findController( controllers=DefaultControllers ):
    "Return first available controller from list, if any"
    for controller in controllers:
        if controller.isAvailable():
            return controller

def DefaultController( name, controllers=DefaultControllers, **kwargs ):
    "Find a controller that is available and instantiate it"
    controller = findController( controllers )
    if not controller:
        raise Exception( 'Could not find a default OpenFlow controller' )
    return controller( name, **kwargs )

def NullController( *_args, **_kwargs ):
    "Nonexistent controller - simply returns None"
    return None
