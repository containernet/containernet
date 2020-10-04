# Containernet

[![Build Status](https://travis-ci.org/containernet/containernet.svg?branch=master)](https://travis-ci.org/containernet/containernet)

## Containernet: Mininet fork that allows to use Docker containers as hosts in emulated networks

<img align="left" width="200" height="200" style="margin-right: 30px" src="https://raw.githubusercontent.com/containernet/logo/master/containernet_logo_v1.png">

Containernet is a fork of the famous [Mininet](http://mininet.org) network emulator and allows to use [Docker](https://www.docker.com) containers as hosts in emulated network topologies. This enables interesting functionalities to build networking/cloud emulators and testbeds. One example for this is the [NFV multi-PoP infrastructure emulator](https://github.com/sonata-nfv/son-emu) which was created by the [SONATA-NFV](http://sonata-nfv.eu) project and is now part of the [OpenSource MANO (OSM)](https://osm.etsi.org) project. Besides this, Containernet is actively used by the research community, focussing on experiments in the field of cloud computing, fog computing, network function virtualization (NFV), and multi-access edge computing (MEC).

Based on: **Mininet 2.3.0d5**

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
## NFV multi-PoP Extension: `vim-emu`

There is an extension of Containernet called [vim-emu](https://github.com/containernet/vim-emu) which is a full-featured multi-PoP emulation platform for NFV scenarios. Vim-emu was developed as part of the [SONATA-NFV](http://www.sonata-nfv.eu) project and is now hosted by the [OpenSource MANO project](https://osm.etsi.org/).

---
## Features

* Add, remove Docker containers to Mininet topologies
* Connect Docker containers to topology (to switches, other containers, or legacy Mininet hosts)
* Execute commands inside containers by using the Mininet CLI
* Dynamic topology changes
   * Add hosts/containers to a *running* Mininet topology
   * Connect hosts/docker containers to a *running* Mininet topology
   * Remove Hosts/Docker containers/links from a *running* Mininet topology
* Resource limitation of Docker containers
   * CPU limitation with Docker CPU share option
   * CPU limitation with Docker CFS period/quota options
   * Memory/swap limitation
   * Change CPU/mem limitations at runtime!
* Expose container ports and set environment variables of containers through Python API
* Traffic control links (delay, bw, loss, jitter)
* Automated installation based on Ansible playbook

---
## Installation

Containernet comes with two installation and deployment options.

### Option 1: Bare-metal installation

Automatic installation is provided through an Ansible playbook.

Requires: **Ubuntu Linux 18.04 LTS** and **Python3**
Experimental: **Ubuntu Linux 20.04 LTS** and **Python3**

```bash
$ sudo apt-get install ansible git aptitude
$ git clone https://github.com/containernet/containernet.git
$ cd containernet/ansible
$ sudo ansible-playbook -i "localhost," -c local install.yml
$ cd ..
```
    
Wait (and have a coffee) ...

You can switch between development (default) and normal installation as follows:

```sh
sudo make develop
# or 
sudo make install
```

### Option 2: Nested Docker deployment

Containernet can be executed within a privileged Docker container (nested container deployment). There is also a pre-build Docker image available on [Docker Hub](https://hub.docker.com/r/containernet/containernet/).

*Attention:* Container resource limitations, e.g., CPU share limits, are not supported in the nested container deployment. Use bare-metal installations if you need those features.

#### Build/Pull

```bash
# build the container locally
$ docker build -t containernet/containernet .

# or pull the latest pre-build container
$ docker pull containernet/containernet
```

#### Run

```bash
# run interactive container and directly start containernet example
$ docker run --name containernet -it --rm --privileged --pid='host' -v /var/run/docker.sock:/var/run/docker.sock containernet/containernet

# run interactive container and drop to shell
$ docker run --name containernet -it --rm --privileged --pid='host' -v /var/run/docker.sock:/var/run/docker.sock containernet/containernet /bin/bash
```

---
## Examples

### Usage example (using bare-metal installation)

Start example topology with some empty Docker containers connected to the network.

* run: `sudo python3 examples/containernet_example.py`
* use: `containernet> d1 ifconfig` to see config of container `d1`
* use: `containernet> d1 ping -c4 d2` to ping between containers

### Topology example

In your custom topology script you can add Docker hosts as follows:

```python
info('*** Adding docker containers\n')
d1 = net.addDocker('d1', ip='10.0.0.251', dimage="ubuntu:trusty")
d2 = net.addDocker('d2', ip='10.0.0.252', dimage="ubuntu:trusty", cpu_period=50000, cpu_quota=25000)
d3 = net.addHost('d3', ip='11.0.0.253', cls=Docker, dimage="ubuntu:trusty", cpu_shares=20)
d4 = net.addDocker('d4', dimage="ubuntu:trusty", volumes=["/:/mnt/vol1:rw"])
```

---
## Tests

```sh
sudo make test
```

---
## Documentation

Containernet's [documentation](https://github.com/containernet/containernet/wiki) can be found in the [GitHub wiki](https://github.com/containernet/containernet/wiki). The documentation for the underlying Mininet project can be found [here](http://mininet.org/).

---
## Contact

### Support

If you have any questions, please use GitHub's [issue system](https://github.com/containernet/containernet/issues) or to get in touch.

### Contribute

Your contributions are very welcome! Please fork the GitHub repository and create a pull request. We use [Travis-CI](https://travis-ci.org/containernet/containernet) to automatically test new commits.

### Lead developer

Manuel Peuster
* Mail: <manuel (at) peuster (dot) de>
* Twitter: [@ManuelPeuster](https://twitter.com/ManuelPeuster)
* GitHub: [@mpeuster](https://github.com/mpeuster)
* Website: [https://peuster.de](https://peuster.de)
