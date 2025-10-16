"""
EMG Proportional Control System
==============================

Main script for real-time proportional EMG control with Unity and ESP32.

Usage:
    python emg_proportional_control.py --decoder mlp --control-mode individual_fingers
    python emg_proportional_control.py --decoder knn --control-mode whole_hand --esp32-enabled 1
"""

import os
import sys
import yaml
import argparse
import queue
from multiprocessing import Process, Queue, Value
from threading import Thread

# Import components
from realtime_components.acquisition import AcquisitionLoop
from realtime_components.proportional_decoding import (
    ProportionalDecodingLoop,
    StoreProportionalPredictions
)
from realtime_components.proportional_control import (
    ProportionalControlLoop,
    ESP32ProportionalControlLoop
)
from realtime_components.events_handler import EventsHandlerLoop
from realtime_components.streaming import StreamingLoop
from realtime_components.esp32_control import ESP32Controller
from utils.communication_64 import connect_to_sq
from utils.general_utils import acquisition_arg_parser


def main():
    """Main function for proportional control"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='EMG Proportional Control System')
    parser.add_argument('--decoder', type=str, default='mlp', choices=['mlp', 'knn'],
                       help='Decoder type (mlp or knn)')
    parser.add_argument('--control-mode', type=str, default='individual_fingers',
                       choices=['individual_fingers', 'whole_hand'],
                       help='Proportional control mode')
    parser.add_argument('--use-mud', type=int, default=0, choices=[0, 1],
                       help='Use motor unit decomposition (0=no, 1=yes)')
    parser.add_argument('--esp32-enabled', type=int, default=0, choices=[0, 1],
                       help='Enable ESP32 control (0=no, 1=yes)')
    parser.add_argument('--subj-type', type=str, default='healthy',
                       help='Subject type (healthy or SCI)')
    parser.add_argument('--subj', type=int, default=0,
                       help='Subject number')
    parser.add_argument('--session', type=int, default=0,
                       help='Session number')
    
    args = parser.parse_args()
    
    print("="*60)
    print("EMG PROPORTIONAL CONTROL SYSTEM")
    print("="*60)
    print(f"Decoder: {args.decoder}")
    print(f"Control mode: {args.control_mode}")
    print(f"Motor unit decomposition: {'Yes' if args.use_mud else 'No'}")
    print(f"ESP32 enabled: {'Yes' if args.esp32_enabled else 'No'}")
    print("="*60)
    
    # Load configurations
    config_folder = 'config'
    
    with open(os.path.join(config_folder, '64_config.yaml')) as f:
        config_64 = yaml.safe_load(f)
    
    with open(os.path.join(config_folder, 'proportional_control.yaml')) as f:
        prop_config = yaml.safe_load(f)
    
    with open(os.path.join(config_folder, 'tcp_server_events.yaml')) as f:
        tcp_server_config = yaml.safe_load(f)
    
    with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
        emg_proc_config = yaml.safe_load(f)
    
    with open(os.path.join(config_folder, 'esp32_control.yaml')) as f:
        esp32_config = yaml.safe_load(f)
    
    # Override configurations from command line
    prop_config['decoder_type'] = args.decoder
    prop_config['proportional_control_mode'] = args.control_mode
    prop_config['use_motor_unit_decomposition'] = bool(args.use_mud)
    
    # Set model file based on decoder type
    if args.decoder == 'mlp':
        prop_config['proportional_model_file'] = prop_config['proportional_model_file_mlp']
    else:
        prop_config['proportional_model_file'] = prop_config['proportional_model_file_knn']
    
    # ESP32 override
    if args.esp32_enabled is not None:
        esp32_config['enabled'] = bool(args.esp32_enabled)
    
    # Setup data folders
    subj_id = f'S{args.subj}'
    data_folder = os.path.join('data', args.subj_type, subj_id, 'proportional')
    os.makedirs(data_folder, exist_ok=True)
    
    # File names
    session_id = f'session_{args.session:02d}'
    data_filename = os.path.join(data_folder, f'{session_id}.npy')
    predictions_filename = os.path.join(data_folder, f'{session_id}_predictions.pkl')
    
    # Check if session already exists
    if os.path.exists(data_filename):
        print(f"\nError: Session file already exists: {data_filename}")
        print("Please use a different session number.")
        sys.exit(1)
    
    # Multiprocessing control variables
    stop_program = Value('b', False)
    
    # Queues
    dec_queue = Queue()
    prop_control_queue = Queue()
    prop_save_queue = Queue()
    save_queue = Queue()
    events_queue = Queue()
    unity_events_queue = Queue() if esp32_config['enabled'] else None
    stream_queue = Queue() if emg_proc_config['stream']['enabled'] else None
    prop_esp32_queue = Queue(maxsize=50) if esp32_config['enabled'] else None
    
    # Connect to EMG amplifier
    print("\nConnecting to EMG amplifier...")
    ip_address = config_64['ip_address']
    port = config_64['port']
    num_channels_emg = emg_proc_config['num_channels_emg']
    
    conn_64, num_channels_64, fsample, bytes_in_sample = connect_to_sq(
        ip_address, port, num_channels=num_channels_emg
    )
    
    if conn_64 is None:
        print("Failed to connect to amplifier. Exiting.")
        sys.exit(1)
    
    print(f"✓ Connected to amplifier: {ip_address}:{port}")
    print(f"  Channels: {num_channels_emg}, Sampling rate: {fsample} Hz")
    
    # Setup acquisition parameters
    acq_params = {
        'num_channels_64': num_channels_64,
        'num_channels_emg': num_channels_emg,
        'fsample': fsample,
        'buffer_length': emg_proc_config['acq_buffer_length'],
        'streaming_active': emg_proc_config['stream']['enabled']
    }
    
    # Setup decoding parameters
    dec_params = dict(prop_config)
    dec_params['fsample'] = fsample
    
    # Start acquisition process
    print("\nStarting acquisition process...")
    acquisition_process = Process(
        target=AcquisitionLoop,
        args=(conn_64, bytes_in_sample, acq_params, emg_proc_config,
              dec_queue, save_queue, stop_program, stream_queue)
    )
    acquisition_process.start()
    
    # Start proportional decoding process
    print("Starting proportional decoding process...")
    decoding_process = Process(
        target=ProportionalDecodingLoop,
        args=(acq_params, dec_params, dec_queue, prop_control_queue,
              prop_save_queue, stop_program, stream_queue)
    )
    decoding_process.start()
    
    # Start prediction saving thread
    print("Starting prediction saving thread...")
    save_thread = Thread(
        target=StoreProportionalPredictions,
        args=(prop_save_queue, predictions_filename, stop_program),
        daemon=True
    )
    save_thread.start()
    
    # Start data saving thread
    print("Starting data saving thread...")
    from emg_control_64 import SaveData
    data_save_thread = Thread(
        target=SaveData,
        args=(data_filename, save_queue, stop_program),
        daemon=True
    )
    data_save_thread.start()
    
    # Connect to Unity via TCP
    print("\nConnecting to Unity...")
    import socket
    events_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        events_socket.connect((
            tcp_server_config['ip_address'],
            tcp_server_config['port']
        ))
        print(f"✓ Connected to Unity: {tcp_server_config['ip_address']}:{tcp_server_config['port']}")
    except Exception as e:
        print(f"⚠ Could not connect to Unity: {e}")
        print("  Continuing without Unity visualization...")
    
    # Start proportional control process
    print("Starting proportional control process...")
    control_params = {
        'control_mode': 'synchronized',
        'min_update_interval': prop_config.get('min_update_interval', 0.05)
    }
    
    control_process = Process(
        target=ProportionalControlLoop,
        args=(events_socket, control_params, prop_control_queue, stop_program,
              prop_esp32_queue, unity_events_queue)
    )
    control_process.start()
    
    # Start ESP32 control (if enabled)
    esp32_process = None
    if esp32_config['enabled']:
        print("Starting ESP32 proportional control...")
        
        # Create ESP32 controller
        esp32_controller = ESP32Controller(
            esp32_ip=esp32_config['ip_address'],
            tcp_port=esp32_config['port'],
            timeout=esp32_config['timeout'],
            connection_mode=esp32_config['connection_mode'],
            heartbeat_interval=esp32_config['heartbeat_interval']
        )
        
        # Connect to ESP32
        if esp32_controller.connect():
            print(f"✓ Connected to ESP32: {esp32_config['ip_address']}")
            
            # Set default pressures and speed
            esp32_controller.set_pressure(
                esp32_config['default_pressure']['flexion'],
                esp32_config['default_pressure']['extension']
            )
            esp32_controller.set_speed(esp32_config['default_speed'])
            
            # Start ESP32 control loop
            esp32_process = Process(
                target=ESP32ProportionalControlLoop,
                args=(prop_esp32_queue, esp32_controller, stop_program)
            )
            esp32_process.start()
        else:
            print("⚠ Could not connect to ESP32. Continuing without ESP32 control...")
    
    # Start streaming (if enabled)
    streaming_process = None
    if emg_proc_config['stream']['enabled']:
        print("Starting streaming visualization...")
        
        with open(os.path.join(config_folder, 'streaming_gui.yaml')) as f:
            stream_config = yaml.safe_load(f)
        
        streaming_process = Process(
            target=StreamingLoop,
            args=(stream_queue, stream_config, stop_program)
        )
        streaming_process.start()
    
    # Main loop
    print("\n" + "="*60)
    print("PROPORTIONAL CONTROL ACTIVE")
    print("="*60)
    print("Press Ctrl+C to stop...")
    print("="*60 + "\n")
    
    try:
        # Wait for processes
        acquisition_process.join()
        decoding_process.join()
        control_process.join()
        
        if esp32_process:
            esp32_process.join()
        
        if streaming_process:
            streaming_process.join()
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        stop_program.value = True
        
        # Wait for processes to finish
        acquisition_process.join(timeout=2)
        decoding_process.join(timeout=2)
        control_process.join(timeout=2)
        
        if esp32_process:
            esp32_process.join(timeout=2)
        
        if streaming_process:
            streaming_process.join(timeout=2)
        
        # Terminate if still running
        for proc in [acquisition_process, decoding_process, control_process, 
                     esp32_process, streaming_process]:
            if proc and proc.is_alive():
                proc.terminate()
    
    print("\n✓ Proportional control system stopped")
    print(f"Data saved to: {data_filename}")
    print(f"Predictions saved to: {predictions_filename}")


if __name__ == '__main__':
    main()
