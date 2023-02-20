# from https://www.anyscale.com/blog/introducing-collective-communication-primitive-apis-in-ray
import numpy as np
import ray
import ray.util.collective as col


@ray.remote(num_cpus=1)
class Worker:
    def __init__(self):
        self.gradients = np.ones((10,), dtype=np.float32)

    def setup(self, world_size, rank):
        col.init_collective_group(
            world_size=world_size,
            rank=rank,
            backend="gloo")

    def allreduce(self):
        col.allreduce(self.gradients)
        return self.gradients


num_workers = 3
workers = [Worker.remote() for i in range(num_workers)]
setup_rets = ray.get([w.setup.remote(num_workers, i) for i, w in enumerate(workers)])

results = ray.get([w.allreduce.remote() for w in workers])
print(results)