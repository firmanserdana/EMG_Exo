import re
import os
import math
import pickle
import yaml
import numpy as np
import pandas as pd
import copy
import torch
import torch.nn.functional as F
from sklearn.preprocessing import LabelEncoder
from scipy import signal as scipy_signal

from . import signal_filtering

def load_data_numpy(file_name):
    """
    Load data from a numpy file.
    
    Parameters:
    - file_path: Path to the numpy file.
    
    Returns:
    - data: Loaded data as a numpy array.
    """
    total_data = []

    with open(file_name, 'rb') as f:
        while True:
            try:
                data = np.load(f)
                total_data.append(data)
            except EOFError:
                break
            except ValueError:
                break

    return np.vstack(total_data)

def load_pickle(path):
    """
    Load data from a pickle file.

    Parameters:
        path (str): Path to the pickle file.
    Returns:
        data: Loaded data from the pickle file.
    """
    with open(path, 'rb') as f:
        data = pickle.load(f)

    return data

def create_events_df(events, time_start):
    """
    Create a DataFrame from event data.

    Parameters:
        events (list): List of event dictionaries.
        time_start (float): Start time of the recording.
    Returns:
        pd.DataFrame: DataFrame containing event data.
    """
    
    if not events:
        return pd.DataFrame()

    events_df = []

    for event in events:
        # Handle both old tuple format and new dictionary format
        if isinstance(event, dict):
            event_type = event.get('event_type', '')
            timestamp = event.get('timestamp', 0)
        else:
            # Legacy tuple format: (event_type, timestamp)
            event_type = event[0]
            timestamp = event[1]

        # Check if event_type matches 'grasp_start_{id}'
        match = re.match(r'(grasp_start|grasp_objective_start|grasp_decoded|trial_result)_(\d+)', event_type)

        if match:
            event_type = match.group(1)
            event_id = int(match.group(2))
        else:
            event_id = np.nan

        event_data = {
            'event_type': event_type,
            'event_id': event_id,
            'time': timestamp - time_start
        }

        events_df.append(event_data)

    # Creating DataFrame
    events_df = pd.DataFrame(events_df)
    events_df['event_id'] = events_df['event_id'].astype('Int64')
    
    return events_df

# load pickle matrix
def load_pickle_matrix(path):
    """
    Load a matrix from a pickle file, which may contain multiple arrays concatenated.
    
    Parameters:
        path (str): Path to the pickle file.
    Returns:
        predictions (np.ndarray): Concatenated predictions from the pickle file. 
    """
    predictions = []

    with open(path, 'rb') as f:
        while True:
            try:
                predictions.append(pickle.load(f))
            except EOFError:
                break

    return np.concatenate(predictions, axis=0)

def calc_features(data, feature_type, fsample=1000):
    """
    Calculate features from the EMG data based on the specified feature type.
    
    Parameters:
    - data: EMG data as a numpy array.
    - feature_type: Type of feature to extract (e.g., 'mav', 'rms', 'envelope', etc.).
    - fsample: Sampling frequency in Hz (default: 1000Hz).
    
    Returns:
    - features: Extracted features as a numpy array.
    """

    features = None

    if 'mav' in feature_type:
        features = np.mean(np.abs(data), axis=0)
    elif 'rms' in feature_type:
        features = np.sqrt(np.mean(data ** 2, axis=0))
    elif 'raw' in feature_type:
        features = data
    else:
        raise ValueError(f"Feature type '{feature_type}' is not supported.")
    
    if 'envelope' in feature_type:
        # Compute envelope by rectifying and low-pass filtering at 20Hz
        
        # Rectify the signal (absolute value)
        rectified = np.abs(data)
        
        # Design low-pass filter at 20Hz
        cutoff_freq = 20.0  # Hz
        nyquist_freq = fsample / 2.0
        normalized_cutoff = cutoff_freq / nyquist_freq
        
        # Butterworth low-pass filter (4th order)
        b, a = scipy_signal.butter(4, normalized_cutoff, btype='low')
        
        # Apply filter to each channel and compute 90th percentile
        features_env = np.zeros(rectified.shape[1])

        for ch in range(rectified.shape[1]):
            envelope_signal = scipy_signal.filtfilt(b, a, rectified[:, ch])
            features_env[ch] = np.mean(envelope_signal)

        if features is None:
            features = features_env
        else:
            # If features already exist, concatenate the envelope features
            features = np.concatenate((features, features_env), axis=0)

    return features

