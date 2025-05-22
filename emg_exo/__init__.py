"""
EMG_Exo - EMG-Based Exoskeleton Control System Package

A comprehensive system for processing EMG signals, interpreting hand gestures with 
machine learning, and visualizing results with real-time feedback.
"""

__version__ = '1.0.0'
__author__ = 'EMG_Exo Team'

# Core package imports
from emg_exo.core.acquisition import *
from emg_exo.core.processing import *
from emg_exo.core.decoder import *
from emg_exo.core.interface import *