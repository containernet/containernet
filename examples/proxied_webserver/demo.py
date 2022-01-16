#!/usr/bin/python3

from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel

setLogLevel("info")

# ----
# Setup the network.
# ----

net = Containernet(controller=Controller, link=TCLink)
net.addController("c0")

# ----
# Add all hosts.
# ----

# Setup some clients.
numberOfClients = 5
clients = []
for i in range(numberOfClients):
    clients.append(
        net.addDocker(f"client{i+1}", ip=f"10.0.0.{i+1}", dimage="demo_client")
    )

# Setup the reverse proxy host and start nginx.
proxy = net.addDocker(
    "proxy", ip="10.0.1.1", dimage="demo_nginx", dcmd="nginx -g 'daemon off;'"
)

# Setup the server.
# Limit the CPU speed to 10%.
server = net.addDocker(
    "server",
    ip="20.0.0.2",
    dimage="demo_server",
    environment={"REDIS_HOST": "20.0.0.3", "REDIS_PORT": "6379", "REDIS_DB": "0"},
    cpu_period=100000,
    cpu_quota=10000,
)

# Setup the database.
db = net.addDocker("db", ip="20.0.0.3", dimage="demo_redis", dcmd="redis-server")

# ----
# Connect the clients with the proxy.
# ----

switch1 = net.addSwitch("switch1")
for client in clients:
    net.addLink(client, switch1)
net.addLink(switch1, proxy)

# ----
# Connect the proxy to the service network.
# ----

switch2 = net.addSwitch("switch2")
# The proxy should have its service network IP assigned to the corresponding interface:
net.addLink(proxy, switch2, params1={"ip": "20.0.0.1/24"})
net.addLink(switch2, server)
net.addLink(switch2, db)

# ----
# Start the network and CLI.
# ----

net.start()
server.cmd(
    "uwsgi --socket 20.0.0.2:3031 --wsgi-file server.py --callable app --daemonize /tmp/uwsgi.log"
)
CLI(net)
net.stop()
