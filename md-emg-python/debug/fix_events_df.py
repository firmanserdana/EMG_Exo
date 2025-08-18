import sys
import os
import yaml
import numpy as np
import pandas as pd
import pickle
import argparse

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_utils import *


def parse_args():
    parser = argparse.ArgumentParser(description="Fix/augment events pickles across subjects/sessions/tasks")
    parser.add_argument("--subj-type", choices=["healthy", "SCI"], default="SCI", help="Cohort folder")
    parser.add_argument(
        "--subjects",
        type=int,
        nargs="+",
        default=[0, 1, 2, 3, 4, 5],
        help="Subject indices to process (space-separated)",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=["open_close", "grasp_patterns", "single_fingers"],
        help="Tasks to process",
    )
    parser.add_argument(
        "--add-trial-result-events",
        action="store_true",
        help="Use original fix to add trial_result events instead of trial_end",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    subj_type = args.subj_type
    subjects = args.subjects
    tasks = args.tasks

    # Event fix configuration
    # True for original fix (add trial_result events)
    # False for new fix (add trial_end after trial_duration_expired)
    add_trial_result_events = args.add_trial_result_events

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
                timestamps = data[:, -1]
                data = data[:, 0:num_channels_emg]  # remove the timestamp column and other channels not used

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
                        # New fix: Add trial_end after trial_duration_expired
                        if event_name == 'trial_duration_expired':
                            new_events.append(['trial_end', event_time])

                # Save the new events DataFrame overriding the old one
                new_events_file = os.path.join(subj_data_folder, f'session_{session_id:02d}_events.pkl')

                # pickle save the new events
                with open(new_events_file, 'wb') as f:
                    pickle.dump(new_events, f)

                fix_type = "trial_result events" if add_trial_result_events else "trial_end events"
                print(f'  - Fixed events for session {session_id:02d} - Added {fix_type}')


if __name__ == "__main__":
    main()