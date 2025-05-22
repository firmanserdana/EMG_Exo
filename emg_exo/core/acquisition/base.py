"""
Base EMG acquisition module.

This module defines the base class for EMG acquisition systems.
"""

import numpy as np
import abc
from typing import Optional, Tuple, Dict, Any

class BaseEMGSystem(abc.ABC):
    """Abstract base class for EMG acquisition systems.
    
    This class defines the interface that all EMG systems must implement.
    """
    
    @abc.abstractmethod
    def connect(self) -> bool:
        """Connect to the EMG system.
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abc.abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the EMG system."""
        pass
    
    @abc.abstractmethod
    def configure_board(self) -> bool:
        """Configure the EMG system settings.
        
        Returns:
            bool: True if configuration successful
        """
        pass
    
    @abc.abstractmethod
    def start_streaming(self) -> bool:
        """Start streaming EMG data from the system.
        
        Returns:
            bool: True if streaming started successfully
        """
        pass
    
    @abc.abstractmethod
    def stop_streaming(self) -> None:
        """Stop streaming EMG data from the system."""
        pass
    
    @abc.abstractmethod
    def get_data(self, blocking: bool = False, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Get a chunk of EMG data from the buffer.
        
        Args:
            blocking: If True, wait until data is available
            timeout: Maximum time to wait if blocking is True
            
        Returns:
            numpy.ndarray: EMG data array with shape (channels, samples)
                           or None if no data is available
        """
        pass
    
    @abc.abstractmethod
    def simulate_data(self, duration: float = 1.0, gesture: Optional[str] = None) -> np.ndarray:
        """Generate simulated EMG data for testing.
        
        Args:
            duration: Duration of data in seconds
            gesture: Specific gesture to simulate
            
        Returns:
            numpy.ndarray: Simulated EMG data array with shape (channels, samples)
        """
        pass
