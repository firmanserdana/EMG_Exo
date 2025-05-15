# EMG-Based Hand Control System

A comprehensive system for processing EMG signals from the Sessantaquatro board, performing motor unit decomposition, interpreting hand gestures with machine learning, and controlling a 3D Unity hand model.

## System Overview

This application consists of two main components:
1. **Python Backend**: Captures and processes EMG signals, performs motor unit decomposition, and translates them into hand movement commands
2. **Unity Frontend**: A 3D visualization system with a hand model that receives commands from the Python backend

## Features

- Acquisition of EMG signals from the Sessantaquatro board (64 channels)
- Advanced signal processing pipeline with filtering and feature extraction
- Motor unit decomposition to extract individual motor unit firings
- Machine learning-based gesture recognition using kNN and MLP classifiers
- Control of a 12 DoF 3D hand model in Unity:
  - Thumb, index and middle finger with 3 DoF each (flexion, extension, pinching)
  - Ring and little finger with shared 2 DoF (flexion, extension)
  - Thumb abduction as an additional DoF

## Prerequisites

### Python Backend
- Python 3.8 or higher
- Required Python packages (see `requirements.txt`)
- Access to a Sessantaquatro EMG board

### Unity Frontend
- Unity 2020.3 or higher
- Basic understanding of Unity's UI and GameObject system

## Installation

1. Clone this repository:
```
git clone https://github.com/yourusername/EMG_Exo.git
cd EMG_Exo
```

2. Install Python dependencies:
```
pip install -r requirements.txt
```

3. Open the Unity project located in the `Unity` folder using Unity Hub

## Usage

### Python Backend

#### Running the Application

The main application can be run in different modes:

1. **Normal Mode** - Processes EMG signals and controls the Unity hand:
```
python main.py --port COMx
```

2. **Training Mode** - Collects labeled EMG data for classifier training:
```
python main.py --train --port COMx
```

3. **Recording Mode** - Records raw EMG data for later analysis:
```
python main.py --record --port COMx
```

4. **Decomposition Mode** - Enables motor unit decomposition:
```
python main.py --decompose --port COMx
```

Replace `COMx` with your actual COM port where the Sessantaquatro board is connected.

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

## Project Structure

```
EMG_Exo/
├── emg_acquisition.py      # Sessantaquatro board interface
├── emg_processing.py       # Signal processing and MU decomposition
├── emg_decoder.py          # ML-based gesture classification
├── unity_hand_interface.py # Unity communication interface
├── main.py                 # Main application entry point
├── ini.py                  # Configuration settings
├── requirements.txt        # Python dependencies
├── Unity/                  # Unity project folder
│   ├── Scripts/            # C# scripts for Unity
│   ├── Prefabs/            # Unity prefabs
│   └── Materials/          # Materials for the 3D hand
└── data/                   # Created at runtime for storing recordings
```

## References

This implementation is based on research in EMG decomposition and hand control:
- [Motor Unit Decomposition Techniques](https://ieeexplore.ieee.org/abstract/document/10210135)
- [Soft Robotic Glove Design](https://www.liebertpub.com/doi/full/10.1089/soro.2019.0105)

## License

[Include license information here]

## Contributing

[Include contribution guidelines here]