#!/bin/bash

sudo docker rm -f $(sudo docker ps --filter 'label=com.containernet' -a -q)
sudo ./mn -c