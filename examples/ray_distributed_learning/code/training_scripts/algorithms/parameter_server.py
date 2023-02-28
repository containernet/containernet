import torch
import torch.nn.functional as F
import numpy as np
import ray

from .base_algorithm import Algorithm


@ray.remote
class ParameterServer():
    def __init__(self, model, optimizer, lr):
        self.model = model
        self.optimizer = optimizer(self.model.parameters(), lr=lr)

    def apply_gradients(self, *gradients):
        summed_gradients = [
            np.stack(gradient_zip).sum(axis=0) for gradient_zip in zip(*gradients)
        ]
        self.optimizer.zero_grad()
        self.model.set_gradients(summed_gradients)
        self.optimizer.step()
        return self.model.get_weights()

    def get_weights(self):
        return self.model.get_weights()


@ray.remote
class DataWorker():
    def __init__(self, model, train_loader):
        self.model = model
        self.train_loader = train_loader
        self.data_iterator = iter(train_loader)

    def compute_gradients(self, weights):
        self.model.set_weights(weights)
        try:
            data, target = next(self.data_iterator)
        except StopIteration:  # When the epoch ends, start a new epoch.
            self.data_iterator = iter(self.train_loader)
            data, target = next(self.data_iterator)
        self.model.zero_grad()
        output = self.model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        return self.model.get_gradients()


def setup_nodes(cluster, model: str, num_workers: int, train_loader, optimizer=torch.optim.SGD, unlock_head: bool = False, lr: float = 0.01,
                head_ip: str = "172.20.40.52"):

    head_node = [c['NodeID'] for c in cluster if c['NodeName'] == head_ip]
    worker_nodes = [c['NodeID'] for c in cluster if not c['NodeName'] == head_ip][:num_workers]
    if unlock_head:
        ps = ParameterServer.remote(model, optimizer, lr=lr)
    else:
        ps = ParameterServer.options(
            scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=head_node[0],
                soft=False
            )
        ).remote(model, optimizer, lr=lr)

    workers = [DataWorker.options(
        scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
            node_id=node,
            soft=False
        )
    ).remote(model, train_loader) for node in worker_nodes]
    return ps, workers


class ParameterServerSync(Algorithm):

    name = "ps_sync"

    def setup(self, num_workers: int, *args, **kwargs):
        self.ps, self.workers = setup_nodes(ray.nodes(), self.model, num_workers, self.train_loader)
        print(self.workers)

    def run(self, iterations: int, evaluate, *args, **kwargs):
        print("Running synchronous parameter server training.")
        current_weights = self.ps.get_weights.remote()
        for i in range(iterations):
            gradients = [worker.compute_gradients.remote(current_weights) for worker in self.workers]
            # Calculate update after all gradients are available.
            current_weights = self.ps.apply_gradients.remote(*gradients)

            if i % 10 == 0:
                # Evaluate the current model.
                self.model.set_weights(ray.get(current_weights))
                accuracy = evaluate(self.model, self.test_loader)
                print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

        print("Final accuracy is {:.1f}.".format(accuracy))
        ray.shutdown()


class ParameterServerASync(Algorithm):

    name = "ps_async"

    def setup(self, num_workers: int, *args, **kwargs):
        self.ps, self.workers = setup_nodes(ray.nodes(), self.model, num_workers, self.train_loader)
        print(self.workers)

    def run(self, iterations: int, evaluate, *args, **kwargs):
        print("Running Asynchronous Parameter Server Training.")
        current_weights = self.ps.get_weights.remote()

        gradients = {}
        for worker in self.workers:
            gradients[worker.compute_gradients.remote(current_weights)] = worker

        for i in range(iterations * len(self.workers)):
            ready_gradient_list, _ = ray.wait(list(gradients))
            ready_gradient_id = ready_gradient_list[0]
            worker = gradients.pop(ready_gradient_id)

            # Compute and apply gradients.
            current_weights = self.ps.apply_gradients.remote(*[ready_gradient_id])
            gradients[worker.compute_gradients.remote(current_weights)] = worker

            if i % 10 == 0:
                # Evaluate the current model after every 10 updates.
                self.model.set_weights(ray.get(current_weights))
                accuracy = evaluate(self.model, self.test_loader)
                print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

        print("Final accuracy is {:.1f}.".format(accuracy))
        ray.shutdown()


