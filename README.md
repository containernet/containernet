Containernet
============

[![Join the chat at https://gitter.im/mpeuster/containernet](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/mpeuster/containernet?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![Build Status](https://travis-ci.org/containernet/containernet.svg?branch=master)](https://travis-ci.org/containernet/containernet)

**Attention:** This repository was moved to an own account: https://github.com/containernet/containernet

### Containernet: Mininet fork that allows to use Docker containers as hosts in emulated networks

This fork of Mininet allows to use Docker containers as Mininet hosts. This enables interesting functionalities to built networking/cloud testbeds. The integration is done by subclassing the original Host class.

Based on: Mininet 2.2.1

* Mininet:  http://mininet.org
* Original Mininet repository: https://github.com/mininet/mininet

### Cite this work

If you use Containernet for your research and/or other publications, please cite the following paper to reference our work:

* Manuel Peuster, Holger Karl, and Steven van Rossem. "**MeDICINE: Rapid Prototyping of Production-Ready Network Services in Multi-PoP Environments.**" to appear in IEEE Conference on Network Function Virtualization and Software Defined Network (NFV-SDN), 2016.
  * Pre-print online: http://arxiv.org/abs/1606.05995

### NFV multi-PoP Extension

There is an extension of Containernet called MeDICINE which is a full-featured multi-PoP emulation platform for NFV scenarios which is developed as part of the SONATA project.

* MeDICINE platform repository: https://github.com/sonata-nfv/son-emu
* SONATA project: http://www.sonata-nfv.eu

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
 * Change CPU/mem limitations at runtime!
* Traffic control links (delay, bw, loss, jitter)
 * (missing: TCLink support for dynamically added containers/hosts)
* Automated unit tests for all new features
* Automated installation based on Ansible playbook

### Installation
Automatic installation is provide through an Ansible playbook.
* Requires: Ubuntu **14.04 LTS**
* `sudo apt-get update`
* `sudo apt-get upgrade`
* `sudo apt-get install ansible git aptitude`
* `sudo vim /etc/ansible/hosts`
* Add: `localhost ansible_connection=local`
* `git clone https://github.com/containernet/containernet.git`
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

* `sudo py.test -v mininet/test/test_containernet.py`

### Vagrant support

Using the provided Vagrantfile is the most simple way to run and test Containernet:

```
git clone https://github.com/containernet/containernet.git
cd containernet
vagrant up
vagrant ssh
```

### Credits
Containernet (c) 2015 by Manuel Peuster

* Inspired by: http://techandtrains.com/2014/08/21/docker-container-as-mininet-host/


### Contact
Manuel Peuster
manuel (dot) peuster (at) upb (dot) de

