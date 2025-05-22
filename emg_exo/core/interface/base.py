#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module defines base classes and interfaces for hand control interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Callable, Optional, Union
import numpy as np


class BaseHandInterface(ABC):
    """Abstract base class for hand control interfaces.
    
    This class defines the interface that all hand control systems must implement.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the hand control system.
        
        Returns:
            True if connection was established successfully
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the hand control system."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to the hand control system.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    def send_hand_control(self, dof_values: Union[Dict[str, float], List[float], np.ndarray]) -> bool:
        """Send hand control values to the interface.
        
        Args:
            dof_values: Degrees of freedom values for hand
                If dict: keys are DoF names, values are position values (0-1)
                If list/array: values are in predefined order
                
        Returns:
            True if message sent successfully
        """
        pass
    
    @abstractmethod
    def send_gesture_info(self, gesture_id: Optional[int], gesture_name: str, confidence: float) -> bool:
        """Send gesture classification information.
        
        Args:
            gesture_id: ID of recognized gesture or None
            gesture_name: Name of recognized gesture
            confidence: Classification confidence (0-1)
                
        Returns:
            True if message sent successfully
        """
        pass
