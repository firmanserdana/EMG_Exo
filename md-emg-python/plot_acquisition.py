import os
import numpy as np
import yaml
import pickle
from matplotlib import pyplot as plt

from utils.data_utils import *
from utils.signal_filtering import *

subj_type = 'SCI' # 'healthy' or 'SCI'
subj = 3
session_num = 1
rest_mvc_data = False # to export the rest and MVC data file

# folders definition
config_folder = 'config'
data_folder = os.path.join('data', subj_type, f'S{subj}', 'raw')

# loading config file
with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
    emg_proc_cfg = yaml.load(f, Loader=yaml.FullLoader)

channel_range = emg_proc_cfg.get('channel_range', [0, emg_proc_cfg['num_channels_emg']])
num_channels_emg = channel_range[1] - channel_range[0]  # actual number of recorded channels

total_data = []

# loading data
if rest_mvc_data:
    file_name = f'{data_folder}/rest_mvc.npy'
else:
    file_name = f'{data_folder}/session_{session_num:02d}.npy'

data = load_data_numpy(file_name)

timestamps = data[:,-1]
data = data[:,0:num_channels_emg]  # remove the timestamp column and other channels not used

# load events
if not rest_mvc_data:
    events = load_pickle(f'{data_folder}/session_{session_num:02d}_events.pkl')    

# processing the data
data_proc = data
fsample = emg_proc_cfg['fsample_emg']

# filtering the data
if emg_proc_cfg['notch']:
    print('- Notch filtering')
    b_notch, a_notch, zi_notch = notch(
        notch_freq=emg_proc_cfg['notch']['freq'], 
        Q=emg_proc_cfg['notch']['Q'], 
        fs=fsample
    )
    zi_notch = np.transpose(np.array([zi_notch for _ in range(num_channels_emg)]))
    data_proc,_ = notch_filter(data_proc, b_notch, a_notch, zi_notch)

if emg_proc_cfg['bandpass']:
    print('- Bandpass filtering')
    b_band, a_band, zi_band = butter_bandpass(
        lowcut=emg_proc_cfg['bandpass']['freq'][0], 
        highcut=emg_proc_cfg['bandpass']['freq'][1], 
        order=emg_proc_cfg['bandpass']['order'], 
        fs=fsample
    )
    zi_band = np.transpose(np.array([zi_band for _ in range(num_channels_emg)]))
    data_proc,_ = butter_bandpass_filter(data_proc, b_band, a_band, zi_band)

# plot the data
time_emg = timestamps - timestamps[0]
start_time = timestamps[0]

# make fig full screen
plt.figure(figsize=(17,8))

for ch in range(num_channels_emg):
    # normalized each channel respect to max abs value
    normalized_emg = data_proc[:,ch] / np.max(np.abs(data_proc[:,ch]))
    plt.plot(time_emg, ch+normalized_emg, linewidth=0.5)

if not rest_mvc_data:
    # retrieving events (convert to numpy arrays for scalar subtraction)
    grasps_start = np.array([event['timestamp'] for event in events if event['event_type'].startswith('grasp_start')]) - timestamps[0]
    grasp_released = np.array([event['timestamp'] for event in events if event['event_type'] == 'grasp_released']) - timestamps[0]

    # plot the events
    for event in grasps_start:
        plt.axvline(x=event, color='g', linestyle='-', linewidth=2)

    for event in grasp_released:
        plt.axvline(x=event, color='r', linestyle='-', linewidth=2)

# plt.xticks(np.arange(0, time_emg[-1], 1000))
plt.xlim([0, time_emg[-1]])
plt.yticks(np.arange(0, num_channels_emg, 1), np.arange(1, num_channels_emg+1, 1))
plt.ylim([-0.75, num_channels_emg-0.25])
plt.ylabel('EMG channels')
plt.xlabel('Time (s)')
plt.title('EMG data (pre-processed)')
plt.show()