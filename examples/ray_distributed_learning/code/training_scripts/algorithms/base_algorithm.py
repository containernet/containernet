from typing import Callable

from ..data import get_test_loader

class Algorithm:

    name = ""

    def __init__(self, model, dataset_name: str):
        self.dataset_name = dataset_name
        self.test_loader = get_test_loader(self.dataset_name)
        self.model = model

    def setup(self, num_workers: int, use_gpu: bool, *args, **kwargs):
        raise NotImplementedError(
            "Implement this function for setting up the workers and initialize all that is needed.")

    def run(self, iterations: int, evaluate: Callable):
        raise NotImplementedError(
            "Implement this function for running the algorithm")
