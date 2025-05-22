#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shared utility functions for the EMG Exo project
"""

import numpy as np
import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, Union


def ensure_directory_exists(directory_path: str) -> bool:
    """Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to create
        
    Returns:
        True if directory exists or was created successfully
    """
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            return True
        except Exception as e:
            logging.error(f"Failed to create directory {directory_path}: {e}")
            return False
    return True


def calculate_rms(data: np.ndarray) -> float:
    """Calculate the Root Mean Square of a signal.
    
    Args:
        data: Input signal
        
    Returns:
        RMS value
    """
    return np.sqrt(np.mean(np.square(data)))


def calculate_mav(data: np.ndarray) -> float:
    """Calculate the Mean Absolute Value of a signal.
    
    Args:
        data: Input signal
        
    Returns:
        MAV value
    """
    return np.mean(np.abs(data))


def calculate_zero_crossings(data: np.ndarray, threshold: float = 0) -> int:
    """Calculate the number of zero crossings in a signal.
    
    Args:
        data: Input signal
        threshold: Threshold to avoid counting noise
        
    Returns:
        Number of zero crossings
    """
    # Apply threshold to avoid counting noise
    if threshold == 0:
        threshold = 0.01 * np.std(data)
    
    # Calculate zero crossings
    return np.sum(np.abs(np.diff(np.signbit(data))) & (np.abs(np.diff(data)) > threshold))


def calculate_slope_sign_changes(data: np.ndarray, threshold: float = 0) -> int:
    """Calculate the number of slope sign changes in a signal.
    
    Args:
        data: Input signal
        threshold: Threshold to avoid counting noise
        
    Returns:
        Number of slope sign changes
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


def calculate_waveform_length(data: np.ndarray) -> float:
    """Calculate the waveform length of a signal.
    
    Args:
        data: Input signal
        
    Returns:
        Waveform length
    """
    return np.sum(np.abs(np.diff(data)))


def save_data_as_json(data: Dict[str, Any], file_path: str) -> bool:
    """Save data as JSON file.
    
    Args:
        data: Data to save
        file_path: Path to save the file
        
    Returns:
        True if saved successfully
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


def load_data_from_json(file_path: str) -> Optional[Dict[str, Any]]:
    """Load data from JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Loaded data or None if error
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        logging.error(f"Error loading data from {file_path}: {e}")
        return None


def generate_timestamp() -> str:
    """Generate a formatted timestamp for file naming.
    
    Returns:
        Formatted timestamp
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def normalize_signal(signal: np.ndarray, min_val: Optional[float] = None, max_val: Optional[float] = None) -> np.ndarray:
    """Normalize a signal to [0, 1] range.
    
    Args:
        signal: Input signal
        min_val: Optional minimum value for normalization
        max_val: Optional maximum value for normalization
        
    Returns:
        Normalized signal
    """
    if min_val is None:
        min_val = np.min(signal)
        
    if max_val is None:
        max_val = np.max(signal)
    
    # Avoid division by zero
    if max_val == min_val:
        return np.zeros_like(signal)
        
    return (signal - min_val) / (max_val - min_val)


def moving_average(data: np.ndarray, window_size: int) -> np.ndarray:
    """Apply moving average filter to a signal.
    
    Args:
        data: Input signal
        window_size: Window size for filtering
        
    Returns:
        Filtered signal
    """
    return np.convolve(data, np.ones(window_size)/window_size, mode='same')
