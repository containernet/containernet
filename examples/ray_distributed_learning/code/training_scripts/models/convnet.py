from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvNet(nn.Module):
    """Small ConvNet."""

    def __init__(self, num_classes: int, input_shape: Tuple[int]):
        super(ConvNet, self).__init__()
        self.conv1 = nn.Conv2d(input_shape[1], 3, kernel_size=3)
        self.pool = nn.MaxPool2d(3)
        self.flatten = nn.Flatten()

        # Calculate output size after convolution and pooling layers
        pool_out = self._calculate_output_size(input_shape)

        self.fc = nn.Linear(pool_out, num_classes)

    def forward(self, x):
        x = F.relu(self.pool(self.conv1(x)))
        x = self.flatten(x)
        x = self.fc(x)
        return x

    def _calculate_output_size(self, input_shape: Tuple[int]):
        with torch.no_grad():
            dummy_input = torch.zeros(1, *input_shape[1:])
            dummy_output = self.pool(self.conv1(dummy_input))
            return dummy_output.numel()

    def get_weights(self):
        return {k: v.cpu() for k, v in self.state_dict().items()}

    def set_weights(self, weights):
        self.load_state_dict(weights)

    def get_gradients(self):
        grads = []
        for param in self.parameters():
            grad = None if param.grad is None else param.grad.data
            grads.append(grad)
        return grads

    def set_gradients(self, gradients):
        for g, param in zip(gradients, self.parameters()):
            if g is not None:
                param.grad = g
