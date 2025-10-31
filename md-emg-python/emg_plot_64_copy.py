import os
import time
import yaml
import glob
import re
import argparse
import json
import threading
import datetime
import numpy as np
from multiprocessing import Process, Queue, Value
from threading import Thread
try:
    import keyboard
except ImportError:
    print("Warning: keyboard module not installed. Install with: pip install keyboard")
    keyboard = None

from realtime_components.acquisition import AcquisitionLoop
from realtime_components.decoding import *
from realtime_components.control import *
from realtime_components.streaming import *
from utils.signal_filtering import *
from utils.communication_64 import *
from utils.network_utils import *
from utils.data_utils import *


def parse_args():
    parser = argparse.ArgumentParser(
        description="EMG acquisition pipeline with optional decoding/control."
    )
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="Disable decoding/control loops so the script only streams EMG for plotting.",
    )
    parser.add_argument(
        "--save-emg",
        action="store_true",
        help="Persist streamed EMG buffers to disk alongside plotting.",
    )
    parser.add_argument(
        "--save-dir",
        default=None,
        help="Directory where EMG buffers will be stored (defaults to subject data folder).",
    )
    parser.add_argument(
        "--enable-gestures",
        action="store_true",
        help="Enable gesture timestamp marking with space bar.",
    )
    return parser.parse_args()

# Global variables for timestamp marking
gesture_timestamps = []
timestamp_lock = threading.Lock()
start_time = None
gesture_counter = 0

def keyboard_listener(stop_program, enable_gestures):
    """
    Listen for keyboard events to mark gesture timestamps.
    Press SPACE to mark when a gesture occurs.
    """
    global gesture_timestamps, gesture_counter, start_time
    
    if not keyboard or not enable_gestures:
        return

    import platform
    if platform.system() == 'Linux':
        if os.geteuid() != 0:
            script_name = os.path.basename(__file__)
            print("\nWARNING: Gesture marking requires root privileges on Linux")
            print(f"Run with: sudo python {script_name} --enable-gestures")
            print("Gesture marking is disabled for this session.\n")
            return
        
    print("\n=== GESTURE MARKING ENABLED ===")
    print("Press SPACE when a gesture occurs to mark the timestamp")
    print("Timestamps will be saved alongside EMG data")
    print("================================\n")
    
    while not stop_program.value:
        try:
            # Check for space bar press
            if keyboard.is_pressed('space'):
                if start_time is not None:
                    current_time = time.time()
                    relative_timestamp = current_time - start_time
                    
                    with timestamp_lock:
                        gesture_counter += 1
                        timestamp_data = {
                            'gesture_id': gesture_counter,
                            'timestamp': relative_timestamp,
                            'absolute_time': datetime.datetime.now().isoformat(),
                            'description': f'Gesture {gesture_counter}'
                        }
                        gesture_timestamps.append(timestamp_data)
                        
                    print(f"\n*** GESTURE {gesture_counter} MARKED at {relative_timestamp:.3f}s ***")
                    
                    # Prevent multiple rapid triggers
                    time.sleep(0.5)
                    
            time.sleep(0.05)  # Small delay to prevent high CPU usage
            
        except Exception as e:
            print(f"Error in keyboard listener: {e}")
            break

def save_timestamps(session_file, timestamps):
    """
    Save gesture timestamps to a JSON file alongside the EMG data.
    """
    if not timestamps or not session_file:
        return
        
    # Create timestamp filename based on session file
    timestamp_file = session_file.replace('.npy', '_timestamps.json')
    
    try:
        with open(timestamp_file, 'w') as f:
            json.dump({
                'session_info': {
                    'total_gestures': len(timestamps),
                    'session_file': os.path.basename(session_file),
                    'created_at': datetime.datetime.now().isoformat()
                },
                'gestures': timestamps
            }, f, indent=2)
        print(f"\n*** Gesture timestamps saved to: {timestamp_file} ***")
        print(f"*** Total gestures marked: {len(timestamps)} ***")
    except Exception as e:
        print(f"Error saving timestamps: {e}")

# Thread for saving the predictions made by the model
def StorePredictionLoop(pred_save_queue):
    print('Starting the prediction saving loop')

    while True:
        # Get the predictions from the queue
        predictions = pred_save_queue.get()

        if predictions is not None:
            continue  # just clearing the queue
        else:
            break

    print('Prediction saving loop stopped')

# Thread for saving the EMG raw data recorded
def SaveData(save_queue, save_enabled=False, session_file=None, dtype=np.float32):
    print('Starting the saving loop')

    file_handle = None
    try:
        if save_enabled and session_file:
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            file_handle = open(session_file, 'ab')

        while True:
            try:
                data = save_queue.get()

                if data is None:
                    break

                if save_enabled and file_handle:
                    np.save(file_handle, data.astype(dtype))
            except KeyboardInterrupt:
                break
    finally:
        if file_handle:
            file_handle.close()

    if save_enabled and session_file:
        print(f"Saved EMG session to {session_file}")

    print('Saving loop stopped')

