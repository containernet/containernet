#! /bin/bash -e

service openvswitch-switch start

if [[ $# -eq 0 ]]; then
    exec /bin/bash
else
    $*
fi