def calc_features_multi_win(data, data_raw, feature_type, params):
    """
    Calculate features from the EMG data based on the specified feature type.
    
    Parameters:
    - data: EMG data as a numpy array.
    - data_raw: Raw EMG data as a numpy array (used for some feature types).
    - feature_type: Type of feature to extract (e.g., 'mav', 'rms', etc.).
    - params: Dictionary containing parameters for feature extraction, including:
        - win_len: Length of the window for feature extraction.
        - win_shift: Shift of the window for feature extraction.
        - freq_params: Parameters for frequency-based features (if applicable).
    
    Returns:
    - features: Extracted features as a numpy array.
    """

    win_shift = params['win_shift']
    win_len = params['win_len']

    num_channels = data.shape[1]
    num_bins = math.floor((data.shape[0] - win_len) / win_shift) + 1

    if 'freq' in feature_type:
        num_freq_bins = len(params['freq_params']['fft_bands'])

    if 'raw' in feature_type:
        if 'freq' in feature_type:
            features = np.zeros((num_bins, win_len, num_channels))
        else:
            features = np.zeros((num_bins, win_len, num_channels + num_channels*num_freq_bins))
    elif 'freq' in feature_type:
        features = np.zeros((num_bins, num_channels+num_channels*num_freq_bins))
    elif '+' in feature_type:
        num_features = feature_type.count('+') + 1
        features = np.zeros((num_bins, num_channels * num_features))  # For features like 'rms+envelope'
    else:
        features = np.zeros((num_bins, num_channels))

    for i in range(num_bins):
        start = i * win_shift
        end = start + win_len

        features[i] = calc_features(data[start:end, :], feature_type, params['fsample'])

    if 'freq' in feature_type:
        freq_features, freqs = extract_fft_features(
            signal=data_raw,
            sampling_rate=params['fsample'],
            fft_params=params['freq_params']
        )

        freq_features, _ = group_freq_features(
            freq_features=freq_features, 
            freqs=freqs, 
            intervals=params['freq_params']['fft_bands']
        )
        
        # freq_features shape: (num_channels, num_bins, num_freq_bins)
        freq_features = freq_features.transpose(1, 0, 2)  # (num_bins, num_channels, num_freq_bins)
        features[:, num_channels:] = freq_features.reshape(num_bins, -1)  # (num_bins, num_channels * num_freq_bins)

    return features

def extract_mvc_data(mvc_file, events_file, emg_proc_cfg):
    """
    Extract neural features from the data file based on the specified feature type.
    
    Parameters:
    
    Returns:
    """
    channel_range = emg_proc_cfg.get('channel_range', [0, emg_proc_cfg['num_channels_emg']])
    num_channels = channel_range[1] - channel_range[0]
    fsample = emg_proc_cfg['fsample_emg']

    # Load data and events
    data = load_data_numpy(mvc_file)

    timestamps = data[:,-1]
    time_start = timestamps[0]  # start time of the recording
    timestamps = timestamps - time_start # normalize timestamps to start at 0
    data = data[:,0:num_channels]  # remove the timestamp column and other channels not used

    # load events
    events = load_pickle(events_file)
    events_df = create_events_df(events, time_start=time_start)

    # filtering the data
    if emg_proc_cfg['notch']:
        print('  + Notch filtering')
        b_notch, a_notch, zi_notch = signal_filtering.notch(
            notch_freq=emg_proc_cfg['notch']['freq'], 
            Q=emg_proc_cfg['notch']['Q'], 
            fs=fsample
        )
        zi_notch = np.transpose(np.array([zi_notch for _ in range(num_channels)]))
        data,_ = signal_filtering.notch_filter(data, b_notch, a_notch, zi_notch)

    if emg_proc_cfg['bandpass']:
        print('  + Bandpass filtering')
        b_band, a_band, zi_band = signal_filtering.butter_bandpass(
            lowcut=emg_proc_cfg['bandpass']['freq'][0], 
            highcut=emg_proc_cfg['bandpass']['freq'][1], 
            order=emg_proc_cfg['bandpass']['order'], 
            fs=fsample
        )
        zi_band = np.transpose(np.array([zi_band for _ in range(num_channels)]))
        data,_ = signal_filtering.butter_bandpass_filter(data, b_band, a_band, zi_band)

    mvc_start_time = events_df[events_df['event_type']=='mvc_start']['time'].values[0]
    mvc_end_time = events_df[events_df['event_type']=='mvc_end']['time'].values[0]

    mvc_start_sample = np.searchsorted(timestamps, mvc_start_time, side='left')
    mvc_end_sample = np.searchsorted(timestamps, mvc_end_time, side='left')

    mvc_data_mean = np.mean(data[mvc_start_sample:mvc_end_sample, :], axis=0)

    return mvc_data_mean

