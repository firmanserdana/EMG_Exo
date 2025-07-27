import os
import sys
import pickle
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_utils import *

# Set seaborn style
plt.rcParams['figure.facecolor'] = 'white'

# General params
subj_type = 'SCI' # 'healthy' or 'SCI'
class_label_map = {
    'open_close': {0: "Hand open", 1: "Hand close"},
    'grasp_patterns': {2: "Hook grasp", 3: "Lateral grasp", 4: "Index pointing"},
    'single_fingers': {5: "Thumb flexion", 6: "Index flexion", 7: "MRP flexion"}
}

# Define task-specific colors for class accuracy plots
task_colors = {
    'open_close': ['#cad2c5', '#354f52'],
    'single_fingers': ['#f4d35e', '#ee964b', '#f95738']
}

# Plotting parameters
plot_total_accuracy = False
plot_total_conf_matrix = False
plot_class_accuracy = True

root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
results_folder = os.path.join(root_folder, 'results-online')
pkl_path = os.path.join(results_folder, f"{subj_type}_task_accuracy_results.pkl")

with open(pkl_path, "rb") as f:
    df = pickle.load(f)  # should be a pandas DataFrame

# --- Prepare ---
subjects = df['subj'].unique()
tasks = df['task'].unique()
num_tasks = len(tasks)
# Use Blues colormap for subject colors (gradient)
subject_colors = {subj: plt.cm.Blues(0.4 + 0.6 * i / (len(subjects) - 1)) for i, subj in enumerate(subjects)}

# --- Plot: Total Accuracy for Each Subject and Each Task ---
if plot_total_accuracy:
    fig, axes = plt.subplots(1, num_tasks, figsize=(6*num_tasks, 6), squeeze=False)
    axes = axes[0]  # flatten

    for i, task in enumerate(tasks):
        ax = axes[i]
        task_df = df[df['task'] == task]
        
        # Compute mean and std accuracy per subject for this task
        means = task_df.groupby('subj')['total_accuracy'].mean()
        stds = task_df.groupby('subj')['total_accuracy'].std()
        
        subs = means.index.tolist()
        accs = means.values
        
        # Prepare error bars, handling NaN values
        yerr = []
        for subj in subs:
            std_val = stds.loc[subj]
            yerr.append(std_val if not pd.isna(std_val) else 0)
        
        # Plot individual subject bars with error bars
        bars = ax.bar(subs, accs, color=[subject_colors[s] for s in subs], 
                     yerr=yerr, capsize=3, zorder=3, alpha=0.8, width=0.5)
        
        # Add average bar for all subjects
        overall_mean = task_df['total_accuracy'].mean()
        overall_std = task_df['total_accuracy'].std()
        
        # Position the average bar after the subject bars with some spacing
        avg_position = len(subs) + 0.5
        avg_bar = ax.bar(avg_position, overall_mean, 
                        color='#c1121f', yerr=overall_std, capsize=3, 
                        zorder=3, alpha=0.9, label='Average', width=0.5)
        
        ax.set_title(f"Task: {task}")
        ax.set_ylim(0, 105)
        ax.set_yticks(np.arange(0, 101, 10))

        if i==0:
            ax.set_ylabel("Total Accuracy (%)")
        else:
            ax.set_yticklabels([])
        
        ax.set_xlabel("Subjects")
        
        # Update x-axis to include the average bar
        all_labels = subs + ['Mean']
        all_positions = list(range(len(subs))) + [avg_position]
        ax.set_xticks(all_positions)
        ax.set_xticklabels(all_labels)

    plt.tight_layout()
    plt.savefig(os.path.join(results_folder, f"{subj_type}_total_accuracy_plot.svg"), dpi=300)
    plt.show()

