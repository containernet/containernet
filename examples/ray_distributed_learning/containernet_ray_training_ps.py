#!/usr/bin/python
"""
Use with script ps_ray.py.
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
dataset = "fashion_mnist"
head_commands = f"/bin/bash -c 'python ./code/training_scripts/data/data.py --data {dataset}; \
                /bin/bash code/utils/edit_hosts.sh;" \
               "ray start --head --node-ip-address 10.0.0.251 --disable-usage-stats ;" \
               "exec /bin/bash'"
worker_commands = f"/bin/bash -c 'python ./code/training_scripts/data/data.py --data {dataset};" \
                  "/bin/bash ./code/utils/edit_hosts.sh;" \
                  "ray start --address 10.0.0.251:6379 --disable-usage-stats;" \
                  "exec /bin/bash'"
# ray:2.2.0_net_utils
host_data_folder='/home/sysgen/data'
workers_data_folder='/root/data'
m01 = net.addDocker('d1', ip='10.0.0.251', dimage="ray:GPU", dcmd=head_commands, cpuset_cpus='0', cpus=1, shm_size="1000mb", dns=["8.8.8.8"], volumes=[f'{host_data_folder}:{workers_data_folder}'])
m1 = net.addDocker('d2', ip='10.0.0.252', dimage="ray:GPU", dcmd=worker_commands, cpuset_cpus='1', cpus=1, shm_size="1000mb", dns=["8.8.8.8"], volumes=[f'{host_data_folder}:{workers_data_folder}'])
m2 = net.addDocker('d3', ip='10.0.0.253', dimage="ray:GPU", dcmd=worker_commands, cpuset_cpus='2', cpus=1, shm_size="1000mb", dns=["8.8.8.8"], volumes=[f'{host_data_folder}:{workers_data_folder}'])
m3 = net.addDocker('d4', ip='10.0.0.254', dimage="ray:GPU", dcmd=worker_commands, cpuset_cpus='3', cpus=1, shm_size="1000mb", dns=["8.8.8.8"], volumes=[f'{host_data_folder}:{workers_data_folder}'])
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

