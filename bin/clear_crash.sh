#!/bin/bash

sudo docker rm -f $(sudo docker ps --filter 'label=com.dockernet' -a -q)
sudo ./mn -c