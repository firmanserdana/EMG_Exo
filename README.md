# EMG-Based Hand Control System

A comprehensive system for processing EMG signals, interpreting hand gestures with machine learning, and visualizing results with real-time feedback. The system supports hardware-based acquisition with either the Sessantaquatro board or Delsys Trigno EMG system, as well as a simulation mode for development and demonstrations without hardware.

![EMG Visualization Demo](https://via.placeholder.com/800x400?text=EMG+Visualization+Demo)

## System Overview

This application consists of three main components:

1. **EMG Acquisition**: Captures EMG signals from the Sessantaquatro board or generates simulated signals
2. **Signal Processing & Recognition**: Processes EMG signals, extracts features, and classifies gestures
3. **Visualization**: Real-time visualization of EMG signals and recognized gestures

## Features

- **Multiple Hardware Support**:
  - Sessantaquatro EMG board via serial connection
  - Delsys Trigno EMG system via network connection
  - Realistic signal simulation for development without hardware
- **Advanced Signal Processing**:
  - Digital filtering (high-pass, low-pass, notch)
  - Feature extraction (time and frequency domain)
  - Signal envelope calculation
  - Muscle activity detection
- **Machine Learning-Based Gesture Recognition**:
  - Multiple classifier support (kNN and MLP)
  - Automated model training and evaluation
  - Real-time classification
- **Gesture Support**:
  - Thumb, index, and middle finger control (flexion, extension, pinching)
  - Ring and little finger control (flexion, extension)
  - Thumb abduction
  - Customizable gesture set
- **Visualization**:
  - Real-time signal plotting
  - Gesture recognition display
  - Interactive controls for gesture simulation

## Project Structure

The project is organized as a Python package with the following structure:

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

## Getting Started

### Quick Start

1. Clone the repository
2. Install the package: `pip install -e .`
3. Run the demo: `emg-demo`

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions and [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for transitioning from the old structure.

### Documentation

- [API Documentation](API_DOCUMENTATION.md): Complete API reference
- [Tutorial](TUTORIAL.md): Step-by-step guide to using the system

## Prerequisites

- Python 3.8 or higher
- Optional: Sessantaquatro EMG board for hardware-based acquisition
- Optional: Delsys Trigno EMG system for wireless EMG acquisition
- Optional: Unity for 3D hand visualization

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/EMG_Exo.git
cd EMG_Exo
```

2. Install the package:
```bash
pip install -e .
```

3. Open the Unity project located in the `Unity` folder using Unity Hub

## Usage

### Command-Line Applications

The package provides several command-line entry points:

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

### Python API

The system can also be used as a Python library:

```python
from emg_exo.core.acquisition import create_emg_system
from emg_exo.core.processing import EMGProcessor
from emg_exo.core.decoder import EMGDecoder
from emg_exo.core.interface import UnityHandInterface

# Create components
emg = create_emg_system("sessantaquatro")
processor = EMGProcessor()
decoder = EMGDecoder()
interface = UnityHandInterface()

# Connect to hardware
emg.connect()
interface.connect()

# Main loop
while True:
    # Get EMG data
    emg_data = emg.read()
    
    # Process data
    processed_data = processor.preprocess(emg_data)
    features = processor.extract_features(processed_data)
    
    # Decode gesture
    gesture_id, gesture_name, confidence = decoder.classify(features)
    
    # Send to interface
    interface.send_gesture_info(gesture_id, gesture_name, confidence)
```

Replace `COMx` with your actual COM port where the Sessantaquatro board is connected.

##### Using the Delsys Trigno EMG System

1. **Normal Mode** - Processes EMG signals and controls the Unity hand:
```
python main.py --emg-system delsys_trigno --host 192.168.1.x
```

2. **Training Mode** - Collects labeled EMG data for classifier training:
```
python main.py --train --emg-system delsys_trigno --host 192.168.1.x
```

3. **Recording Mode** - Records raw EMG data for later analysis:
```
python main.py --record --emg-system delsys_trigno --host 192.168.1.x
```

4. **Decomposition Mode** - Enables motor unit decomposition:
```
python main.py --decompose --emg-system delsys_trigno --host 192.168.1.x
```

Replace `192.168.1.x` with the actual IP address of the computer running the Delsys Trigno Control Utility.

##### Using Simulation Mode

For development or demo purposes without hardware:

```
python main.py --emg-system simulation
```

##### Special Delsys Trigno Demo

A dedicated demo script is available for testing just the Delsys Trigno integration:

```
python delsys_trigno_demo.py --host 192.168.1.x
```

For testing with simulated data:

```
python delsys_trigno_demo.py --simulate
```

#### Modules

The Python backend consists of these key modules:

- `emg_acquisition.py` - Communicates with the Sessantaquatro EMG board
- `emg_processing.py` - Performs signal preprocessing and motor unit decomposition
- `emg_decoder.py` - Implements kNN and MLP classifiers for gesture recognition
- `unity_hand_interface.py` - Sends commands to control the Unity 3D hand
- `main.py` - Integrates all components into a complete application
- `ini.py` - Contains configuration settings for all components

### Unity Frontend

See the [Unity README](Unity/README.md) for detailed instructions on:
- Setting up the Unity scene
- Configuring the communication interface
- Testing the 3D hand model
- Troubleshooting common issues

## Code Evaluation

### EMG Acquisition
The EMG acquisition module handles communication with the Sessantaquatro board via serial connection. It's designed to:
- Configure the board with appropriate sampling rates
- Handle the streaming of raw EMG signals
- Parse the binary data packets into usable signal values
- Maintain a data queue for asynchronous processing

The module includes robust error handling and implements a producer-consumer pattern for efficient data transfer.

### Signal Processing & Motor Unit Decomposition
The EMG processing module implements several signal processing techniques:
- Bandpass filtering to remove noise and artifacts
- Feature extraction for EMG signal analysis
- Motor unit decomposition using FastICA, PCA, or custom methods
- Spike train extraction with refractory period constraints

The decomposition algorithm has been optimized to handle real-time data streams while maintaining accuracy.

### Gesture Classification
The decoding module implements two machine learning algorithms:
1. **kNN (k-Nearest Neighbors)** - Fast and effective for simpler gesture sets
2. **MLP (Multi-Layer Perceptron)** - More powerful for complex gesture recognition

Both classifiers achieve high accuracy with proper training data. The system includes a complete pipeline for:
- Feature extraction and normalization
- Cross-validation and model evaluation
- Model persistence for later use
- Real-time classification

### Unity Interface
The Unity communication is handled through a network socket (UDP/TCP) interface that:
- Serializes hand control commands into JSON
- Maintains reliable communication with the Unity application
- Provides a high-level gesture mapping API
- Includes error recovery mechanisms for connection issues

## Detailed Project Structure

```
EMG_Exo/
├── emg_exo/                      # Main package
│   ├── __init__.py               # Package initialization
│   ├── apps/                     # Application entry points
│   │   ├── __init__.py
│   │   └── main_app.py           # Main application
│   ├── config/                   # Configuration management
│   │   ├── __init__.py
│   │   ├── config.py             # Configuration loading
│   │   └── default_config.json   # Default settings
│   ├── core/                     # Core functionality
│   │   ├── __init__.py
│   │   ├── acquisition/          # EMG systems
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base EMG system
│   │   │   ├── factory.py        # EMG system factory
│   │   │   ├── sessantaquatro.py # Sessantaquatro board
│   │   │   └── trigno.py         # Delsys Trigno system
│   │   ├── decoder/              # Gesture recognition
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base decoder
│   │   │   └── decoder.py        # EMG decoder
│   │   ├── interface/            # Output interfaces
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base interface
│   │   │   └── unity.py          # Unity interface
│   │   ├── processing/           # Signal processing
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base processor
│   │   │   └── processor.py      # EMG processor
│   │   └── utils/                # Utilities
│   │       ├── __init__.py
│   │       └── utils.py          # Utility functions
│   ├── docs/                     # Documentation
│   └── tests/                    # Unit tests
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
├── MIGRATION_GUIDE.md            # Migration guide
├── Unity/                        # Unity project folder
│   ├── Scripts/                  # C# scripts for Unity
│   ├── Prefabs/                  # Unity prefabs
│   └── Materials/                # Materials for the 3D hand
└── data/                         # Created at runtime for storing recordings
```

## References

This implementation is based on research in EMG decomposition and hand control:
- [Motor Unit Decomposition Techniques](https://ieeexplore.ieee.org/abstract/document/10210135)
- [Soft Robotic Glove Design](https://www.liebertpub.com/doi/full/10.1089/soro.2019.0105)

## License

[Include license information here]

## Contributing

[Include contribution guidelines here]