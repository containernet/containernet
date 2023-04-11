from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class LeNet(nn.Module):
    def __init__(self, num_classes: int, input_shape: Tuple[int]):
        super(LeNet, self).__init__()
        self.conv1 = nn.Conv2d(input_shape[1], 6, kernel_size=5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, kernel_size=5)
        self.flatten = nn.Flatten()

        # Calculate output size after convolution and pooling layers
        conv_out = self._calculate_output_size(input_shape)

        self.fc1 = nn.Linear(conv_out, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, num_classes)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.flatten(x)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return F.log_softmax(x, dim=1)

    def _calculate_output_size(self, input_shape: Tuple[int]):
        with torch.no_grad():
            dummy_input = torch.zeros(1, *input_shape[1:])
            dummy_output = self.pool(F.relu(self.conv1(dummy_input)))
            dummy_output = self.pool(F.relu(self.conv2(dummy_output)))
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
