import os
import re
import glob
import time
import keyboard
import yaml
import json
import numpy as np
import scipy.io
import pickle
import torch
from torch.nn.functional import softmax
from multiprocessing import Process, Queue, Value
from threading import Thread
from collections import deque

from utils.signal_filtering import *
from utils.communication_64 import *
from utils.network_utils import *
from utils.data_utils import *

# Sottoprocesso di acquisizione
def AcquisitionLoop(connection, acq_params, dec_params, dec_queue, save_queue, stop_program, decoding_active=False):
    print('\nStarting the acquisition loop')
    
    # loading the acquisition and decoding parameters
    num_channels_64 = acq_params['num_channels_64']
    num_channels_emg = acq_params['num_channels_emg']
    fsample = acq_params['fsample']
    acq_buffer_length = acq_params['buffer_length']
    bytes_in_sample = acq_params['bytes_in_sample']

    if decoding_active:
        if dec_params['mvc_normalization']:
            mvc_data = scipy.io.loadmat(dec_params['mvc_file'])
            mvc = mvc_data['mvc'][0]

        dec_win_length = dec_params['dec_win_length']
        dec_win_shift = dec_params['dec_win_shift']

        dec_win_samples = round(fsample*dec_win_length)
        dec_win_shift_samples = round(fsample*dec_win_shift)

    # initialization
    buffer_data = deque([], maxlen=int(fsample*acq_buffer_length)) # using deque for circular buffer

    for _ in range(int(fsample*acq_buffer_length)):
        buffer_data.append(np.zeros(num_channels_emg+1,))

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

    t0 = time.perf_counter()
    last_ts = t0  # last timestamp of the sample received

    # loop for reading the data from the 64
    while not stop_program.value:
        sample_bytes = read_raw_bytes(connection, num_channels_64, bytes_in_sample)
        
        # getting the timestamp of data
        timestamp = time.perf_counter()

        time_acq = timestamp - last_ts

        if time_acq > 0.100:
            print(f"Warning: acquisition time exceeded! ({time_acq:.3f}s)")

        last_ts = timestamp  # update the last timestamp

        # Convert the bytes into integer values
        sample_from_channels = bytes_to_integers(sample_bytes, num_channels_64, bytes_in_sample, output_milli_volts=False)

        # saving the data in the buffer (filling it like a circular buffer)
        buffer_data.append(np.concatenate((sample_from_channels[:num_channels_emg], [timestamp]))) # 1st sample
        buffer_data.append(np.concatenate((sample_from_channels[num_channels_64:num_channels_64+num_channels_emg], [timestamp]))) # 2nd sample

        sample_i += 2

        # putting the data in the decoding buffer for prediction
        if decoding_active and sample_i % dec_win_shift_samples == 0:
            buffer_raw_data = np.array(buffer_data)[:,:num_channels_emg]

            # filtering the data
            if acq_params['notch']:
                buffer_raw_data, zi_notch = notch_filter(buffer_raw_data, b_notch, a_notch, zi_notch)

            if acq_params['bandpass']:
                buffer_raw_data, zi_band = butter_bandpass_filter(buffer_raw_data, b_band, a_band, zi_band)

            # mvc normalization
            if dec_params['mvc_normalization']:
                buffer_raw_data = buffer_raw_data / mvc

            dec_queue.put(buffer_raw_data[-dec_win_samples:,:])

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

    print('Acquisition loop stopped')   

# Thread for reading the Unity TCP events
def EventsLoop(events_socket, events_queue, stop_program):
    print('\nStarting the events loop')

    # reading events loop
    while not stop_program.value:
        try:
            data = events_socket.recv(1024)
            if not data:
                continue

            timestamp = time.perf_counter()

            buffer = data.decode()

            while '\n' in buffer:
                event_msg, buffer = buffer.split('\n', 1)

                try:
                    event_json = json.loads(event_msg)
                except json.JSONDecodeError:
                    print(f"Received invalid JSON data: {event_msg}")
                    continue

                event = event_json.get("event", "")
                event_id = event_json.get("event_id")
                
                if event_id is not None:
                    event = f"{event}_{event_id}"

                events_queue.put((event, timestamp))  # Put the received data and timestamp in the queue
        except socket.timeout:
            continue  # Timeout occurred, check stop_program and loop again
        except KeyboardInterrupt:
            break
        except OSError:
            break

    print("Events loop stopped")     