# ------ MAIN ------
if __name__ == "__main__":
    args = parse_args()
    # TODO: move this to the parameters input of the script - since it's based on the type of decoding being performed
    subj_type = 'healthy' # 'healthy' or 'SCI' - TODO: make this a parameter of the script
    subj = 10 # TODO: make this a parameter of the script
    task = 'open_close' # options: ['open_close','grasp_patterns','single_fingers'] - TODO: make this a parameter of the script
    decoding_active = True # TODO: make this a parameter of the script
    if args.plot_only:
        # Plot-only mode disables decoding/control loops so only EMG streaming remains active
        decoding_active = False
    model_version = 'open_loop' # options ['open_loop','both'] - TODO: make this a parameter of the script

    subj_id = f'S{subj}'

    # folders definition
    config_folder = 'config'
    data_folder = os.path.join('data', subj_type, subj_id)
    data_mvc_folder = os.path.join(data_folder, 'mvc') # destination folder for the MVC data
    models_folder = os.path.join('models-subjects', subj_type, subj_id, task)

    # loading configurations files
    with open(os.path.join(config_folder, '64_config.yaml')) as f:
        config_64 = yaml.load(f, Loader=yaml.FullLoader)

    if decoding_active:  
        with open(os.path.join(config_folder, 'tcp_server_events.yaml')) as f:
            tcp_server_events = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
        emg_proc_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'features_params.yaml')) as f:
        features_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'decoding_params.yaml')) as f:
        decoding_cfg = yaml.load(f, Loader=yaml.FullLoader)
            
    # 64 connection parameters
    ip_address = config_64['ip_address']
    port = config_64['port']   

    # file names setup
    mvc_file = os.path.join(data_mvc_folder, 'dataset_mvc.pkl')

    # controlling variable and queues initialization
    stop_program = Value('b', False)
    is_decoding = Value('b', True if decoding_active else False) # variable to control when the decoding is active

    save_queue = Queue()
    dec_queue = Queue()
    dec_state_queue = Queue() # queue for the decoding state (if needed)

    if decoding_active:
        pred_control_queue = Queue() # predictions queue for the session control
        pred_save_queue = Queue() # predictions queue for the saving of the predictions

    # queue for the streaming data
    # Stream settings control whether EMG samples are forwarded to the GUI/VR stack
    stream_cfg = emg_proc_cfg.get('stream', {})
    streaming_enabled = stream_cfg.get('enabled', True)
    stream_queue = Queue() if streaming_enabled else None

    # Open connection to the amplifier      
    num_channels_emg = emg_proc_cfg['num_channels_emg'] # number of EMG channels to be used       
    (conn_64,num_channels_64,fsample,bytes_in_sample) = connect_to_sq(ip_address, port, num_channels=num_channels_emg)

    if conn_64 is None:
        print("Failed to connect to the amplifier. Exiting the program.")
        exit()

    # setup params
    acq_params = {
        'num_channels_64': num_channels_64, # number of total channels from the 64
        'num_channels_emg': num_channels_emg, # number of EMG channels to be used
        'fsample': fsample, 
        'buffer_length': emg_proc_cfg['acq_buffer_length'],
        'bytes_in_sample': bytes_in_sample,
        'notch': emg_proc_cfg['notch'] if 'notch' in emg_proc_cfg else False,
        'bandpass': emg_proc_cfg['bandpass'] if 'bandpass' in emg_proc_cfg else False,
        'streaming_active': streaming_enabled,
        'proc_interval': emg_proc_cfg['processing_interval']
    }

    if features_cfg['normalization'] == 'mvc':
        acq_params['mvc_normalization'] = True
        acq_params['mvc_file'] = mvc_file
    else:
        acq_params['mvc_normalization'] = False

    if features_cfg['normalization'] == 'zscore':
        acq_params['zscore_normalization'] = True
        acq_params['zscore_win_len'] = features_cfg['normalization_params']['zscore']['win_length']
    else:
        acq_params['zscore_normalization'] = False

    if decoding_active:
        with open(os.path.join(config_folder, 'subjects', subj_type, f'{subj_id}.yaml')) as f:
            subj_cfg = yaml.load(f, Loader=yaml.FullLoader)

        model_type = subj_cfg[f'task_{task}']['model_type'] # options: ['LSTM', 'TFM', 'CTFM']
        model_file = os.path.join(models_folder, f'{model_type}_{model_version}.pth')

        labels_encoder_file = os.path.join(data_folder, f'{model_version}_{task}_labels_encoder.pkl')

        seq_len = subj_cfg[f'task_{task}']['seq_len'] # sequence length for the model    
        feature_type = features_cfg['feature_type'] # type of features to be extracted
        feature_win_len = features_cfg['windows_length'][feature_type]['win_length']
        feature_win_shift = features_cfg['windows_length'][feature_type]['win_shift']

        dec_params = {
            'feature_type': feature_type,
            'dec_win_length': feature_win_len,
            'dec_win_shift': feature_win_shift,
            'model_file': model_file,
            'labels_encoder_file': labels_encoder_file,
            'seq_len': seq_len,
            'buffer_predictions_size': decoding_cfg['buffer_predictions_size']
        }

        control_params = {
            'proc_interval': emg_proc_cfg['processing_interval'],
            'use_consec_pred': decoding_cfg['use_consec_pred']
        }

        if decoding_cfg['use_consec_pred']:
            control_params['num_consec_pred'] = decoding_cfg['num_consec_pred']
    else:
        dec_params = None
        control_params = None

    if decoding_active:
        # opening the events server socket
        events_socket = socket_connect(
            host=tcp_server_events['host'], 
            port=tcp_server_events['port'],
            timeout=tcp_server_events['timeout']
        )

        if events_socket is None:
            print("Failed to connect to the events server. Exiting the program.")
            exit()

    # opening the streaming socket (if enabled)
    stream_socket = None
    if streaming_enabled:
        stream_socket = socket_connect(
            host=emg_proc_cfg['stream']['sender']['host'], 
            port=emg_proc_cfg['stream']['sender']['port'],
            timeout=emg_proc_cfg['stream']['timeout']
        )

        if stream_socket is None:
            print("Failed to connect to the streaming server. Exiting the program.")
            exit()

    # starting the sub-processes
    p_acquisition = Process(
        target=AcquisitionLoop, 
        args=(conn_64, acq_params, dec_params, dec_queue, save_queue, stop_program, decoding_active, is_decoding, stream_queue)
    )
    save_enabled = args.save_emg
    save_directory = args.save_dir or os.path.join(data_folder, 'emg_logs')
    session_file = None
    if save_enabled:
        os.makedirs(save_directory, exist_ok=True)

        existing_sessions = sorted(glob.glob(os.path.join(save_directory, 'session_[0-9]*.npy')))

        if not existing_sessions:
            session_index = 0
        else:
            session_match = re.search(r'session_(\d+)\.npy', os.path.basename(existing_sessions[-1]))
            session_index = int(session_match.group(1)) + 1 if session_match else 0

        session_file = os.path.join(save_directory, f'session_{session_index:02d}.npy')
        print(f"EMG session will be saved to: {session_file}")
    p_datasave = Thread(
        target=SaveData,
        args=(save_queue, save_enabled, session_file),
        kwargs={"dtype": np.float32},
    ) # better using Thread for I/O workers
    
    if decoding_active:
        p_decoding = Process(
            target=DecodingLoop, 
            args=(acq_params, dec_params, dec_queue, pred_control_queue, pred_save_queue, stop_program, stream_queue)
        )
        p_control = Process(
            target=ControlLoop, 
            args=(events_socket, control_params, pred_control_queue, stop_program)
        )
        p_pred_save = Thread(
            target=StorePredictionLoop, 
            args=(pred_save_queue,)
        )

    p_stream = None
    if streaming_enabled:
        p_stream = Thread(
            target=StreamDataLoop, 
            args=(stream_socket, stream_queue, stop_program)
        )
    
    # Start keyboard listener thread for gesture marking
    p_keyboard = None
    if args.enable_gestures and keyboard:
        p_keyboard = Thread(
            target=keyboard_listener,
            args=(stop_program, args.enable_gestures)
        )
        p_keyboard.daemon = True
    
    print(f'\nStarting the acquisition system: {num_channels_emg} channels with {fsample} sampling rate')

    # Record start time for relative timestamps
    start_time = time.time()
    
    p_acquisition.start()
    p_datasave.start()

    if decoding_active:
        p_decoding.start()
        p_control.start()
        p_pred_save.start()

    if p_stream:
        p_stream.start()
        
    if p_keyboard:
        p_keyboard.start()

    time.sleep(2.5) # wait for the processes to start

    try:   
        input("Press Enter to stop the acquisition...")  # wait for the user to start the acquisition
    except KeyboardInterrupt:
        print("\nStopping the program...")
    
    stop_program.value = True

    if p_datasave.is_alive():
        p_datasave.join()  

    time.sleep(2) # sleep for allowing the threads to complete the saving
    
    # Save gesture timestamps if any were recorded
    if gesture_timestamps and save_enabled:
        save_timestamps(session_file, gesture_timestamps.copy())

    if decoding_active:
        print("Events socket closed")

        if p_decoding.is_alive():
            p_decoding.terminate()

        if p_control.is_alive():
            p_control.terminate()

        if p_pred_save.is_alive():
            p_pred_save.join()

    if streaming_enabled and stream_socket is not None:
        socket_close(stream_socket)
        print("Streaming socket closed")

    if p_acquisition.is_alive():
        p_acquisition.terminate()

    print("\nProgram ended")