def extract_fft_features(signal, sampling_rate, fft_params):
    """
    Extract fft features from a neural signal using FFT with zero-padding and overlapping windows.

    Parameters:
    - signal: numpy.ndarray or torch.Tensor, shape (n_bins, n_channels)
    - sampling_rate: int, sampling rate in Hz
    - fft_params: dict, must contain the following
        + window_size: float, window size in seconds
        + window_shift: float, number of seconds to shift the window
        + freq_range: tuple, frequency range to extract features from
        + zero_padding_factor: int, factor by which to increase the segment length with zero-padding, default=2

    Returns:
    - freq_features: numpy, shape (n_channels, n_windows, n_freqs)
    """
    # Convert signal to torch.Tensor if it is a numpy.ndarray
    if isinstance(signal, np.ndarray):
        signal = torch.from_numpy(signal)

    window_size = fft_params['fft_win_size']
    window_shift = fft_params['fft_win_shift']
    freq_range = fft_params['fft_freq_range']
    zero_padding_factor = fft_params.get('zero_padding_factor', 2)

    n_samples = len(signal)

    if freq_range is not None:
        min_freq, max_freq = freq_range

    # Convert window size and window shift from seconds to samples
    window_size_samples = int(window_size * sampling_rate)
    window_shift_samples = int(window_shift * sampling_rate)

    # Define Hanning window and padding length
    hanning_window = torch.hann_window(window_size_samples)
    padded_len = window_size_samples * zero_padding_factor
    padding_samples = padded_len - window_size_samples

    # Initialize the frequency features tensor
    freq_features = []

    # Calculate the number of windows with overlap
    for start in range(0, n_samples - window_size_samples + 1, window_shift_samples):
        end = start + window_size_samples

        # Extract the windowed segment
        segment = signal[start:end, :].T

        # Apply Hanning window
        segment = segment * hanning_window

        # Zero-padding (pad only at the end)
        padded_segment = torch.nn.functional.pad(segment, (0, padding_samples))

        # Apply rFFT
        rfft_result = torch.abs(torch.fft.rfft(padded_segment, dim=-1))

        # Calculate the frequency bins
        freqs = torch.fft.rfftfreq(padded_len, d=1/sampling_rate)

        # Extract the desired frequency range if any
        if freq_range is not None:
            freq_mask = (freqs.numpy() >= min_freq) & (freqs.numpy() <= max_freq)
            freq_features.append(rfft_result[:, freq_mask])
        else:
            freq_features.append(rfft_result)

    # Stack the frequency features
    freq_features = torch.stack(freq_features, dim=1).numpy()

    if freq_range is not None:
        freqs = freqs[freq_mask]

    return freq_features, freqs

