
import sys
import os
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optm_utils import *
from utils.data_utils import *
from utils.nn_model_training import *
from utils.plots_utils import *

# General params
optimization_name = 'runforward_seq_len_comparison'

# plot params
plot_group_by_model = False
plot_run_forward_timecourse = False
plot_run_forward_metrics = True

# folders definition
root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
config_folder = os.path.join(root_folder, 'config')
optim_config_folder = os.path.join(config_folder, 'optimizations')

# load optimization config
optim_config_file = os.path.join(optim_config_folder, f'{optimization_name}.yaml')

with open(optim_config_file, 'r') as f:
    optim_cfg = yaml.safe_load(f)

# create a folder for the optimization configuration results
subj_type = optim_cfg['subj_type']
results_optm_folder = os.path.join(root_folder, 'results-optimization', subj_type)

# load the results file
results_file = os.path.join(results_optm_folder, f'{optimization_name}_results.pkl')

optm_results = pd.read_pickle(results_file)

if plot_run_forward_timecourse:
    for i,row in optm_results.iterrows():
        print(f"Run forward for optimization {row.optm_name} on task {row.task} and subject {row.subj_id}")

        subj = row['subj_id']
        task = row['task']
        model_type = row['model_type']
        optm_name = row['optm_name']
        run_forward_results = row['run_forward_results']

        for session_id in run_forward_results:
            events_ts = run_forward_results[session_id]['events_ts']
            grasp_ids = run_forward_results[session_id]['grasp_ids']
            trials_results = run_forward_results[session_id]['trials_results']
            timestamps = run_forward_results[session_id]['timestamps']
            predictions = run_forward_results[session_id]['predictions']
            preds_probs = run_forward_results[session_id]['preds_probs']
            preds_times = run_forward_results[session_id]['preds_times']

            # Create save path for the plot
            os.path.join(results_optm_folder, 
                f'{optimization_name}_{subj}_{task}_{model_type}_{session_id:02d}_predictions.png')
            
            # Determine the midpoint for splitting the data
            total_time = preds_times[-1] - preds_times[0]
            mid_time = preds_times[0] + total_time / 2
            
            # Split data into two parts
            mask_part1 = preds_times <= mid_time
            mask_part2 = preds_times > mid_time
            trials_part1 = events_ts['trials_start'] <= mid_time
            trials_part2 = events_ts['trials_start'] > mid_time
            
            # Part 1 data
            preds_times_part1 = preds_times[mask_part1]
            predictions_part1 = predictions[mask_part1]
            preds_probs_part1 = preds_probs[mask_part1]
            grasp_ids_part1 = grasp_ids[trials_part1]

            # Part 2 data
            preds_times_part2 = preds_times[mask_part2]
            predictions_part2 = predictions[mask_part2]
            preds_probs_part2 = preds_probs[mask_part2]
            grasp_ids_part2 = grasp_ids[trials_part2]
            
            # Filter events for each part
            events_ts_part1 = {}
            events_ts_part2 = {}
            
            for event_key, event_times in events_ts.items():
                if isinstance(event_times, (list, np.ndarray)):
                    events_ts_part1[event_key] = [t for t in event_times if t <= mid_time]
                    events_ts_part2[event_key] = [t for t in event_times if t > mid_time]
                else:
                    events_ts_part1[event_key] = event_times
                    events_ts_part2[event_key] = event_times
            
            # Plot Part 1
            if len(preds_times_part1) > 0:
                plot_predictions_with_events(
                    fig_title=f'Optm: {optm_name} | Subject: {subj} | Task: {task} | Session: {session_id} | Part 1',
                    preds_times=preds_times_part1,
                    predictions=predictions_part1,
                    preds_probs=preds_probs_part1,
                    events_ts=events_ts_part1,
                    grasp_ids=grasp_ids_part1,
                    save_path=f'{save_path}_part_1'
                )
            
            # Plot Part 2
            if len(preds_times_part2) > 0:
                plot_predictions_with_events(
                    fig_title=f'Optm: {optm_name} | Subject: {subj} | Task: {task} | Session: {session_id} | Part 2',
                    preds_times=preds_times_part2,
                    predictions=predictions_part2,
                    preds_probs=preds_probs_part2,
                    events_ts=events_ts_part2,
                    grasp_ids=grasp_ids_part2,
                    save_path=f'{save_path}_part_2'
                )