# --- Plot: Total Confusion Matrix for Each Task ---
if plot_total_conf_matrix:
    # Filter out rows where confusion_matrix is None
    df_filtered = df[df['confusion_matrix'].notna()]
    
    if df_filtered.empty:
        print("No confusion matrix data available")
    else:
        # Get all unique subjects across all tasks
        all_subjects = sorted(df_filtered['subj'].unique())
        num_subjects = len(all_subjects)
        num_tasks = len(tasks)
        
        # Create single figure with subplots: rows = tasks, columns = subjects
        fig, axes = plt.subplots(num_tasks, num_subjects, figsize=(6*num_subjects, 6*num_tasks))
        
        # Handle case where there's only one task or one subject
        if num_tasks == 1 and num_subjects == 1:
            axes = [[axes]]
        elif num_tasks == 1:
            axes = [axes]
        elif num_subjects == 1:
            axes = [[ax] for ax in axes]
        
        for task_idx, task in enumerate(tasks):
            task_df = df_filtered[df_filtered['task'] == task]
            
            if task_df.empty:
                print(f"No confusion matrix data available for task: {task}")
                # Fill empty subplots for this task
                for subj_idx in range(num_subjects):
                    ax = axes[task_idx][subj_idx]
                    ax.text(0.5, 0.5, 'No Data', ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'Task: {task} - Subject: {all_subjects[subj_idx]}')
                    ax.set_xticks([])
                    ax.set_yticks([])
                continue
            
            # Get the shape of confusion matrix from the first valid entry
            first_valid_cm = None
            for cm in task_df['confusion_matrix']:
                if cm is not None:
                    first_valid_cm = np.array(cm)
                    break
            
            if first_valid_cm is None:
                print(f"No valid confusion matrix found for task: {task}")
                continue
            
            n_classes = first_valid_cm.shape[0]
            
            for subj_idx, subject in enumerate(all_subjects):
                ax = axes[task_idx][subj_idx]
                
                # Get all sessions for this subject and task
                subject_task_df = task_df[task_df['subj'] == subject]
                
                if subject_task_df.empty:
                    # No data for this subject-task combination
                    ax.text(0.5, 0.5, 'No Data', ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'Task: {task} - Subject: {subject}')
                    ax.set_xticks([])
                    ax.set_yticks([])
                    continue
                
                # Sum confusion matrices across all sessions for this subject
                subject_cm_sum = np.zeros((n_classes, n_classes), dtype=int)
                valid_cms = 0
                
                for cm in subject_task_df['confusion_matrix']:
                    if cm is not None:
                        subject_cm_sum += np.array(cm)
                        valid_cms += 1
                
                if valid_cms == 0:
                    ax.text(0.5, 0.5, 'No Valid Data', ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'Task: {task} - Subject: {subject}')
                    ax.set_xticks([])
                    ax.set_yticks([])
                    continue
                
                # Get class labels for this task
                unique_classes = subject_task_df['unique_classes'].iloc[0]
                if task in class_label_map:
                    class_labels = [class_label_map[task].get(cls, str(cls)) for cls in unique_classes]
                else:
                    class_labels = [str(cls) for cls in unique_classes]
                
                # Convert confusion matrix to percentages (normalize by row - true class)
                subject_cm_percent = subject_cm_sum.astype('float') / subject_cm_sum.sum(axis=1)[:, np.newaxis] * 100
                # Handle division by zero (if a true class has no samples)
                subject_cm_percent = np.nan_to_num(subject_cm_percent)
                
                # Plot confusion matrix using seaborn with percentages
                sns.heatmap(subject_cm_percent, 
                           annot=True, 
                           fmt='.1f',  # Show 1 decimal place for percentages
                           cmap='Reds', 
                           ax=ax,
                           xticklabels=class_labels,
                           yticklabels=class_labels,
                           cbar=False,  # Disable individual colorbars for cleaner look
                           vmin=0, vmax=100)  # Set color scale from 0% to 100%
                
                # Set title and labels
                ax.set_title(f'Task: {task} - Subject: {subject}\n(Sessions: {len(subject_task_df)})', fontsize=10)
                
                # Only show x-axis labels on bottom row
                if task_idx == num_tasks - 1:
                    ax.set_xlabel('Predicted Class')
                else:
                    ax.set_xlabel('')
                
                # Only show y-axis labels on leftmost column
                if subj_idx == 0:
                    ax.set_ylabel('True Class')
                else:
                    ax.set_ylabel('')
        
        plt.tight_layout()
        plt.savefig(os.path.join(results_folder, f"{subj_type}_confusion_matrix_all_tasks_subjects.png"), dpi=300, bbox_inches='tight')
        plt.show()

# --- Plot: Class Accuracy for Each Task ---
if plot_class_accuracy:
    fig, axes = plt.subplots(1, num_tasks, figsize=(6*num_tasks, 6), squeeze=False)
    axes = axes[0]  # flatten

    for i, task in enumerate(tasks):
        ax = axes[i]
        task_df = df[df['task'] == task]
        # Find all class IDs for this task
        class_ids = sorted({cid for d in task_df['class_accuracy'] for cid in d.keys()})
        labels = [class_label_map[task].get(cid, str(cid)) for cid in class_ids]
        
        # Calculate average accuracy and std across all subjects for each class
        avg_class_accs = []
        std_class_accs = []
        
        for cid in class_ids:
            # Collect all accuracy values for this class across all subjects
            all_accs = []
            for subj in subjects:
                subj_df = task_df[task_df['subj'] == subj]
                accs = [d.get(cid, np.nan) for d in subj_df['class_accuracy']]
                accs = [a for a in accs if not pd.isna(a)]
                if accs:
                    all_accs.append(np.mean(accs))
            
            # Calculate mean and std across all subjects
            if all_accs:
                avg_class_accs.append(np.mean(all_accs))
                std_class_accs.append(np.std(all_accs) if len(all_accs) > 1 else 0)
            else:
                avg_class_accs.append(np.nan)
                std_class_accs.append(0)
        
        # Get colors for this task
        if task in task_colors:
            colors = task_colors[task][:len(class_ids)]  # Take only needed colors
        else:
            colors = ['#2E86AB'] * len(class_ids)  # Fallback color
        
        # Plot bars with error bars
        bars = ax.bar(
            np.arange(len(class_ids)), avg_class_accs,
            width=0.5,
            yerr=std_class_accs,
            capsize=3,
            color=colors,  # Use task-specific colors
            zorder=3
        )
        
        ax.set_title(f"Class Accuracy: {task}")
        ax.set_xticks(np.arange(len(class_ids)))
        ax.set_xticklabels(labels, ha='center')
        ax.set_ylim(0, 105)
        ax.set_yticks(np.arange(0, 101, 10))
        ax.set_xlim(-0.5, len(class_ids) - 0.5)

        if i==0:
            ax.set_ylabel("Class Accuracy (%)")
        else:
            ax.set_yticklabels([])

    plt.tight_layout()
    plt.savefig(os.path.join(results_folder, f"{subj_type}_class_accuracy_plot.svg"), dpi=300)
    plt.show()