def group_freq_features(freq_features, freqs, intervals=None, uniform_resolution=None):
    """
    Group frequency features into specific bands defined by intervals or with a specified uniform resolution.
    
    Parameters:
    - freq_features: 3D NumPy array of shape (n_samples, n_channels, n_freqs)
                     Power spectral density values for each sample and channel.
    - freqs: 1D NumPy array of frequency values corresponding to the last dimension of freq_features.
    - intervals: List of [start_freq, end_freq] pairs defining specific frequency bands.
                 Example: [[50, 150], [150, 500], [500, 1000]]
                 If None, uniform_resolution should be used.
    - uniform_resolution: Float specifying the width of each frequency band for uniform grouping.
                          Example: 100 for bands like [min, min+100], [min+100, min+200], etc.
                          Ignored if intervals are provided.

    Returns:
    - grouped_freq_features: 3D NumPy array of shape (n_samples, n_channels, n_bands)
                             Average power within each frequency band.
    - bands: 2D NumPy array of shape (n_bands, 2) indicating the frequency ranges of each band.
    - freqs_in_bands: List of 1D NumPy arrays, each containing the frequencies within the corresponding band.
    """

    # Validate inputs
    if intervals is not None and uniform_resolution is not None:
        raise ValueError("Provide either 'intervals' or 'uniform_resolution', not both.")

    if intervals is None and uniform_resolution is None:
        raise ValueError("Either 'intervals' or 'uniform_resolution' must be provided.")

    if isinstance(freqs, torch.Tensor):
        freqs = freqs.cpu().numpy()

    # Determine frequency bands
    if intervals is not None:
        n_bands = len(intervals)
        bands = np.array(intervals)
    else:
        # Calculate the number of frequency bands based on uniform resolution
        min_freq = freqs.min()
        max_freq = freqs.max()
        n_bands = int(np.ceil((max_freq - min_freq) / uniform_resolution))

        bands = np.zeros((n_bands, 2))
        for i in range(n_bands):
            start_freq = min_freq + i * uniform_resolution
            end_freq = min(min_freq + (i + 1) * uniform_resolution, max_freq)
            bands[i] = [start_freq, end_freq]

    # Initialize the grouped frequency features tensor
    n_samples, n_channels, _ = freq_features.shape
    grouped_freq_features = np.zeros((n_samples, n_channels, n_bands))

    # Initialize a list to hold frequencies used in each band
    freqs_in_bands = []

    # Group frequency features
    for i in range(n_bands):
        start_freq, end_freq = bands[i]

        # Select the frequencies within the specified range
        freq_range = (freqs >= start_freq) & (freqs < end_freq)
        selected_freqs = freqs[freq_range]
        selected_freq_features = freq_features[:, :, freq_range]  # Shape: (n_samples, n_channels, n_selected_freqs)

        # Store the frequencies used in this band
        freqs_in_bands.append(selected_freqs)

        if selected_freqs.size == 0:
            grouped_freq_features[:, :, i] = np.nan  # Or 0.0, based on preference
            continue

        # Calculate the mean of the frequency features in the band
        grouped_freq_features[:, :, i] = np.mean(selected_freq_features, axis=-1)

    return grouped_freq_features, freqs_in_bands

def zscore_normalization(signal, win_len):
    """
    Apply z-score normalization to the signal using a moving window.

    Parameters:
        - signal (np.ndarray): Input signal to be normalized.
        - win_len (int): Length of the moving window for normalization.
    Returns:
        - output (np.ndarray): Z-score normalized signal.
    """
    # Pad with the first win_len samples of the signal
    padding_data = signal[:win_len, :]
    padded = np.concatenate([padding_data, signal], axis=0)

    # Cumulative sum and sum of squares
    cumsum = np.cumsum(padded, axis=0)
    cumsum2 = np.cumsum(padded ** 2, axis=0)

    # Compute moving sums and stds
    sum_win = cumsum[win_len:] - cumsum[:-win_len]
    sum_sq_win = cumsum2[win_len:] - cumsum2[:-win_len]

    mean = sum_win / win_len
    var = sum_sq_win / win_len - mean ** 2
    std = np.sqrt(np.maximum(var, 0)) + 1e-8

    output = (signal - mean) / std

    return output

