import os
import psutil
import platform
import re
import glob
import time
import json
import yaml
import queue
import sys
import select
import numpy as np
from multiprocessing import Process, Queue, Value
from threading import Thread

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None

from realtime_components.acquisition import AcquisitionLoop
from realtime_components.events_handler import *
from realtime_components.decoding import *
from realtime_components.control import *
from realtime_components.streaming import *
from realtime_components.esp32_control import ESP32ControlLoop
from utils.signal_filtering import *
from utils.communication_64 import *
from utils.network_utils import *
from utils.data_utils import *
from utils.general_utils import *

# Set the process priority to real-time
process = psutil.Process(os.getpid())

try:
    if platform.system() == "Windows":
        # On Windows, use REALTIME_PRIORITY_CLASS for highest priority
        process.nice(psutil.REALTIME_PRIORITY_CLASS) # requires admin privileges
    else:  # macOS/Linux
        # Range: -20 (highest) to 19 (lowest), default is 0
        process.nice(-20)  # Highest priority (requires sudo/admin privileges)
    
    print(f"Process priority set to: {process.nice()}")
except psutil.AccessDenied:
    print("Warning: Unable to set real-time priority. Run with sudo for higher priority.")
    print(f"Current process priority: {process.nice()}")
except Exception as e:
    print(f"Warning: Could not set process priority: {e}")
    print(f"Current process priority: {process.nice()}")

# Thread for saving the predictions made by the model
def StorePredictionLoop(pred_save_queue, pred_file_name, stop_program):
    print('Starting the prediction saving loop')

    while not stop_program.value:
        try:
            # Get the predictions from the queue
            predictions = pred_save_queue.get(timeout=0.1)

            if predictions is not None:
                with open(pred_file_name, 'ab') as f:
                    pickle.dump(predictions, f)
            else:
                break
        except queue.Empty:
            continue
        except KeyboardInterrupt:
            break

    print('Prediction saving loop stopped')

# Thread for saving the EMG raw data recorded
def SaveData(data_filename, save_queue, stop_program):
    print('Starting the saving loop')

    # saving the data
    with open(data_filename, 'ab') as file:
        while not stop_program.value:
            try:
                data = save_queue.get(timeout=0.1) # wait until there is something in the queue to save

                if data is not None:
                    np.save(file, data)
                else:
                    break
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                break

    print('Saving loop stopped')  


def wait_for_enter_to_stop(prompt="Press Enter to stop the acquisition..."):
    """Wait for Enter using robust TTY handling.

    Supports both regular newline and CSI-u encoded Enter keys (e.g. '\x1b[13u').
    """
    print(prompt, end='', flush=True)

    # Fallback to standard input if no interactive TTY is available.
    if not sys.stdin.isatty() or termios is None or tty is None:
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer = ''

    try:
        tty.setcbreak(fd)
        while True:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if not ready:
                continue

            chunk = os.read(fd, 32)
            if not chunk:
                break

            text = chunk.decode(errors='ignore')
            buffer += text

            if ('\n' in text) or ('\r' in text) or ('\x1b[13u' in buffer) or ('\x1b[27;13~' in buffer):
                break

            # Keep buffer bounded while still preserving escape sequence tails.
            if len(buffer) > 64:
                buffer = buffer[-64:]
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print()


def SendUnitySessionContext(
    events_socket,
    output_directory,
    session_label,
    session_index,
    subject_id,
    task_name,
    acquisition_type,
):
    """Publish the current save location so Unity-side logs land beside EMG files."""
    payload = {
        'eventName': 'session_context',
        'eventID': int(session_index),
        'outputDirectory': os.path.abspath(output_directory),
        'sessionLabel': session_label,
        'subjectID': subject_id,
        'taskName': task_name,
        'acquisitionType': acquisition_type,
    }

    try:
        events_socket.sendall((json.dumps(payload) + '\n').encode('utf-8'))
        print(
            'Sent Unity session context: '
            f"folder={payload['outputDirectory']}, label={payload['sessionLabel']}"
        )
    except Exception as exc:
        print(f'Warning: failed to send Unity session context: {exc}')

