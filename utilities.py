#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
utilities.py - Shared utility functions for the EMG Exo project
"""

import numpy as np
import os
import logging
import json
from datetime import datetime

def ensure_directory_exists(directory_path):
    """Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory_path (str): Path to the directory to create
        
    Returns:
        bool: True if directory exists or was created successfully
    """
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            return True
        except Exception as e:
            logging.error(f"Failed to create directory {directory_path}: {e}")
            return False
    return True

def calculate_rms(data):
    """Calculate the Root Mean Square of a signal.
    
    Args:
        data (numpy.ndarray): Input signal
        
    Returns:
        float: RMS value
    """
    return np.sqrt(np.mean(np.square(data)))

def calculate_mav(data):
    """Calculate the Mean Absolute Value of a signal.
    
    Args:
        data (numpy.ndarray): Input signal
        
    Returns:
        float: MAV value
    """
    return np.mean(np.abs(data))

def calculate_zero_crossings(data, threshold=0):
    """Calculate the number of zero crossings in a signal.
    
    Args:
        data (numpy.ndarray): Input signal
        threshold (float): Threshold to avoid counting noise
        
    Returns:
        int: Number of zero crossings
    """
    # Apply threshold to avoid counting noise
    if threshold == 0:
        threshold = 0.01 * np.std(data)
    
    # Calculate zero crossings
    return np.sum(np.abs(np.diff(np.signbit(data))) & (np.abs(np.diff(data)) > threshold))

def calculate_slope_sign_changes(data, threshold=0):
    """Calculate the number of slope sign changes in a signal.
    
    Args:
        data (numpy.ndarray): Input signal
        threshold (float): Threshold to avoid counting noise
        
    Returns:
        int: Number of slope sign changes
    """
    if threshold == 0:
        threshold = 0.01 * np.std(data)
    
    ssc = 0
    for i in range(1, len(data) - 1):
        if ((data[i] > data[i-1] and data[i] > data[i+1]) or 
            (data[i] < data[i-1] and data[i] < data[i+1])):
            if (abs(data[i] - data[i-1]) > threshold or 
                abs(data[i] - data[i+1]) > threshold):
                ssc += 1
    return ssc

def calculate_waveform_length(data):
    """Calculate the waveform length of a signal.
    
    Args:
        data (numpy.ndarray): Input signal
        
    Returns:
        float: Waveform length
    """
    return np.sum(np.abs(np.diff(data)))

def save_data_as_json(data, file_path):
    """Save data as JSON file.
    
    Args:
        data (dict): Data to save
        file_path (str): Path to save the file
        
    Returns:
        bool: True if saved successfully
    """
    try:
        # Make directory if it doesn't exist
        directory = os.path.dirname(file_path)
        ensure_directory_exists(directory)
        
        # Save the data
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving data to {file_path}: {e}")
        return False

def load_data_from_json(file_path):
    """Load data from JSON file.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        dict: Loaded data or None if error
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        logging.error(f"Error loading data from {file_path}: {e}")
        return None

def generate_timestamp():
    """Generate a formatted timestamp for file naming.
    
    Returns:
        str: Formatted timestamp
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def normalize_signal(signal, method='minmax'):
    """Normalize a signal using specified method.
    
    Args:
        signal (numpy.ndarray): Input signal
        method (str): Normalization method ('minmax', 'zscore')
        
    Returns:
        numpy.ndarray: Normalized signal
    """
    if method == 'minmax':
        min_val = np.min(signal)
        max_val = np.max(signal)
        if max_val > min_val:
            return (signal - min_val) / (max_val - min_val)
        return np.zeros_like(signal)
        
    elif method == 'zscore':
        std_val = np.std(signal)
        if std_val > 0:
            return (signal - np.mean(signal)) / std_val
        return np.zeros_like(signal)
    
    # Default: return original signal
    return signal

def apply_bandpass_filter(signal, sampling_rate, low_freq, high_freq):
    """Apply a bandpass filter to a signal.
    
    Args:
        signal (numpy.ndarray): Input signal
        sampling_rate (float): Sampling rate in Hz
        low_freq (float): Lower cutoff frequency in Hz
        high_freq (float): Upper cutoff frequency in Hz
        
    Returns:
        numpy.ndarray: Filtered signal
    """
    try:
        from scipy import signal as sp_signal
        
        # Calculate filter coefficients
        nyquist = 0.5 * sampling_rate
        low = low_freq / nyquist
        high = high_freq / nyquist
        
        # Create and apply filter
        b, a = sp_signal.butter(4, [low, high], btype='band')
        return sp_signal.filtfilt(b, a, signal)
    except Exception as e:
        logging.error(f"Error applying bandpass filter: {e}")
        return signal  # Return original signal on error