if plot_run_forward_metrics:
    # Collect all accuracy data
    accuracy_data = []
    
    for i, row in optm_results.iterrows():
        print(f"Run forward for optimization {row.optm_name} on task {row.task} and subject {row.subj_id}")
        
        subj = row['subj_id']
        task = row['task']
        model_type = row['model_type']
        optm_name = row['optm_name']
        run_forward_results = row['run_forward_results']
        
        # Calculate average accuracy across all sessions for this optimization
        session_accuracies = []
        for session_id in run_forward_results:
            accuracy = run_forward_results[session_id]['forward_accuracy']
            session_accuracies.append(accuracy)
        
        avg_accuracy = np.mean(session_accuracies) if session_accuracies else 0
        
        accuracy_data.append({
            'subj_id': subj,
            'task': task,
            'model_type': model_type,
            'optm_name': optm_name,
            'forward_accuracy': avg_accuracy
        })
    
    # Convert to DataFrame
    accuracy_df = pd.DataFrame(accuracy_data)
    
    # Get unique values
    tasks = accuracy_df['task'].unique()
    optm_names = accuracy_df['optm_name'].unique()
    subjects = accuracy_df['subj_id'].unique()
    
    # Assign colors to subjects
    palette = sns.color_palette("tab10", len(subjects))
    subject_colors = {subj: palette[i % len(palette)] for i, subj in enumerate(subjects)}
    
    # Create subplots - one row per task
    fig, axes = plt.subplots(len(tasks), 1, figsize=(12, 6*len(tasks)), squeeze=False)
    
    for task_idx, task in enumerate(tasks):
        ax = axes[task_idx, 0]
        
        # Filter data for current task
        task_data = accuracy_df[accuracy_df['task'] == task]
        
        # Get unique optimization names for this task
        task_optm_names = task_data['optm_name'].unique()
        
        # Set up bar positions
        x_positions = np.arange(len(task_optm_names))
        bar_width = 0.8 / len(subjects)  # Adjust width based on number of subjects
        
        # Plot bars for each subject
        for subj_idx, subject in enumerate(subjects):
            subj_data = task_data[task_data['subj_id'] == subject]
            
            # Get accuracies for each optimization for this subject
            accuracies = []
            for optm_name in task_optm_names:
                subj_optm_data = subj_data[subj_data['optm_name'] == optm_name]
                if len(subj_optm_data) > 0:
                    accuracies.append(subj_optm_data['forward_accuracy'].iloc[0])
                else:
                    accuracies.append(0)  # No data for this subject-optimization combination
            
            # Calculate bar positions for this subject
            bar_positions = x_positions + (subj_idx - len(subjects)/2 + 0.5) * bar_width
            
            # Plot bars
            ax.bar(bar_positions, accuracies, bar_width, 
                  label=f'Subject {subject}', 
                  color=subject_colors[subject],
                  alpha=1)
        
        # Customize the plot
        ax.set_title(f'Forward Accuracy by Optimization - Task: {task}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Optimization Name', fontsize=12)
        ax.set_ylabel('Forward Accuracy (%)', fontsize=12)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(task_optm_names, ha='right')
        ax.set_ylim(0, 100)
        ax.set_yticks(np.arange(0, 101, 10))
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Add value labels on bars (optional)
        for subj_idx, subject in enumerate(subjects):
            subj_data = task_data[task_data['subj_id'] == subject]
            for optm_idx, optm_name in enumerate(task_optm_names):
                subj_optm_data = subj_data[subj_data['optm_name'] == optm_name]
                if len(subj_optm_data) > 0:
                    accuracy = subj_optm_data['forward_accuracy'].iloc[0]
                    bar_pos = x_positions[optm_idx] + (subj_idx - len(subjects)/2 + 0.5) * bar_width
                    ax.text(bar_pos, accuracy + 1, f'{accuracy:.1f}', 
                           ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.show()

if plot_group_by_model:
    model_types = optm_results['model_type'].unique()
    tasks = optm_results['task'].unique()
    subjects = optm_results['subj_id'].unique()
    num_models = len(model_types)
    num_tasks = len(tasks)

    # Assign a color to each subject
    palette = sns.color_palette("tab10", len(subjects))
    subject_colors = {subj: palette[i % len(palette)] for i, subj in enumerate(subjects)}

    fig, axes = plt.subplots(num_tasks, num_models, figsize=(6*num_models, 5*num_tasks), squeeze=False)

    for row, task in enumerate(tasks):
        for col, model in enumerate(model_types):
            ax = axes[row, col]
            model_df = optm_results[(optm_results['model_type'] == model) & (optm_results['task'] == task)].copy()
            model_df['test_accuracy'] = model_df['test_accuracy'].apply(lambda x: float(x))

            # Boxplot
            sns.boxplot(
                data=model_df,
                x='optm_name',
                y='test_accuracy',
                ax=ax,
                showfliers=False,
                color='lightgray'
            )

            sns.stripplot(
                data=model_df,
                x='optm_name',
                y='test_accuracy',
                hue='subj_id',
                ax=ax,
                palette=subject_colors,
                size=6,
                jitter=True,
                dodge=True
            )

            ax.set_title(f"Task: {task} | Model: {model}")
            ax.set_xlabel("Optimization Name")
            if col == 0:
                ax.set_ylabel("Test Accuracy")
            else:
                ax.set_ylabel("")
            ax.set_ylim(-1, 101)
            ax.set_yticks(np.arange(0, 101, 10))
            ax.grid(True, zorder=0)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='center')

    plt.tight_layout(rect=[0, 0, 0.98, 1])
    plt.show()