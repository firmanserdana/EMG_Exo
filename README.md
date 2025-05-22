# EMG-Based Hand Control System

A comprehensive system for processing EMG signals, interpreting hand gestures with machine learning, and visualizing results with real-time feedback. The system supports both hardware-based acquisition with the Sessantaquatro board and simulation mode for development and demonstrations without hardware.

![EMG Visualization Demo](https://via.placeholder.com/800x400?text=EMG+Visualization+Demo)

## System Overview

This application consists of three main components:

1. **EMG Acquisition**: Captures EMG signals from the Sessantaquatro board or generates simulated signals
2. **Signal Processing & Recognition**: Processes EMG signals, extracts features, and classifies gestures
3. **Visualization**: Real-time visualization of EMG signals and recognized gestures

## Features

- **Hardware or Simulation**: Use real Sessantaquatro EMG hardware or realistic signal simulation
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

## Getting Started

### Quick Start

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the demo: `python simple_demo.py`

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions.

### Documentation

- [API Documentation](API_DOCUMENTATION.md): Complete API reference
- [Tutorial](TUTORIAL.md): Step-by-step guide to using the system

## Prerequisites

- Python 3.8 or higher
- Required Python packages (see `requirements.txt`)
- Optional: Sessantaquatro EMG board for hardware-based acquisition

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