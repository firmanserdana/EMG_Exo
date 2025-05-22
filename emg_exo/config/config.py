"""
Configuration management for EMG_Exo package.

This module provides a centralized way to manage configuration settings.
"""

import os
import logging
import sys
from datetime import datetime
import json
from pathlib import Path

# Base package directories
BASE_DIR = Path(__file__).parent.parent.absolute()
DATA_DIR = BASE_DIR / 'data'
MODEL_DIR = BASE_DIR / 'models'
CONFIG_DIR = BASE_DIR / 'config'
LOG_DIR = BASE_DIR / 'logs'

# Ensure directories exist
for directory in [DATA_DIR, MODEL_DIR, CONFIG_DIR, LOG_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# Default config file paths
DEFAULT_CONFIG_FILE = CONFIG_DIR / 'default_config.json'
USER_CONFIG_FILE = CONFIG_DIR / 'user_config.json'

# Default configuration
DEFAULT_CONFIG = {
    # Logging configuration
    "logging": {
        "level": "INFO",
        "file_level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    },
    
    # Paths configuration
    "paths": {
        "data_dir": str(DATA_DIR),
        "model_dir": str(MODEL_DIR),
        "log_dir": str(LOG_DIR)
    },
    
    # EMG Sessantaquatro board configuration
    "emg_sessantaquatro": {
        "port": "COM3",  # Default COM port for Windows
        "baudrate": 115200,
        "sampling_rate": 2048,  # Hz
        "channels": 64,  # Sessantaquatro board has 64 channels
        "resolution": 24,  # bits
        "reference": "monopolar"
    },

    # Delsys Trigno EMG configuration
    "emg_trigno": {
        "host": "127.0.0.1",  # Default local IP address for the Trigno control utility
        "command_port": 50040,  # Default command port for the Trigno system
        "emg_port": 50041,     # Default EMG data port
        "aux_port": 50042,     # Default accelerometer/auxiliary data port
        "sampling_rate": 2000, # Default sampling rate in Hz
        "channels": 16,        # Default: Trigno system supports up to 16 sensors
        "resolution": 16,      # Bits of resolution
        "use_aux_data": False  # Whether to use accelerometer/auxiliary data
    },

    # EMG processing configuration
    "emg_processing": {
        "window_size": 1024,  # samples
        "window_overlap": 512,  # samples
        "bandpass_low": 10.0,  # Hz
        "bandpass_high": 500.0,  # Hz
        "notch_freq": 50.0,  # Hz (for power line interference)
        "notch_quality": 30.0,  # Quality factor for notch filter
        "highpass_cutoff": 20.0,  # Hz
        "lowpass_cutoff": 450.0,  # Hz
        "buffer_time": 5.0,  # seconds
        "feature_window": 0.25,  # seconds
        "feature_overlap": 0.5,  # ratio of overlap
        "features_enabled": ["rms", "mav", "zc", "ssc", "wl", "var", "freq_mean", "freq_median", "freq_power"],
        "decomposition_method": "FastICA"  # Options: "FastICA", "PCA", "CKC"
    },

    # Recording configuration
    "recording": {
        "save_raw_emg": True,
        "save_processed_emg": True,
        "save_decomposed_mus": True
    },

    # Machine learning / decoder configuration
    "decoding": {
        "classifiers": ["kNN", "MLP"],
        "features": ["RMS", "MAV", "WL", "ZC", "SSC", "AR"],
        "training_ratio": 0.7,  # 70% training, 30% testing
        "cv_folds": 5,  # Cross-validation folds
        "normalize": True  # Standardize features
    },

    # Unity hand control configuration
    "unity_interface": {
        "ip_address": "127.0.0.1",  # localhost
        "port": 9000,
        "protocol": "UDP",  # Options: "UDP", "TCP"
        "update_rate": 30,  # Updates per second
        "command_delay": 0.01  # Seconds between commands
    },

    # Degrees of Freedom configuration
    "dof_config": {
        "thumb": ["flexion", "extension", "pinching"],
        "index": ["flexion", "extension", "pinching"],
        "middle": ["flexion", "extension", "pinching"],
        "ring_little": ["flexion", "extension"],
        "thumb_abduction": True
    }
}

# Save default config if it doesn't exist
if not DEFAULT_CONFIG_FILE.exists():
    with open(DEFAULT_CONFIG_FILE, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

# Global config object
CONFIG = {}

def load_config():
    """Load configuration from files, merging default and user configs."""
    # Start with default config
    config = DEFAULT_CONFIG.copy()
    
    # Load user config if it exists and merge with default
    if USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
            
            # Deep merge configs
            _deep_merge(config, user_config)
        except Exception as e:
            print(f"Error loading user config: {e}")
    
    return config

def _deep_merge(base, update):
    """Deep merge two dictionaries."""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base

def save_user_config(config):
    """Save user configuration to file."""
    with open(USER_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def update_config(path, value):
    """Update configuration at specific path.
    
    Args:
        path (str): Dot-separated path to config value (e.g. "emg_sessantaquatro.port")
        value: Value to set
    """
    global CONFIG
    path_parts = path.split('.')
    
    # Navigate to the right level
    current = CONFIG
    for part in path_parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    # Set the value
    current[path_parts[-1]] = value
    
    # Save to user config
    save_user_config(CONFIG)

# Setup logger
def setup_logger():
    """Configure logger based on settings."""
    # Get logging config
    logging_config = CONFIG.get('logging', {})
    
    # Create logger
    logger = logging.getLogger('EMGExo')
    logger.setLevel(logging.getLevelName(logging_config.get('level', 'INFO')))
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.getLevelName(logging_config.get('level', 'INFO')))
    
    # Create log file
    log_dir = CONFIG.get('paths', {}).get('log_dir', str(LOG_DIR))
    log_file = os.path.join(log_dir, f'emg_exo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.getLevelName(logging_config.get('file_level', 'DEBUG')))
    
    # Create formatter and add it to handlers
    formatter = logging.Formatter(logging_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# Initialize configuration
CONFIG = load_config()
logger = setup_logger()

# For backward compatibility
EMG_CONFIG = CONFIG.get('emg_sessantaquatro', {})
TRIGNO_CONFIG = CONFIG.get('emg_trigno', {})
EMG_PROCESSING = CONFIG.get('emg_processing', {})
RECORDING = CONFIG.get('recording', {})
DECODING = CONFIG.get('decoding', {})
HAND_CONTROL = CONFIG.get('unity_interface', {})
DOF_CONFIG = CONFIG.get('dof_config', {})

# Update paths for backward compatibility
RECORDING["save_dir"] = os.path.join(CONFIG.get('paths', {}).get('data_dir', str(DATA_DIR)), "recordings")
os.makedirs(RECORDING["save_dir"], exist_ok=True)

if __name__ == "__main__":
    print("EMG Exo Application Configuration")
    print("=================================")
    
    # Print each section of the config
    for section, values in CONFIG.items():
        print(f"\n{section.replace('_', ' ').title()} Configuration:")
        if isinstance(values, dict):
            for key, value in values.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {values}")