def DecodingLoop(acq_params, dec_params, dec_queue, pred_control_queue, pred_save_queue, stop_program):
    print('\nStarting the decoding loop...')

    # loading the decoding parameters
    feature_type = dec_params['feature_type']
    seq_len = dec_params['seq_len']

    # loading the model
    is_cuda = torch.cuda.is_available()
    device = torch.device("cuda") if is_cuda else torch.device("cpu")

    model = torch.load(dec_params['model_file'], weights_only=False, map_location=device)
    model.eval()

    # buffers initialization
    buffer_features = deque([], maxlen=seq_len) # using deque for circular buffer

    for _ in range(seq_len):
        buffer_features.append(np.zeros((acq_params['num_channels_emg'],)))

    buffer_predictions_len = dec_params['buffer_predictions_size']
    buffer_predictions = deque([], maxlen=buffer_predictions_len) # using deque for circular buffer
    pred_i = 0 

    # decoding loop
    while not stop_program.value:
        data = dec_queue.get()

        if data is not None:
            # retrieve and store the features
            features = calc_features(data, feature_type)
            buffer_features.append(features) # append the features to the buffer

            # decoding
            data = torch.tensor(np.array(buffer_features), dtype=torch.float32).unsqueeze(0).to(device)

            with torch.no_grad():
                output = model(data)

            prediction = torch.argmax(output, 1).cpu().numpy()[0] # get the prediction from the model
            pred_prob = softmax(output).cpu().numpy()[0]

            pred_control_queue.put((prediction, pred_prob[prediction]))  # Put the prediction in the control queue

            # saving the prediction
            buffer_predictions.append((prediction, pred_prob[prediction]))

            if len(buffer_predictions) == buffer_predictions_len:
                pred_save_queue.put(np.array(buffer_predictions))
                buffer_predictions.clear()

            # Empty the queue
            while not dec_queue.empty():
                dec_queue.get()
        else:
            break
    
    pred_control_queue.put(None) # Put None in the control queue to stop the control loop
    pred_save_queue.put(np.array(buffer_predictions)[-pred_i:])
    pred_save_queue.put(None) # Put None in the save queue to stop the saving loop
    
    print('Decoding loop stopped')    

def ControlLoop(events_socket, control_params, pred_control_queue, stop_program):
    print('\nStarting the control loop...')
    
    # variables initialization
    dec_win_shift = control_params['dec_win_shift']
    last_ts = time.perf_counter()  # last timestamp of the event received

    # decoding loop
    while not stop_program.value:
        data = pred_control_queue.get()
        rcv_time = time.perf_counter()

        if data is not None:
            pred = data[0]  # prediction from the model
            pred_prob = data[1]  # prediction probability

            # check online time constraint
            if (rcv_time - last_ts) > dec_win_shift+0.75*dec_win_shift:
                print(f"Warning: time constraint exceeded! (time interval: {rcv_time - last_ts:.3f}s)")
            
            # print(f"pred: {pred} - prob: {pred_prob:.2f} (time interval: {rcv_time - last_ts:.3f}s)")
            last_ts = rcv_time  # update the last timestamp
        else:
            break

    print('Control loop stopped')

# Thread for saving the predictions made by the model
def StorePredictionLoop(pred_save_queue, pred_file_name, stop_program):
    print('\nStarting the prediction saving loop')

    while not stop_program.value:
        # Get the predictions from the queue
        predictions = pred_save_queue.get()

        if predictions is not None:
            with open(pred_file_name, 'ab') as f:
                pickle.dump(predictions, f)
        else:
            break

    print('Prediction saving loop stopped')

# Thread for saving the EMG raw data recorded
def SaveData(data_filename, save_queue):
    print('\nStarting the saving loop')

    # saving the data
    with open(data_filename, 'ab') as file:
        while True:  
            data = save_queue.get() # wait until there is something in the queue to save

            if data is not None:
                np.save(file, data)  
            else:
                break   

    print('Saving loop stopped')  
            
