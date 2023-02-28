import ray
import ray.util.collective as col
import torch
from torch import nn
import torch.nn.functional as F

from .base_algorithm import Algorithm


@ray.remote(num_cpus=1)
class RingWorker:
    def __init__(self, rank: int, num_workers: int, backend: str, model: nn.Module,
                 train_loader: torch.utils.data.DataLoader, optimizer=torch.optim.SGD):
        self.num_workers = num_workers
        self.rank = rank
        self.next_rank = (rank + 1) % self.num_workers
        self.prev_rank = (rank - 1) % self.num_workers
        self._model = model
        self.train_loader = train_loader
        self.data_iterator = iter(self.train_loader)
        self.params = list(self._model.parameters())
        self.backend = backend
        self.optimizer = optimizer(self._model.parameters(), lr=0.01)


    def compute_gradients(self):
        try:
            data, target = next(self.data_iterator)
        except StopIteration:  # When the epoch ends, start a new epoch.
            self.data_iterator = iter(self.train_loader)
            data, target = next(self.data_iterator)
        self._model.zero_grad()
        output = self._model(data)
        loss = F.nll_loss(output, target)
        loss.backward()

    def update_weights(self):
        self.optimizer.step()

    def setup(self, world_size: int, rank: int):
        col.init_collective_group(world_size, rank, backend=self.backend)

    def set_bag(self, parameter_id: int):
        self.bags = torch.tensor_split(self.params[parameter_id].grad.data, self.num_workers)

    def get_gradients(self):
        return self._model.get_gradients()

    def get_weights(self):
        return self._model.get_weights()

    def recv_bag(self, tensor_shape):
        tensor = torch.empty(tensor_shape)  # , dtype=np.float32)
        col.recv(tensor, self.prev_rank)
        return tensor

    def send_bag(self, iteration: int = 0):
        return col.send(self.bags[(self.rank - iteration) % self.num_workers], self.next_rank)

    def add_bag(self, iteration: int = 0):
        bag_rank = (self.prev_rank - iteration) % self.num_workers
        bag_tensor = self.recv_bag(self.bags[bag_rank].shape)
        torch.add(self.bags[bag_rank], bag_tensor, out=self.bags[bag_rank])

    def replace_bag(self, iteration: int = 0):
        bag_rank = (self.prev_rank - iteration) % self.num_workers
        bag_tensor = self.recv_bag(self.bags[bag_rank].shape)#.div_(self.num_workers)
        self.bags[bag_rank].copy_(bag_tensor)


def get_all_gradients(workers):
    results = []
    for i, worker in enumerate(workers):
        results.append(worker.get_gradients.remote())
    grads = ray.get(results)
    return grads

# def equalize_weights(workers)

def perform_all_reduce(workers, model):
    num_parameters = sum(1 for _ in model.parameters())
    for w in workers:
        w.set_bag.remote(0)

    num_workers = len(workers)

    # send each parameter of model
    for param in range(num_parameters):
        # select current parameter
        for w in workers:
            w.set_bag.remote(param)
        # scatter-reduce stage
        for i in range(num_workers):
            for worker_id in range(num_workers):
                workers[worker_id].send_bag.remote(i)
                workers[(worker_id + 1) % num_workers].add_bag.remote(i)
        # all-gather stage
        for i in range(-1, num_workers - 2):
            for worker_id in range(num_workers):
                workers[worker_id].send_bag.remote(i)
                workers[(worker_id + 1) % num_workers].replace_bag.remote(i)


class AllReduceRing(Algorithm):

    name = "all_reduce_ring"

    def setup(self, num_workers, use_gpu: bool = False):
        if use_gpu:
            backend = "nccl"
        else:
            backend = "gloo"
        self.workers = [RingWorker.remote(i, num_workers, backend, self.model, self.train_loader) for i in range(num_workers)]
        for i, w in enumerate(self.workers):
            w.setup.remote(num_workers, i)

    def run(self, iterations: int, evaluate):

        # run training
        for i in range(iterations):
            for w in self.workers:
                w.compute_gradients.remote()
            perform_all_reduce(self.workers, self.model)
            # run optimizer
            for w in self.workers:
                w.update_weights.remote()

            if i % 10 == 0:
                # Evaluate the current model.
                self.model.set_weights(ray.get(self.workers[0].get_weights.remote()))
                accuracy = evaluate(self.model, self.test_loader)
                print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

        print("Final accuracy is {:.1f}.".format(accuracy))
        ray.shutdown()
