import time
import numpy as np
from collections import deque
import scipy.io

from utils.data_utils import load_pickle
from utils.signal_filtering import *
from utils.communication_64 import *

def AcquisitionLoop(conn_64, acq_params, dec_params, dec_queue, save_queue, stop_program, decoding_active=False, is_decoding=None, stream_queue=None):
    print('Starting the acquisition loop')
    
    # loading the acquisition and decoding parameters
    num_channels_64 = acq_params['num_channels_64']
    num_channels_emg = acq_params['num_channels_emg']
    channel_range = acq_params.get('channel_range', [0, num_channels_emg]) # [start, end) channel indices
    ch_start, ch_end = channel_range[0], channel_range[1]
    fsample = acq_params['fsample']
    acq_buffer_length = acq_params['buffer_length']
    bytes_in_sample = acq_params['bytes_in_sample']
    streaming_active = acq_params['streaming_active']
    proc_interval = acq_params['proc_interval']
    proc_interval_samples = round(fsample*proc_interval)

    if acq_params['mvc_normalization']:
        mvc_mean = load_pickle(acq_params['mvc_file'])['mvc_mean']
    elif acq_params['zscore_normalization']:
        zscore_win_len = acq_params['zscore_win_len']
        zscore_win_samples = round(fsample*zscore_win_len)
        
        buffer_zscore = deque([], maxlen=zscore_win_samples) # buffer for z-score normalization
        buffer_zscore.extend(np.zeros((1, num_channels_emg))) # initialization

    if decoding_active:
        seq_len = dec_params['seq_len']
        dec_win_length = dec_params['dec_win_length']
        dec_win_shift = dec_params['dec_win_shift']

        dec_win_samples = round(fsample*dec_win_length)
        dec_win_shift_samples = round(fsample*dec_win_shift)
        dec_seq_len_samples = dec_win_samples + (seq_len-1)*dec_win_shift_samples # number of samples for each prediction sequence

    # initialization
    buffer_data = deque([], maxlen=int(fsample*acq_buffer_length)) # using deque for circular buffer

    buffer_data.extend(np.zeros((int(fsample*acq_buffer_length), num_channels_emg+1))) # initialization

    sample_i = 0

    # initialization of the filters
    if acq_params['notch']:
        b_notch, a_notch, zi_notch = notch(
            notch_freq=acq_params['notch']['freq'], 
            Q=acq_params['notch']['Q'], 
            fs=fsample
        )
        zi_notch = np.transpose(np.array([zi_notch for _ in range(num_channels_emg)]))

    if acq_params['bandpass']:
        b_band, a_band, zi_band = butter_bandpass(
            lowcut=acq_params['bandpass']['freq'][0], 
            highcut=acq_params['bandpass']['freq'][1],
            order=acq_params['bandpass']['order'],
            fs=fsample
        )
        zi_band = np.transpose(np.array([zi_band for _ in range(num_channels_emg)]))

    # =============================================================================
    # SCI-Specific Filters Initialization
    # =============================================================================
    sci_config = acq_params.get('sci_config', {})
    sci_enabled = sci_config.get('enabled', False)
    
    # Spatial filter (Laplacian or CAR)
    spatial_filter = None
    if sci_enabled:
        spatial_cfg = sci_config.get('signal_enhancement', {}).get('spatial_filter', {})
        if spatial_cfg.get('enabled', False):
            filter_type = spatial_cfg.get('type', 'laplacian')
            if filter_type == 'laplacian':
                grid_shape = tuple(spatial_cfg.get('grid_shape', [8, 4]))
                laplacian_type = spatial_cfg.get('laplacian_type', 'small')
                spatial_filter = LaplacianFilter(grid_shape=grid_shape, filter_type=laplacian_type)
                print(f'  + Laplacian spatial filter enabled ({laplacian_type}, grid: {grid_shape})')
            elif filter_type == 'car':
                spatial_filter = CommonAverageReference()
                print('  + Common Average Reference (CAR) filter enabled')
    
    # Adaptive LMS filter for motor artifact removal
    adaptive_filter = None
    if sci_enabled:
        adaptive_cfg = sci_config.get('signal_enhancement', {}).get('adaptive_filter', {})
        if adaptive_cfg.get('enabled', False):
            filter_order = adaptive_cfg.get('filter_order', 32)
            learning_rate = adaptive_cfg.get('learning_rate', 0.01)
            adaptive_filter = LMSAdaptiveFilter(
                n_channels=num_channels_emg,
                filter_order=filter_order,
                mu=learning_rate
            )
            print(f'  + LMS adaptive filter enabled (order: {filter_order}, mu: {learning_rate})')
    
    # Motion artifact detector
    artifact_detector = None
    if sci_enabled:
        artifact_cfg = sci_config.get('signal_enhancement', {}).get('motion_artifact', {})
        if artifact_cfg.get('enabled', False):
            threshold = artifact_cfg.get('threshold_factor', 5.0)
            artifact_detector = MotionArtifactDetector(
                n_channels=num_channels_emg,
                fsample=fsample,
                artifact_threshold=threshold
            )
            print(f'  + Motion artifact detector enabled (threshold: {threshold}x)')
    
    # Highpass filter for removing low-frequency motion artifacts (SCI-specific)
    highpass_enabled = sci_enabled and sci_config.get('signal_enhancement', {}).get('highpass', {}).get('enabled', False)
    if highpass_enabled:
        hp_cutoff = sci_config.get('signal_enhancement', {}).get('highpass', {}).get('cutoff', 20)
        hp_order = sci_config.get('signal_enhancement', {}).get('highpass', {}).get('order', 2)
        b_high, a_high, zi_high = butter_highpass(cutoff=hp_cutoff, order=hp_order, fs=fsample)
        zi_high = np.transpose(np.array([zi_high for _ in range(num_channels_emg)]))
        print(f'  + Highpass filter enabled ({hp_cutoff} Hz, order {hp_order})')

    t0 = time.perf_counter()

    # loop for reading the data from the 64
    while not stop_program.value:
        sample_bytes = read_raw_bytes(conn_64, num_channels_64, bytes_in_sample)
        
        # getting the timestamp of data
        timestamp = time.perf_counter()

        # Convert the bytes into integer values
        sample_from_channels = bytes_to_integers(sample_bytes, num_channels_64, bytes_in_sample, output_milli_volts=False)

        # saving the data in the buffer (filling it like a circular buffer)
        buffer_data.append(np.concatenate((sample_from_channels[ch_start:ch_end], [timestamp]))) # 1st sample
        buffer_data.append(np.concatenate((sample_from_channels[num_channels_64+ch_start:num_channels_64+ch_end], [timestamp]))) # 2nd sample

        sample_i += 2

        # putting the data in the decoding buffer for prediction
        if sample_i % proc_interval_samples == 0:
            buffer_raw_data = np.array(buffer_data)[:,:num_channels_emg]

            # filtering the data
            if acq_params['notch']:
                buffer_raw_data, zi_notch = notch_filter(buffer_raw_data, b_notch, a_notch, zi_notch)

            if acq_params['bandpass']:
                buffer_raw_data, zi_band = butter_bandpass_filter(buffer_raw_data, b_band, a_band, zi_band)

            # =============================================================================
            # SCI-Specific Filtering Pipeline
            # =============================================================================
            if sci_enabled:
                # Apply highpass to remove low-frequency motion artifacts
                if highpass_enabled:
                    buffer_raw_data, zi_high = butter_highpass_filter(buffer_raw_data, b_high, a_high, zi_high)
                
                # Apply spatial filter (Laplacian or CAR) for EMI reduction
                if spatial_filter is not None:
                    buffer_raw_data = spatial_filter.apply(buffer_raw_data)
                
                # Detect and suppress motion artifacts
                if artifact_detector is not None:
                    is_artifact, artifact_mask = artifact_detector.detect(buffer_raw_data[-proc_interval_samples:,:])
                    if np.any(is_artifact):
                        # Apply soft mask to suppress artifacts
                        buffer_raw_data[-proc_interval_samples:,:] *= artifact_mask[:, np.newaxis]

            # decoding
            if decoding_active and is_decoding.value:
                dec_raw_data = buffer_raw_data[-dec_seq_len_samples:,:]

                if acq_params['zscore_normalization']:
                    # z-score normalization
                    buffer_array = np.array(buffer_zscore)
                    zscore_mean = np.mean(buffer_array, axis=0)
                    zscore_std = np.std(buffer_array, axis=0)
                    dec_raw_data = (dec_raw_data - zscore_mean) / (zscore_std + 1e-8)
                elif acq_params['mvc_normalization']:
                    # mvc normalization
                    dec_raw_data = dec_raw_data / mvc_mean
            
                # put the data in the decoding queue
                dec_queue.put(dec_raw_data)

            # streaming data if streaming is active
            if streaming_active:
                # put the data in the streaming queue
                stream_queue.put(buffer_raw_data[-proc_interval_samples:,:])

            # extending the zscore buffer if z-score normalization is used
            if acq_params['zscore_normalization']:
                buffer_zscore.extend(buffer_raw_data[-proc_interval_samples:,:])

        # saving the data in the buffer
        if sample_i >= fsample*acq_buffer_length:
            t1 = time.perf_counter()

            # put the data in the queue
            save_queue.put(np.array(buffer_data))            

            sample_i = 0 # reset the sample counter

            # check of the sample frequency at which the data are acquired            
            total_time = t1-t0
            current_fsample = (fsample*acq_buffer_length/total_time)

            if current_fsample>fsample*1.1 or current_fsample<fsample*0.9:
                print(f"Sample frequency: {current_fsample:.0f} Hz")

            t0 = time.perf_counter()  

    save_queue.put(np.array(buffer_data)[-sample_i:]) # put the remaining data in the queue  
    save_queue.put(None) # put None in the queue to stop the saving loop
    
    if decoding_active:
        dec_queue.put(None) # put None in the queue to stop the decoding loop

    if streaming_active:
        stream_queue.put(None)

    print('Acquisition loop stopped')   