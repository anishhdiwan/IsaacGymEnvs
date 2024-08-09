from tbparse import SummaryReader
import matplotlib.pyplot as plt
import numpy as np
import os, sys
from pathlib import Path
import pandas as pd
import random

plt.rcParams['text.usetex'] = True

PARENT_DIR_PATH = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(PARENT_DIR_PATH)


from experiment_plotter import Colours


def get_scalars_from_dfs(scalar, trial_dfs):
    # Returns a list of np  arrays, of the scalar from each trial and a np array of steps
    trial_scalars = []
    trial_steps = None
    for trial_df in trial_dfs:
        series_df = trial_df[[scalar, 'step']]
        series_df = series_df.dropna(subset=[scalar])
        trial_scalars.append(series_df[scalar].to_numpy())
        if trial_steps is None:
            trial_steps = series_df['step'].to_numpy()

    return trial_scalars, trial_steps


if __name__ == "__main__":

    # Get all events in this dir
    # event_file = "./ncsn_runs/temp_runs/"
    event_file = "../../NEAR_experiments/plot_runs_temp/"
    
    df_path = Path(os.path.join(PARENT_DIR_PATH, "../../NEAR_experiments/plot_runs_df.pkl"))
    if df_path.is_file():
        df = pd.read_pickle(df_path)
    else:
        reader = SummaryReader(event_file, pivot=True, extra_columns={'dir_name'})
        df = reader.scalars
        df.to_pickle(df_path)
    

    ###### INPUTS #######
    
    TASK_NAME = "crane_pose"
    PLOT_SUBPLOTS = True
    seeds = [42, 700, 8125, 97, 3538]

    experiment_lables = {
        r"NCSN-v2 $\vert$ Annealing $\vert$ $e_{\theta}$":[f"ABLATION_HumanoidNEAR_{TASK_NAME}_-1_True_w_style_10_{seed}" for seed in seeds],
        r"NCSN-v2 $\vert$ Annealing $\vert$ $0.5 e_{\theta} + 0.5 r^{task}$":[f"ABLATION_HumanoidNEAR_{TASK_NAME}_-1_True_w_style_05_{seed}" for seed in seeds],
        r"NCSN-v2 $\vert$ $\sigma_5 $ $\vert$ $e_{\theta}$":[f"ABLATION_HumanoidNEAR_{TASK_NAME}_5_True_w_style_10_{seed}" for seed in seeds],
        r"NCSN-v2 $\vert$ $\sigma_5 $ $\vert$ $0.5 e_{\theta} + 0.5 r^{task}$":[f"ABLATION_HumanoidNEAR_{TASK_NAME}_5_True_w_style_05_{seed}" for seed in seeds],
        # r"NCSN-v1 $\vert$ Annealing $\vert$ $e_{\theta}$":[f"ABLATION_HumanoidNEAR_{TASK_NAME}_-1_False_w_style_10_{seed}" for seed in seeds],
    }

    expert_values = {
        "walk": {"spectral_arc_length/step": -5.40, "root_body_velocity/step": 1.31, "root_body_acceleration/step": 3.37, "root_body_jerk/step": 130.11},
        "run": {"spectral_arc_length/step":  -3.79, "root_body_velocity/step": 3.55, "root_body_acceleration/step": 16.35, "root_body_jerk/step": 513.68},
        "crane_pose": {"spectral_arc_length/step": -12.28, "root_body_velocity/step": 0.03, "root_body_acceleration/step": 0.96, "root_body_jerk/step": 49.05}
        }
    expert_values = expert_values[TASK_NAME]

    title = f"Humanoid {TASK_NAME.replace('_', ' ').title()} - NCSN Ablation"
    ###### INPUTS #######
    
    scalars = [
        # "episode_lengths/step", 
        "mean_dtw_pose_error/step", 
        # "minibatch_combined_reward/step", 
        # "minibatch_energy/step", 
        # "ncsn_perturbation_level/step", 
        # "root_body_acceleration/step",
        "root_body_jerk/step",
        "root_body_velocity/step",
        "spectral_arc_length/step",
        ]
    scalar_labels = [
        # "Episode Length", 
        "Average Pose Error", 
        # "Horizon Return", 
        # "Horizon Energy Return", 
        # "NCSN Perturbation Level", 
        # "Root Body Acceleration",
        "Root Body Jerk",
        "Root Body Velocity",
        "Spectral Arc Length (SPARC)",
        ]

    for idx, scalar in enumerate(scalars):
        subplt_idx = 0
        annotate = True
        if PLOT_SUBPLOTS:
            fig, (ax1, ax2) = plt.subplots(2)
            annotations = {ax1:{}, ax2:{}}
        else:
            annotations = {}

        for exp_label, trial_names in experiment_lables.items():
            trial_names = [name + "/summaries" for name in trial_names]
            exp_dfs = []
            for trial in trial_names:
                exp_dfs.append(df[df['dir_name'] == trial])

            # for idx, scalar in enumerate(scalars):
            exp_scalars, exp_steps = get_scalars_from_dfs(scalar, exp_dfs)
            exp_scalars = np.stack(exp_scalars, axis=1)
            mean_scalar = np.mean(exp_scalars, axis=1)
            std_scalar = np.std(exp_scalars, axis=1)
            std_interval = 1.0
            min_interval = mean_scalar - std_interval*std_scalar
            max_interval = mean_scalar + std_interval*std_scalar
            linestyle = '-'
            hatch = None   

            if PLOT_SUBPLOTS:         
                # Ablate Task Reward
                colours = {0:0, 1:1, 2:0, 3:1}

                # Ablate Annealing
                # colours = {0:0, 1:0, 2:1, 3:1}
                
                colour_idx = colours[subplt_idx]

                # Ablate Annealing
                # if subplt_idx%2 == 0:
                
                # Ablate Task Reward
                if subplt_idx < 2:
                    ax1.plot(exp_steps, mean_scalar, color=Colours[colour_idx], linewidth=1.5, label=exp_label, linestyle=linestyle)
                    ax1.fill_between(exp_steps, min_interval, max_interval, alpha=0.2, color=Colours[colour_idx], hatch=hatch)

                    if annotate:
                        if scalar not in ["minibatch_combined_reward/step"]:
                            annotations[ax1][round(mean_scalar[-1], 4)] = [(exp_steps[-1], mean_scalar[-1]), Colours[colour_idx]]
                
                else:
                    ax2.plot(exp_steps, mean_scalar, color=Colours[colour_idx], linewidth=1.5, label=exp_label, linestyle=linestyle)
                    ax2.fill_between(exp_steps, min_interval, max_interval, alpha=0.2, color=Colours[colour_idx], hatch=hatch)

                    if annotate:
                        if scalar not in ["minibatch_combined_reward/step"]:
                            annotations[ax2][round(mean_scalar[-1], 4)] = [(exp_steps[-1], mean_scalar[-1]), Colours[colour_idx]]
            
            else:
                colour_idx = subplt_idx
                plt.plot(exp_steps, mean_scalar, color=Colours[colour_idx], linewidth=1.5, label=exp_label, linestyle=linestyle)
                plt.fill_between(exp_steps, min_interval, max_interval, alpha=0.2, color=Colours[colour_idx], hatch=hatch)

                if annotate:
                    if scalar not in ["minibatch_combined_reward/step"]:
                        annotations[round(mean_scalar[-1], 4)] = [(exp_steps[-1], mean_scalar[-1]), Colours[colour_idx]]

            subplt_idx += 1


        if PLOT_SUBPLOTS:
            for ax in (ax1, ax2):
                ax.set_xlabel('Training Samples')
                ax.set_ylabel(scalar_labels[idx])
                # ax.set_title(title)
                if scalar in list(expert_values.keys()):
                    ax.axhline(y=expert_values[scalar], color='#f032e6', linestyle='-', linewidth=1.5, label="Expert's Value")
                    if annotate:
                        ax.annotate(f'{expert_values[scalar]}', xy=(plt.gca().get_xlim()[1], expert_values[scalar]), xytext=(1.001*plt.gca().get_xlim()[1], expert_values[scalar]), color='#f032e6')

                if annotate:
                    ax_annotations = annotations[ax]
                    if len(ax_annotations) > 0:
                        wiggle_const = 0
                        for offset_idx, text in enumerate(sorted(list(ax_annotations.keys()), key=float)):
                            # offset = float(offset_idx+1+wiggle_const)*0.1*plt.gca().get_ylim()[1]
                            offset = [float(1)*0.1*plt.gca().get_ylim()[0], -float(1)*0.1*plt.gca().get_ylim()[0]][offset_idx]
                            ax.annotate(round(text,2), xy=ax_annotations[text][0], xytext=(1.002*plt.gca().get_xlim()[1],  ax_annotations[text][0][1]+offset), arrowprops=dict(arrowstyle='->', color=ax_annotations[text][1]))

                ax.legend()
            
            fig.suptitle(title)
        
        else:
            plt.xlabel('Training Samples')
            plt.ylabel(scalar_labels[idx])
            plt.title(title)

            if scalar in list(expert_values.keys()):
                plt.axhline(y=expert_values[scalar], color='#f032e6', linestyle='-', linewidth=1.5, label="Expert's Value")
                if annotate:
                    plt.annotate(f'{expert_values[scalar]}', xy=(plt.gca().get_xlim()[1], expert_values[scalar]), xytext=(1.001*plt.gca().get_xlim()[1], expert_values[scalar]), color='#f032e6')

            if annotate:
                if len(annotations) > 0:
                    for offset_idx, text in enumerate(sorted(list(annotations.keys()), key=float)):
                        offset = float(offset_idx+1)*0.1*plt.gca().get_ylim()[1]
                        # offset = [float(1)*0.25*plt.gca().get_ylim()[1], float(1)*0.2*plt.gca().get_ylim()[1]][offset_idx]
                        plt.annotate(round(text,2), xy=annotations[text][0], xytext=(1.002*plt.gca().get_xlim()[1],  annotations[text][0][1]+offset), arrowprops=dict(arrowstyle='->', color=annotations[text][1]))

            plt.legend()

        plt.tight_layout()
        plt.show()
