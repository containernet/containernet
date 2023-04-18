#!/bin/bash
# This script is used to deactivate the default network interface and configure the IP address
# for the specified interface, so that Ray uses the correct interface for communication.

# Get the hostname of the current machine
HOST=$(hostname)

# Get the IP address of the specified interface (in this case, HOST-eth0)
IP=$(ip -f inet addr show $HOST-eth0 | awk '/inet / {print $2}' | cut -d'/' -f1)

# Update the /etc/hosts file with the correct IP address and hostname
ex -sc "%s/.*$HOST/$IP\t$HOST/g" -cx /etc/hosts

# Deactivate the default eth0 interface
ifconfig eth0 down

