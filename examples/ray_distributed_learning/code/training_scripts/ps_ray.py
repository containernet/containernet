import argparse
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import datasets, transforms
from filelock import FileLock
import numpy as np

import ray


def get_data_loader():
    """Safely downloads data. Returns training/validation set dataloader."""
    mnist_transforms = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]
    )

    # We add FileLock here because multiple workers will want to
    # download data, and this may cause overwrites since
    # DataLoader is not threadsafe.
    with FileLock(os.path.expanduser("~/data.lock")):
        train_loader = torch.utils.data.DataLoader(
            datasets.MNIST(
                "~/data", train=True, download=True, transform=mnist_transforms
            ),
            batch_size=128,
            shuffle=True,
        )
        test_loader = torch.utils.data.DataLoader(
            datasets.MNIST("~/data", train=False, download=True, transform=mnist_transforms),
            batch_size=128,
            shuffle=True,
        )
    return train_loader, test_loader


def evaluate(model, test_loader):
    """Evaluates the accuracy of the model on a validation dataset."""
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for batch_idx, (data, target) in enumerate(test_loader):
            # This is only set to finish evaluation faster.
            if batch_idx * len(data) > 1024:
                break
            outputs = model(data)
            _, predicted = torch.max(outputs.data, 1)
            total += target.size(0)
            correct += (predicted == target).sum().item()
    return 100.0 * correct / total


class ConvNet(nn.Module):
    """Small ConvNet for MNIST."""

    def __init__(self):
        super(ConvNet, self).__init__()
        self.conv1 = nn.Conv2d(1, 3, kernel_size=3)
        self.fc = nn.Linear(192, 10)

    def forward(self, x):
        x = F.relu(F.max_pool2d(self.conv1(x), 3))
        x = x.view(-1, 192)
        x = self.fc(x)
        return F.log_softmax(x, dim=1)

    def get_weights(self):
        return {k: v.cpu() for k, v in self.state_dict().items()}

    def set_weights(self, weights):
        self.load_state_dict(weights)

    def get_gradients(self):
        grads = []
        for p in self.parameters():
            grad = None if p.grad is None else p.grad.data.cpu().numpy()
            grads.append(grad)
        return grads

    def set_gradients(self, gradients):
        for g, p in zip(gradients, self.parameters()):
            if g is not None:
                p.grad = torch.from_numpy(g)


@ray.remote
class ParameterServer(object):
    def __init__(self, lr):
        self.model = ConvNet()
        self.optimizer = torch.optim.SGD(self.model.parameters(), lr=lr)

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
class DataWorker(object):
    def __init__(self):
        self.model = ConvNet()
        self.data_iterator = iter(get_data_loader()[0])

    def compute_gradients(self, weights):
        self.model.set_weights(weights)
        try:
            data, target = next(self.data_iterator)
        except StopIteration:  # When the epoch ends, start a new epoch.
            self.data_iterator = iter(get_data_loader()[0])
            data, target = next(self.data_iterator)
        self.model.zero_grad()
        output = self.model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        return self.model.get_gradients()


def get_nodes(cluster, unlock_head: bool = True, lr : float = 0.01, head_ip = None):
    if not head_ip:
        head_ip = "172.20.40.52"
    head_node = [c['NodeID'] for c in cluster if c['NodeName'] == head_ip]
    worker_nodes = [c['NodeID'] for c in cluster if not c['NodeName'] == head_ip]
    if unlock_head:
        ps = ParameterServer.remote(lr)
    else:
        ps = ParameterServer.options(
            scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=head_node[0],
                soft=False
            )
        ).remote(lr=lr)

    workers = [DataWorker.options(
        scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
            node_id=node,
            soft=False
        )
    ).remote() for _, node in enumerate(worker_nodes)]
    # workers = [DataWorker.remote() for i in range(num_workers)]

    return ps, workers




## set head node to given IP

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--address", required=False, type=str, default=None, help="the address to use for Ray"
    )
    parser.add_argument(
        "--num-workers",
        "-n",
        type=int,
        default=1,
        help="Sets number of workers for training.",
    )
    parser.add_argument(
        "--iter", type=int, default=10, help="Set number of iterations for training"
    )

    parser.add_argument(
        "--use-gpu", action="store_true", default=False, help="Enables GPU training"
    )
    parser.add_argument(
        "--sync", action="store_true", default=False, help="Run Parameter Server in in synchronous mode"
    )
    parser.add_argument(
        "--unlock_head", action="store_true", default=False, help="Set PS to run on head node"
    )
    parser.add_argument(
        "--data", action="store_true", default=False, help="Only download data"
    )

    args, _ = parser.parse_known_args()

    if args.data:
        mnist_transforms = transforms.Compose(
            [transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]
        )
        datasets.MNIST(
            "~/data", train=True, download=True, transform=mnist_transforms
        )

        datasets.MNIST("~/data", download=True, train=False, transform=mnist_transforms)
        exit()


    iterations = args.iter
    num_workers = args.num_workers
    ray.init(ignore_reinit_error=True)
    model = ConvNet()
    test_loader = get_data_loader()[1]
    ps, workers = get_nodes(ray.nodes(), args.unlock_head, head_ip=args.address)

    if args.sync:
        print("Running synchronous parameter server training.")
        current_weights = ps.get_weights.remote()
        for i in range(iterations):
            gradients = [worker.compute_gradients.remote(current_weights) for worker in workers]
            # Calculate update after all gradients are available.
            current_weights = ps.apply_gradients.remote(*gradients)

            if i % 10 == 0:
                # Evaluate the current model.
                model.set_weights(ray.get(current_weights))
                accuracy = evaluate(model, test_loader)
                print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

        print("Final accuracy is {:.1f}.".format(accuracy))
        # Clean up Ray resources and processes before the next example.
    else:
        print("Running Asynchronous Parameter Server Training.")
        current_weights = ps.get_weights.remote()

        gradients = {}
        for worker in workers:
            gradients[worker.compute_gradients.remote(current_weights)] = worker

        for i in range(iterations * num_workers):
            ready_gradient_list, _ = ray.wait(list(gradients))
            ready_gradient_id = ready_gradient_list[0]
            worker = gradients.pop(ready_gradient_id)

            # Compute and apply gradients.
            current_weights = ps.apply_gradients.remote(*[ready_gradient_id])
            gradients[worker.compute_gradients.remote(current_weights)] = worker

            if i % 10 == 0:
                # Evaluate the current model after every 10 updates.
                model.set_weights(ray.get(current_weights))
                accuracy = evaluate(model, test_loader)
                print("Iter {}: \taccuracy is {:.1f}".format(i, accuracy))

        print("Final accuracy is {:.1f}.".format(accuracy))

    ray.shutdown()

