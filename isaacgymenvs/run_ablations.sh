#!/bin/bash

ncsn_cfg=$(python ~/thesis_background/IsaacGymEnvs/isaacgymenvs/cfg/ablation_generator.py --model=ncsn)

# Run ncsn if the cfg is not empty or done
if [ "${ncsn_cfg}" = "done" ]; then
  echo "cmds done!"
  echo "------------"
else
  echo ${ncsn_cfg}
  # python ~/thesis_background/IsaacGymEnvs/isaacgymenvs/train_ncsn.py ${ncsn_cfg}
fi

sleep 1.0

rl_cfg=$(python ~/thesis_background/IsaacGymEnvs/isaacgymenvs/cfg/ablation_generator.py --model=rl)

# Run rl (either AMP or NEAR) if not done
if [ "${rl_cfg}" = "done" ]; then
  echo "cmds done!"
  echo "------------"
else
  echo ${rl_cfg}
  # python ~/thesis_background/IsaacGymEnvs/isaacgymenvs/train.py ${rl_cfg}
  
fi