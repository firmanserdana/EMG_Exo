"""
EMG Acquisition Package

This package provides interfaces for various EMG acquisition systems.
"""

from emg_exo.core.acquisition.base import BaseEMGSystem
from emg_exo.core.acquisition.sessantaquatro import SessantaquatroEMG
from emg_exo.core.acquisition.trigno import DelsysTrignoEMG
from emg_exo.core.acquisition.factory import (
    get_emg_system, 
    get_system_type_from_args,
    SUPPORTED_EMG_SYSTEMS
)