def one_hot_encoding(labels, num_classes, smoothing=0):
    # Create a matrix filled with smoothing/(num_classes-1) for the one-hot encoding
    output = np.full((labels.size, num_classes), smoothing / (num_classes - 1), dtype=np.float32)

    # Set the true class to 1-smoothing
    output[np.arange(labels.size), labels.astype(int)] = 1.0 - smoothing

    return output

def extract_neural_features(
        data_file, 
        events_file, 
        emg_proc_cfg, 
        features_cfg, 
        mvc_file=None, 
        add_hand_open_class=False, 
        add_rest_class=False,
        labels_encoder=None, 
        acq_type='open_loop', 
        seq_len=1, 
        logging=True
    ):
    """
    Extract neural features from the data file based on the specified feature type.
    
    Parameters:
    - data_file: Path to the data file containing EMG signals.
    - events_file: Path to the events file containing event markers.
    - emg_proc_conf: Configuration for EMG signal processing.
    - features_cfg: Configuration for feature extraction.
    - mvc_file: Optional path to the MVC file for normalization.
    - add_hand_open_class: Boolean indicating whether to remove or not the hand open class.
    - add_rest_class: Boolean indicating whether to add a rest class to the labels.
    - labels_encoder: LabelEncoder already initialized to transform labels (optional).
    - acq_type: Type of acquisition ('open_loop' or 'closed_loop').
    - seq_len: Sequence length for the features (default is 1).
    - logging: Boolean indicating whether to log the processing steps.
    
    Returns:
    - neural_features: Extracted neural features.
    - labels: Corresponding labels for the features.
    """
    channel_range = emg_proc_cfg.get('channel_range', [0, emg_proc_cfg['num_channels_emg']])
    num_channels = channel_range[1] - channel_range[0]
    fsample = emg_proc_cfg['fsample_emg']

    feature_type = features_cfg['feature_type']
    feature_win_len = int(features_cfg['windows_length'][feature_type]['win_length'] * fsample)
    feature_win_shift = int(features_cfg['windows_length'][feature_type]['win_shift'] * fsample)

    features_params = {
        'win_len': feature_win_len,
        'win_shift': feature_win_shift,
        'fsample': fsample
    }

    if 'freq' in feature_type:
        features_params['freq_params'] = features_cfg['freq_params']

    # Load data and events
    data = load_data_numpy(data_file)

    timestamps = data[:,-1]
    time_start = timestamps[0]  # start time of the recording
    timestamps = timestamps - time_start # normalize timestamps to start at 0
    data = data[:,0:num_channels]  # remove the timestamp column and other channels not used

    # load events
    events = load_pickle(events_file)
    events_df = create_events_df(events, time_start=time_start)

    # filtering the data
    if 'notch' in emg_proc_cfg and emg_proc_cfg['notch']:
        if logging:
            print('  + Notch filtering')

        b_notch, a_notch, zi_notch = signal_filtering.notch(
            notch_freq=emg_proc_cfg['notch']['freq'], 
            Q=emg_proc_cfg['notch']['Q'], 
            fs=fsample
        )
        zi_notch = np.transpose(np.array([zi_notch for _ in range(num_channels)]))
        data,_ = signal_filtering.notch_filter(data, b_notch, a_notch, zi_notch)

    if 'bandpass' in emg_proc_cfg and emg_proc_cfg['bandpass']:
        if logging:
            print('  + Bandpass filtering')

        b_band, a_band, zi_band = signal_filtering.butter_bandpass(
            lowcut=emg_proc_cfg['bandpass']['freq'][0], 
            highcut=emg_proc_cfg['bandpass']['freq'][1], 
            order=emg_proc_cfg['bandpass']['order'], 
            fs=fsample
        )
        zi_band = np.transpose(np.array([zi_band for _ in range(num_channels)]))
        data,_ = signal_filtering.butter_bandpass_filter(data, b_band, a_band, zi_band)

    data_raw = copy.deepcopy(data)  # keep a copy of the raw data for later use

    # Normalization
    if features_cfg['normalization'] == 'mvc':
        # MVC normalization
        if logging:
            print('  + MVC normalization')
        
        mvc_mean = load_pickle(mvc_file)['mvc_mean']
        
        data = data / mvc_mean
    elif features_cfg['normalization'] == 'zscore':
        # Z-score normalization
        if logging:
            print('  + Z-score normalization')

        zscore_win_len = int(features_cfg['normalization_params']['zscore']['win_length'] * fsample)

        data = zscore_normalization(data, zscore_win_len)
    
    num_trials = len(events_df[events_df['event_type']=='trial_end'])

    # initilizing the events name based on the acquisition type
    start_event_name = features_cfg[f'{acq_type}_events']['grasp_start_name']
    start_event_offset = int(features_cfg[f'{acq_type}_events']['grasp_start_time'] * fsample)
    end_event_name = features_cfg[f'{acq_type}_events']['grasp_end_name']
    end_event_offset = int(features_cfg[f'{acq_type}_events']['grasp_end_time'] * fsample)

    # retrieving the toi for each trial
    if acq_type == 'open_loop':
        grasp_labels_raw = events_df[events_df['event_type']=='grasp_start']['event_id'].values
    else:
        grasp_labels_raw = events_df[events_df['event_type']=='grasp_objective_start']['event_id'].values

    grasps_start = events_df[events_df['event_type']==start_event_name]
    grasps_start_time = grasps_start['time'].values
    grasps_end = events_df[events_df['event_type']==end_event_name]
    grasps_end_time = grasps_end['time'].values

    # retrieving the start and end samples for each grasp
    grasps_start_samples = np.searchsorted(timestamps, grasps_start_time, side='left')
    grasps_end_samples = np.searchsorted(timestamps, grasps_end_time, side='left')

    if add_rest_class:
        rest_start_name = features_cfg[f'{acq_type}_events']['rest_start_name']
        rest_start_offset = int(features_cfg[f'{acq_type}_events']['rest_start_time'] * fsample)
        rests_start = events_df[events_df['event_type']==rest_start_name]
        rests_start_time = rests_start['time'].values
        rests_start_samples = np.searchsorted(timestamps, rests_start_time, side='left')

    # extracting the neural features
    neural_features = []
    labels = []

    print(f'  + Extracting {feature_type} features')

    for trl in range(num_trials):
        grasp_start_sample = grasps_start_samples[trl] + start_event_offset
        grasp_end_sample = grasps_end_samples[trl] + end_event_offset
        grasp_label = grasp_labels_raw[trl]

        if not(add_hand_open_class) and grasp_label == 0:
            # skip the hand open class
            continue

        # add grasp features
        grasp_features = calc_features_multi_win(
            data=data[grasp_start_sample:grasp_end_sample, :],
            data_raw=data_raw[grasp_start_sample:grasp_end_sample, :],
            feature_type=feature_type,
            params=features_params
        )
        
        if add_rest_class:
            grasp_label += 1  # increment the label to account for the rest class that is always 0

            rest_start_sample = rests_start_samples[trl] + rest_start_offset
            rest_end_sample = rest_start_sample - rest_start_offset

            rest_features = calc_features_multi_win(
                data=data[rest_start_sample:rest_end_sample, :],
                data_raw=data_raw[rest_start_sample:rest_end_sample, :],
                feature_type=feature_type,
                params=features_params
            )

            # append the rest features
            neural_features.append(rest_features)
            labels.append(np.repeat(0, len(rest_features)))  # rest class is always 0

        neural_features.append(grasp_features)
        labels.append(np.repeat(grasp_label, len(grasp_features)))

    neural_features = np.concatenate(neural_features, axis=0)
    labels = np.concatenate(labels, axis=0)

    if labels_encoder is not None:
        # if labels_encoder is provided, use it to transform the labels
        labels = labels_encoder.transform(labels)
    else:
        # creating and fitting the labels encoder
        labels_encoder = LabelEncoder()
        labels = labels_encoder.fit_transform(labels)

    return neural_features, labels, labels_encoder

