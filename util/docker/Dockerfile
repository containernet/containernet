FROM ubuntu:xenial

# install required packages
RUN apt-get clean
RUN apt-get update \
    && apt-get install -y  git \
    net-tools \
    aptitude \
    build-essential \
    python-setuptools \
    python-dev \
    python-pip \
    software-properties-common \
    ansible \
    curl \
    iptables \
    iputils-ping \
    sudo

# install containernet (using its Ansible playbook)
COPY . /containernet
WORKDIR /containernet/ansible
RUN ansible-playbook -i "localhost," -c local --skip-tags "notindocker" install.yml
WORKDIR /containernet
RUN python setup.py develop

# Important: This entrypoint is required to start the OVS service
ENTRYPOINT ["util/docker/entrypoint.sh"]
CMD ["python", "examples/containernet_example.py"]

