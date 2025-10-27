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
import logging
import signal
import time
from pathlib import Path
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_config_files(config_folder):
    """Validate that all required config files exist."""
    required_configs = [
        '64_config.yaml',
        'proportional_control.yaml', 
        'tcp_server_events.yaml',
        'emg_signal_processing.yaml',
        'esp32_control.yaml'
    ]
    
    missing_configs = []
    for config in required_configs:
        config_path = os.path.join(config_folder, config)
        if not os.path.exists(config_path):
            missing_configs.append(config)
    
    if missing_configs:
        logger.error(f"Missing config files: {missing_configs}")
        return False
    
    return True


def validate_model_file(prop_config, decoder_type):
    """Validate that the decoder model file exists."""
    if decoder_type == 'mlp':
        model_file = prop_config.get('proportional_model_file_mlp')
    else:
        model_file = prop_config.get('proportional_model_file_knn')
    
    if not model_file:
        logger.error(f"No model file specified for decoder type: {decoder_type}")
        return False, None
    
    if not os.path.exists(model_file):
        logger.warning(f"Model file does not exist: {model_file}")
        logger.info("You will need to train a model first using train_proportional_decoder.py")
        return False, model_file
    
    return True, model_file


def setup_signal_handlers(processes, stop_program):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        stop_program.value = True
        
        # Give processes time to cleanup
        time.sleep(1)
        
        # Terminate processes if they don't stop
        for proc in processes:
            if proc and proc.is_alive():
                proc.terminate()
                proc.join(timeout=2)
                if proc.is_alive():
                    proc.kill()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def setup_data_directories(args):
    """Setup and validate data directories."""
    subj_id = f'S{args.subj}'
    data_folder = Path('data') / args.subj_type / subj_id / 'proportional'
    
    # Create directories if they don't exist
    data_folder.mkdir(parents=True, exist_ok=True)
    
    # Also create results directory
    results_folder = Path('results-online') / 'proportional' / args.subj_type / subj_id
    results_folder.mkdir(parents=True, exist_ok=True)
    
    return data_folder, results_folder


def create_session_filenames(data_folder, session_num):
    """Create session filenames and check for conflicts."""
    session_id = f'session_{session_num:02d}'
    data_filename = data_folder / f'{session_id}.npy'
    predictions_filename = data_folder / f'{session_id}_predictions.pkl'
    
    # Check if session already exists
    if data_filename.exists():
        logger.error(f"Session file already exists: {data_filename}")
        logger.info("Please use a different session number or delete the existing session.")
        return None, None
    
    return str(data_filename), str(predictions_filename)


