# Containernet

<img align="left" width="200" height="200" style="margin: 30px 30px 0 0;" src="/assets/logo.png" />

Containernet is a fork of the famous [Mininet](http://mininet.org) network emulator and allows to use [Docker](https://www.docker.com) containers as hosts in emulated network topologies. This enables interesting functionalities to build networking/cloud emulators and testbeds. Containernet is actively used by the research community, focussing on experiments in the field of cloud computing, fog computing, network function virtualization (NFV) and multi-access edge computing (MEC). One example for this is the [NFV multi-PoP infrastructure emulator](https://github.com/sonata-nfv/son-emu) which was created by the SONATA-NFV project and is now part of the [OpenSource MANO (OSM)](https://osm.etsi.org) project.

## Features

- Add, remove Docker containers to Mininet topologies
- Connect Docker containers to topology (to switches, other containers, or legacy Mininet hosts)
- Execute commands inside containers by using the Mininet CLI
- Dynamic topology changes
  - Add hosts/containers to a _running_ Mininet topology
  - Connect hosts/docker containers to a _running_ Mininet topology
  - Remove Hosts/Docker containers/links from a _running_ Mininet topology
- Resource limitation of Docker containers
  - CPU limitation with Docker CPU share option
  - CPU limitation with Docker CFS period/quota options
  - Memory/swap limitation
  - Change CPU/mem limitations at runtime!
- Expose container ports and set environment variables of containers through Python API
- Traffic control links (delay, bw, loss, jitter)
- Automated installation based on Ansible playbook

## Installation

Containernet comes with two installation and deployment options.

### Option 1: Bare-metal installation

This option is the most flexible. Your machine should run Ubuntu **20.04 LTS** and **Python3**.

First install Ansible:

```bash
sudo apt-get install ansible
```

Then clone the repository:

```bash
git clone https://github.com/containernet/containernet.git
```

Finally run the Ansible playbook to install required dependencies:

```bash
sudo ansible-playbook -i "localhost," -c local containernet/ansible/install.yml
```

After the installation finishes, you should be able to [get started](#get-started).

### Option 2: Nested Docker deployment

Containernet can be executed within a privileged Docker container (nested container deployment). There is also a pre-build Docker image available on [Docker Hub](https://hub.docker.com/r/containernet/containernet/).

**Attention:** Container resource limitations, e.g. CPU share limits, are not supported in the nested container deployment. Use bare-metal installations if you need those features.

You can build the container locally:

```bash
docker build -t containernet/containernet .
```

or alternatively pull the latest pre-build container:

```bash
docker pull containernet/containernet
```

You can then directly start the default containernet example:

```bash
docker run --name containernet -it --rm --privileged --pid='host' -v /var/run/docker.sock:/var/run/docker.sock containernet/containernet
```

or run an interactive container and drop to the shell:

```bash
docker run --name containernet -it --rm --privileged --pid='host' -v /var/run/docker.sock:/var/run/docker.sock containernet/containernet /bin/bash
```

## Get started

Using Containernet is very similar to using Mininet.

### Running a basic example

Make sure you are in the `containernet` directory. You can start an example topology with some empty Docker containers connected to the network:

```bash
sudo python3 examples/containernet_example.py
```

After launching the emulated network, you can interact with the involved containers through Mininet's interactive CLI. You can for example:

- use `containernet> d1 ifconfig` to see the config of container `d1`
- use `containernet> d1 ping -c4 d2` to ping between containers

You can exit the CLI using `containernet> exit`.

### Running a client-server example

Let's simulate a webserver and a client making requests. For that, we need a server and client image.
First, change into the `containernet/examples` directory.

Containernet already provides a simple Python server for testing purposes. To build the server image, just run

```bash
docker build -f example-containers/webserver_curl/Dockerfile.server -t test_server:latest example-containers/webserver_curl/
```

We further need a basic client to make a CURL request. Containernet provides that as well. Please run

```bash
docker build -f example-containers/Dockerfile.curl -t test_client:latest example-containers/
```

Now that we have a server and client image, we can create hosts using them. You can either checkout the topology
script `containernet_example_server_client.py` first or run it directly:

```bash
sudo python3 containernet_example_server_curl.py
```

### Customizing topologies

You can also add hosts with resource restrictions or mounted volumes:

```python
# ...

d1 = net.addDocker('d1', ip='10.0.0.251', dimage="ubuntu:trusty")
d2 = net.addDocker('d2', ip='10.0.0.252', dimage="ubuntu:trusty", cpu_period=50000, cpu_quota=25000)
d3 = net.addHost('d3', ip='11.0.0.253', cls=Docker, dimage="ubuntu:trusty", cpu_shares=20)
d4 = net.addDocker('d4', dimage="ubuntu:trusty", volumes=["/:/mnt/vol1:rw"])

# ...
```

## Documentation

Containernet's documentation can be found in the [GitHub wiki](https://github.com/containernet/containernet/wiki). The documentation for the underlying Mininet project can be found on the [Mininet website](http://mininet.org/).

## Research

Containernet has been used for a variety of research tasks and networking projects. If you use Containernet, let us know!

### Cite this work

If you use Containernet for your work, please cite the following publication:

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

### Publications

- M. Peuster, H. Karl, and S. v. Rossem: [MeDICINE: Rapid Prototyping of Production-Ready Network Services in Multi-PoP Environments](http://ieeexplore.ieee.org/document/7919490/). IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN), Palo Alto, CA, USA, pp. 148-153. doi: 10.1109/NFV-SDN.2016.7919490. IEEE. (2016)

- S. v. Rossem, W. Tavernier, M. Peuster, D. Colle, M. Pickavet and P. Demeester: [Monitoring and debugging using an SDK for NFV-powered telecom applications](https://biblio.ugent.be/publication/8521281/file/8521284.pdf). IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN), Palo Alto, CA, USA, Demo Session. IEEE. (2016)

- Qiao, Yuansong, et al. [Doopnet: An emulator for network performance analysis of Hadoop clusters using Docker and Mininet.](http://ieeexplore.ieee.org/document/7543832/) Computers and Communication (ISCC), 2016 IEEE Symposium on. IEEE. (2016)

- M. Peuster, S. Dräxler, H. Razzaghi, S. v. Rossem, W. Tavernier and H. Karl: [A Flexible Multi-PoP Infrastructure Emulator for Carrier-grade MANO Systems](https://cs.uni-paderborn.de/fileadmin/informatik/fg/cn/Publications_Conference_Paper/Publications_Conference_Paper_2017/peuster_netsoft_demo_paper_2017.pdf). In IEEE 3rd Conference on Network Softwarization (NetSoft) Demo Track . (2017) **Best demo award!**

- M. Peuster and H. Karl: [Profile Your Chains, Not Functions: Automated Network Service Profiling in DevOps Environments](http://ieeexplore.ieee.org/document/8169826/). IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN), Berlin, Germany. IEEE. (2017)

- M. Peuster, H. Küttner and H. Karl: [Let the state follow its flows: An SDN-based flow handover protocol to support state migration](https://ris.uni-paderborn.de/publication/3345). In IEEE 4th Conference on Network Softwarization (NetSoft). IEEE. (2018) **Best student paper award!**

- M. Peuster, J. Kampmeyer and H. Karl: [Containernet 2.0: A Rapid Prototyping Platform for Hybrid Service Function Chains](https://ris.uni-paderborn.de/publication/3346). In IEEE 4th Conference on Network Softwarization (NetSoft) Demo, Montreal, Canada. (2018)

- M. Peuster, M. Marchetti, G. García de Blas, H. Karl: [Emulation-based Smoke Testing of NFV Orchestrators in Large Multi-PoP Environments](https://ris.uni-paderborn.de/publication/3347). In IEEE European Conference on Networks and Communications (EuCNC), Lubljana, Slovenia. (2018)

- S. Schneider, M. Peuster,Wouter Tvernier and H. Karl: [A Fully Integrated Multi-Platform NFV SDK](https://ris.uni-paderborn.de/record/6974). In IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN) Demo, Verona, Italy. (2018)

- M. Peuster, S. Schneider, Frederic Christ and H. Karl: [A Prototyping Platform to Validate and Verify Network Service Header-based Service Chains](https://ris.uni-paderborn.de/record/6483). In IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN) 5GNetApp, Verona, Italy. (2018)

- S. Schneider, M. Peuster and H. Karl: [A Generic Emulation Framework for Reusing and Evaluating VNF Placement Algorithms](https://ris.uni-paderborn.de/record/6972). In IEEE Conference on Network Function Virtualization and Software Defined Networks (NFV-SDN), Verona, Italy. (2018)

- M. Peuster, S. Schneider, D. Behnke, M. Müller, P-B. Bök, and H. Karl: [Prototyping and Demonstrating 5G Verticals: The Smart Manufacturing Case](https://ris.uni-paderborn.de/record/8792). In IEEE 5th Conference on Network Softwarization (NetSoft) Demo, Paris, France. (2019)

- M. Peuster, M. Marchetti, G. Garcia de Blas, Holger Karl: [Automated testing of NFV orchestrators against carrier-grade multi-PoP scenarios using emulation-based smoke testing](https://ris.uni-paderborn.de/record/10325). In EURASIP Journal on Wireless Communications and Networking (2019)

## Other projects and links

There is an extension of Containernet called [vim-emu](https://github.com/containernet/vim-emu) which is a full-featured multi-PoP emulation platform for NFV scenarios. Vim-emu was developed as part of the [SONATA-NFV](http://www.sonata-nfv.eu) project and is now hosted by the [OpenSource MANO project](https://osm.etsi.org/):

<p align="center">
    <a href="https://osm.etsi.org/wikipub/index.php/Research" target="_blank">
        <img align="center" width="200" src="/assets/osm_ecosystem_research.png">
    </a>
</p>

For running Mininet or Containernet distributed in a cluster, checkout [Maxinet](http://maxinet.github.io).

You can also find an alternative/teaching-focused approach for Container-based Network Emulation by TU Dresden in [their repository](https://git.comnets.net/public-repo/comnetsemu).

## Contact

### Support

If you have any questions, please use GitHub's [issue system](https://github.com/containernet/containernet/issues).

### Contribute

Your contributions are very welcome! Please fork the GitHub repository and create a pull request.

Please make sure to test your code using

```bash
sudo make test
```

### Lead developer

Manuel Peuster

- Mail: <manuel (at) peuster (dot) de>
- Twitter: [@ManuelPeuster](https://twitter.com/ManuelPeuster)
- GitHub: [@mpeuster](https://github.com/mpeuster)
- Website: [https://peuster.de](https://peuster.de)
