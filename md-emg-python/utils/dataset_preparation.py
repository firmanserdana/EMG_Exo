import os
import yaml
import pickle

from utils.data_utils import *

def dataset_preparation(subj_type, subj, task, acquisition_type, session):
    """Prepare dataset for EMG decoding."""
    print(f'Using subject type: {subj_type}, subject: {subj}, task: {task}, acquisition type: {acquisition_type}')

    # folders definition
    config_folder = 'config'
    data_folder_src = os.path.join('data', subj_type, f'S{subj}', 'raw') # source folder for the data
    data_folder_mvc = os.path.join('data', subj_type, f'S{subj}', 'mvc') # source folder for the data
    data_folder_dest = os.path.join('data', subj_type, f'S{subj}') # destination folder for the processed data

    # file paths
    subj_config_file = os.path.join('config', 'subjects', subj_type, f'S{subj}.yaml')
    emg_proc_conf_file = os.path.join('config', 'emg_signal_processing.yaml')
    features_conf_file = os.path.join('config', 'features_params.yaml')

    # Load the config file
    with open(subj_config_file, 'r') as f:
        subj_cfg = yaml.safe_load(f)

    with open(emg_proc_conf_file, 'r') as f:
        emg_proc_cfg = yaml.safe_load(f)

    with open(features_conf_file, 'r') as f:
        features_cfg = yaml.safe_load(f)

    add_hand_open_class = features_cfg.get('add_hand_open_class', False)
    add_rest_class = features_cfg.get('add_rest_class', True)

    if task not in ['grasp_patterns', 'single_fingers']:
        add_hand_open_class = True

    subj_id = f'S{subj}'

    # create folders
    os.makedirs(data_folder_dest, exist_ok=True)

    if features_cfg['normalization'] == 'mvc':
        mvc_file = os.path.join(data_folder_mvc, 'dataset_mvc.pkl')
    else:
        mvc_file = None

    dest_data_file = os.path.join(data_folder_dest, f'{acquisition_type}_{task}_data.pkl')
    dest_labels_enc_file = os.path.join(data_folder_dest, f'{acquisition_type}_{task}_labels_encoder.pkl')

    # variables initialization
    total_neural_features = []
    total_labels = []
    labels_encoder = None
    seq_len = subj_cfg[f'task_{task}']['seq_len']
    num_features = 0
    closed_loop_start_idx = None

    # open loop data
    if acquisition_type == 'open_loop' or acquisition_type == 'both':
        if session in subj_cfg[f'task_{task}']['sessions_open_loop']:
            print(f'- Processing open loop session {session} for task {task}')

            neural_features, labels, labels_encoder = extract_neural_features(
                data_file=os.path.join(data_folder_src, f'session_{session:02d}.npy'),
                events_file=os.path.join(data_folder_src, f'session_{session:02d}_events.pkl'),
                emg_proc_cfg=emg_proc_cfg,
                features_cfg=features_cfg,
                mvc_file=mvc_file,
                add_hand_open_class=add_hand_open_class,
                add_rest_class=add_rest_class,
                labels_encoder=labels_encoder,
                acq_type='open_loop',
                seq_len=seq_len
            ) 

            total_neural_features.append(neural_features)
            total_labels.append(labels)

            num_features += len(neural_features)

    # closed loop data
    if acquisition_type == 'closed_loop' or acquisition_type == 'both':
        closed_loop_start_idx = num_features

        if session in subj_cfg[f'task_{task}']['sessions_closed_loop']:
            print(f'- Processing closed loop session {session} for task {task}')

            neural_features, labels, _ = extract_neural_features(
                data_file=os.path.join(data_folder_src, f'session_{session:02d}.npy'),
                events_file=os.path.join(data_folder_src, f'session_{session:02d}_events.pkl'),
                emg_proc_cfg=emg_proc_cfg,
                features_cfg=features_cfg,
                mvc_file=mvc_file,
                add_hand_open_class=add_hand_open_class,
                add_rest_class=add_rest_class,
                labels_encoder=labels_encoder,
                acq_type='closed_loop',
                seq_len=seq_len
            ) 

            total_neural_features.append(neural_features)
            total_labels.append(labels)

    if len(total_neural_features) == 0:
        raise ValueError(f'No sessions data found for task {task}.')

    # concatenate all features and labels
    total_neural_features = np.concatenate(total_neural_features, axis=0)
    total_labels = np.concatenate(total_labels, axis=0)

    # one hot encoding with potential label smoothing
    num_classes = len(labels_encoder.classes_)

    total_labels = one_hot_encoding(total_labels, num_classes, features_cfg['labels_smoothing'])

    # Save the data
    data = {
        'neural_data': total_neural_features,
        'labels': total_labels,
        'closed_loop_start_idx': closed_loop_start_idx
    }

    with open(dest_data_file, "wb") as f:
        pickle.dump(data, f)

    # Save the labels encoder
    with open(dest_labels_enc_file, "wb") as f:
        pickle.dump({'labels_encoder':labels_encoder}, f)

# Backward-compatible alias (correct spelling)
def dataset_preration(subj_type, subj, task, acquisition_type, session):
    """Alias for dataset_preparation to maintain backward compatibility."""
    return dataset_preparation(subj_type, subj, task, acquisition_type, session)