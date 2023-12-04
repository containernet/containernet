import time

import torch
import torch.nn.functional as F
import ray
from tqdm import trange

from .base_algorithm import Algorithm
from ..data import get_train_loader
from ..utils import log_manager


@ray.remote
class ParameterServer:
    def __init__(self, model, num_workers: int, use_gpu: bool, optimizer, lr):
        if use_gpu:
            assert torch.cuda.is_available()
        self.device = torch.device("cuda" if use_gpu else "cpu")
        self.num_workers = num_workers
        self.model = model.to(self.device)
        self.optimizer = optimizer(self.model.parameters(), lr=lr, momentum=0.9)

    def apply_gradients(self, *gradients):
        summed_gradients = [
            torch.stack(gradient_zip).sum(dim=0) for gradient_zip in zip(*gradients)
        ]
        averaged_gradients = [grad / self.num_workers for grad in summed_gradients]
        self.optimizer.zero_grad()
        self.model.set_gradients(averaged_gradients)
        self.optimizer.step()
        return self.model.get_weights()

    def get_weights(self):
        return self.model.get_weights()


@ray.remote
class DataWorker:
    def __init__(self, model, use_gpu: bool, train_loader):
        if use_gpu:
            assert torch.cuda.is_available()
        self.device = torch.device("cuda" if use_gpu else "cpu")
        self.model = model.to(self.device)
        self.train_loader = train_loader
        self.data_iterator = iter(train_loader)

    def compute_gradients(self, weights):
        self.model.set_weights(weights)
        try:
            data, target = next(self.data_iterator)
        except StopIteration:  # When the epoch ends, start a new epoch.
            self.data_iterator = iter(self.train_loader)
            data, target = next(self.data_iterator)
        data, target = data.to(self.device), target.to(self.device)
        self.model.zero_grad()
        output = self.model(data)
        loss = F.cross_entropy(output, target)
        loss.backward()
        return self.model.get_gradients()


def setup_nodes(
    model: str,
    num_workers: int,
    dataset_name,
    use_gpu: bool,
    optimizer=torch.optim.SGD,
    lr: float = 0.01,
    batch_size: int = 64,
):
    num_data_workers = num_workers - 1

    cluster = ray.nodes()
    head_node_ip = ray.worker.global_worker.node_ip_address
    head_node = [c["NodeID"] for c in cluster if c["NodeName"] == head_node_ip]
    if len(head_node) != 1:
        print(
            f"Could not create exactly one head node. Created {len(head_node)} instead"
        )
    head_node = head_node[0]
    worker_nodes = [c["NodeID"] for c in cluster if not c["NodeName"] == head_node_ip][
        :num_data_workers
    ]

    if len(cluster) < num_workers:
        print(
            f"Not enough nodes to create {num_workers} workers. Created only {len(worker_nodes)} worker nodes."
        )

    if use_gpu:
        num_gpu = 1.0
        num_cpu = 0.0
    else:
        num_gpu = 0.0
        num_cpu = 1.0

    ps = ParameterServer.options(
        scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
            node_id=head_node, soft=False
        ),
        num_cpus=num_cpu,
        num_gpus=num_gpu,
    ).remote(model, num_workers, use_gpu, optimizer, lr=lr)

    workers = [
        DataWorker.options(
            scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=node, soft=False
            ),
            num_cpus=num_cpu,
            num_gpus=num_gpu,
        ).remote(
            model,
            use_gpu,
            get_train_loader(
                dataset_name,
                num_workers=num_data_workers,
                worker_rank=i,
                batch_size=batch_size,
            ),
        )
        for i, node in enumerate(worker_nodes)
    ]
    return ps, workers


class ParameterServerSync(Algorithm):
    name = "ps_sync"

    def setup(
        self,
        num_workers: int,
        use_gpu: bool,
        lr: float,
        batch_size: int,
        *args,
        **kwargs,
    ):
        super().setup(num_workers - 1, use_gpu, lr, batch_size, *args, **kwargs)
        self.ps, self.workers = setup_nodes(
            self.model,
            num_workers,
            self.dataset_name,
            use_gpu,
            lr=lr,
            batch_size=batch_size,
        )

    def run(self, num_epochs: int, evaluate, *args, **kwargs):
        print("Running synchronous parameter server training.")
        current_weights = self.ps.get_weights.remote()
        for epoch in range(num_epochs):
            start_time_epoch = time.perf_counter()
            for _ in trange(self.iterations_per_epoch):
                gradients = [
                    worker.compute_gradients.remote(current_weights)
                    for worker in self.workers
                ]
                # Wait for all remote workers to finish computing gradients.
                gradients = ray.get(gradients)
                # Calculate update after all gradients are available.
                current_weights = self.ps.apply_gradients.remote(*gradients)
            elapsed_time_epoch = time.perf_counter() - start_time_epoch
            log_manager.update("epoch_time", elapsed_time_epoch)

            # Evaluate the current model.
            self.model.set_weights(ray.get(current_weights))
            accuracy = evaluate(self.model, self.test_loader)
            print("Epoch {}: \taccuracy is {:.1f}".format(epoch, accuracy))
            log_manager.update("accuracy", accuracy)
        ray.shutdown()


class ParameterServerASync(Algorithm):
    name = "ps_async"

    def setup(
        self,
        num_workers: int,
        use_gpu: bool,
        lr: float,
        batch_size: int,
        *args,
        **kwargs,
    ):
        super().setup(num_workers, use_gpu, lr, batch_size, *args, **kwargs)
        self.ps, self.workers = setup_nodes(
            self.model, num_workers, self.dataset_name, use_gpu, lr=lr
        )

    def run(self, num_epochs: int, evaluate, *args, **kwargs):
        print("Running Asynchronous Parameter Server Training.")
        current_weights = self.ps.get_weights.remote()

        for epoch in range(num_epochs):
            start_time_epoch = time.perf_counter()
            gradients = {}
            for worker in self.workers:
                gradients[worker.compute_gradients.remote(current_weights)] = worker

            for _ in trange(self.iterations_per_epoch * len(self.workers)):
                ready_gradient_list, _ = ray.wait(list(gradients))
                ready_gradient_id = ready_gradient_list[0]
                worker = gradients.pop(ready_gradient_id)

                # Compute and apply gradients.
                current_weights = self.ps.apply_gradients.remote(*[ready_gradient_id])
                gradients[worker.compute_gradients.remote(current_weights)] = worker

            elapsed_time_epoch = time.perf_counter() - start_time_epoch
            log_manager.update("epoch_time", elapsed_time_epoch)

            # Evaluate the current model.
            self.model.set_weights(ray.get(current_weights))
            accuracy = evaluate(self.model, self.test_loader)
            print("Epoch {}: \taccuracy is {:.1f}".format(epoch, accuracy))
            log_manager.update("accuracy", accuracy)

        ray.shutdown()
