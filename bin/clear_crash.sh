#!/bin/bash

sudo pkill python
sudo docker rm -f $(sudo docker ps -a -q)
sudo ./mn -c