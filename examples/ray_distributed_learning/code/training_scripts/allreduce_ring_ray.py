import ray
import numpy as np
import ray.util.collective as col


@ray.remote(num_cpus=1)
class Worker:
    def __init__(self, rank: int, num_workers: int):
        self.gradients = np.arange(10, dtype=np.float32)
        self.num_workers = num_workers
        self.bag_size = len(self.gradients) // self.num_workers
        self.rank = rank
        self.next_rank = (rank + 1) % self.num_workers
        self.prev_rank = (rank - 1) % self.num_workers
        self.bags = np.array_split(self.gradients, self.bag_size)
        # self.setup(self.num_workers)

    def setup(self, world_size: int, rank: int):
        col.init_collective_group(world_size, rank, backend="gloo")

    def get_gradients(self):
        return self.gradients

    def recv_bag(self, tensor_length: int):
        tensor = np.zeros(tensor_length, dtype=np.float32)
        col.recv(tensor, self.prev_rank)
        return tensor

    def send_bag(self, iteration: int = 0):
        return col.send(self.bags[(self.rank - iteration) % self.num_workers], self.next_rank)

    def add_bag(self, iteration: int = 0):
        bag_rank = (self.prev_rank - iteration) % self.num_workers
        bag_tensor = self.recv_bag(len(self.bags[bag_rank]))
        np.add(self.bags[bag_rank], bag_tensor, out=self.bags[bag_rank])

    def replace_bag(self, iteration: int = 0):
        bag_rank = (self.prev_rank - iteration) % self.num_workers
        bag_tensor = self.recv_bag(len(self.bags[bag_rank]))
        np.copyto(self.bags[bag_rank], bag_tensor)


num_workers = 3
workers = [Worker.remote(i, num_workers) for i in range(num_workers)]
setup_rets = ray.get([w.setup.remote(num_workers, i) for i, w in enumerate(workers)])

# Perform allreduce
calls = []
print("Performing the Scatter-Reduce")
for i in range(num_workers - 1):
    for worker_id in range(num_workers):
        calls.append(workers[worker_id].send_bag.remote(i))
        calls.append(workers[(worker_id + 1) % num_workers].add_bag.remote(i))

print("Sending the accumulated weights")

for i in range(-1, num_workers - 2):
    for worker_id in range(num_workers):
        calls.append(workers[worker_id].send_bag.remote(i))
        calls.append(workers[(worker_id + 1) % num_workers].replace_bag.remote(i))

# ray.wait(calls, num_returns=len(calls), timeout=None)
results = []
for i, worker in enumerate(workers):
    results.append(worker.get_gradients.remote())
print(f"Results: {ray.get(results)}")

ray.shutdown()
