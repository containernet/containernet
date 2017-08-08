#!/bin/bash

sudo docker rm -f $(sudo docker ps --filter 'label=com.containernet' -a -q)
for domain in $(sudo virsh list --name | grep "^mn\.")
do
    sudo virsh destroy $domain
done
sudo virsh net-destroy mn.libvirt.mgmt
sudo mn -c
