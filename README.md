# Containernet

[![Join the chat at https://gitter.im/containernet/Lobby](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/containernet/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![Build Status](https://travis-ci.org/containernet/containernet.svg?branch=master)](https://travis-ci.org/containernet/containernet)

## Containernet: Mininet fork that allows to use Docker containers as hosts in emulated networks

This fork of Mininet allows to use Docker containers as Mininet hosts. This enables interesting functionalities to built networking/cloud testbeds. The integration is done by subclassing the original Host class.

Based on: **Mininet 2.2.1**

* Containernet website: https://containernet.github.io/
* Mininet website:  http://mininet.org
* Original Mininet repository: https://github.com/mininet/mininet

---
## Cite this work

If you use Containernet for your research and/or other publications, please cite (beside the original Mininet paper) the following paper to reference our work:

M. Peuster, H. Karl, and S. v. Rossem: [**MeDICINE: Rapid Prototyping of Production-Ready Network Services in Multi-PoP Environments**](http://ieeexplore.ieee.org/document/7919490/). IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN), Palo Alto, CA, USA, pp. 148-153. doi: 10.1109/NFV-SDN.2016.7919490. (2016)

Bibtex:

```bibtex
@inproceedings{peuster2016medicine, 
    author={M. Peuster and H. Karl and S. van Rossem}, 
    booktitle={2016 IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN)}, 
    title={MeDICINE: Rapid prototyping of production-ready network services in multi-PoP environments}, 
    year={2016}, 
    volume={}, 
    number={}, 
    pages={148-153}, 
    doi={10.1109/NFV-SDN.2016.7919490},
    month={Nov}
}
```

---
## NFV multi-PoP Extension

There is an extension of Containernet called [son-emu](https://github.com/sonata-nfv/son-emu) which is a full-featured multi-PoP emulation platform for NFV scenarios which is developed as part of the [SONATA](http://www.sonata-nfv.eu) project.

---
## Features

* Add, remove Docker containers to Mininet topologies
* Connect Docker containers to topology (to switches, other containers, or legacy Mininet hosts)
* Execute commands inside Docker containers by using the Mininet CLI
* Dynamic topology changes (lets behave like a small cloud ;-))
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

---
## Installation

Containernet comes with three installation and deployment options.

### Option 1: Bare-metal installation

Automatic installation is provided through an Ansible playbook.
* Requires: **Ubuntu Linux 16.04 LTS**
    ```bash
    $ sudo apt-get install ansible git aptitude
    $ git clone https://github.com/containernet/containernet.git
    $ cd containernet/ansible
    $ sudo ansible-playbook -i "localhost," -c local install.yml
    $ cd ..
    $ sudo python setup.py install
    ```
    Wait (and have a coffee) ...

### Option 2: Nested Docker deployment

Containernet can be executed within a privileged Docker container (nested container deployment). There is also a pre-build Docker image available on [Docker Hub](https://hub.docker.com/r/containernet/containernet/).

```bash
# build the container locally
$ docker build -t containernet .
```

```bash
# or pull the latest pre-build container
$ docker pull containernet/containernet
```

```bash
# run the container
$ docker run --name containernet -it --rm --privileged --pid='host' -v /var/run/docker.sock:/var/run/docker.sock containernet/containernet /bin/bash
```

### Option 3: Vagrant-based VM creation

#### There are to diffrent ways to use Vagrant.

#### 1. in the Containernet directory

If you run the following commands in the cloned repository.
```bash
$ vagrant up
$ vagrant ssh
```
You will get a VM that has the full directory structure sync with `/home/ubuntu/containernet`. If you want to contribute to the Containernet project. This is probably what you want.

#### 2. in a seprate directory

If you want to use Containernet as a dependancy in your own project. You can use:
```bash
$ curl https://raw.githubusercontent.com/containernet/containernet/master/StandaloneVagrantfile -o Vagrantfile
```
to download the `StandaloneVagrantfile`, which is automatically renamed to `Vagrantfile` by the curl command. This `Vagrantfile` will download all nessarry parts needed to get up and running. This means your project structure stays slim.

To start the VM just run
```bash
$ vagrant up
```
After the VM has started, you can use the following command to login as `root`.
```bash
$ vagrant ssh
```
This is needed because mininet needs full access. If you use PyCharm Professional you can use the created VM as a remote interpreter.

### Usage / Run

Start example topology with some empty Docker containers connected to the network.

* `cd containernet`
* run: `sudo python examples/containernet_example.py`
* use: `containernet> d1 ifconfig` to see config of container `d1`

### Topology example

In your custom topology script you can add Docker hosts as follows:

```python
info('*** Adding docker containers\n')
d1 = net.addDocker('d1', ip='10.0.0.251', dimage="ubuntu:trusty")
d2 = net.addDocker('d2', ip='10.0.0.252', dimage="ubuntu:trusty", cpu_period=50000, cpu_quota=25000)
d3 = net.addHost('d3', ip='11.0.0.253', cls=Docker, dimage="ubuntu:trusty", cpu_shares=20)
d4 = net.addDocker('d4', dimage="ubuntu:trusty", volumes=["/:/mnt/vol1:rw"])
```

### Tests

There is a set of Containernet specific unit tests located in `mininet/test/test_containernet.py`. To run these, do:

* `sudo py.test -v mininet/test/test_containernet.py`

---
## Contact

### Support

If you have any questions, please use GitHub's [issue system](https://github.com/containernet/containernet/issues) or Containernet's [Gitter channel](https://gitter.im/containernet/) to get in touch.

### Contribute

Your contributions are very welcome! Please fork the GitHub repository and create a pull request. We use [Travis-CI](https://travis-ci.org/containernet/containernet) to automatically test new commits.

### Lead developer

Manuel Peuster
* Mail: <manuel (dot) peuster (at) upb (dot) de>
* GitHub: [@mpeuster](https://github.com/mpeuster)
* Website: [Paderborn University](https://cs.uni-paderborn.de/cn/person/?tx_upbperson_personsite%5BpersonId%5D=13271&tx_upbperson_personsite%5Bcontroller%5D=Person&cHash=bafec92c0ada0bdfe8af6e2ed99efb4e)
