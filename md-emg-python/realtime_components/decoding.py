import time
import pickle
import numpy as np
import torch
import yaml
from torch.nn.functional import softmax
from collections import deque

from models.lstm_model import *
from models.tfm_model import *
from models.ctfm_model import *
from models.crnn_model import *
from utils.data_utils import *      

def DecodingLoop(acq_params, dec_params, dec_queue, pred_control_queue, pred_save_queue, stop_program, stream_queue=None):
    print('Starting the decoding loop...')

    # loading the decoding parameters
    feature_type = dec_params['feature_type']
    fsample = acq_params['fsample']
    dec_win_length_samples = int(dec_params['dec_win_length'] * fsample)
    dec_win_shift_samples = int(dec_params['dec_win_shift'] * fsample)
    streaming_active = acq_params['streaming_active']

    features_params = {
        'win_len': dec_win_length_samples,
        'win_shift': dec_win_shift_samples,
        'fsample': fsample
    }

    # loading the labels encoder
    with open(dec_params['labels_encoder_file'], 'rb') as f:
        labels_encoder = pickle.load(f)['labels_encoder']

    # loading the model
    is_cuda = torch.cuda.is_available()
    device = torch.device("cuda") if is_cuda else torch.device("cpu")

    # Get the model configuration
    models_cfg_file = os.path.join('config', 'models', f"{dec_params['model_type']}_cfg.yaml")
    with open(models_cfg_file, 'r') as file:
        model_cfg = yaml.safe_load(file)

    # Model initialization
    if dec_params['model_type'] == 'LSTM':
        model = LSTMModel(
            input_dim=acq_params['num_channels_emg'],
            hidden_size=model_cfg['hidden_size'],
            num_output=dec_params['num_class'],
            num_layers=model_cfg['num_layers'],
            drop_prob=model_cfg['dropout']
        )
    elif dec_params['model_type'] == 'CTFM':
        model = CTFMModel(
            emb_size=model_cfg['emb_size'],
            num_layers=model_cfg['num_layers'],
            num_heads=model_cfg['num_heads'],
            time_conv_size=model_cfg['time_conv_size'],
            seq_length=dec_params['seq_len'],
            num_channels=acq_params['num_channels_emg'],
            n_out=dec_params['num_class'],
            use_cls_token=model_cfg['use_cls_token'],
            dropout=model_cfg['dropout']
        )
    elif dec_params['model_type'] == 'TFM':
        model = TFMModel(
            input_dim=acq_params['num_channels_emg'],
            embed_dim=model_cfg['emb_size'],
            num_heads=model_cfg['num_heads'],
            num_layers=model_cfg['num_layers'],
            num_classes=dec_params['num_class'],
            max_len=dec_params['seq_len'],
            use_cls_token=model_cfg['use_cls_token'],
            dropout=model_cfg['dropout']
        )
    elif dec_params['model_type'] == 'CRNN':
        model = CRNNModel(
            input_dim=acq_params['num_channels_emg'],
            time_conv_size=model_cfg['time_conv_size'],
            time_stride=model_cfg['time_stride'],
            num_time_filters=model_cfg['num_time_filters'],
            hidden_size=model_cfg['hidden_size'],
            num_layers=model_cfg['num_layers'],
            num_output=dec_params['num_class'],
            drop_prob=model_cfg['dropout']
        )
    else:
        raise ValueError(f"Unknown model type: {dec_params['model_type']}")

    # Load the model with proper handling for different save formats
    loaded_data = torch.load(dec_params['model_file'], map_location=device, weights_only=False)
    
    # Check if loaded data is a state_dict or the full model
    if isinstance(loaded_data, dict):
        # It's a state_dict
        model.load_state_dict(loaded_data)
    else:
        # It's the full model object - extract state_dict
        model.load_state_dict(loaded_data.state_dict())
    
    model.to(device)
    model.eval()

    # warm-up the model to avoid the first inference delay
    num_features_channels = feature_type.count('+') + 1

    dummy_input = torch.zeros(
        (1, dec_win_length_samples, acq_params['num_channels_emg']*num_features_channels), 
        dtype=torch.float32).to(device)
    
    for _ in range(50):
        with torch.no_grad():
            model(dummy_input)

    # buffers initialization
    buffer_predictions_len = dec_params['buffer_predictions_size']
    buffer_predictions = deque([], maxlen=buffer_predictions_len) # using deque for circular buffer

    # decoding loop
    while not stop_program.value:
        data = dec_queue.get()

        if data is not None:
            # retrieve and store the features
            features = calc_features_multi_win(
                data=data, 
                data_raw=None,  # raw data is not needed for now in the decoding loop
                feature_type=feature_type, 
                params=features_params
            )

            # decoding
            data = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device)

            with torch.no_grad():
                output = model(data)

                prediction = torch.argmax(output, 1).cpu().numpy()[0]
                pred_probs = softmax(output, dim=1).cpu().numpy()[0]
                
            timestamp = time.perf_counter() 

            prediction_prob = pred_probs[prediction] # probability of the predicted class
            prediction = int(labels_encoder.inverse_transform([prediction])[0]) # retrieve the original label

            pred_control_queue.put((prediction, prediction_prob, timestamp)) # Put the prediction in the control queue

            # saving the prediction
            buffer_predictions.append((prediction, prediction_prob))

            if len(buffer_predictions) == buffer_predictions_len:
                pred_save_queue.put(np.array(buffer_predictions))
                buffer_predictions.clear()

            if streaming_active:
                # put the data in the streaming queue
                stream_queue.put(pred_probs)

            # Empty the queue
            while not dec_queue.empty():
                dec_queue.get()
        else:
            break
    
    pred_control_queue.put(None) # Put None in the control queue to stop the control loop
    pred_save_queue.put(np.array(buffer_predictions))
    pred_save_queue.put(None) # Put None in the save queue to stop the saving loop
    
    print('Decoding loop stopped')