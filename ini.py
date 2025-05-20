#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration settings for the EMG processing application.
"""

import os
import logging
import sys
from datetime import datetime

# Setup logging
logger = logging.getLogger('EMGExo')
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create log directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Create file handler for logging
log_file = os.path.join(log_dir, f'emg_exo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Create formatter and add it to handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Paths for saving data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODEL_DIR = os.path.join(BASE_DIR, 'models')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# EMG board configuration
EMG_CONFIG = {
    "port": "COM3",  # Default COM port for Windows
    "baudrate": 115200,
    "sampling_rate": 2048,  # Hz
    "channels": 64,  # Sessantaquatro board has 64 channels
    "resolution": 24,  # bits
    "reference": "monopolar"
}

# EMG processing configuration
EMG_PROCESSING = {
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
}

# Recording configuration
RECORDING = {
    "save_dir": os.path.join(DATA_DIR, "recordings"),
    "save_raw_emg": True,
    "save_processed_emg": True,
    "save_decomposed_mus": True
}

# Machine learning / decoder configuration
DECODING = {
    "classifiers": ["kNN", "MLP"],
    "features": ["RMS", "MAV", "WL", "ZC", "SSC", "AR"],
    "training_ratio": 0.7,  # 70% training, 30% testing
    "cv_folds": 5,  # Cross-validation folds
    "normalize": True  # Standardize features
}

# Unity hand control configuration
HAND_CONTROL = {
    "ip_address": "127.0.0.1",  # localhost
    "port": 9000,
    "protocol": "UDP",  # Options: "UDP", "TCP"
    "update_rate": 30,  # Updates per second
    "command_delay": 0.01  # Seconds between commands
}

# Degrees of Freedom configuration
DOF_CONFIG = {
    "thumb": ["flexion", "extension", "pinching"],
    "index": ["flexion", "extension", "pinching"],
    "middle": ["flexion", "extension", "pinching"],
    "ring_little": ["flexion", "extension"],
    "thumb_abduction": True
}

# If this file is run directly, print configuration
if __name__ == "__main__":
    print("EMG Exo Application Configuration")
    print("=================================")
    
    print("\nEMG Configuration:")
    for key, value in EMG_CONFIG.items():
        print(f"  {key}: {value}")
        
    print("\nProcessing Configuration:")
    for key, value in EMG_PROCESSING.items():
        print(f"  {key}: {value}")
        
    print("\nHand DoF Configuration:")
    for key, value in DOF_CONFIG.items():
        print(f"  {key}: {value}")
        
    print("\nRecording Configuration:")
    for key, value in RECORDING.items():
        print(f"  {key}: {value}")
        
    print("\nDecoding Configuration:")
    for key, value in DECODING.items():
        print(f"  {key}: {value}")
        
    print("\nHand Control Configuration:")
    for key, value in HAND_CONTROL.items():
        print(f"  {key}: {value}")