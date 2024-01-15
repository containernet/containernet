#!/bin/bash
# Script to create a Multi-Instance GPU layout. Read the README.md for more information.

USAGE_STRING="Usage: $(basename $0) [-h/--help] [-n/--num-gpus num gpus] gpu_id:profile ..."
# default value
NUM_GPUS="1"

# Parse cli args
VALID_ARGS=$(getopt -o "hn:" --longoptions "help,num-gpus:" -- "$@")
if [[ $? -ne 0 ]]
then
    exit 1
fi
eval set -- "$VALID_ARGS"

while [ : ]
do
    case "$1" in
        -h | --help)
            echo -e "Setup a specific mig configuration. This will overwrite any current configuration\n$USAGE_STRING\nExample: $(basename $0) -n 2 0:1g.10gb 0:3g.20gb 1:4g.20gb will create a 1g.10gb and a 3g.20gb instance on gpu 0 and a 4g.20gb instance on gpu 1"
            exit 0
            ;;
        -n | --num-gpus)
            if [ -z "$2" ] || ! [[ "$2" =~ ^[0-9]+$ ]]
            then
                echo -e "$2 is not a valid number of GPUs\n$USAGE_STRING"
                exit 1
            fi
            NUM_GPUS="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo -e "Unknown positional argument $1\n$USAGE_STRING"
            shift
            ;;
    esac
done

# Clear current mig setup
for gpu in $(seq 0 $((NUM_GPUS-1)))
do
    for gi in $(nvidia-smi mig -i "$gpu" -lgi | grep "^|" | grep "===" -A 999 | tail -n+2 | tr -s " " | cut -d" " -f 6 | tr "\n" " ")
    do
        for ci in $(nvidia-smi mig -i "$gpu" -gi "$gi" -lci | grep "^|" | grep "===" -A 999 | tail -n+2 | tr -s " " | cut -d" " -f 7 | tr "\n" " ")
        do
            nvidia-smi mig -i "$gpu" -gi "$gi" -ci "$ci" -dci
        done

        nvidia-smi mig -i "$gpu" -gi "$gi" -dgi
    done
done

# Create gpu instances
while ! [[ -z "$1" ]]
do
    gpu=${1%:*}
    profile=${1#*:}

    if [ -z "$gpu" -o -z "$profile" ]
    then
        echo "unable to split $1 at a :"
        shift
        continue
    fi
    if [ "$gpu" -lt 0 -o "$gpu" -ge "$NUM_GPUS" ]
    then
        echo "$gpu in argument $1 should be in range [0, NUM_GPUS)"
        shift
        continue
    fi

    gip=$(nvidia-smi mig -i "$gpu" -lgip | grep "MIG $profile " | tr -s " " | cut -d" " -f 5)
    nvidia-smi mig -i "$gpu" -cgi "$gip"
    shift
done

# Create corresponding compute instances
for gpu in $(seq 0 $((NUM_GPUS-1)))
do
    for instance in $(nvidia-smi mig -i "$gpu" -lgi | grep "^|" | grep "===" -A 999 | tail -n+2 | tr -s " " | cut -d" " -f 4,6 | tr " " ":" | tr "\n" " ")
    do
        profile=${instance%:*}
        gi=${instance#*:}
        cip=$(nvidia-smi mig -i "$gpu" -gi "$gi" -lcip | grep "MIG $profile " | tr -s " " | cut -d" " -f 6 | tr -d "*")
        nvidia-smi mig -i "$gpu" -gi "$gi" -cci "$cip"
    done
done

nvidia-smi -L
