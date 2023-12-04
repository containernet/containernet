from typing import Type, List

from .base_algorithm import Algorithm
from .parameter_server import ParameterServerSync, ParameterServerASync

algorithms = [ParameterServerSync, ParameterServerASync]


def algorithm_from_name(name: str) -> Type[Algorithm]:
    """
    Return an algorithm by the given name.

    Args:
        name (str): name of the algorithm

    Raises:
        ValueError: raised if no algorithm under that name was found

    Returns:
        Model: the model
    """
    for algo_class in algorithms:
        if algo_class.name == name:
            return algo_class
    raise Exception(f"unknown algorithm: {name}")


def algorithm_names() -> List[str]:
    """getter for list of dataset names for argparse

    Returns:
        List: the dataset names
    """
    return [algo_class.name for algo_class in algorithms]
