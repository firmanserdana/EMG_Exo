# script for training the neural network model
import os
import numpy as np
import random
import torch
from torch.nn.functional import softmax
from torch.utils.data import Subset, ConcatDataset, DataLoader, sampler
from collections import deque
from sklearn.metrics import confusion_matrix

from models.lstm_model import *
from models.tfm_model import *
from models.ctfm_model import *
from models.crnn_model import *
from utils.dataset_emg import *
from utils.data_utils import *

# random seed for reproducibility
seed = 18
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def load_model(model_cfg, data_cfg):
    """
    Load the model based on the configuration provided.
    Args:
        model_cfg (dict): Configuration dictionary for the model.
        data_cfg (dict): Configuration dictionary for the data.
    Returns:
        model (torch.nn.Module): The initialized model.
    """
    model_type = model_cfg['type']
    model_params = model_cfg['parameters']

    num_channels = data_cfg['num_channels']
    seq_len = data_cfg['seq_len']
    num_class = data_cfg['num_class']
    input_size = num_channels

    # Model initialization
    if model_type == 'LSTM':
        model = LSTMModel(
            input_dim=input_size,
            hidden_size=model_params['hidden_size'],
            num_output=num_class,
            num_layers=model_params['num_layers'],
            drop_prob=model_params['dropout']
        )
    elif model_type == 'CTFM':
        model = CTFMModel(
            emb_size=model_params['emb_size'],
            num_layers=model_params['num_layers'],
            num_heads=model_params['num_heads'],
            time_conv_size=int(np.min((model_params['time_conv_size'], seq_len))),
            seq_length=seq_len,
            num_channels=num_channels,
            n_out=num_class,
            use_cls_token=model_params['use_cls_token'],
            dropout=model_params['dropout']
        )
    elif model_type == 'TFM':                
        model = TFMModel(
            input_dim=input_size,
            embed_dim=model_params['emb_size'],
            num_heads=model_params['num_heads'],
            num_layers=model_params['num_layers'],
            num_classes=num_class,
            max_len=seq_len,
            use_cls_token=model_params['use_cls_token'],
            dropout=model_params['dropout']
        )
    elif model_type == 'CRNN':
        model = CRNNModel(
            input_dim=input_size,
            time_conv_size=model_params['time_conv_size'],
            time_stride=model_params['time_stride'],
            num_time_filters=model_params['num_time_filters'],
            hidden_size=model_params['hidden_size'],
            num_layers=model_params['num_layers'],
            num_output=num_class,
            drop_prob=model_params['dropout']
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return model

def get_data_loaders(features, labels, data_cfg, training_cfg):
    """ Create DataLoader objects for training, validation, and testing datasets. """
    seq_len = data_cfg['seq_len']
    batch_size = training_cfg['batch_size']
    train_size = training_cfg['train_size']
    valid_size = training_cfg['valid_size']
    test_size = training_cfg['test_size']

    # Prepare the dataset
    ds_open = DatasetEMG(
        raw_features=features['open_loop'], 
        freq_features=None,  # not implemented yet
        labels=labels['open_loop'], 
        sequence_length=seq_len,
        device=device
    )    

    open_labels = ds_open.labels.cpu().numpy()
    is_one_hot = True if open_labels.ndim == 2 else False

    open_train_idx, open_valid_idx, open_test_idx = split_indices(
        labels=open_labels, 
        train_size=train_size,
        valid_size=valid_size,
        test_size=test_size,
        is_one_hot=is_one_hot
    )

    train_datasets = [Subset(ds_open, open_train_idx)]
    valid_datasets = [Subset(ds_open, open_valid_idx)]
    test_datasets  = [Subset(ds_open, open_test_idx)]

    # If closed_loop exists add them
    if features['closed_loop'] is not None:
        ds_closed = DatasetEMG(
            raw_features=features['closed_loop'], 
            freq_features=None,  # not implemented yet
            labels=labels['closed_loop'], 
            sequence_length=seq_len,
            device=device
        )

        closed_labels = ds_closed.labels.cpu().numpy()
        is_one_hot = True if closed_labels.ndim == 2 else False
        
        closed_train_idx, closed_valid_idx, closed_test_idx = split_indices(
            labels=closed_labels, 
            train_size=train_size,
            valid_size=valid_size,
            test_size=test_size,
            is_one_hot=is_one_hot
        )

        train_datasets.append(Subset(ds_closed, closed_train_idx))
        valid_datasets.append(Subset(ds_closed, closed_valid_idx))
        test_datasets.append(Subset(ds_closed, closed_test_idx))

    # Combine splits from open_loop and closed_loop
    train_dataset = train_datasets[0] if len(train_datasets) == 1 else ConcatDataset(train_datasets)
    valid_dataset = valid_datasets[0] if len(valid_datasets) == 1 else ConcatDataset(valid_datasets)
    test_dataset  = test_datasets[0]  if len(test_datasets)  == 1 else ConcatDataset(test_datasets)

    # Create DataLoader objects
    num_train = len(train_dataset)
    num_valid = len(valid_dataset)
    num_test = len(test_dataset)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, 
                            sampler=sampler.RandomSampler(range(num_train)), drop_last=False)
    valid_loader = DataLoader(valid_dataset, batch_size=batch_size,
                            sampler=sampler.RandomSampler(range(num_valid)), drop_last=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, 
                            sampler=sampler.RandomSampler(range(num_test)), drop_last=False)

    return train_loader, valid_loader, test_loader