def extract_neural_data(data_file, events_file, emg_proc_cfg, logging=True):
    """
    Extract neural features from the data file based on the specified feature type.
    
    Parameters:
    - data_file: Path to the data file containing EMG signals.
    - events_file: Path to the events file containing event markers.
    - emg_proc_cfg: Configuration for EMG signal processing.
    - mvc_file: Optional path to the MVC file for normalization.
    - acq_type: Type of acquisition ('open_loop' or 'closed_loop').
    - logging: Boolean indicating whether to log the processing steps.
    
    Returns:
    - neural_features: Extracted neural features.
    - labels: Corresponding labels for the features.
    """
    channel_range = emg_proc_cfg.get('channel_range', [0, emg_proc_cfg['num_channels_emg']])
    num_channels = channel_range[1] - channel_range[0]
    fsample = emg_proc_cfg['fsample_emg']

    # Load data and events
    data = load_data_numpy(data_file)

    timestamps = data[:,-1]
    time_start = timestamps[0]  # start time of the recording
    timestamps = timestamps - time_start # normalize timestamps to start at 0
    data = data[:,0:num_channels]  # remove the timestamp column and other channels not used

    # load events
    events = load_pickle(events_file)
    events_df = create_events_df(events, time_start=time_start)

    # filtering the data
    if 'notch' in emg_proc_cfg and emg_proc_cfg['notch']:
        if logging:
            print('  + Notch filtering')

        b_notch, a_notch, zi_notch = signal_filtering.notch(
            notch_freq=emg_proc_cfg['notch']['freq'], 
            Q=emg_proc_cfg['notch']['Q'], 
            fs=fsample
        )
        zi_notch = np.transpose(np.array([zi_notch for _ in range(num_channels)]))
        data,_ = signal_filtering.notch_filter(data, b_notch, a_notch, zi_notch)

    if 'bandpass' in emg_proc_cfg and emg_proc_cfg['bandpass']:
        if logging:
            print('  + Bandpass filtering')

        b_band, a_band, zi_band = signal_filtering.butter_bandpass(
            lowcut=emg_proc_cfg['bandpass']['freq'][0], 
            highcut=emg_proc_cfg['bandpass']['freq'][1], 
            order=emg_proc_cfg['bandpass']['order'], 
            fs=fsample
        )
        zi_band = np.transpose(np.array([zi_band for _ in range(num_channels)]))
        data,_ = signal_filtering.butter_bandpass_filter(data, b_band, a_band, zi_band)

    return data, timestamps, events_df

