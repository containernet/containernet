Dockernet
=========

### Use Docker containers as hosts inside your Mininet topologies. Interact with the containers through Mininet's CLI.

This fork of Mininet allows to use Docker containers as Mininet hosts. This enables interesting functionalities to built networking/cloud testbeds. The integration is done subclassing the original Host class.


* WIP! Not fully functional yet.
* Contributions welcome :)

Based on: Mininet 2.2.1

### Installation / Requirements

* Ubuntu 14.04 LTS
* Install Docker: `curl -sSL https://get.docker.com/ | sh`
* Docker client library: `pip install docker-py`

### Usage

* see example topology: `examples/dockerhosts.py`

### Run

* run: `sudo python examples/dockerhosts.py`
* test: `mininet> d1 ifconfig` to see config of container d1

### TODOs

* implement, implement, implement
* loglevel('debug') leads to freeze on exit
* STRG+C is not received by container

### Working features

* Container add, remove
* Connect containers to topology
* Execute Mininet CLI commands inside container

### Credits
Dockernet (c) 2015 by Manuel Peuster

* Inspired by: http://techandtrains.com/2014/08/21/docker-container-as-mininet-host/


### Contact
Manuel Peuster
manuel (dot) peuster (at) upb (dot) de