# ------ MAIN ------
if __name__ == "__main__":
    # Parse command line arguments
    args = acquisition_arg_parser(description='Run EMG acquisition and decoding session',)

    # General params
    subj_type = args.subj_type
    subj = args.subj
    task = args.task
    decoding_active = bool(args.decoding_active)
    acquisition_type = args.acquisition_type
    session = args.session
    is_mvc_session = args.is_mvc_session
    esp32_enabled_override = args.esp32_enabled
    control_mode = args.control_mode

    subj_id = f'S{subj}'

    # folders definition
    config_folder = 'config'
    data_folder = os.path.join('data', subj_type, subj_id)
    data_raw_folder = os.path.join(data_folder, 'raw') # destination folder for the raw data
    data_mvc_folder = os.path.join(data_folder, 'mvc') # destination folder for the MVC data
    models_folder = os.path.join('models-subjects', subj_type, subj_id, task)

    os.makedirs(data_raw_folder, exist_ok=True)
    os.makedirs(data_mvc_folder, exist_ok=True)

    # loading configurations files
    with open(os.path.join(config_folder, '64_config.yaml')) as f:
        config_64 = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'tcp_server_events.yaml')) as f:
        tcp_server_events = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
        emg_proc_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'features_params.yaml')) as f:
        features_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'decoding_params.yaml')) as f:
        decoding_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'esp32_control.yaml')) as f:
        esp32_cfg = yaml.load(f, Loader=yaml.FullLoader)

    # Override ESP32 enabled setting if specified via command line
    if esp32_enabled_override is not None:
        esp32_cfg['enabled'] = bool(esp32_enabled_override)
        print(f"ESP32 control override: {'enabled' if esp32_cfg['enabled'] else 'disabled'}")
            
    # 64 connection parameters
    ip_address = config_64['ip_address']
    port = config_64['port']   

    streaming_active = emg_proc_cfg['stream']['enabled']
 
    # file names setup
    if not is_mvc_session:
        existing_files = sorted(glob.glob(os.path.join(data_raw_folder, 'session_[0-9]*.npy')))

        if not existing_files:
            session_num = 0
        else: # last session number + 1
            session_num = int(re.search(r'session_(\d+)\.npy', existing_files[-1]).group(1)) + 1 # use a data_filename with incrementally number
        
        data_filename = os.path.join(data_raw_folder, f'session_{session_num:02d}.npy')
        events_filename = os.path.join(data_raw_folder, f'session_{session_num:02d}_events.pkl')
        pred_save_file_name = os.path.join(data_raw_folder, f'session_{session_num:02d}_predictions.pkl')
        session_index = session_num
        session_label = f'session_{session_num:02d}'
        session_output_directory = data_raw_folder
    else:
        data_filename = os.path.join(data_mvc_folder, 'mvc.npy')
        events_filename = os.path.join(data_mvc_folder, 'mvc_events.pkl')
        pred_save_file_name = os.path.join(data_mvc_folder, 'mvc_predictions.pkl')
        session_index = -1
        session_label = 'mvc'
        session_output_directory = data_mvc_folder
    
    mvc_file = os.path.join(data_mvc_folder, 'dataset_mvc.pkl')

    if os.path.isfile(data_filename):
        print("\n\nCHANGE SESSION NAME: a session with the same name exists already \n\n")
        exit()

    # controlling variable and queues initialization
    stop_program = Value('b', False)
    is_decoding = Value('b', False) # variable to control when the decoding is active

    events_queue = Queue()
    unity_events_queue = Queue() if (decoding_active and esp32_cfg['enabled']) else None
    save_queue = Queue()
    dec_queue = Queue()
    dec_state_queue = Queue() # queue for the decoding state (if needed)

    if decoding_active:
        pred_control_queue = Queue() # predictions queue for the session control
        pred_save_queue = Queue() # predictions queue for the saving of the predictions

    # queue for ESP32 control (if enabled) - increased size for better parallel processing
    pred_esp32_queue = Queue(maxsize=50) if esp32_cfg['enabled'] and decoding_active else None

    # queue for the streaming data
    stream_queue = Queue() if streaming_active else None

    # Open connection to the amplifier      
    num_channels_emg = emg_proc_cfg['num_channels_emg'] # number of EMG channels of the device
    channel_range = emg_proc_cfg.get('channel_range', [0, num_channels_emg]) # [start, end) channel indices
    num_channels_used = channel_range[1] - channel_range[0] # actual number of channels to record
    (conn_64,num_channels_64,fsample,bytes_in_sample) = connect_to_sq(ip_address, port, num_channels=num_channels_emg)

    if conn_64 is None:
        print("Failed to connect to the amplifier. Exiting the program.")
        exit()

    # setup params
    acq_params = {
        'num_channels_64': num_channels_64, # number of total channels from the 64
        'num_channels_emg': num_channels_used, # number of EMG channels to be used
        'channel_range': channel_range, # [start, end) channel indices to record
        'fsample': fsample, 
        'buffer_length': emg_proc_cfg['acq_buffer_length'],
        'bytes_in_sample': bytes_in_sample,
        'notch': emg_proc_cfg['notch'] if 'notch' in emg_proc_cfg else False,
        'bandpass': emg_proc_cfg['bandpass'] if 'bandpass' in emg_proc_cfg else False,
        'streaming_active': streaming_active,
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
        model_file = os.path.join(models_folder, f'{model_type}_{acquisition_type}.pth')

        labels_encoder_file = os.path.join(data_folder, f'{acquisition_type}_{task}_labels_encoder.pkl')

        seq_len = subj_cfg[f'task_{task}']['seq_len'] # sequence length for the model    
        feature_type = features_cfg['feature_type'] # type of features to be extracted
        feature_win_len = features_cfg['windows_length'][feature_type]['win_length']
        feature_win_shift = features_cfg['windows_length'][feature_type]['win_shift']

        # Define number of classes for each task
        task_num_classes = {
            'open_close': 3,  # classes: 0 (rest), 1 (close), 2 (open)
            'grasp_patterns': 4,  # classes: 0 (rest), 2 (hook), 3 (lateral), 4 (index pointing)
            'single_fingers': 4   # classes: 0 (rest), 5 (thumb), 6 (index), 7 (MRP)
        }

        dec_params = {
            'model_type': model_type,
            'num_class': task_num_classes[task],
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
            'use_consec_pred': decoding_cfg['use_consec_pred'],
            'control_mode': control_mode,
            'task': task
        }

        if decoding_cfg['use_consec_pred']:
            control_params['num_consec_pred'] = decoding_cfg['num_consec_pred']
    else:
        dec_params = None
        control_params = None

    # opening the events server socket
    events_socket = socket_connect(
        host=tcp_server_events['host'], 
        port=tcp_server_events['port'],
        timeout=tcp_server_events['timeout']
    )

    if events_socket is None:
        print("Failed to connect to the events server. Exiting the program.")
        exit()

    SendUnitySessionContext(
        events_socket=events_socket,
        output_directory=session_output_directory,
        session_label=session_label,
        session_index=session_index,
        subject_id=subj_id,
        task_name=task,
        acquisition_type=acquisition_type,
    )

    # if streaming is enabled -> opening the streaming socket
    if streaming_active:
        stream_socket = socket_connect(
            host=emg_proc_cfg['stream']['sender']['host'], 
            port=emg_proc_cfg['stream']['sender']['port'],
            timeout=emg_proc_cfg['stream']['timeout']
        )

        if stream_socket is None:
            print("Failed to connect to the streaming server. Exiting the program.")
            exit()
    else:
        stream_socket = None

    # starting the sub-processes
    p_acquisition = Process(
        target=AcquisitionLoop, 
        args=(conn_64, acq_params, dec_params, dec_queue, save_queue, stop_program, decoding_active, is_decoding, stream_queue)
    )
    p_events = Process(
        target=EventsLoop,
        args=(
            events_socket,
            events_queue,
            stop_program,
            decoding_active,
            is_decoding,
            unity_events_queue,
        ),
    )
    p_datasave = Thread(target=SaveData, args=(data_filename, save_queue, stop_program)) # better using Thread for I/O workers      
    
    if decoding_active:
        p_decoding = Process(
            target=DecodingLoop,
            args=(acq_params, dec_params, dec_queue, pred_control_queue, pred_save_queue, stop_program, stream_queue)
        )

        # Dispatch to appropriate control loop based on control_mode
        if control_mode == 'fsm':
            from realtime_components.fsm_control import FSMControlLoop
            p_control = Process(
                target=FSMControlLoop,
                args=(
                    events_socket,
                    control_params,
                    pred_control_queue,
                    stop_program,
                    pred_esp32_queue,
                )
            )
        elif control_mode == 'sci_hybrid':
            from realtime_components.sci_control import SCIControlLoop
            sci_config_path = os.path.join('config', 'sci_patient.yaml')
            with open(sci_config_path, 'r') as f:
                sci_config = yaml.safe_load(f)
            p_control = Process(
                target=SCIControlLoop,
                args=(
                    events_socket,
                    control_params,
                    pred_control_queue,
                    stop_program,
                    pred_esp32_queue,
                    unity_events_queue,
                    sci_config,
                )
            )
        else:  # synchronized, unity_only, esp32_only
            p_control = Process(
                target=ControlLoop,
                args=(
                    events_socket,
                    control_params,
                    pred_control_queue,
                    stop_program,
                    pred_esp32_queue,
                    unity_events_queue,
                )
            )
        p_pred_save = Thread(
            target=StorePredictionLoop, 
            args=(pred_save_queue, pred_save_file_name, stop_program)
        )

    # ESP32 control process (if enabled)
    if esp32_cfg['enabled'] and decoding_active and pred_esp32_queue is not None:
        p_esp32 = Process(
            target=ESP32ControlLoop,
            args=(esp32_cfg, pred_esp32_queue, stop_program, task)
        )

    if streaming_active:
        p_stream = Thread(
            target=StreamDataLoop, 
            args=(stream_socket, stream_queue, stop_program)
        )
    
    print(f'\nStarting the acquisition system: {num_channels_emg} channels with {fsample} sampling rate')

    p_acquisition.start()
    p_events.start()
    p_datasave.start()

    if decoding_active:
        p_decoding.start()
        p_control.start()
        p_pred_save.start()

    # Start ESP32 process if enabled
    if esp32_cfg['enabled'] and decoding_active and pred_esp32_queue is not None:
        p_esp32.start()
        print("ESP32 control process started")

    if streaming_active:
        p_stream.start()

    time.sleep(2.5) # wait for the processes to start

    try:
        wait_for_enter_to_stop("Press Enter to stop the acquisition...")
    except KeyboardInterrupt:
        print("\nStopping the program...")
    
    stop_program.value = True

    if p_datasave.is_alive():
        p_datasave.join()  

    # saving the events
    event_items = []

    while not events_queue.empty():
        event_items.append(events_queue.get())

    with open(events_filename, 'wb') as f:
        pickle.dump(event_items, f)

    # print events list
    print("\nEvents saved:")
    for event in event_items:
        print(f"  - {event['timestamp']}: {event['event_type']} ({event.get('data', '')})")
    print(f"Events saved to {events_filename}")

    print("Events saved")

    time.sleep(2) # sleep for allowing the threads to complete the saving

    socket_close(events_socket)
    print("Events socket closed")

    if decoding_active:
        if p_decoding.is_alive():
            p_decoding.terminate()

        if p_control.is_alive():
            p_control.terminate()

        if p_pred_save.is_alive():
            p_pred_save.join()

        # Terminate ESP32 process if running
        if esp32_cfg['enabled'] and pred_esp32_queue is not None:
            if 'p_esp32' in locals() and p_esp32.is_alive():
                p_esp32.terminate()
                print("ESP32 control process terminated")

    if streaming_active:
        socket_close(stream_socket)
        print("Streaming socket closed")

    if p_acquisition.is_alive():
        p_acquisition.terminate()

    print("\nProgram ended")