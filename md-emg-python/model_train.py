# script for training the neural network model
import os
import numpy as np
import random
import yaml
import pickle
import torch
from torch.utils.data import DataLoader, sampler, Subset

from models.lstm_model import *
from models.tfm_model import *
from models.ctfm_model import *
from models.crnn_model import *
from utils.dataset_emg import *
from utils.data_utils import *
from utils.nn_utils import *
from utils.nn_model_training import *
from utils.general_utils import *
from utils.dataset_preparation import *

# random seed for reproducibility
seed = 18
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Parse command line arguments
args = decoding_arg_parser(description='Train neural network model for EMG decoding')

# General params
subj_type = args.subj_type
subj = args.subj
task = args.task
acquisition_type = args.acquisition_type
session = args.session
load_existing_model = bool(args.load_existing_model)

subj_id = f'S{subj}'

# prepare dataset
dataset_preration(subj_type, subj, task, acquisition_type, session)

# folders definition
config_folder = 'config'
data_folder = os.path.join('data', subj_type, subj_id) # source folder for the data
models_weights_save_folder = os.path.join('models-subjects', subj_type, subj_id, task)
models_results_save_folder = os.path.join('results-training', subj_type, subj_id, task)

# file paths
subj_cfg_file = os.path.join('config', 'subjects', subj_type, f'{subj_id}.yaml')
training_cfg_file = os.path.join('config', f'decoding_train_{task}.yaml')

# Load the config file
with open(subj_cfg_file, 'r') as f:
    subj_cfg = yaml.safe_load(f)

with open(training_cfg_file, 'r') as f:
    training_cfg = yaml.safe_load(f)

# config params initialization
model_type = subj_cfg[f'task_{task}']['model_type'] # options: ['LSTM', 'TFM', 'CTFM']
seq_len = subj_cfg[f'task_{task}']['seq_len'] # sequence length for the model
batch_size = training_cfg.get('batch_size', 64)
train_size = training_cfg.get('train_size', 0.7)
valid_size = training_cfg.get('valid_size', 0.15)
test_size = training_cfg.get('test_size', 0.15)

# create results folders if they do not exist
os.makedirs(models_weights_save_folder, exist_ok=True)
os.makedirs(models_results_save_folder, exist_ok=True)

print(f'Starting the training of model: {model_type} for subject: {subj_id} of task: {task}')

# model config
models_cfg_file = os.path.join('config', 'models', f'{model_type}_cfg.yaml')
with open(models_cfg_file, 'r') as file:
    model_cfg = yaml.safe_load(file)

training_cfg['scheduler'] = model_cfg['scheduler'] # the definition of the scheduler is model dependent

data_file_name = os.path.join(data_folder, f"{acquisition_type}_{task}_data.pkl")

with open(data_file_name, "rb") as f:
    data = pickle.load(f)

neural_features = data['neural_data']
labels = data['labels']
freq_features = None # not implemented yet

if acquisition_type == 'closed_loop' or acquisition_type == 'both':
    closed_loop_start_idx = data['closed_loop_start_idx']
else:
    closed_loop_start_idx = None

# input dimensions
is_one_hot = True if labels.ndim == 2 else False
num_class = labels.shape[1] if is_one_hot else len(np.unique(labels))  # Handle multi-label case
training_cfg['num_class'] = num_class
num_channels = neural_features.shape[-1] # Number of channels
input_size = num_channels

# Prepare the dataset
dataset = DatasetEMG(neural_features, freq_features, labels, seq_len, device=device)

# Extract labels from your dataset (adjust if needed)
all_labels = dataset.labels.cpu().numpy() if hasattr(dataset, 'labels') else labels

# Split the dataset into train, validation, and test sets
if closed_loop_start_idx is not None:
    train_idx, valid_idx, test_idx = split_indices(
        labels=all_labels[:closed_loop_start_idx], 
        train_size=train_size,
        valid_size=valid_size,
        test_size=test_size,
        is_one_hot=is_one_hot
    )

    closed_loop_train_idx, closed_loop_valid_idx, closed_loop_test_idx = split_indices(
        labels=all_labels[closed_loop_start_idx:], 
        train_size=train_size,
        valid_size=valid_size,
        test_size=test_size,
        is_one_hot=is_one_hot
    )

    # Convert to numpy arrays and add correct offset for closed loop indices
    train_idx = np.concatenate((np.array(train_idx), np.array(closed_loop_train_idx) + closed_loop_start_idx))
    valid_idx = np.concatenate((np.array(valid_idx), np.array(closed_loop_valid_idx) + closed_loop_start_idx))
    test_idx = np.concatenate((np.array(test_idx), np.array(closed_loop_test_idx) + closed_loop_start_idx))