def calc_trial_forward_metrics(preds_times, predictions, dec_start, dec_stop, num_consec_pred):
    # Get the predictions within the trial time range
    mask = (preds_times >= dec_start) & (preds_times <= dec_stop)
    trial_preds = predictions[mask]
    
    # Find consecutive predictions
    out_made = False
    out_class = None
    out_latency = None
    
    # Check for consecutive predictions
    current_count = 1
    current_class = trial_preds[0]
    
    for i in range(1, len(trial_preds)):
        if trial_preds[i] == current_class:
            current_count += 1
            if current_count >= num_consec_pred and not out_made:
                # Decision made
                out_made = True
                out_class = int(current_class)
                out_latency = i + 1  # Number of predictions until decision
                break
        else:
            # Reset counter for new class
            current_class = trial_preds[i]
            current_count = 1
    
    return out_class, out_latency

def run_model_forward(source_folder, sessions, model, labels_encoder, params):
    """
    Run the model forward pass on the given sessions.
    Args:
        source_folder (str): Path to the source folder containing data.
        sessions (list): List of session names to process.
        model (torch.nn.Module): The neural network model to use.
        labels_encoder (LabelEncoder): The labels encoder to use for decoding predictions.
        params (dict): Parameters for the model forward pass.
    Returns:
        results (dict): Results from the model forward pass.
    """
    # loading configuration parameters
    emg_proc_cfg = params['emg_proc_cfg']
    features_cfg = params['features_cfg']

    # initialize parameters and variables
    num_channels_emg = emg_proc_cfg['num_channels_emg']
    fsample = emg_proc_cfg['fsample_emg']
    feature_type = features_cfg['feature_type']
    dec_win_len = features_cfg['windows_length'][feature_type]['win_length']
    dec_win_shift = features_cfg['windows_length'][feature_type]['win_shift']

    dec_win_samples = round(fsample*dec_win_len)  # number of samples for each prediction window
    dec_win_shift_samples = round(fsample*dec_win_shift)
    seq_len = params['seq_len']
    dec_seq_len_samples = dec_win_samples + (seq_len-1)*dec_win_shift_samples # number of samples for each prediction sequence

    features_params = {
        'win_len': dec_win_samples,
        'win_shift': dec_win_shift_samples,
        'fsample': fsample
    }

    if features_cfg['normalization'] == 'mvc':
        mvc_mean = load_pickle(params['mvc_file'])['mvc_mean']
    elif features_cfg['normalization'] == 'zscore':
        zscore_win_len = features_cfg['normalization_params']['zscore']['win_length']
        zscore_win_samples = round(fsample*zscore_win_len)
        
        buffer_zscore = deque([], maxlen=zscore_win_samples) # buffer for z-score normalization
            
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    model.eval()

    results = {}

    # loop through each session
    for session_id in sessions:
        print(f' - Running model forward for session {session_id}')
        data_file = os.path.join(source_folder, f'session_{session_id:02d}.npy')
        events_file = os.path.join(source_folder, f'session_{session_id:02d}_events.pkl')

        # Extract neural data
        data, timestamps, events_df = extract_neural_data(
            data_file=data_file,
            events_file=events_file,
            emg_proc_cfg=params['emg_proc_cfg'],
            logging=False
        )

        if features_cfg['normalization'] == 'zscore':
            # Initialize the z-score buffer with the first dec_win_samples samples
            initial_samples = data[:dec_seq_len_samples, :]
            buffer_zscore.extend(initial_samples)

        # storing events timestamps
        trials_start = events_df.loc[events_df['event_type'] == 'trial_start', 'time'].values
        trials_end = events_df.loc[events_df['event_type'] == 'trial_end', 'time'].values
        decoding_start = events_df.loc[events_df['event_type'] == 'decoding_start', 'time'].values
        decoding_stop = events_df.loc[events_df['event_type'] == 'decoding_stop', 'time'].values
        grasp_ids = np.array(events_df.loc[events_df['event_type'] == 'grasp_objective_start', 'event_id'])
        trials_results = np.array(events_df.loc[events_df['event_type'] == 'trial_result', 'event_id'])

        num_samples = len(data)

        predictions = []
        preds_probs = []
        preds_times = []

        # loop over the data simulating the acquisition
        start_sample = dec_seq_len_samples

        for current_sample in range(start_sample, num_samples, dec_win_shift_samples):
            # Extract the sequence data (looking back in time)
            seq_start = current_sample - dec_seq_len_samples
            seq_end = current_sample
            
            # Get the data window for this prediction
            window_data = data[seq_start:seq_end, :]
            window_data_raw = data[seq_start:seq_end, :]  # keep a copy of the raw data for later use
            
            # Apply normalization if needed
            if features_cfg['normalization'] == 'mvc':
                window_data = window_data / mvc_mean
            elif features_cfg['normalization'] == 'zscore':                
                # Apply zscore normalization using current buffer
                buffer_array = np.array(buffer_zscore)
                zscore_mean = np.mean(buffer_array, axis=0)
                zscore_std = np.std(buffer_array, axis=0) + 1e-8
                window_data = (window_data - zscore_mean) / zscore_std

                # Update zscore buffer with new samples (simulating online behavior)
                new_samples = data[seq_end-dec_win_shift_samples:seq_end, :]
                buffer_zscore.extend(new_samples)
            
            # Extract features from the normalized window
            features = calc_features_multi_win(
                data=window_data,
                data_raw=window_data_raw,
                feature_type=feature_type,
                params=features_params
            )

            # model prediction
            features_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device)

            with torch.no_grad():
                output = model(features_tensor)

                prediction = torch.argmax(output, 1).cpu().numpy()[0]
                pred_probs = softmax(output, dim=1).cpu().numpy()[0]

            prediction = int(labels_encoder.inverse_transform([prediction])[0]) # retrieve the original label

            predictions.append(prediction)
            preds_probs.append(pred_probs)
            preds_times.append(timestamps[current_sample])
        
        # convert results to numpy arrays
        predictions = np.array(predictions)
        preds_probs = np.array(preds_probs)
        preds_times = np.array(preds_times)

        pred_type = params['prediction']['type']
        num_consec_pred = params['prediction']['params']['num'] if pred_type == 'consecutive' else 1

        forward_results = []
        forward_latencies = []

        # compute run-forward metrics
        for trl in range(len(decoding_start)):
            # Get the start and end times for the current trial valid for decoding
            dec_start = decoding_start[trl]
            trl_end = trials_end[trl]

            # Get the predictions within the trial time range
            mask = (preds_times >= dec_start) & (preds_times <= trl_end)
            trial_preds = predictions[mask]
            trial_preds_times = preds_times[mask]

            pred_class, pred_latency = calc_trial_forward_metrics(
                preds_times=trial_preds_times,
                predictions=trial_preds,
                dec_start=dec_start,
                dec_stop=trl_end,
                num_consec_pred=num_consec_pred
            )

            # Append results
            forward_results.append(pred_class)
            forward_latencies.append(pred_latency)

        # Computing metrics
        forward_accuracy = np.mean(np.array(forward_results) == np.array(grasp_ids)) * 100

        valid_mask = np.array([result is not None for result in forward_results])
        valid_trial_results = np.array(forward_results)[valid_mask]
        valid_trial_results = np.array([int(res) for res in valid_trial_results])

        valid_grasp_ids = np.array(grasp_ids)[valid_mask]

        unique_classes = np.unique(np.concatenate([valid_trial_results, valid_grasp_ids]))
        forward_conf_matrix = confusion_matrix(valid_grasp_ids, valid_trial_results, labels=unique_classes)
        
        print(f'   Session {session_id} - Forward accuracy: {forward_accuracy:.2f}%')

        # Store results for the session
        results[session_id] = {
            'events_ts': {
                'trials_start': trials_start,
                'trials_end': trials_end,
                'decoding_start': decoding_start,
                'decoding_stop': decoding_stop
            },
            'grasp_ids': grasp_ids,
            'trials_results': trials_results,
            'timestamps': timestamps,
            'predictions': predictions,
            'preds_probs': preds_probs,
            'preds_times': preds_times,
            'forward_results': forward_results,
            'forward_latencies': forward_latencies,
            'forward_accuracy': forward_accuracy,
            'forward_conf_matrix': forward_conf_matrix
        }

    return results