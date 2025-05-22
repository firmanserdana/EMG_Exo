#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This package provides utility functions for the EMG Exo project.
"""

from emg_exo.core.utils.utils import (
    ensure_directory_exists,
    calculate_rms,
    calculate_mav,
    calculate_zero_crossings,
    calculate_slope_sign_changes,
    calculate_waveform_length,
    save_data_as_json,
    load_data_from_json,
    generate_timestamp,
    normalize_signal,
    moving_average
)

__all__ = [
    'ensure_directory_exists',
    'calculate_rms',
    'calculate_mav',
    'calculate_zero_crossings',
    'calculate_slope_sign_changes',
    'calculate_waveform_length',
    'save_data_as_json',
    'load_data_from_json',
    'generate_timestamp',
    'normalize_signal',
    'moving_average'
]