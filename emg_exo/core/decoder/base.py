#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module defines base classes and interfaces for EMG decoder functionality.
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union


class BaseEMGDecoder(ABC):
    """Abstract base class for EMG decoders.
    
    This class defines the interface that all EMG decoders must implement.
    """
    
    @abstractmethod
    def train(self, training_data: np.ndarray, training_labels: np.ndarray) -> Dict[str, Any]:
        """Train the decoder on labeled EMG data.
        
        Args:
            training_data: Feature vectors for training
            training_labels: Class labels for training
            
        Returns:
            Training performance metrics
        """
        pass
    
    @abstractmethod
    def classify(self, features: Union[Dict[str, np.ndarray], np.ndarray], method: str = "best") -> Tuple[int, str, float]:
        """Classify EMG features into a gesture.
        
        Args:
            features: EMG features dict or pre-extracted feature vector
            method: Classification method to use
            
        Returns:
            Tuple of (gesture_id, gesture_name, confidence)
        """
        pass
    
    @abstractmethod
    def extract_classification_features(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Extract a feature vector for classification from a features dictionary.
        
        Args:
            features: Dictionary containing features
            
        Returns:
            Feature vector for classification
        """
        pass
    
    @abstractmethod
    def save_models(self, path: Optional[str] = None) -> bool:
        """Save trained models to disk.
        
        Args:
            path: Optional path to save the models
            
        Returns:
            True if models were saved successfully
        """
        pass
    
    @abstractmethod
    def load_models(self, path: Optional[str] = None) -> bool:
        """Load trained models from disk.
        
        Args:
            path: Optional path to load the models from
            
        Returns:
            True if models were loaded successfully
        """
        pass
