# Distributed Learning with Ray in Containernet

This folder contains code and examples for executing distributed Machine Learning (ML) and Deep Learning (DL) workloads using Containernet and Ray. The primary objective is to emulate the training process in a local environment, thereby facilitating predictions about performance in real-world network environments with physical servers.

## Table of Contents

- [Dependencies and Installation](#dependencies-and-installation)
- [Usage](#usage)

## Dependencies and Installation

### Containernet
* Install Containernet
* On some systems, there are issues with the systemd cgroup driver. 
	* ```bash
		sudo systemctl edit --full docker.service 
		```
	* ```bash
 		# Append the following line to ExecStart=
		--exec-opt native.cgroupdriver=cgroupfs
		```
	* Apply configuration and restart Docker
		```bash
		sudo systemctl daemon-reload
		sudo systemctl restart docker.service
		```

### Nvidia Container Toolkit
* Running the Containers with GPU support requires the [Nvidia Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#setting-up-nvidia-container-toolkit).
	* ```bash
		distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
		&& curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
		&& curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
			sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
			sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
		```
		```bash
			sudo apt-get update
			sudo apt-get install -y nvidia-container-toolkit
			sudo nvidia-ctk runtime configure --runtime=docker
			sudo systemctl restart docker
		```

### OpenMPI

* Install OpenMPI for testing the Allreduce Implementation on GPUs.
	* ```bash
		wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.5.tar.gz
		tar -xzf openmpi-4.1.5.tar.gz
		cd openmpi-4.1.5
		# Load the appropriate CUDA paths:
		export PATH=/usr/local/cuda/bin:$PATH
		export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
		# Configure and build OpenMPI with CUDA support:
		./configure --prefix=/usr/local --with-cuda
		make -j $(nproc)
		# Install OpenMPI:
		sudo make install
		# Update the dynamic linker cache and environment variables:
		sudo ldconfig
		echo "export PATH=/usr/local/bin:$PATH" >> ~/.bashrc
		echo "export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH" >> ~/.bashrc
		source ~/.bashrc
		# test CUDA-aware MPI (OpenMPI)
		ompi_info --parsable --all | grep mpi_built_with_cuda_support:value
		```

### Dockerfile
Build the dockerfile with
```bash
docker build -t ray:GPU .
```

## Usage

### Setup


Run the `ray_training.py` script with the appropriate options using the following command:
```bash
sudo python3 ray_training.py [options]
```

The available options for the script are:

- `-h`, `--help`: Show the help message and exit.
- `--data-dir DATA_DIR`: Specify the host directory for the data folder.
- `--results-dir RESULTS_DIR`: Specify the host directory for the results folder.
- `--num_nodes NUM_NODES`: Set the number of nodes, including the head node.
- `--delay DELAY`: Define the delay between nodes in milliseconds.

For example, to run the script with a data directory of `/root/data`, a results directory of `/root/results`, 5 nodes, and a delay of 10 milliseconds between all nodes, use the following command:
```bash
sudo python3 ray_training.py --data-dir /root/data --results-dir /root/results --num_nodes 5 --delay 10
```
`--data-dir` defaults to `/home/user/data` and `results-dir` to `/home/user/results`. 

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
- `--use-gpu`: Enables GPU training (default: False).
- `--dataset`: Set the dataset to use, with available choices: `mnist`, `fashion_mnist`, `cifar100` (default: "cifar100").
- `--algorithm`: Set the distributed training algorithm (required), with available choices: `all_reduce_ring`, `ps_sync`, `ps_async`.

For example, to run the script with 4 workers, 50 iterations, a learning rate of 0.02, the "lenet" model, GPU training enabled, the "cifar10" dataset, and the "algorithm1" distributed training algorithm, use the following command:
```bash
head python train.py --num-workers 4 --iter 50 --lr 0.02 --model lenet --use-gpu --dataset cifar100 --algorithm all_reduce_ring
```
