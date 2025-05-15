#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Initialization file for EMG Exoskeleton Control System.
Contains configuration parameters for the application.
"""

import os
import logging
from datetime import datetime

# Setup logging
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.path.join(LOG_DIR, f"emg_exo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
)
logger = logging.getLogger("EMG_Exo")

# Sessantaquatro board configuration
EMG_CONFIG = {
    "device_name": "Sessantaquatro",
    "sampling_rate": 2048,  # Hz
    "channels": 64,  # Number of EMG channels
    "port": "COM3",  # Default port, can be changed by the user
    "baudrate": 2000000,
    "resolution": 24,  # bits
}

# EMG Processing parameters
EMG_PROCESSING = {
    "window_size": 256,  # samples
    "window_overlap": 128,  # samples
    "bandpass_low": 10,  # Hz
    "bandpass_high": 500,  # Hz
    "notch_freq": 50,  # Hz (power line interference)
    "decomposition_method": "FastICA"  # Options: "FastICA", "CKC", "PCA"
}

# Recording parameters
RECORDING = {
    "save_raw_emg": True,
    "save_processed_emg": True,
    "save_decomposed_mus": True,
    "save_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    "file_format": "hdf5"  # Options: "hdf5", "csv", "mat"
}

# Decoding parameters
DECODING = {
    "classifiers": ["kNN", "MLP"],
    "features": ["RMS", "MAV", "WL", "ZC", "SSC", "AR"],
    "training_ratio": 0.7,
    "cv_folds": 5,
    "normalize": True,
}

# Unity hand control parameters
HAND_CONTROL = {
    "ip_address": "127.0.0.1",
    "port": 9000,
    "protocol": "UDP",
    "update_rate": 50,  # Hz
    "command_delay": 0.02,  # seconds
}

# Degree of Freedom (DoF) configuration for the glove
DOF_CONFIG = {
    "thumb": ["flexion", "extension", "pinching"],
    "index": ["flexion", "extension", "pinching"],
    "middle": ["flexion", "extension", "pinching"],
    "ring_little": ["flexion", "extension"],
    "thumb_abduction": True,
    "total_dofs": 12
}

# Create necessary directories
DATA_DIR = RECORDING["save_dir"]
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

logger.info("Initialization complete. Application ready to start.")

if __name__ == "__main__":
    print("EMG Exoskeleton Control System - Configuration Loaded")
    print(f"EMG Device: {EMG_CONFIG['device_name']}")
    print(f"Sampling Rate: {EMG_CONFIG['sampling_rate']} Hz")
    print(f"Total DoFs: {DOF_CONFIG['total_dofs']}")
    print(f"Log file: {os.path.join(LOG_DIR, f'emg_exo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log')}")