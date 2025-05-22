"""
EMG Processing Base Module

This module defines base classes and interfaces for EMG signal processing.
"""

import numpy as np
import abc
from typing import Dict, Optional, Any, List, Union

class BaseEMGProcessor(abc.ABC):
    """Abstract base class for EMG signal processors."""
    
    @abc.abstractmethod
    def preprocess(self, emg_data: np.ndarray) -> np.ndarray:
        """Preprocess raw EMG data.
        
        Args:
            emg_data: Raw EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: Processed EMG data
        """
        pass
    
    @abc.abstractmethod
    def extract_features(self, emg_data: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract features from EMG data.
        
        Args:
            emg_data: Processed EMG data of shape (channels, samples)
            
        Returns:
            Dict[str, np.ndarray]: Dictionary of feature arrays
        """
        pass
    
    @abc.abstractmethod
    def decompose_motor_units(self, emg_data: np.ndarray) -> tuple:
        """Decompose EMG data into motor unit activity.
        
        Args:
            emg_data: Processed EMG data of shape (channels, samples)
            
        Returns:
            tuple: (components, mixing matrix, spike trains)
        """
        pass
    
    @abc.abstractmethod
    def save_results(self, raw_emg: Optional[np.ndarray] = None, 
                    processed_emg: Optional[np.ndarray] = None, 
                    filename: Optional[str] = None) -> str:
        """Save EMG processing results.
        
        Args:
            raw_emg: Raw EMG data
            processed_emg: Processed EMG data
            filename: Output filename
            
        Returns:
            str: Path to saved file
        """
        pass
