import re
import subprocess
import time
import os
import pty

import ray
import ray.util.collective as col
import torch
from torch import nn
import torch.nn.functional as F
from mpi4py import MPI
from tqdm import trange

from .base_algorithm import Algorithm
from ..data import get_train_loader
from ..utils import log_manager


class BaseWorker:
    def __init__(self, rank: int, num_workers: int, model: nn.Module,
                 train_loader: torch.utils.data.DataLoader, lr: float, optimizer=torch.optim.SGD, device=torch.device("cpu")):
        self.num_workers = num_workers
        self.rank = rank
        self.next_rank = (rank + 1) % self.num_workers
        self.prev_rank = (rank - 1) % self.num_workers
        self.device = device
        self._model = model.to(self.device)
        self.train_loader = train_loader
        self.data_iterator = iter(self.train_loader)
        self.params = list(self._model.parameters())
        self.optimizer = optimizer(self._model.parameters(), lr=lr, momentum=0.9)

    def compute_gradients(self):
        try:
            data, target = next(self.data_iterator)
        except StopIteration:  # When the epoch ends, start a new epoch.
            self.data_iterator = iter(self.train_loader)
            data, target = next(self.data_iterator)
        data, target = data.to(self.device), target.to(self.device)
        self._model.zero_grad()
        output = self._model(data)
        loss = F.cross_entropy(output, target)
        loss.backward()

    def update_weights(self):
        self.optimizer.step()

    def setup(self):
        raise NotImplementedError(
            "Implement this function for setting up the workers.")

    def create_bags(self, parameter_id: int):
        self.bags = torch.tensor_split(self.params[parameter_id].grad.data, self.num_workers)

    def get_gradients(self):
        return self._model.get_gradients()

    def get_weights(self):
        return self._model.get_weights()

    def recv_bag(self, tensor_shape):
        raise NotImplementedError(
            "Implement this function for setting up the workers.")

    def send_bag(self, iteration: int = 0):
        raise NotImplementedError(
            "Implement this function for setting up the workers.")

    def add_bag(self, iteration: int = 0):
        bag_rank = (self.prev_rank - iteration) % self.num_workers
        bag_tensor = self.recv_bag(self.bags[bag_rank].shape)
        self.bags[bag_rank].add_(bag_tensor)

    def replace_bag(self, iteration: int = 0):
        bag_rank = (self.prev_rank - iteration) % self.num_workers
        bag_tensor = self.recv_bag(self.bags[bag_rank].shape)
        self.bags[bag_rank].copy_(bag_tensor)

    def normalize_bag(self, bag_rank: int):
        self.bags[bag_rank].div_(self.num_workers)

@ray.remote
class RingWorker(BaseWorker):
    def __init__(self, rank: int, num_workers: int, model: nn.Module,
                 train_loader: torch.utils.data.DataLoader, lr: float, optimizer=torch.optim.SGD):
        super().__init__(rank, num_workers, model, train_loader, lr, optimizer)

    def setup(self):
        col.init_collective_group(self.num_workers, self.rank, "gloo")
        return True

    def recv_bag(self, tensor_shape):
        tensor = torch.empty(tensor_shape)
        col.recv(tensor, self.prev_rank)
        return tensor

    def send_bag(self, iteration: int = 0):
        return col.send(self.bags[(self.rank - iteration) % self.num_workers], self.next_rank)


@ray.remote
class MPIWorker(BaseWorker):
    def __init__(self, rank: int, num_workers: int, model: nn.Module,
                 train_loader: torch.utils.data.DataLoader, lr: float, optimizer=torch.optim.SGD):
        super().__init__(rank, num_workers, model, train_loader, lr, optimizer, device=torch.device("cuda"))
        self.intercomms = dict()

    def setup(self):
        pass

    def publish_name(self):
        self.port = MPI.Open_port(MPI.INFO_NULL)
        MPI.Publish_name(f"client_{self.rank}", self.port, MPI.INFO_NULL)

    def unpublish_name(self):
        MPI.Close_port(self.port)
        MPI.Unpublish_name(f"client_{self.rank}", self.port, MPI.INFO_NULL)

    def connect_intercomm(self, other_rank: int):
        comm = MPI.COMM_SELF
        target_port = MPI.Lookup_name(f"client_{other_rank}", MPI.INFO_NULL)
        intercomm = comm.Connect(target_port, MPI.INFO_NULL, 0)
        intercomm.send(self.rank, dest=0)
        self.intercomms[other_rank] = intercomm

    def accept_intercomms(self, num_clients: int):
        self.publish_name()
        comm = MPI.COMM_SELF
        for _ in range(num_clients):
            own_port = MPI.Lookup_name(f"client_{self.rank}", MPI.INFO_NULL)
            intercomm = comm.Accept(own_port, MPI.INFO_NULL, 0)
            other_rank = intercomm.recv(source=0)
            self.intercomms[other_rank] = intercomm
        self.unpublish_name()

    def recv_bag(self, tensor_shape):
        tensor = torch.empty(tensor_shape).to(self.device)
        self.intercomms[self.prev_rank].Recv(tensor, source=MPI.ANY_SOURCE)
        return tensor

    def send_bag(self, iteration: int = 0):
        tensor = self.bags[(self.rank - iteration) % self.num_workers]
        self.intercomms[self.next_rank].Send(tensor, dest=0)


