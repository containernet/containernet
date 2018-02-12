#! /bin/bash -e

# start OVS
/usr/share/openvswitch/scripts/ovs-ctl start --system-id=random

# check if docker socket is mounted
if [ ! -S /var/run/docker.sock ]; then
    echo 'Error: the Docker socket file "/var/run/docker.sock" was not found. It should be mounted as a volume.'
    exit 1
fi

# this cannot be done from the Dockerfile since we have the socket not mounted during build
set +e
echo 'Pulling the "centos:7" image for later use...'
docker pull 'centos:7'
set -e

echo "Welcome to Containernet running within a Docker container ..."

if [[ $# -eq 0 ]]; then
    exec /bin/bash
else
    exec $*
fi
