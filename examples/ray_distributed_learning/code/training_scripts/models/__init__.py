from typing import Type

from torch import nn

from .convnet import ConvNet
from .lenet import LeNet

models = [ConvNet, LeNet]


def model_from_name(name: str) -> Type[nn.Module]:
    """
    Return a model by the given name.

    Args:
        name (str): name of the model

    Raises:
        ValueError: raised if no model under that name was found

    Returns:
        Model: the model
    """
    for model_class in models:
        if model_class.__name__.lower() == name:
            return model_class
    raise ValueError(f"{name} model not found!")
