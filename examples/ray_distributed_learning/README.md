# Distributed Learning with Ray in Containernet

This folder contains code and examples for executing distributed Machine Learning (ML) and Deep Learning (DL) workloads using Containernet and Ray. The primary objective is to emulate the training process in a local environment, thereby facilitating predictions about performance in real-world network environments with physical servers.

## Table of Contents

- [Dependencies and Installation](#dependencies-and-installation)
- [Usage](#usage)

## Dependencies and Installation

### Containernet

- Install Containernet
- On some systems, there are issues with the systemd cgroup driver.

    ```bash
    sudo systemctl edit --full docker.service
    ```

    ```bash
    # Append the following line to ExecStart=
    --exec-opt native.cgroupdriver=cgroupfs
    ```

    ```bash
    # Apply configuration and restart Docker
    sudo systemctl daemon-reload
    sudo systemctl restart docker.service
    ```

### Nvidia Container Toolkit

- If you plan to use GPUs to accelerate your distributed learning scenario, you need to install the [Nvidia Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#setting-up-nvidia-container-toolkit). For Debian-based systems like Ubuntu, you can use apt:

    ```bash
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID) && \
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    ```

    ```bash
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    ```

### Dockerfile

Build the container with

```bash
docker build -t ray .
```

If you want to use GPUs, you need to build the container using the GPU Dockerfile

```bash
docker build -t ray:gpu -f Dockerfile.gpu .
```

### Multi-Instance GPUs

- Some Nvidia GPUs have the ability to split themselves into multiple GPU instances. This can be useful if you want to assign a separate GPU to each container, but have less GPUs than containers. Information on how to create GPU instances can be found in `nvidia-smi mig --help` or the [nvidia blogpost](https://developer.nvidia.com/blog/getting-the-most-out-of-the-a100-gpu-with-multi-instance-gpu/). If you want to automatically switch to a MIG setup, you can use the `setup-mig.sh` script in this folder:

The available options for the script are:

- `-h`, `--help`: Show the help message and exit
- `-n`, `--num-gpus`: Specify the number of GPUs in your system. Default: 1

For example, to create six instances of different sizes, spanning two GPUs, use the following command:

```bash
sudo ./setup-mig.sh --num-gpus 2 0:1g.5gb 0:2g.10gb 0:4g.20gb 1:1g.5gb 1:2g.10gb 1:4g.20gb
```

To remove the current configuration, use:

```bash
sudo ./setup-mig.sh --num-gpus <Number of GPUs in your system>
```

## Usage

### Setup

Run the `ray_training.py` script with the appropriate options using the following command:

```bash
sudo python3 ray_training.py [options]
```

The available options for the script are:

- `-h`, `--help`: Show the help message and exit.
- `--data-dir DATA_DIR`: Specify the host directory for the data folder. Defaults to `/home/user/data`
- `--results-dir RESULTS_DIR`: Specify the host directory for the results folder. Defaults to `/home/user/results`
- `--num-nodes NUM_NODES`: Set the number of nodes, including the head node.
- `--delay DELAY`: Define the delay between nodes in milliseconds.
- `--image IMAGE`: Define the docker image used. Is `ray` by default
- `--cpus-per-node NUM_CPUS`: Set the number of CPUs of each node. Is 1 by default. If you don't plan to use a GPU, we strongly recommend increasing this.
- `--gpu-instances INSTANCE INSTANCE ...`: Specify the GPU UUIDs, if you want to attach GPUs to the containers. If this is specified, it has to contain exactly `NUM_NODES` UUIDs. The first UUID is assigned to the head node. You can specify a UUID multiple times. To find the UUID(s) on your system, use `nvidia-smi -L`. If you have exactly NUM_NODES number of GPUs in your system, you can use `$(nvidia-smi -L | grep -Eo "GPU-[0-9a-f\-]+" | tr "\n" " ")` as the value of this flag

For example, to run the script with 16 CPUs assigned to each container with a data directory of `/root/data`, a results directory of `/root/results`, 3 nodes, and a delay of 10 milliseconds between all nodes, use the following command:

```bash
sudo python3 ray_training.py --data-dir /root/data --results-dir /root/results --num-nodes 3 --delay 10 --cpus-per-node 16
```

A similar setup using GPUs might look like this

```bash
sudo python3 ray_training.py --data-dir /root/data --results-dir /root/results --num-nodes 3 --delay 10 --gpu-instances GPU-38f8fa35-6e28-024a-aa8d-893ad0020924 GPU-38f8fa35-6e28-024a-aa8d-893ad0020924 GPU-3ffbb989-4b31-b7f7-939b-608b48b920a8
```

### Run Experiments

After the environment is started, the experiments can be started using the `train.py` script.

```bash
head python train.py [options]
```

The available options for the script are:

- `--address`: The address to use for Ray (default: None).
- `--num-workers` or `-n`: Sets the number of workers for training (default: 3).
- `--epochs`: Set the number of epochs for training (default: 3).
- `--lr`: Set the learning rate (default: 0.01).
- `--batch-size`: Set the batch size for training (default: 64).
- `--model`: The model to use for training and inference (required).
- `--use-gpu`: Enables GPU training. Make sure that you have specified `--gpu-instances` when creating the network.
- `--dataset`: Set the dataset to use, with available choices: `mnist`, `fashion_mnist`, `cifar100` (default: "mnist").
- `--algorithm`: Set the distributed training algorithm (required), with available choices: `ps_sync`, `ps_async`. The parameter server will always be assigned to the ray head node, and the workers will be assigned to ray workers.

For example, to run the script with 3 workers, 50 iterations, a learning rate of 0.02, the "lenet" model, GPU training enabled, the "mnist" dataset, and the synchronous parameter server algorithm, use the following command:

```bash
head python train.py --num-workers 3 --iter 50 --lr 0.02 --model lenet --use-gpu --dataset mnist --algorithm ps_sync
```

This will create one parameter server and two workers.

You can also open the Ray dashboard in your browser at `http://localhost:8265` to monitor the training process.