def connect_to_amplifier(config_64, emg_proc_config, max_retries=3, retry_delay=2):
    """Connect to EMG amplifier with retry logic."""
    ip_address = config_64['ip_address']
    port = config_64['port']
    num_channels_emg = emg_proc_config['num_channels_emg']
    
    for attempt in range(max_retries):
        logger.info(f"Connecting to EMG amplifier... (attempt {attempt + 1}/{max_retries})")
        
        try:
            conn_64, num_channels_64, fsample, bytes_in_sample = connect_to_sq(
                ip_address, port, num_channels=num_channels_emg
            )
            
            if conn_64 is not None:
                logger.info(f"✓ Connected to amplifier: {ip_address}:{port}")
                logger.info(f"  Channels: {num_channels_emg}, Sampling rate: {fsample} Hz")
                return conn_64, num_channels_64, fsample, bytes_in_sample
            
        except Exception as e:
            logger.error(f"Connection attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    logger.error("Failed to connect to amplifier after all retries.")
    return None, None, None, None


def connect_to_unity(tcp_server_config, max_retries=3, retry_delay=1):
    """Connect to Unity with retry logic."""
    import socket
    
    events_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    events_socket.settimeout(5)  # 5 second timeout
    
    for attempt in range(max_retries):
        try:
            events_socket.connect((
                tcp_server_config['ip_address'],
                tcp_server_config['port']
            ))
            logger.info(f"✓ Connected to Unity: {tcp_server_config['ip_address']}:{tcp_server_config['port']}")
            return events_socket
            
        except Exception as e:
            logger.warning(f"Unity connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    logger.warning("⚠ Could not connect to Unity. Continuing without Unity visualization...")
    
    # Close the socket since connection failed
    try:
        events_socket.close()
    except:
        pass
    
    return None


def setup_esp32_controller(esp32_config):
    """Setup ESP32 controller with error handling."""
    try:
        esp32_controller = ESP32Controller(
            esp32_ip=esp32_config['ip_address'],
            tcp_port=esp32_config['port'],
            timeout=esp32_config.get('timeout', 5),
            connection_mode=esp32_config.get('connection_mode', 'tcp'),
            heartbeat_interval=esp32_config.get('heartbeat_interval', 1)
        )
        
        if esp32_controller.connect():
            logger.info(f"✓ Connected to ESP32: {esp32_config['ip_address']}")
            
            # Set default pressures and speed
            default_pressure = esp32_config.get('default_pressure', {'flexion': 0, 'extension': 0})
            esp32_controller.set_pressure(
                default_pressure.get('flexion', 0),
                default_pressure.get('extension', 0)
            )
            esp32_controller.set_speed(esp32_config.get('default_speed', 2))
            
            return esp32_controller
        else:
            logger.warning("ESP32 connection failed during setup")
            return None
            
    except Exception as e:
        logger.error(f"Error setting up ESP32 controller: {e}")
        return None


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
    parser.add_argument('--config-folder', type=str, default='config',
                       help='Configuration folder path')
    parser.add_argument('--dry-run', action='store_true',
                       help='Test configuration without connecting to hardware')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("EMG PROPORTIONAL CONTROL SYSTEM")
    logger.info("="*60)
    logger.info(f"Decoder: {args.decoder}")
    logger.info(f"Control mode: {args.control_mode}")
    logger.info(f"Motor unit decomposition: {'Yes' if args.use_mud else 'No'}")
    logger.info(f"ESP32 enabled: {'Yes' if args.esp32_enabled else 'No'}")
    logger.info(f"Dry run mode: {'Yes' if args.dry_run else 'No'}")
    logger.info("="*60)
    
    # Validate config files
    if not validate_config_files(args.config_folder):
        logger.error("Configuration validation failed. Exiting.")
        sys.exit(1)
    
    # Load configurations
    try:
        with open(os.path.join(args.config_folder, '64_config.yaml')) as f:
            config_64 = yaml.safe_load(f)
        
        with open(os.path.join(args.config_folder, 'proportional_control.yaml')) as f:
            prop_config = yaml.safe_load(f)
        
        with open(os.path.join(args.config_folder, 'tcp_server_events.yaml')) as f:
            tcp_server_config = yaml.safe_load(f)
        
        with open(os.path.join(args.config_folder, 'emg_signal_processing.yaml')) as f:
            emg_proc_config = yaml.safe_load(f)
        
        with open(os.path.join(args.config_folder, 'esp32_control.yaml')) as f:
            esp32_config = yaml.safe_load(f)
            
    except Exception as e:
        logger.error(f"Error loading configuration files: {e}")
        sys.exit(1)
    
    # Override configurations from command line
    prop_config['decoder_type'] = args.decoder
    prop_config['proportional_control_mode'] = args.control_mode
    prop_config['use_motor_unit_decomposition'] = bool(args.use_mud)
    
    # Validate and set model file
    model_exists, model_file = validate_model_file(prop_config, args.decoder)
    if not model_exists and not args.dry_run:
        logger.error("Model validation failed. Please train a model first or use --dry-run mode.")
        sys.exit(1)
    
    if model_file:
        prop_config['proportional_model_file'] = model_file
    
    # ESP32 override
    if args.esp32_enabled is not None:
        esp32_config['enabled'] = bool(args.esp32_enabled)
    
    # Setup data directories and filenames
    try:
        data_folder, results_folder = setup_data_directories(args)
        data_filename, predictions_filename = create_session_filenames(data_folder, args.session)
        
        if data_filename is None:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error setting up data directories: {e}")
        sys.exit(1)
    
    # Early exit for dry run
    if args.dry_run:
        logger.info("✓ Configuration validation passed")
        logger.info(f"✓ Data would be saved to: {data_filename}")
        logger.info(f"✓ Predictions would be saved to: {predictions_filename}")
        logger.info("Dry run completed successfully!")
        return
    
    # Multiprocessing control variables
    stop_program = Value('b', False)
    
    # Queues
    dec_queue = Queue(maxsize=10)  # Limit queue size to prevent memory issues
    prop_control_queue = Queue(maxsize=50)
    prop_save_queue = Queue(maxsize=100)
    save_queue = Queue(maxsize=100)
    events_queue = Queue()
    unity_events_queue = Queue() if esp32_config['enabled'] else None
    stream_queue = Queue() if emg_proc_config['stream']['enabled'] else None
    prop_esp32_queue = Queue(maxsize=50) if esp32_config['enabled'] else None
    
    # Connect to EMG amplifier
    conn_64, num_channels_64, fsample, bytes_in_sample = connect_to_amplifier(config_64, emg_proc_config)
    if conn_64 is None:
        logger.error("Failed to connect to amplifier. Exiting.")
        sys.exit(1)
    
    # Setup acquisition parameters
    acq_params = {
        'num_channels_64': num_channels_64,
        'num_channels_emg': emg_proc_config['num_channels_emg'],
        'fsample': fsample,
        'buffer_length': emg_proc_config['acq_buffer_length'],
        'streaming_active': emg_proc_config['stream']['enabled']
    }
    
    # Setup decoding parameters
    dec_params = dict(prop_config)
    dec_params['fsample'] = fsample
    
    # Connect to Unity (returns None if connection fails)
    events_socket = connect_to_unity(tcp_server_config)
    
    # Setup ESP32 controller if enabled
    esp32_controller = None
    if esp32_config['enabled']:
        esp32_controller = setup_esp32_controller(esp32_config)
        if esp32_controller is None:
            logger.warning("⚠ ESP32 setup failed. Continuing without ESP32 control...")
            esp32_config['enabled'] = False
    
    # Process list for signal handling
    processes = []
    
    try:
        # Start acquisition process
        logger.info("Starting acquisition process...")
        acquisition_process = Process(
            target=AcquisitionLoop,
            args=(conn_64, bytes_in_sample, acq_params, emg_proc_config,
                  dec_queue, save_queue, stop_program, stream_queue)
        )
        acquisition_process.start()
        processes.append(acquisition_process)
        
        # Start proportional decoding process
        logger.info("Starting proportional decoding process...")
        decoding_process = Process(
            target=ProportionalDecodingLoop,
            args=(acq_params, dec_params, dec_queue, prop_control_queue,
                  prop_save_queue, stop_program, stream_queue)
        )
        decoding_process.start()
        processes.append(decoding_process)
        
        # Start prediction saving thread
        logger.info("Starting prediction saving thread...")
        save_thread = Thread(
            target=StoreProportionalPredictions,
            args=(prop_save_queue, predictions_filename, stop_program),
            daemon=True
        )
        save_thread.start()
        
        # Start data saving thread
        logger.info("Starting data saving thread...")
        from emg_control_64 import SaveData
        data_save_thread = Thread(
            target=SaveData,
            args=(data_filename, save_queue, stop_program),
            daemon=True
        )
        data_save_thread.start()
        
        # Start proportional control process (handles both Unity and ESP32 routing)
        logger.info("Starting proportional control process...")
        control_params = {
            'control_mode': prop_config.get('control_mode', 'synchronized'),  # Use config value
            'min_update_interval': prop_config.get('min_update_interval', 0.05)
        }
        
        control_process = Process(
            target=ProportionalControlLoop,
            args=(events_socket, control_params, prop_control_queue, stop_program,
                  prop_esp32_queue, unity_events_queue)
        )
        control_process.start()
        processes.append(control_process)
        
        # Start ESP32 control process
        esp32_process = None
        if esp32_controller:
            logger.info("Starting ESP32 proportional control process...")
            esp32_process = Process(
                target=ESP32ProportionalControlLoop,
                args=(prop_esp32_queue, esp32_controller, stop_program)
            )
            esp32_process.start()
            processes.append(esp32_process)
        
        # Start streaming process
        streaming_process = None
        if emg_proc_config['stream']['enabled']:
            logger.info("Starting streaming visualization...")
            
            with open(os.path.join(args.config_folder, 'streaming_gui.yaml')) as f:
                stream_config = yaml.safe_load(f)
            
            streaming_process = Process(
                target=StreamingLoop,
                args=(stream_queue, stream_config, stop_program)
            )
            streaming_process.start()
            processes.append(streaming_process)
        
        # Setup signal handlers
        setup_signal_handlers(processes, stop_program)
        
        # Main loop
        logger.info("\n" + "="*60)
        logger.info("PROPORTIONAL CONTROL ACTIVE")
        logger.info("="*60)
        logger.info("Press Ctrl+C to stop...")
        logger.info("="*60 + "\n")
        
        # Wait for processes
        for process in processes:
            if process:
                process.join()
    
    except KeyboardInterrupt:
        logger.info("\n\nReceived interrupt signal. Shutting down...")
        stop_program.value = True
        
        # Wait for processes to finish gracefully
        for process in processes:
            if process:
                process.join(timeout=3)
        
        # Terminate remaining processes
        for process in processes:
            if process and process.is_alive():
                logger.warning(f"Terminating process {process.pid}")
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        stop_program.value = True
        raise
    
    finally:
        # Cleanup
        if 'conn_64' in locals() and conn_64:
            try:
                conn_64.close()
            except:
                pass
        
        if 'events_socket' in locals() and events_socket:
            try:
                events_socket.close()
            except:
                pass
    
    logger.info("\n✓ Proportional control system stopped")
    logger.info(f"Data saved to: {data_filename}")
    logger.info(f"Predictions saved to: {predictions_filename}")


if __name__ == '__main__':
    main()
