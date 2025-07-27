# script for training the neural network model
import os
import numpy as np
import random
import yaml
import torch
from collections import deque
from matplotlib import pyplot as plt

from models.lstm_model import *
from utils.dataset_emg import *
from utils.nn_utils import *
from utils.data_utils import *
from utils.signal_filtering import *

# random seed for reproducibility
seed = 18
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# General params
subj_type = 'healthy' # 'healthy' or 'SCI'
subj = 0
session = 0
task = 'open_close' # options: ['open_close','single_fingers','grasp_patterns']
model_version = 'open_loop' # options ['open_loop','closed_loop']

subj_id = f'S{subj}'

# folders definition
config_folder = 'config'
data_folder = os.path.join('data', subj_type, subj_id, 'raw')
models_folder = os.path.join('models-subjects', subj_type, subj_id, task)

# file paths
subj_cfg_file = os.path.join('config', 'subjects', subj_type, f'{subj_id}.yaml')

# Load the config file
with open(subj_cfg_file, 'r') as f:
    subj_cfg = yaml.safe_load(f)

with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
    emg_proc_cfg = yaml.load(f, Loader=yaml.FullLoader)

with open(os.path.join(config_folder, 'features_params.yaml')) as f:
    features_cfg = yaml.load(f, Loader=yaml.FullLoader)

# params initialization
model_type = subj_cfg[f'task_{task}']['model_type'] # options: ['LSTM', 'TFM', 'CTFM']
model_file = os.path.join(models_folder, f'{model_type}_{model_version}.pth')

num_channels_emg = emg_proc_cfg['num_channels_emg']
fsample = emg_proc_cfg['fsample_emg']

seq_len = subj_cfg[f'task_{task}']['seq_len']
feature_type = features_cfg['feature_type']
feature_win_len = features_cfg['windows_length'][feature_type]['win_length']
feature_win_shift = features_cfg['windows_length'][feature_type]['win_shift']
dec_win_samples = round(fsample*feature_win_len)
dec_win_shift_samples = round(fsample*feature_win_shift)

# loading the model
print('Loading the model\n')
model = torch.load(model_file, weights_only=False, map_location=device)
model.eval()

for block_id in subj_cfg[f'task_{task}']['sessions_open_loop'][session]:
    print(f'- Processing open loop block {block_id} for task {task} (session {session})')

    data_file = os.path.join(data_folder, f'session_{block_id:02d}.npy')
    events_file = os.path.join(data_folder, f'session_{block_id:02d}_events.pkl')

    # Load data and events
    data = load_data_numpy(data_file)
    timestamps = data[:, -1]
    time_emg = timestamps - timestamps[0]
    data = data[:, 0:num_channels_emg]  # remove the timestamp column and other channels not used

    events = load_pickle(events_file)
    events_df = create_events_df(events, time_start=timestamps[0])

    # filtering the data
    if emg_proc_cfg['notch']:
        print('- Notch filtering')
        b_notch, a_notch, zi_notch = notch(
            notch_freq=emg_proc_cfg['notch']['freq'], 
            Q=emg_proc_cfg['notch']['Q'], 
            fs=fsample
        )
        zi_notch = np.transpose(np.array([zi_notch for _ in range(num_channels_emg)]))
        data,_ = notch_filter(data, b_notch, a_notch, zi_notch)

    if emg_proc_cfg['bandpass']:
        print('- Bandpass filtering')
        b_band, a_band, zi_band = butter_bandpass(
            lowcut=emg_proc_cfg['bandpass']['freq'][0], 
            highcut=emg_proc_cfg['bandpass']['freq'][1], 
            order=emg_proc_cfg['bandpass']['order'], 
            fs=fsample
        )
        zi_band = np.transpose(np.array([zi_band for _ in range(num_channels_emg)]))
        data,_ = butter_bandpass_filter(data, b_band, a_band, zi_band)

    # simulate the decoding process
    buffer_features = deque([], maxlen=seq_len)

    for _ in range(seq_len):
        buffer_features.append(np.zeros(num_channels_emg))

    num_bins = int(len(data) / dec_win_shift_samples)-3

    predictions = np.zeros((num_bins,))
    predictions_time = np.zeros((num_bins,))

    for bin_i in range(num_bins):
        start_sample = bin_i * dec_win_shift_samples
        end_sample = start_sample + dec_win_samples

        # extract the features for the current bin
        features = calc_features(data[start_sample:end_sample], feature_type)

        # update the buffer with the new features
        buffer_features.append(features)

        # convert to tensor
        input_tensor = torch.tensor(np.array(buffer_features), dtype=torch.float32).unsqueeze(0).to(device)

        # forward pass through the model
        with torch.no_grad():
            output = model(input_tensor)

        # process output (e.g., predictions)
        predictions[bin_i] = output.argmax(dim=1).cpu().numpy()
        predictions_time[bin_i] = time_emg[end_sample]


    # Plot predictions and signal
    grasp_start_events = events_df[events_df['event_type'] == 'grasp_start']['time'].values
    grasp_release_events = events_df[events_df['event_type'] == 'grasp_released']['time'].values

    plt.figure(figsize=(17,8))
    plt.subplot(2, 1, 1)
    plt.plot(predictions_time, predictions, linewidth=0.5, label='Predictions')

    for event in grasp_start_events:
        plt.axvline(x=event, color='g', linestyle='-', linewidth=2, label='Grasp Start')
    for event in grasp_release_events:
        plt.axvline(x=event, color='r', linestyle='-', linewidth=2, label='Grasp Release')

    plt.subplot(2, 1, 2)
    for ch in range(num_channels_emg):
        # normalized each channel respect to max abs value
        normalized_emg = data[:,ch] / np.max(np.abs(data[:,ch]))
        plt.plot(time_emg, ch+normalized_emg, linewidth=0.5)

    for event in grasp_start_events:
        plt.axvline(x=event, color='g', linestyle='-', linewidth=2)
    for event in grasp_release_events:
        plt.axvline(x=event, color='r', linestyle='-', linewidth=2)

    plt.show()