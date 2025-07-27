import sys
import os
import yaml
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix as sklearn_confusion_matrix

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_utils import *

# General params
subj_type = 'SCI' # 'healthy' or 'SCI'
subjects = [0,1,2,3,4]
tasks = ['open_close','single_fingers'] # options: ['open_close','grasp_patterns','single_fingers']

trial_timeout_id = 2 # result id value for timeout trials

# folders definition
root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
config_folder = os.path.join(root_folder, 'config')
data_folder_src = os.path.join('data', subj_type) # source folder for the data

# loading config file
with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
    emg_proc_cfg = yaml.load(f, Loader=yaml.FullLoader)

# initializing variables
num_channels_emg = emg_proc_cfg['num_channels_emg']
results_accuracy = []

# loop through subjects and tasks
for subj in subjects:
    subj_id = f'S{subj}'
    subj_data_folder = os.path.join(data_folder_src, subj_id, 'raw')
    subj_config_file = os.path.join(config_folder, 'subjects', subj_type, f'{subj_id}.yaml')

    # load config file
    with open(subj_config_file, 'r') as f:
        subj_cfg = yaml.safe_load(f)

    subj_identifier = subj_cfg['subj_identifier']

    for task in tasks:
        print(f'Processing task {task} for subject {subj_id}')

        sessions = subj_cfg[f'task_{task}']['sessions_closed_loop']
        num_sessions = len(sessions)

        if num_sessions == 0:
            print(f'No closed loop sessions found for task {task} in subject {subj_id}. Skipping...')
            continue

        for session_id in range(num_sessions):
            block_ids = sessions[session_id]

            print(f'Processing session {session_id + 1}/{num_sessions} for task {task} in subject {subj_id}')

            for block_id in block_ids:
                # load data
                data_file = os.path.join(subj_data_folder, f'session_{block_id:02d}.npy')
                events_file = os.path.join(subj_data_folder, f'session_{block_id:02d}_events.pkl')

                data = load_data_numpy(data_file)
                timestamps = data[:,-1]
                data = data[:,0:num_channels_emg]  # remove the timestamp column and other channels not used

                time_emg = timestamps - timestamps[0]
                time_start = timestamps[0]

                events = load_pickle(events_file)
                events_df = create_events_df(events, time_start=time_start)

                start_times = events_df.loc[events_df['event_type'] == 'decoding_start', 'time'].reset_index(drop=True)
                stop_times = events_df.loc[events_df['event_type'] == 'decoding_stop', 'time'].reset_index(drop=True)
                grasp_ids = np.array(events_df.loc[events_df['event_type'] == 'grasp_objective_start', 'event_id'])
                trials_results = np.array(events_df.loc[events_df['event_type'] == 'trial_result', 'event_id'])
                
                # Extract predicted classes (if available)
                predicted_classes_df = events_df.loc[events_df['event_type'] == 'grasp_decoded', 'event_id']
                
                if len(predicted_classes_df) != len(grasp_ids):
                    timeout_trials = np.where(trials_results == trial_timeout_id)[0]
                    grasp_ids = np.delete(grasp_ids, timeout_trials)
                    trials_results = np.delete(trials_results, timeout_trials)

                unique_classes = np.unique(grasp_ids)

                # Compute per-class accuracy
                class_accuracy = {}
                
                for cls in unique_classes:
                    idx = (grasp_ids == cls)
                    total = np.sum(idx)
                    acc = (np.sum(trials_results[idx] == 1) / total) * 100
                    class_accuracy[int(cls)] = acc
                    print(f"Class {cls}: accuracy = {acc:.2f}% ({np.sum(trials_results[idx] == 1)}/{total})")
                
                # Compute confusion matrix      
                if not predicted_classes_df.empty and len(predicted_classes_df) == len(grasp_ids):
                    predicted_classes = np.array(predicted_classes_df)
                    confusion_matrix = sklearn_confusion_matrix(grasp_ids, predicted_classes, labels=unique_classes)
                else:
                    raise ValueError("Predicted classes are not available or do not match the number of grasp IDs.")

                # Print the duration for each trial
                # for i, (start, stop) in enumerate(zip(start_times, stop_times)):
                #     print(f"Trial {i}: duration = {stop - start:.3f} seconds")

                num_success = (events_df['event_type'] == 'grasp_success').sum()
                num_error = (events_df['event_type'] == 'grasp_error').sum()
                total = num_success + num_error

                total_accuracy = (num_success / total) * 100
                print(f"Accuracy: {total_accuracy:.2f}% ({num_success}/{total})")

                results_accuracy.append({
                    'subj': subj_id,
                    'subj_identifier': subj_identifier,
                    'task': task,
                    'session': session_id,
                    'block': block_id,
                    'total_accuracy': total_accuracy,
                    'class_accuracy': class_accuracy,
                    'confusion_matrix': confusion_matrix.tolist() if confusion_matrix is not None else None,
                    'unique_classes': unique_classes.tolist(),
                    'num_success': int(num_success),
                    'num_error': int(num_error),
                    'total_trials': total
                })

# convert results to a DataFrame
results_df = pd.DataFrame(results_accuracy)

# Save results to bot .pkl and .csv files
results_file = os.path.join(root_folder, 'results-online', f'{subj_type}_task_accuracy_results')

results_df.to_pickle(f'{results_file}.pkl')
results_df.to_csv(f'{results_file}.csv', index=False)