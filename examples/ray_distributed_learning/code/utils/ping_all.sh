#!/bin/sh
# This script waits until all ip addresses given as cli args are reachable

for ip in "$@"
do
    until ping -c1 -W1 "$ip"
    do
        sleep 1
    done
done