# ------ MAIN ------
if __name__ == "__main__":
    # TODO: move this to the parameters input of the script - since it's based on the type of decoding being performed
    subj_type = 'healthy' # 'healthy' or 'SCI' - TODO: make this a parameter of the script
    subj = 0 #int(input("Subject number: ")) # TODO: make this a parameter of the script
    task = 'open_close' # options: ['open_close','single_fingers','grasp_patterns'] - TODO: make this a parameter of the script
    decoding_active = True # TODO: make this a parameter of the script
    model_version = 'open_loop' # options ['open_loop','closed_loop'] - TODO: make this a parameter of the script

    subj_id = f'S{subj}'

    # folders definition
    config_folder = 'config'
    data_folder = os.path.join('data', subj_type, subj_id, 'raw')  # destination folder for the data
    data_mvc_folder = os.path.join('data', subj_type, subj_id, 'mvc')
    models_folder = os.path.join('models-subjects', subj_type, subj_id, task)

    os.makedirs(data_folder, exist_ok=True)
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
            
    # 64 connection parameters
    ip_address = config_64['ip_address']
    port = config_64['port']   
 
    # file names setup
    existing_files = sorted(glob.glob(os.path.join(data_folder, 'session_[0-9]*.npy')))

    if not existing_files:
        session_num = 0
    else: # last session number + 1
        session_num = int(re.search(r'session_(\d+)\.npy', existing_files[-1]).group(1)) + 1 # use a data_filename with incrementally number
    
    data_filename = os.path.join(data_folder, f'session_{session_num:02d}.npy')
    events_filename = os.path.join(data_folder, f'session_{session_num:02d}_events.pkl')
    pred_save_file_name = os.path.join(data_folder, f'session_{session_num:02d}_predictions.pkl')
    mvc_file = os.path.join(data_mvc_folder, 'raw_dataset_mvc.mat')

    if os.path.isfile(data_filename):
        print("\n\nCHANGE SESSION NAME: a session with the same name exists already \n\n")
        exit()

    # controlling variable and queues initialization
    stop_program = Value('b', False)

    events_queue = Queue()
    save_queue = Queue()
    dec_queue = Queue()

    if decoding_active:
        pred_control_queue = Queue() # predictions queue for the session control
        pred_save_queue = Queue() # predictions queue for the saving of the predictions

    # Open connection to the amplifier      
    num_channels_emg = emg_proc_cfg['num_channels_emg'] # number of EMG channels to be used       
    (connection,num_channels_64,fsample,bytes_in_sample) = connect_to_sq(ip_address, port, num_channels=num_channels_emg)

    # setup params
    acq_params = {
        'num_channels_64': num_channels_64, # number of total channels from the 64
        'num_channels_emg': num_channels_emg, # number of EMG channels to be used
        'fsample': fsample, 
        'buffer_length': emg_proc_cfg['acq_buffer_length'],
        'bytes_in_sample': bytes_in_sample,
        'notch': emg_proc_cfg['notch'] if 'notch' in emg_proc_cfg else False,
        'bandpass': emg_proc_cfg['bandpass'] if 'bandpass' in emg_proc_cfg else False,
    }

    if decoding_active:
        with open(os.path.join(config_folder, 'subjects', subj_type, f'{subj_id}.yaml')) as f:
            subj_cfg = yaml.load(f, Loader=yaml.FullLoader)

        with open(os.path.join(config_folder, 'features_params.yaml')) as f:
            features_cfg = yaml.load(f, Loader=yaml.FullLoader)

        model_type = subj_cfg[f'task_{task}']['model_type'] # options: ['LSTM', 'TFM', 'CTFM']
        model_file = os.path.join(models_folder, f'{model_type}_{model_version}.pth')

        seq_len = subj_cfg[f'task_{task}']['seq_len'] # sequence length for the model    
        num_class = decoding_cfg['num_class'][f'task_{task}'] # number of classes for the decoding
        feature_type = features_cfg['feature_type'] # type of features to be extracted
        feature_win_len = features_cfg['windows_length'][feature_type]['win_length']
        decoding_win_shift = decoding_cfg['decoding_win_shift']

        dec_params = {
            'feature_type': feature_type,
            'dec_win_length': feature_win_len,
            'dec_win_shift': decoding_win_shift,
            'model_file': model_file,
            'seq_len': subj_cfg[f'task_{task}']['seq_len'],
            'num_class': num_class,
            'buffer_predictions_size': decoding_cfg['buffer_predictions_size']
        }

        if features_cfg['normalization'] == 'mvc':
            dec_params['mvc_normalization'] = True
            dec_params['mvc_file'] = mvc_file
        else:
            dec_params['mvc_normalization'] = False

        control_params = {
            'dec_win_shift': decoding_win_shift
        }
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

    # starting the sub-processes
    p_acquisition = Process(
        target=AcquisitionLoop, 
        args=(connection, acq_params, dec_params, dec_queue, save_queue, stop_program, decoding_active)
    )
    p_events = Process(target=EventsLoop, args=(events_socket, events_queue, stop_program))
    p_datasave = Thread(target=SaveData, args=(data_filename, save_queue)) # better using Thread for I/O workers      
    
    if decoding_active:
        p_decoding = Process(
            target=DecodingLoop, 
            args=(acq_params, dec_params, dec_queue, pred_control_queue, pred_save_queue, stop_program)
        )
        p_control = Process(
            target=ControlLoop, 
            args=(events_socket, control_params, pred_control_queue, stop_program)
        )
        p_pred_save = Process(
            target=StorePredictionLoop, 
            args=(pred_save_queue, pred_save_file_name, stop_program)
        )
    
    p_acquisition.start()
    p_events.start()
    p_datasave.start()

    if decoding_active:
        p_decoding.start()
        p_control.start()
        p_pred_save.start()

    print(f'\nStarting the acquisition system: {num_channels_emg} channels with {fsample} sampling rate')

    time.sleep(2.5) # wait for the processes to start

    print("Press 'esc' to stop the script\n")

    try:               
        keyboard.wait('esc')   
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
            p_pred_save.terminate()

    if p_acquisition.is_alive():
        p_acquisition.join()
        p_acquisition.terminate()

    print("\nProgram ended")