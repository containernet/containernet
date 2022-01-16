# Proxied Webserver Example

This example runs the following setup:

```
 ┌───────────┐
 │           │                                           ┌────────────────┐
 │  Client1  ├───────┐                                   │                │
 │           │       │                               ┌───┤  flask Server  │
 └───────────┘       │                               │   │                │
                     │                               │   └────────────────┘
 ┌───────────┐       │       ┌───────────────┐       │
 │           │  ┌────┴────┐  │               │  ┌────┴────┐
 │  Client2  ├──┤ Switch1 ├──┤  nginx Proxy  ├──┤ Switch2 │
 │           │  └────┬────┘  │               │  └────┬────┘
 └───────────┘       │       └───────────────┘       │
                     │                               │   ┌──────────────────┐
 ┌───────────┐       │                               │   │                  │
 │           │       │                               └───┤  redis Database  │
 │    ...    ├───────┘                                   │                  │
 │           │                                           └──────────────────┘
 └───────────┘
```

The server behind the reverse proxy is running an app which counts prime numbers up to a given limit. After calculation it will write the result to the connected Redis database and return it in its response. The app container is constrained to 10% of the host CPU.

## Setup

To run it, first build the Docker images with

```sh
$ ./build.sh
```

Then, start the example with

```sh
$ sudo ./demo.py
```

You should find yourself in the CLI and can inspect the network with

```sh
$ containernet> dump
```  

which should display something like

```txt
<Docker client1: client1-eth0:10.0.0.1 pid=...>
<Docker client2: client2-eth0:10.0.0.2 pid=...>
<Docker client3: client3-eth0:10.0.0.3 pid=...>
<Docker proxy: proxy-eth0:10.0.1.1,proxy-eth1:20.0.0.1 pid=...>
<Docker server: server-eth0:20.0.0.2 pid=...>
<Docker db: db-eth0:20.0.0.3 pid=...>
<OVSSwitch switch1: lo:127.0.0.1,switch1-eth1:None,switch1-eth2:None,switch1-eth3:None,switch1-eth4:None pid=...>
<OVSSwitch switch2: lo:127.0.0.1,switch2-eth1:None,switch2-eth2:None,switch2-eth3:None pid=...>
<Controller c0: 127.0.0.1:6653 pid=...>
```

## Making requests

You can simulate making a request from a client to the server with

```sh
$ containernet> client1 curl 10.0.1.1/primes?limit=5000
```

`10.0.1.1` is the IP assigned to the nginx server, which will forward the request to the connected app server.

After a short wait you will see the result of the calculation:

```txt
Found 669 primes in 0.97 seconds.
```

You can also check for the result in the database with

```sh
$ containernet> db redis-cli get 5000
```

which should also return the previously calculated result:

```txt
"669 primes in 0.97 seconds"
```

You can exit the CLI with

```sh
$ containernet> exit
```

## Modifying the setup

You can experiment with different options by changing the `demo.py` file. For example, you can comment out the CPU restriction options when setting up the server: 

```py
server = net.addDocker(
    "server",
    ip="20.0.0.2",
    dimage="demo_server",
    environment={"REDIS_HOST": "20.0.0.3", "REDIS_PORT": "6379", "REDIS_DB": "0"},
    # cpu_period=100000,
    # cpu_quota=10000,
)
```

You will notice that clients receive their responses much faster now.

## Monitoring running containers

Sometimes the CLI that is provided when running an experiment is not sufficient. While running Containernet, you can list used containers with `docker ps`. In this scenario it will show something like

```txt
CONTAINER ID   IMAGE         COMMAND                  CREATED         STATUS         PORTS                                         NAMES
13f42ebc3e78   demo_redis    "redis-server"           3 seconds ago   Up 2 seconds   0.0.0.0:49215->6379/tcp, :::49215->6379/tcp   mn.db
bb9e64dfb39d   demo_server   "/bin/bash"              4 seconds ago   Up 3 seconds                                                 mn.server
930fa2fe035e   demo_nginx    "nginx -g 'daemon of…"   5 seconds ago   Up 4 seconds   0.0.0.0:49214->80/tcp, :::49214->80/tcp       mn.proxy
4f6db5898a58   demo_client   "/bin/bash"              5 seconds ago   Up 5 seconds                                                 mn.client3
6664e3cab3c3   demo_client   "/bin/bash"              6 seconds ago   Up 5 seconds                                                 mn.client2
479b74f79243   demo_client   "/bin/bash"              6 seconds ago   Up 6 seconds
```

Here you could for example log into the app container using `docker exec -it bb9e64dfb39d bash`. You can then monitor resource usage with `htop` while simulating a client request through the Containernet CLI in a different terminal session.