else:
    train_idx, valid_idx, test_idx = split_indices(
        labels=all_labels, 
        train_size=train_size,
        valid_size=valid_size,
        test_size=test_size,
        is_one_hot=is_one_hot
    )

train_dataset = Subset(dataset, train_idx) 
valid_dataset = Subset(dataset, valid_idx)
test_dataset = Subset(dataset, test_idx)

# Create DataLoader objects
num_train = len(train_dataset)
num_valid = len(valid_dataset)
num_test = len(test_dataset)

pin_memory = True if device.type == 'cuda' else False

train_loader = DataLoader(train_dataset, batch_size=batch_size, 
                          sampler=sampler.RandomSampler(range(num_train)),
                          drop_last=False,
                          pin_memory=pin_memory)
valid_loader = DataLoader(valid_dataset, batch_size=batch_size,
                          sampler=sampler.RandomSampler(range(num_valid)),
                          drop_last=False,
                          pin_memory=pin_memory)
test_loader = DataLoader(test_dataset, batch_size=batch_size, 
                         sampler=sampler.RandomSampler(range(num_test)),
                         drop_last=False,
                         pin_memory=pin_memory)

# Model initialization
if model_type == 'LSTM':
    model = LSTMModel(
        input_dim=input_size,
        hidden_size=model_cfg['hidden_size'],
        num_output=num_class,
        num_layers=model_cfg['num_layers'],
        drop_prob=model_cfg['dropout']
    )
elif model_type == 'CTFM':
    model = CTFMModel(
        emb_size=model_cfg['emb_size'],
        num_layers=model_cfg['num_layers'],
        num_heads=model_cfg['num_heads'],
        time_conv_size=model_cfg['time_conv_size'],
        seq_length=neural_features.shape[1]*seq_len,
        num_channels=num_channels,
        n_out=num_class,
        use_cls_token=model_cfg['use_cls_token'],
        dropout=model_cfg['dropout']
    )
elif model_type == 'TFM':                
    model = TFMModel(
        input_dim=input_size,
        embed_dim=model_cfg['emb_size'],
        num_heads=model_cfg['num_heads'],
        num_layers=model_cfg['num_layers'],
        num_classes=num_class,
        max_len=seq_len,
        use_cls_token=model_cfg['use_cls_token'],
        dropout=model_cfg['dropout']
    )
elif model_type == 'CRNN':
    model = CRNNModel(
        input_dim=input_size,
        time_conv_size=model_cfg['time_conv_size'],
        time_stride=model_cfg['time_stride'],
        num_time_filters=model_cfg['num_time_filters'],
        hidden_size=model_cfg['hidden_size'],
        num_layers=model_cfg['num_layers'],
        num_output=num_class,
        drop_prob=model_cfg['dropout']
    )
else:
    raise ValueError(f"Unknown model type: {model_type}")

if load_existing_model:
    # loading the model
    print('Loading the model from previous decoding session\n')
    existing_file = os.path.join(models_weights_save_folder, f'{model_type}_open_loop.pth')
    model = torch.load(existing_file, weights_only=False, map_location=device)

# model weights initialization
# model.apply(weights_init)

# moving model to the GPU (if available)
model.to(device)

# Launch the training of the model
results, losses = train_nn_model(model, train_loader, valid_loader, test_loader, training_cfg)

# results is a pd.dataframe containing details about the training (like the losses) and the final test results
results.to_csv(os.path.join(models_results_save_folder, f'{model_type}_{acquisition_type}.csv'), index=False)

# Save the trained model
model_save_path = os.path.join(models_weights_save_folder, f'{model_type}_{acquisition_type}.pth')
torch.save(model, model_save_path)