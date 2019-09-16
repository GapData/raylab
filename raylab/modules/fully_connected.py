# pylint: disable=missing-docstring
import torch.nn as nn
from ray.rllib.utils.annotations import override

from raylab.utils.pytorch import get_activation


class FullyConnectedModule(nn.Module):
    """Neural network module that applies several fully connected modules to inputs."""

    __constants__ = {"in_features", "out_features"}

    def __init__(self, in_features, units=(), activation="relu", layer_norm=False):
        super().__init__()
        self.in_features = in_features
        activation = get_activation(activation)
        units = (self.in_features,) + tuple(units)
        modules = []
        for in_dim, out_dim in zip(units[:-1], units[1:]):
            modules.append(nn.Linear(in_dim, out_dim))
            if layer_norm:
                modules.append(nn.LayerNorm(out_dim))
            modules.append(activation())
        self.sequential_module = nn.Sequential(*modules)
        self.out_features = units[-1]

    @override(nn.Module)
    def forward(self, inputs):  # pylint: disable=arguments-differ
        return self.sequential_module(inputs)
