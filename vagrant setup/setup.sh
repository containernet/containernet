#!/bin/bash
sudo apt-get update
sudo curl -sS https://get.docker.com | sh
sudo apt-get install -y git \
    aptitude \
    apt-transport-https \
    ca-certificates \
    curl \
    python-setuptools \
    python-dev \
    build-essential \
    python-pip \
    iptables \
    software-properties-common
pip install pytest
pip install docker
pip install python-iptable
# Cloning of the repo
git clone https://github.com/containernet/containernet
#Installation
sudo bash containernet/util/install.sh
cd containernet
sudo make develop
#Pulling docker images
sudo docker pull ubuntu:trusty
sudo docker pull ubuntu:xenial
#Test
sudo python examples/containernet_example.py
