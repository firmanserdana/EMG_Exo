import sys
import os
import yaml
import numpy as np
import pandas as pd
import pickle

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_utils import *

# General params
subj_type = 'SCI' # 'healthy' or 'SCI'
subjects = [0,1,2,3,4,5]
tasks = ['open_close','grasp_patterns','single_fingers']

# Event fix configuration
# Set to True for the original fix (add trial_result events)
# Set to False for the new fix (add decoding_stop after trial_duration_expired)
add_trial_result_events = False

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

        session_ids = subj_cfg[f'task_{task}']['sessions_closed_loop']

        if not session_ids:
            print(f'No closed loop sessions found for task {task} in subject {subj_id}. Skipping...')
            continue

        for session_id in session_ids:
            # load data
            data_file = os.path.join(subj_data_folder, f'session_{session_id:02d}.npy')
            events_file = os.path.join(subj_data_folder, f'session_{session_id:02d}_events.pkl')

            data = load_data_numpy(data_file)
            timestamps = data[:,-1]
            data = data[:,0:num_channels_emg]  # remove the timestamp column and other channels not used

            time_emg = timestamps - timestamps[0]
            time_start = timestamps[0]

            events = load_pickle(events_file)

            # events: list of [event_name, event_time]
            new_events = []

            for event_name, event_time in events:
                new_events.append([event_name, event_time])
                
                if add_trial_result_events:
                    # Original fix: Add trial_result events
                    if event_name == 'grasp_success':
                        new_events.append(['trial_result_1', event_time])
                    elif event_name == 'grasp_error':
                        new_events.append(['trial_result_0', event_time])
                    elif event_name == 'trial_duration_expired':
                        new_events.append(['trial_result_2', event_time])
                else:
                    # New fix: Add decoding_stop after trial_duration_expired
                    if event_name == 'trial_duration_expired':
                        new_events.append(['trial_end', event_time])

            # Save the new events DataFrame overriding the old one
            new_events_file = os.path.join(subj_data_folder, f'session_{session_id:02d}_events.pkl')

            #pickle save the new events
            with open(new_events_file, 'wb') as f:
                pickle.dump(new_events, f)
                
            fix_type = "trial_result events" if add_trial_result_events else "decoding_stop events"
            print(f'  - Fixed events for session {session_id:02d} - Added {fix_type}')