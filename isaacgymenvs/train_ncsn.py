import hydra

from omegaconf import DictConfig, OmegaConf, open_dict

# Importing from the file path
import sys
import os
FILE_PATH = os.path.abspath(os.path.dirname(__file__))
sys.path.append(FILE_PATH)

from datetime import datetime
import argparse
from utils.ncsn_utils import dict2namespace

@hydra.main(version_base="1.1", config_name="gym_env_config", config_path="./cfg")
def launch_hydra(cfg: DictConfig):

    # import argparse
    # import traceback
    # import time
    # import shutil
    # import logging
    # import torch
    # import numpy as np
    from learning.motion_ncsn.runners.anneal_runner import AnnealRunner
    from isaacgymenvs.utils.reformat import omegaconf_to_dict, print_dict

    # ensure checkpoints can be specified as relative paths
    # if cfg.checkpoint:
    #     cfg.checkpoint = to_absolute_path(cfg.checkpoint)

    visualise = cfg.test
    dmp_cfg = cfg.train.params.config.dmp_config

    # add device
    device = dmp_cfg.get('device', 'cuda:0')
    with open_dict(dmp_cfg):
        dmp_cfg.device = device


    # dump config dict
    if not visualise:

        # Printing the config
        dmp_cfg_dict = omegaconf_to_dict(dmp_cfg)
        print("TRAIN CFG")
        print_dict(dmp_cfg_dict)
        print("-----")

        experiment_dir = os.path.join('ncsn_runs', cfg.train.params.config.name + '_NCSN' + 
        '_{date:%d-%H-%M-%S}'.format(date=datetime.now()))

        os.makedirs(experiment_dir, exist_ok=True)
        with open(os.path.join(experiment_dir, 'ncsn_config.yaml'), 'w') as f:
            f.write(OmegaConf.to_yaml(dmp_cfg))

        # AnnealRunner generally takes in command line arguments for training log paths and other options. Setting up an artifical args object here to feed in the options
        args = argparse.Namespace()
        args.run = experiment_dir
        args.log = os.path.join(experiment_dir, 'nn')
        os.makedirs(args.log, exist_ok=True)
        args.doc = '_'


        runner = AnnealRunner(args, dmp_cfg)
        runner.train()
    
    else:
        # Empty args
        args = argparse.Namespace()
        runner = AnnealRunner(args, dmp_cfg)
        runner.visualise_energy()


if __name__ == "__main__":
    launch_hydra()