def split_indices(labels, train_size, valid_size, test_size, is_one_hot=False):
    """Split indices into train, valid, test using stratification.
    
    Parameters:
        labels: numpy array, either class indices (1D) or one-hot encoded (2D)
        train_size: float, proportion for training set
        valid_size: float, proportion for validation set
        test_size: float, proportion for test set
        is_one_hot: bool, whether labels are one-hot encoded
    Returns:
        train_idx, valid_idx, test_idx: lists of indices for each split
    """
    train_idx = []
    valid_idx = []
    test_idx = []

    # Handle one-hot or class index labels
    if is_one_hot:
        num_class = labels.shape[1]  # One-hot: num classes is second dimension
        # For each class, find samples where this class has highest probability
        for label in range(num_class):
            label_idx = np.where(np.argmax(labels, axis=1) == label)[0]
            n_train = int(np.floor(len(label_idx) * train_size))
            n_valid = int(np.floor(len(label_idx) * valid_size))
            n_test = int(np.floor(len(label_idx) * test_size))

            # Take the first n_train for train, the rest for test (preserving order)
            train_idx.extend(int(x) for x in label_idx[:n_train])
            remaining_idx = label_idx[n_train:]

            # Split the remaining indices into valid and test
            valid_idx.extend(int(x) for x in remaining_idx[:n_valid])
            test_idx.extend(int(x) for x in remaining_idx[n_valid:n_valid + n_test])
    else:
        num_class = len(np.unique(labels))  # Class indices: count unique values
        for label in range(num_class):
            label_idx = np.where(labels == label)[0]
            n_train = int(np.floor(len(label_idx) * train_size))
            n_valid = int(np.floor(len(label_idx) * valid_size))
            n_test = int(np.floor(len(label_idx) * test_size))

            # Take the first n_train for train, the rest for test (preserving order)
            train_idx.extend(int(x) for x in label_idx[:n_train])
            remaining_idx = label_idx[n_train:]

            # Split the remaining indices into valid and test
            valid_idx.extend(int(x) for x in remaining_idx[:n_valid])
            test_idx.extend(int(x) for x in remaining_idx[n_valid:n_valid + n_test])

    return train_idx, valid_idx, test_idx

