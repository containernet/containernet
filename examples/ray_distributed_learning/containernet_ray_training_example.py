#!/usr/bin/python
"""
Use with script torch_fashion_mnixt_example.py.
"""
from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import info, setLogLevel
setLogLevel('info')

net = Containernet(controller=Controller)
info('*** Adding controller\n')
net.addController('c0')
info('*** Adding docker containers\n')

head_commands= "/bin/bash -c 'python ./code/training_scripts/torch_fashion_mnist_example.py --data ; \
    /bin/bash code/utils/edit_hosts.sh ; ray start --head --node-ip-address 10.0.0.251 --disable-usage-stats ;exec /bin/bash'"
worker_commands = "/bin/bash -c '/bin/bash ./code/utils/edit_hosts.sh; /home/ray/anaconda3/bin/ray start --address 10.0.0.251:6379 --disable-usage-stats; exec /bin/bash'"

m01 = net.addDocker('d1', ip='10.0.0.251', dimage="ray:2.2.0_net_utils", dcmd=head_commands, cpuset_cpus='0', cpus=1, shm_size="1000mb")
m1 = net.addDocker('d2', ip='10.0.0.252', dimage="ray:2.2.0_net_utils", dcmd=worker_commands, cpuset_cpus='1', cpus=1, shm_size="1000mb")
m2 = net.addDocker('d3', ip='10.0.0.253', dimage="ray:2.2.0_net_utils", dcmd=worker_commands, cpuset_cpus='2', cpus=1, shm_size="1000mb")
m3 = net.addDocker('d4', ip='10.0.0.254', dimage="ray:2.2.0_net_utils", dcmd=worker_commands, cpuset_cpus='3', cpus=1, shm_size="1000mb")
info('*** Adding switches\n')
s1 = net.addSwitch('s1')
info('*** Creating links\n')
net.addLink(m01, s1, delay='0.055ms')
net.addLink(m1, s1, delay='0.07ms')
net.addLink(m2, s1, delay='0.07ms')
net.addLink(m3, s1, delay='0.06ms')
info('*** Starting network\n')
net.start()
info('*** Testing connectivity\n')
net.ping([m01, m1])
info('*** Running CLI\n')
CLI(net)
info('*** Stopping network')
net.stop()

