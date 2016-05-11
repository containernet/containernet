Containernet
============

[![Join the chat at https://gitter.im/mpeuster/containernet](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/mpeuster/containernet?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

### Use Docker containers as hosts inside your Mininet topologies. Interact with the containers through Mininet's CLI.

This fork of Mininet allows to use Docker containers as Mininet hosts. This enables interesting functionalities to built networking/cloud testbeds. The integration is done by subclassing the original Host class.

Based on: Mininet 2.2.1

* WIP! Not fully functional yet.
* Contributions welcome :-)


### Features

* Add, remove Docker containers to Mininet topologies
* Connect Docker containers to topology (to switches, other containers, or legacy Mininet hosts )
* Execute commands inside Docker containers by using the Mininet CLI 
* Dynamic topology changes (lets behave like a small cloud ;-) )
 * Add Hosts/Docker containers to a *running* Mininet topology
 * Connect Hosts/Docker containers to a *running* Mininet topology
 * Remove Hosts/Docker containers/Links from a *running* Mininet topology
* Resource limitation of Docker containers
 * CPU limitation with Docker CPU share option
 * CPU limitation with Docker CFS period/quota options
 * Memory/swap limitation
 * UPDATE CPU/Mem limitations at runtime!
* Traffic control links (delay, bw, loss, jitter)
 * (missing: TCLink support for dynamically added containers/hosts)
* Automated unit tests for all new features
* Automated installation based on Ansible playbook

### Dependencies

* Ubuntu 14.04 LTS
* Docker 
* docker-py 

### Installation
Automatic installation is provide through an Ansible playbook.
* Requires: Ubuntu 14.04 LTS
* `sudo apt-get install ansible git`
* `sudo vim /etc/ansible/hosts`
* Add: `localhost ansible_connection=local`
* `git clone https://github.com/mpeuster/containernet.git`
* `cd containernet/ansible`
* `sudo ansible-playbook install.yml`
* Wait (and have a coffee) ...

### Usage / Run
Start example topology with some empty Docker containers connected to the network.

* `cd containernet`
* run: `sudo python examples/dockerhosts.py`
* use: `containernet> d1 ifconfig` to see config of container d1

### Tests
There is a set of Containernet specific unit tests located in `mininet/test/test_containernet.py`. To run these, do:

* `sudo pytest mininet/test/test_containernet.py -v`

### Cleanup

* Run `bin/clear_crash.sh` to cleanup the environment after something went wrong.


### Docker support

Containernet can be executed within a container itself. This results in a containers-inside-container setup and simplifies its distribution.

A pre-build image is also available on Docker Hub (auto build of latest code revision on GitHub):

* https://hub.docker.com/r/mpeuster/containernet/

To run the Containernet Docker image:

* `docker run -ti --rm=true --net=host --pid=host --privileged=true -v '/var/run/docker.sock:/var/run/docker.sock' mpeuster/containernet`

To build the Containernet Docker image:

* `docker build -t containernet .`



### Credits
Containernet (c) 2015 by Manuel Peuster

* Inspired by: http://techandtrains.com/2014/08/21/docker-container-as-mininet-host/


### Contact
Manuel Peuster
manuel (dot) peuster (at) upb (dot) de