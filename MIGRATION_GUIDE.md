# Migration Guide

This document provides guidance on migrating from the old EMG_Exo project structure to the new modular package structure.

## Overview of Changes

The EMG_Exo project has been reorganized into a proper Python package structure with the following changes:

- All core functionality is now organized in the `emg_exo` package
- Modules are organized into logical subpackages by functionality
- Abstract base classes define interfaces for each component
- Configuration is centralized in JSON files 
- Entry points are provided for common tasks

## Directory Structure

The new structure is organized as follows:

```
emg_exo/
├── __init__.py
├── apps/                  # Application entry points
├── config/                # Configuration management
├── core/                  # Core functionality
│   ├── acquisition/       # EMG system interfaces
│   ├── decoder/           # Gesture classification
│   ├── interface/         # Exoskeleton control
│   ├── processing/        # Signal processing
│   └── utils/             # Utility functions
├── docs/                  # Documentation
└── tests/                 # Unit tests
```

## Code Migration

### Importing Modules

If you were previously importing directly from Python files, update your imports as follows:

**Old imports:**
```python
from emg_acquisition import SessantaquatroEMG
from delsys_trigno_emg import DelsysTrignoEMG
from emg_processing import EMGProcessor
from emg_decoder import EMGDecoder
from unity_hand_interface import UnityHandInterface
```

**New imports:**
```python
from emg_exo.core.acquisition import SessantaquatroEMG, DelsysTrignoEMG
from emg_exo.core.processing import EMGProcessor
from emg_exo.core.decoder import EMGDecoder
from emg_exo.core.interface import UnityHandInterface
```

### Working with Configuration

The old `ini.py` module has been replaced with a more flexible JSON-based configuration system:

**Old configuration usage:**
```python
from ini import EMG_CHANNELS, SAMPLING_RATE

# Access configuration values directly
num_channels = EMG_CHANNELS
```

**New configuration usage:**
```python
from emg_exo.config.config import CONFIG

# Access configuration values through the CONFIG dictionary
num_channels = CONFIG["emg_sessantaquatro"]["channels"]
```

### Using the Factory Pattern

For EMG acquisition, we now use a factory pattern to create the appropriate EMG system:

**Old instantiation:**
```python
from emg_acquisition import SessantaquatroEMG
emg = SessantaquatroEMG()
```

**New instantiation:**
```python
from emg_exo.core.acquisition import create_emg_system
emg = create_emg_system("sessantaquatro")  # or "trigno"
```

### Command-Line Usage

The project now provides command-line entry points for common tasks:

```bash
# Run the main EMG exoskeleton application
emg-exo

# Run the EMG exoskeleton application with Trigno system
emg-exo --emg trigno

# Run the training mode
emg-train

# Run a simple demo
emg-demo
```

### Working with Utilities

Utility functions are now available through the utils module:

**Old utility usage:**
```python
from utilities import calculate_rms, calculate_mav

rms = calculate_rms(data)
```

**New utility usage:**
```python
from emg_exo.core.utils import calculate_rms, calculate_mav

rms = calculate_rms(data)
```

## Custom Development

If you're developing custom components, follow these guidelines:

1. **EMG Systems**: Extend `BaseEMGSystem` from `emg_exo.core.acquisition.base`
2. **Signal Processors**: Extend `BaseEMGProcessor` from `emg_exo.core.processing.base`
3. **Decoders**: Extend `BaseEMGDecoder` from `emg_exo.core.decoder.base`
4. **Interfaces**: Extend `BaseHandInterface` from `emg_exo.core.interface.base`

## Installation

Install the package using pip:

```bash
pip install -e .
```

This installs the package in development mode, allowing you to make changes to the code without reinstalling.
