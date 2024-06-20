import argparse
from collections import deque
import torch
import copy

def to_relative_pose(pose_traj, root_idx):
    """Transform a vector of body poses to be relative to the root joint and return the flattened vectors

    Args:
        pose_traj (torch.Tensor): Tensor of a body pose trajectory. Required shape: [num_frames, num_joints, 3]
        root_idx (int): index of the root joint. Must be in [0,num_joints)
    """
    assert len(pose_traj.shape) == 3, "Required trajectory shape: [num_frames, num_joints, 3]"
    assert 0 <= root_idx < pose_traj.shape[1], "Root joint index must be in [0, num_joints)"

    # Subtract the root body cartesian pose from the other joints
    return (pose_traj - pose_traj[:, root_idx, :].unsqueeze(1)).flatten(start_dim=1, end_dim=-1)

def get_series_derivative(series, dt):
    """Compute the derivative of a time series diven a time step length dt

    Args:
        series (torch.Tensor): time series of shape [d, dim]
        dt (float): time step
    """
    if series.shape[0] < 2:
        return torch.zeros((1, series.shape[-1]))

    else:
        series_shift = copy.deepcopy(series)
        series_shift[:-1,:] = series_shift.clone()[1:,:]
        series_shift = series_shift[:-1]
        series = series[:-1]
        derivative = (series_shift - series)/dt

        return derivative

def dict2namespace(config):
    """Convert a disctionary (typically containing config params) to a namespace structure (https://tedboy.github.io/python_stdlib/generated/generated/argparse.Namespace.html#argparse.Namespace)

    Args:
        config (dict): dictionary of configs params
    """
    namespace = argparse.Namespace()
    for key, value in config.items():
        if isinstance(value, dict):
            new_value = dict2namespace(value)
        else:
            new_value = value
        setattr(namespace, key, new_value)
    return namespace


class LastKMovingAvg:
    """Given a time series where data is continously being added, keep a buffer of the last k elements and return their stats

    Assumes that the elements are torch tensors
    """

    def __init__(self, maxlen=3):
        self.maxlen = maxlen
        self.buffer = deque([], maxlen=self.maxlen)
    
    def append(self, element, return_avg=True):
        self.buffer.append(element)

        if return_avg:
            return torch.mean(torch.stack(list(self.buffer))).item()

    def reset(self):
        self.buffer = deque([], maxlen=self.maxlen)