def get_subjects_sessions(subjects, task_list, train_data_type, run_model_forward, subjs_config_folder):
    """
    Get the sessions for each subject and task based on the acquisition type.

    Parameters:
    - subjects: List of subjects.
    - task_list: List of tasks for which retrieving the sessions.
    - train_data_type: Type of training data ('open_loop', or 'both').
    - run_model_forward: Boolean indicating whether to load a session for running the model forward.
    - subjs_config_folder: Path to the folder containing subject configuration files.

    Returns:
    - sessions: DataFrame containing subjects, tasks, and their corresponding sessions.
    """
    result = []

    for subj in subjects:
        subj_id = f'S{subj}'
        subj_cfg_file = os.path.join(subjs_config_folder, f'{subj_id}.yaml')

        with open(subj_cfg_file, 'r') as f:
            subj_cfg = yaml.safe_load(f)

        for task in task_list:
            open_loop_sessions = subj_cfg[f'task_{task}']['sessions_open_loop']

            if len(open_loop_sessions) == 0:
                continue

            if train_data_type == 'closed_loop' or train_data_type == 'both' or run_model_forward:
                closed_loop_sessions = subj_cfg[f'task_{task}']['sessions_closed_loop']
            else:
                closed_loop_sessions = []

            if run_model_forward:
                if train_data_type == 'open_loop':
                    run_forward_sessions = closed_loop_sessions[:]
                    closed_loop_sessions = []
                elif len(closed_loop_sessions) > 1:
                    run_forward_sessions = [closed_loop_sessions[-1]]
                    closed_loop_sessions = closed_loop_sessions[:-1]
                else:
                    run_forward_sessions = closed_loop_sessions
                    closed_loop_sessions = []
            else:
                run_forward_sessions = []
        
            result.append({
                'subj_id': subj_id,
                'task': task,
                'open_loop_sessions': open_loop_sessions,
                'closed_loop_sessions': closed_loop_sessions,
                'run_forward_sessions': run_forward_sessions
            })

    # convert result to DataFrame
    result = pd.DataFrame(result)

    return result

def get_sessions_neural_features(source_folder, sessions, task, acq_type, params):
    """
    Get neural features for the specified sessions.

    Parameters:
    - source_folder: Path to the folder containing the data files.
    - sessions: List of session IDs.
    - task: Task name for which the features are being extracted.
    - acq_type: Type of acquisition ('open_loop' or 'closed_loop').
    - params: Dictionary containing parameters for feature extraction.

    Returns:
    - features: List of neural features for each session.
    """
    total_features = []
    total_labels = []
    labels_encoder = None

    print(f' - Loading sessions {sessions}')

    for session_id in sessions:
        data_file = os.path.join(source_folder, f'session_{session_id:02d}.npy')
        events_file = os.path.join(source_folder, f'session_{session_id:02d}_events.pkl')

        neural_features, labels, labels_encoder = extract_neural_features(
            data_file=data_file,
            events_file=events_file,
            emg_proc_cfg=params['emg_proc_cfg'],
            features_cfg=params['features_cfg'],
            mvc_file=params.get('mvc_file'),
            add_hand_open_class=False if task != "open_close" else True,
            labels_encoder=params.get('labels_encoder'),
            acq_type=acq_type,
            logging=False
        )

        total_features.append(neural_features)
        total_labels.append(labels)

    total_features = np.concatenate(total_features, axis=0)
    total_labels = np.concatenate(total_labels, axis=0)

    # one hot encoding with potential label smoothing
    num_classes = len(labels_encoder.classes_)

    total_labels = one_hot_encoding(labels=total_labels, num_classes=num_classes, smoothing=0)

    return total_features, total_labels, labels_encoder