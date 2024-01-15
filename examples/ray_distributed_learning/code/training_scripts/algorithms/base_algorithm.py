from typing import Callable

from ..data import get_test_loader, get_train_loader


class Algorithm:
    name = ""

    def __init__(self, model, dataset_name: str):
        self.dataset_name = dataset_name
        self.model = model

    def setup(
        self,
        num_workers: int,
        use_gpu: bool,
        lr: float,
        batch_size: int,
        *args,
        **kwargs
    ):
        self.test_loader = get_test_loader(self.dataset_name, batch_size=batch_size)
        train_loader = get_train_loader(
            self.dataset_name,
            num_workers=num_workers,
            worker_rank=0,
            batch_size=batch_size,
        )
        self.iterations_per_epoch = len(train_loader)

    def run(self, num_epochs: int, evaluate: Callable):
        raise NotImplementedError("Implement this function for running the algorithm")
