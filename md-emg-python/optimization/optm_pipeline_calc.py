# script for optimizatione pipeline execution: data preparation - model training - model evaluation
import sys
import os
import yaml
import numpy as np
import pandas as pd

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optm_utils import *
from utils.data_utils import *
from utils.nn_model_training import *

# General params
optimization_name = 'runforward_seq_len_comparison'

# folders definition
root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
config_folder = os.path.join(root_folder, 'config')
optim_config_folder = os.path.join(config_folder, 'optimizations')

# load optimization config
optim_config_file = os.path.join(optim_config_folder, f'{optimization_name}.yaml')

with open(optim_config_file, 'r') as f:
    optim_cfg = yaml.safe_load(f)

# create a folder for the optimization configuration results
results_optm_folder = os.path.join(root_folder, 'results-optimization', optim_cfg['subj_type'])
os.makedirs(results_optm_folder, exist_ok=True)

# variable initialization
subjs_config_folder = os.path.join(config_folder, 'subjects', optim_cfg['subj_type'])
data_folder = os.path.join(root_folder, 'data', optim_cfg['subj_type'])

optm_configurations = optim_cfg['configurations']

features_cfg = {
    'open_loop_events': optim_cfg['open_loop_events'],
    'closed_loop_events': optim_cfg['closed_loop_events'],
}

# retrieving the subjects sessions DataFrame
subj_task_sessions = get_subjects_sessions(
    subjects=optim_cfg['subjects'],
    task_list=optim_cfg['task'],
    train_data_type=optim_cfg['train_data_type'],
    run_model_forward=optim_cfg['run_model_forward'],
    subjs_config_folder=subjs_config_folder
)

optm_results = []

# loop through each configuration for retrieving the data, training and testing the different configs
for optm_config in optm_configurations:
    optm_name = optm_config['name']
    
    # defining the features extraction parameters
    emg_proc_cfg = {
        'num_channels_emg': optim_cfg['num_channels_emg'],
        'fsample_emg': optim_cfg['fsample_emg']
    }

    features_cfg['windows_length'] = {
        optm_config['features']['type']: optm_config['features']['params']
    }

    features_cfg['feature_type'] = optm_config['features']['type']

    if optm_config['normalization'] != 'none':
        normalization_type = optm_config['normalization']['type']

        features_cfg['normalization'] = normalization_type
        features_cfg['normalization_params'] = optm_config['normalization']['params']

    if len(optm_config['signal_filtering']) > 0:
        for filter in optm_config['signal_filtering']:
            emg_proc_cfg[filter['type']] = filter['params']

    features_extraction_params = {
        'emg_proc_cfg': emg_proc_cfg,
        'features_cfg': features_cfg
    }

    # iterate over the rows of subj_task_sessions DataFrame
    for index, row in subj_task_sessions.iterrows():
        subj_id = row['subj_id']
        task = row['task']
        open_loop_sessions = row['open_loop_sessions']
        closed_loop_sessions = row['closed_loop_sessions']
        run_forward_sessions = row['run_forward_sessions']
        model_type = optm_config['model']['type']

        print(f'Processing subj {subj_id} - task {task} - model {model_type} [{optm_name}]')

        subj_data_folder = os.path.join(data_folder, subj_id, 'raw')

        if normalization_type == 'mvc':
            subj_mvc_folder = os.path.join(data_folder, subj_id, 'mvc')
            mvc_file = os.path.join(subj_mvc_folder, 'dataset_mvc.pkl')
            features_extraction_params['mvc_file'] = mvc_file

        # loading the task training configuration
        training_cfg_file = os.path.join(config_folder, f'decoding_train_{task}.yaml')

        with open(training_cfg_file, 'r') as f:
            training_cfg = yaml.safe_load(f)

        training_cfg['log_plot'] = False
        training_cfg['log_epochs_num'] = 251

        # getting the neural features for the open loop sessions
        features_ol, labels_ol, labels_encoder = get_sessions_neural_features(
            source_folder=subj_data_folder,
            sessions=open_loop_sessions,
            task=task,
            acq_type='open_loop',
            params=features_extraction_params
        )

        # getting the neural features for the closed loop sessions  
        if optim_cfg['train_data_type'] == 'both' and len(closed_loop_sessions) > 0: 
            features_cl, labels_cl, _ = get_sessions_neural_features(
                source_folder=subj_data_folder,
                sessions=closed_loop_sessions,
                task=task,
                acq_type='closed_loop',
                params=features_extraction_params
            )
        else:
            features_cl, labels_cl = None, None

        features = {
            'open_loop': features_ol,
            'closed_loop': features_cl,
        }

        labels = {
            'open_loop': labels_ol,
            'closed_loop': labels_cl,
        }

        is_one_hot = True if labels_ol.ndim == 2 else False
        num_class = labels_ol.shape[1] if is_one_hot else len(np.unique(labels_ol))  # Handle multi-label case
        
        # initializing the model
        num_features = features_cfg['feature_type'].count('+') + 1
        
        data_cfg = {
            'seq_len': optm_config['features']['seq_len'],
            'num_class': num_class,
            'num_channels': emg_proc_cfg['num_channels_emg']*num_features,
        }

        model = load_model(model_cfg=optm_config['model'], data_cfg=data_cfg)

        # initializing the train/test dataloaders
        train_loader, valid_loader, test_loader = get_data_loaders(
            features=features,
            labels=labels,
            data_cfg=data_cfg,
            training_cfg=training_cfg
        )

        # Launch the training of the model
        print(' - Training the model')
        results, losses = train_nn_model(model, train_loader, valid_loader, test_loader, training_cfg) 
        
        if optim_cfg['run_model_forward']:
            params = copy.deepcopy(features_extraction_params)

            params['seq_len'] = optm_config['features']['seq_len']
            params['prediction'] = optm_config['prediction']

            run_forward_results = run_model_forward(
                source_folder=subj_data_folder,
                sessions=run_forward_sessions,
                model=model,
                labels_encoder=labels_encoder,
                params=params
            )

        optm_results.append({
            'optm_name': optm_name,
            'subj_id': subj_id,
            'task': task,
            'model_type': model_type,
            'num_epochs': results['num_epochs'],
            'valid_loss': results['best_valid_loss'],
            'valid_accuracy': results['best_valid_accuracy'],
            'test_accuracy': results['test_accuracy'],
            'losses': losses,
            'run_forward_results': run_forward_results if optim_cfg['run_model_forward'] else None
        })
        
# Convert results to DataFrame
optm_results_df = pd.DataFrame(optm_results)

# Save the results to a Pickle file
results_file = os.path.join(results_optm_folder, f'{optimization_name}_results.pkl')
optm_results_df.to_pickle(results_file)