import time
import pickle
import numpy as np
import torch
from torch.nn.functional import softmax
from collections import deque

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

    model = torch.load(dec_params['model_file'], weights_only=False, map_location=device)
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