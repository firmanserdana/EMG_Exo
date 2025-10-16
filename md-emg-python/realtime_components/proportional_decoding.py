"""
Proportional Decoding Loop for Real-time EMG Control
===================================================

This module implements the proportional decoding loop for continuous EMG control
with support for MLP and KNN decoders, and motor unit decomposition.

Features:
---------
- Real-time proportional decoding
- Support for MLP and KNN decoders
- Motor unit decomposition option
- Per-finger and whole-hand control modes
- Smooth output filtering
"""

import time
import pickle
import numpy as np
import torch
import yaml
from collections import deque
from scipy.ndimage import gaussian_filter1d

from models.proportional_decoders import (
    MLPProportionalDecoder,
    KNNProportionalDecoder,
    ProportionalControlMapper,
    load_proportional_decoder
)
from utils.motor_unit_decomposition import get_mud_features
from utils.data_utils import calc_features_multi_win


def ProportionalDecodingLoop(acq_params, dec_params, dec_queue, 
                             prop_control_queue, prop_save_queue, 
                             stop_program, stream_queue=None):
    """
    Real-time proportional decoding loop for continuous EMG control.
    
    Args:
        acq_params (dict): Acquisition parameters
        dec_params (dict): Decoding parameters
        dec_queue (Queue): Input queue with EMG data
        prop_control_queue (Queue): Output queue for control commands
        prop_save_queue (Queue): Queue for saving predictions
        stop_program (Value): Multiprocessing flag to stop the loop
        stream_queue (Queue, optional): Queue for streaming visualization
    """
    print('Starting the proportional decoding loop...')
    
    # Load decoding parameters
    decoder_type = dec_params.get('decoder_type', 'mlp')  # 'mlp' or 'knn'
    use_mud = dec_params.get('use_motor_unit_decomposition', False)
    control_mode = dec_params.get('proportional_control_mode', 'individual_fingers')
    fsample = acq_params['fsample']
    dec_win_length_samples = int(dec_params['dec_win_length'] * fsample)
    dec_win_shift_samples = int(dec_params['dec_win_shift'] * fsample)
    
    # Output smoothing parameters
    smooth_window_size = dec_params.get('smooth_window_size', 5)
    smooth_sigma = dec_params.get('smooth_sigma', 1.5)
    
    # Confidence threshold for output
    min_activation_threshold = dec_params.get('min_activation_threshold', 0.1)
    
    print(f"  Decoder type: {decoder_type}")
    print(f"  Motor unit decomposition: {use_mud}")
    print(f"  Control mode: {control_mode}")
    print(f"  Smoothing window: {smooth_window_size}, sigma: {smooth_sigma}")
    
    # Initialize decoder
    is_cuda = torch.cuda.is_available()
    device = torch.device("cuda") if is_cuda else torch.device("cpu")
    
    model_file = dec_params.get('proportional_model_file')
    if not model_file:
        raise ValueError("proportional_model_file must be specified in dec_params")
    
    # Load proportional decoder
    if decoder_type == 'mlp':
        decoder = load_proportional_decoder(model_file, decoder_type='mlp', device=device)
        print(f"  MLP decoder loaded from: {model_file}")
    elif decoder_type == 'knn':
        decoder = load_proportional_decoder(model_file, decoder_type='knn')
        print(f"  KNN decoder loaded from: {model_file}")
    else:
        raise ValueError(f"Unknown decoder type: {decoder_type}")
    
    # Initialize control mapper
    num_fingers = dec_params.get('num_fingers', 5)
    mapper = ProportionalControlMapper(control_mode=control_mode, num_fingers=num_fingers)
    print(f"  Control mapper initialized: {num_fingers} fingers, {control_mode} mode")
    
    # Warm-up the decoder
    if decoder_type == 'mlp':
        dummy_input_dim = decoder.input_dim
        dummy_input = torch.zeros((1, dummy_input_dim), dtype=torch.float32).to(device)
        
        for _ in range(50):
            with torch.no_grad():
                _ = decoder(dummy_input)
        print("  MLP decoder warmed up")
    
    # Smoothing buffer for outputs
    output_buffer = deque(maxlen=smooth_window_size)
    
    # Prediction buffer for saving
    buffer_predictions_len = dec_params.get('buffer_predictions_size', 100)
    buffer_predictions = deque([], maxlen=buffer_predictions_len)
    
    # Feature extraction parameters
    feature_type = dec_params.get('feature_type', 'rms')
    features_params = {
        'win_len': dec_win_length_samples,
        'win_shift': dec_win_shift_samples,
        'fsample': fsample
    }
    
    # Main decoding loop
    print("Proportional decoding loop running...")
    
    while not stop_program.value:
        data = dec_queue.get()
        
        if data is None:
            break
        
        try:
            # Extract features
            if use_mud:
                # Use motor unit decomposition features
                features = get_mud_features(data, fsample=fsample, use_mud=True)
            else:
                # Use standard EMG features
                features = calc_features_multi_win(
                    data=data,
                    data_raw=None,
                    feature_type=feature_type,
                    params=features_params
                )
                
                # Flatten features if needed
                if len(features.shape) > 1:
                    # Take mean across time windows
                    features = np.mean(features, axis=0)
            
            # Decode to proportional values
            if decoder_type == 'mlp':
                # MLP decoder
                features_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device)
                
                with torch.no_grad():
                    proportional_output = decoder(features_tensor).cpu().numpy()[0]
            
            elif decoder_type == 'knn':
                # KNN decoder
                features_array = features.reshape(1, -1)
                proportional_output = decoder.predict(features_array)[0]
            
            # Apply minimum activation threshold
            proportional_output[proportional_output < min_activation_threshold] = 0.0
            
            # Add to smoothing buffer
            output_buffer.append(proportional_output)
            
            # Apply smoothing
            if len(output_buffer) >= 3:
                # Stack buffer and apply Gaussian smoothing
                stacked_outputs = np.array(output_buffer)
                smoothed_output = gaussian_filter1d(stacked_outputs, sigma=smooth_sigma, axis=0)
                final_output = smoothed_output[-1]  # Take most recent smoothed value
            else:
                final_output = proportional_output
            
            # Map to finger control structure
            finger_control = mapper.decode_output(final_output)
            
            # Create timestamp
            timestamp = time.perf_counter()
            
            # Prepare control data
            control_data = {
                'timestamp': timestamp,
                'control_type': 'proportional',
                'finger_control': finger_control,
                'raw_output': final_output,
                'unity_format': mapper.to_unity_format(finger_control),
                'esp32_format': mapper.to_esp32_format(finger_control)
            }
            
            # Send to control queue
            prop_control_queue.put(control_data)
            
            # Store for saving
            buffer_predictions.append({
                'timestamp': timestamp,
                'proportional_output': final_output,
                'finger_control': finger_control
            })
            
            # Save buffer when full
            if len(buffer_predictions) == buffer_predictions_len:
                prop_save_queue.put(list(buffer_predictions))
                buffer_predictions.clear()
            
            # Send to streaming queue for visualization
            if stream_queue is not None:
                stream_queue.put({
                    'type': 'proportional',
                    'output': final_output,
                    'finger_control': finger_control
                })
            
            # Clear queue to prevent backlog
            while not dec_queue.empty():
                dec_queue.get()
        
        except Exception as e:
            print(f"Error in proportional decoding loop: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Cleanup
    prop_control_queue.put(None)
    
    # Save remaining predictions
    if len(buffer_predictions) > 0:
        prop_save_queue.put(list(buffer_predictions))
    prop_save_queue.put(None)
    
    print('Proportional decoding loop stopped')


def StoreProportionalPredictions(prop_save_queue, save_file_name, stop_program):
    """
    Thread for saving proportional predictions.
    
    Args:
        prop_save_queue (Queue): Queue with predictions to save
        save_file_name (str): Output file path
        stop_program (Value): Stop flag
    """
    print('Starting proportional prediction saving loop')
    
    all_predictions = []
    
    while not stop_program.value:
        try:
            predictions = prop_save_queue.get(timeout=0.1)
            
            if predictions is None:
                break
            
            all_predictions.extend(predictions)
        
        except Exception:
            continue
    
    # Save all predictions at once
    if len(all_predictions) > 0:
        with open(save_file_name, 'wb') as f:
            pickle.dump(all_predictions, f)
        
        print(f"Saved {len(all_predictions)} proportional predictions to {save_file_name}")
    
    print('Proportional prediction saving loop stopped')
