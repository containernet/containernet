#! /bin/bash -e

service openvswitch-switch start

if [ ! -S /var/run/docker.sock ]; then
    echo 'Error: the Docker socket file "/var/run/docker.sock" was not found. It should be mounted as a volume.'
    exit 1
fi
echo 'Pulling the "ubuntu:latest" image ... please wait'
docker pull 'ubuntu:latest'

if [[ $# -eq 0 ]]; then
    exec /bin/bash
else
    $*
fi
