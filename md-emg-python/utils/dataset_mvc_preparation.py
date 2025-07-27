import os
import yaml
import pickle

from utils.data_utils import *

# General params
subj_type = 'SCI' # 'healthy' or 'SCI' - TODO: make this a parameter of the script
subj = 1 # TODO: make this a parameter of the script

subj_id = f'S{subj}'

# folders definition
config_folder = 'config'
data_folder_mvc = os.path.join('data', subj_type, subj_id, 'mvc') # source folder for the data

# file paths
subj_config_file = os.path.join('config', 'subjects', subj_type, f'{subj_id}.yaml')
emg_proc_conf_file = os.path.join('config', 'emg_signal_processing.yaml')

# Load the config file
with open(emg_proc_conf_file, 'r') as f:
    emg_proc_cfg = yaml.safe_load(f)

dest_data_file = os.path.join(data_folder_mvc, f'dataset_mvc.pkl')

total_neural_features = []
total_labels = []
labels_encoder = None

mvc_file = os.path.join(data_folder_mvc, f'mvc.npy')
events_file = os.path.join(data_folder_mvc, f'mvc_events.pkl')

mvc_mean = extract_mvc_data(
    mvc_file=mvc_file,
    events_file=events_file,
    emg_proc_cfg=emg_proc_cfg
)

# Save the data
data = {
    'mvc_mean': mvc_mean
}

with open(dest_data_file, "wb") as f:
    pickle.dump(data, f)