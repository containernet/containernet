#! /bin/bash -e

service openvswitch-switch start

if [ ! -S /var/run/docker.sock ]; then
    echo 'Error: the Docker socket file "/var/run/docker.sock" was not found. It should be mounted as a volume.'
    exit 1
fi

# this cannot be done from the Dockerfile since we have the socket not mounted during build
echo 'Pulling the "ubuntu:trusty" image ... please wait'
docker pull 'ubuntu:trusty'

echo "Welcome to Containernet running within a Docker container ..."

if [[ $# -eq 0 ]]; then
    exec /bin/bash
else
    exec $*
fi