def get_all_gradients(workers):
    results = []
    for i, worker in enumerate(workers):
        results.append(worker.get_gradients.remote())
    grads = ray.get(results)
    return grads


class AllReduceRing(Algorithm):
    name = "all_reduce_ring"

    def setup(self, num_workers: int, use_gpu: bool, lr: float, batch_size: int, *args, **kwargs):
        super().setup(num_workers, use_gpu, lr, batch_size, *args, **kwargs)
        if use_gpu:
            worker_class = MPIWorker
            num_gpus = 1 / num_workers
            num_cpus = 0

            ompi_server_process, uri = get_server_process_and_uri()
            runtime_env = {
                'env_vars': {'OMPI_MCA_pmix_server_uri': uri}
            }
        else:
            num_gpus = 0
            num_cpus = 1
            worker_class = RingWorker
            runtime_env = {}

        worker_nodes = [c['NodeID'] for c in ray.nodes()][:num_workers]
        self.workers = [worker_class.options(
            scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=node,
                soft=False
            ),
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            runtime_env=runtime_env
        ).remote(i, num_workers, self.model, get_train_loader(self.dataset_name, num_workers=num_workers, worker_rank=i, batch_size=batch_size), lr=lr) for i, node in enumerate(worker_nodes)]
        init_rets = []
        for w in self.workers:
            init_rets.append(w.setup.remote())
        ray.get(init_rets)

        if use_gpu:
            # connect comms
            for i, worker in enumerate(self.workers[:-1]):
                num_workers_left = num_workers - i - 1
                worker.accept_intercomms.remote(num_workers_left)
                for other_worker in self.workers[i + 1:]:
                    ray.get(other_worker.connect_intercomm.remote(i))

            ompi_server_process.terminate()
            ompi_server_process.wait()

    def run(self, num_epochs: int, evaluate):
        # run training
        for epoch in range(num_epochs):
            start_time_epoch = time.perf_counter()
            for _ in trange(self.iterations_per_epoch):
                for w in self.workers:
                    w.compute_gradients.remote()
                perform_all_reduce(self.workers, self.model)
                # run optimizer
                for w in self.workers:
                    ray.get(w.update_weights.remote())

            elapsed_time_epoch = time.perf_counter() - start_time_epoch
            log_manager.update("epoch_time", elapsed_time_epoch)

            # Evaluate the current model.
            self.model.set_weights(ray.get(self.workers[0].get_weights.remote()))
            accuracy = evaluate(self.model, self.test_loader)
            print("Epoch {}: \taccuracy is {:.1f}".format(epoch, accuracy))
            log_manager.update("accuracy", accuracy)

        ray.shutdown()


def perform_all_reduce(workers, model):
    num_parameters = sum(1 for _ in model.parameters())
    num_workers = len(workers)
    # send each parameter of model
    for param in range(num_parameters):
        # select current parameter
        for w in workers:
            w.create_bags.remote(param)
        # scatter-reduce stage
        for i in range(num_workers - 1):
            for worker_id in range(num_workers):
                workers[worker_id].send_bag.remote(i)
                workers[(worker_id + 1) % num_workers].add_bag.remote(i)
        # normalize the bag each worker will send in the first gather step
        for worker_id in range(num_workers):
            worker_rank = workers[worker_id].rank
            workers[worker_id].normalize_bag.remote((worker_rank + 1) % num_workers)
        # all-gather stage
        for i in range(-1, num_workers - 2):
            for worker_id in range(num_workers):
                workers[worker_id].send_bag.remote(i)
                workers[(worker_id + 1) % num_workers].replace_bag.remote(i)


def get_server_process_and_uri():
    def get_server_uri(stdout_str):
        for line in stdout_str.splitlines():
            match = re.search(r"(\d+\.\d+;tcp://[\d.,]+:\d+)", line)
            if match:
                return match.group(1)
        return None

    command = ['/usr/local/bin/ompi-server', '--no-daemonize', '-r', '-']
    # Create a pseudo-terminal for the subprocess
    master_fd, slave_fd = pty.openpty()
    ompi_server_process = subprocess.Popen(command, stdout=slave_fd, stderr=subprocess.PIPE, text=True, env=os.environ)
    # Close the slave descriptor as it's not needed in the parent process
    os.close(slave_fd)
    uri = None
    while uri is None:
        stdout_str = os.read(master_fd, 1024).decode()
        uri = get_server_uri(stdout_str)
        time.sleep(0.1)

    # Clean up the master descriptor
    os.close(master_fd)

    return ompi_server_process, uri
