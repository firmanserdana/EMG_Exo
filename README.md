# EMG-Based Hand Control System

A comprehensive system for processing EMG signals, interpreting hand gestures with machine learning, and providing real-time feedback via visualization and VR interfaces. The system supports hardware-based acquisition with various EMG systems as well as a s   - Multiple training and feedback modes
   - Customizable animation configurations

3. **Advanced Research Tools**
   - Real-time signal analysis
   - Advanced machine learning algorithm implementations
   - Model optimization and evaluation pipeline
   - Scientific data visualization and exportn mode for development and demonstrations without hardware.

![EMG Visualization Demo](https://via.placeholder.com/800x400?text=EMG+Visualization+Demo)

## System Overview

This application consists of four main components:

1. **EMG Acquisition**: Captures EMG signals from various hardware systems or generates simulated signals
2. **Signal Processing & Recognition**: Processes EMG signals, extracts features, and classifies gestures
3. **Visualization & Data Recording**: Real-time visualization of EMG signals and comprehensive data recording
4. **VR Integration**: Unity-based VR interface for real-time hand control and feedback

## Features

- **Multiple Hardware Support**:
  - Sessantaquatro 64-channel EMG system
  - Delsys Trigno EMG system via network connection
  - Realistic signal simulation for development without hardware
- **Advanced Signal Processing**:
  - Digital filtering (high-pass, low-pass, notch)
  - Feature extraction (time and frequency domain)
  - Signal envelope calculation
  - Muscle activity detection
  - Real-time spectral analysis
- **Machine Learning-Based Gesture Recognition**:
  - Multiple classifier support (kNN, MLP, LSTM, CRNN, TFM)
  - Automated model training and evaluation
  - Real-time classification with confidence metrics
  - Model optimization pipeline
- **Gesture Support**:
  - Thumb, index, and middle finger control (flexion, extension, pinching)
  - Ring and little finger control (flexion, extension)
  - Thumb abduction
  - Multi-finger gestures and grasp patterns
  - Customizable gesture set
- **Visualization & Data Management**:
  - Real-time signal plotting with multiple visualization modes
  - Gesture recognition display with confidence metrics
  - Interactive controls for gesture simulation
  - Comprehensive data recording and export (CSV, NPZ, MATLAB)
  - Spectrogram visualization for frequency analysis

- **VR Integration**:
  - Unity-based VR hand visualization
  - TCP/IP communication for real-time control
  - Customizable hand animations and configurations
  - Training and feedback modes for rehabilitation

## Project Structure

The project is organized with the following major components:

```
EMG_Exo/
├── md-emg-python/           # Advanced EMG processing framework
│   ├── emg_control_64.py    # 64-channel EMG control system
│   ├── emg_plot_64.py       # Advanced visualization
│   ├── model_train.py       # ML model training pipeline
│   ├── model_evaluate.py    # Model evaluation utilities
│   ├── streaming_gui.py     # Real-time streaming interface
│   ├── config/              # Configuration files
│   │   ├── 64_config.yaml   # 64-channel system configuration
│   │   └── ...              # Other configuration files
│   ├── realtime_components/ # Real-time processing modules
│   ├── utils/               # Utility functions
│   └── models/              # ML model implementations
│
├── md-emg-VR/               # Unity VR integration
│   ├── Assets/
│   │   ├── Scripts/         # C# implementation
│   │   │   ├── HandController.cs       # Hand movement control
│   │   │   ├── TcpServerManager.cs     # Communication interface
│   │   │   └── ...                     # Other components
│   │   ├── Scenes/          # Unity scenes
│   │   └── Config/          # Configuration files
│   └── ...                  # Unity project files
```

## Getting Started

### Quick Start

1. Clone the repository
2. Install the requirements for the advanced system: `pip install -r md-emg-python/requirements.txt`

For the full VR integration:
1. Open the Unity project in the `md-emg-VR` folder using Unity Hub
2. Run the Python backend: `python md-emg-python/emg_control_64.py`
3. Start the Unity application

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions and [FEATURES_GUIDE.md](FEATURES_GUIDE.md) for advanced features.

### Documentation

- [API Documentation](API_DOCUMENTATION.md): Complete API reference

## Prerequisites

- Python 3.8 or higher
- PyTorch, h5py, dearpygui, and other dependencies in md-emg-python/requirements.txt
- Optional: Unity 2022.3 or higher for VR integration
- Optional: Sessantaquatro EMG board or other hardware for physical acquisition

## Installation

1. Clone this repository:
```bash
git clone https://github.com/firmanserdana/EMG_Exo.git
cd EMG_Exo
```

2. Install the advanced 64-channel system requirements:
```bash
pip install -r md-emg-python/requirements.txt
```

3. For VR integration, open the Unity project in the `md-emg-VR` folder using Unity Hub

## Usage

### Main Applications

The repository provides several main applications:

```bash
# Run the 64-channel EMG system
cd md-emg-python
python emg_control_64.py

# Run the EMG visualization
cd md-emg-python
python emg_plot_64.py
```

### Advanced 64-Channel System

The md-emg-python folder contains scripts for advanced EMG processing with 64-channel systems:

```bash
# Run the 64-channel EMG control system
python md-emg-python/emg_control_64.py

# Run the EMG visualization tool
python md-emg-python/emg_plot_64.py

# Train a new model with custom dataset
python md-emg-python/model_train.py --config config/decoding_train_grasp_patterns.yaml

# Evaluate model performance
python md-emg-python/model_evaluate.py --model models/my_model.pkl

# Run the streaming GUI
python md-emg-python/streaming_gui.py
```

### 64-Channel System API

### 64-Channel System API

For the advanced 64-channel system:

```python
from realtime_components.acquisition import AcquisitionLoop
from realtime_components.decoding import DecodingLoop
from realtime_components.control import ControlLoop
from realtime_components.streaming import StreamingClient

# Load configuration
with open('config/64_config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# Set up communication channels
data_queue = Queue()
pred_queue = Queue()

# Start acquisition loop
acquisition = AcquisitionLoop(data_queue, config)
acquisition.start()

# Start decoding loop with pre-trained model
decoding = DecodingLoop(data_queue, pred_queue, config)
decoding.load_model('models/trained_model.pkl')
decoding.start()

# Start control loop to send commands to VR
control = ControlLoop(pred_queue, config)
control.connect_to_vr('127.0.0.1', 8080)
control.start()
```

### Unity VR Integration

To use the Unity VR integration:

1. Start the Python backend with TCP server:
```
python md-emg-python/emg_control_64.py
```

2. Open and run the Unity project in the `md-emg-VR` folder.

3. The Unity application will connect to the Python backend via TCP/IP, enabling:
   - Real-time hand movement control based on EMG signals
   - Customizable hand animation configurations
   - Training and feedback modes for rehabilitation

### Data Management

The advanced 64-channel system includes comprehensive data management capabilities:

```python
# Example of data management in the 64-channel system
python md-emg-python/model_train.py --config config/decoding_train_grasp_patterns.yaml --save-data

# Data will be stored in the configured directories based on the YAML configuration
```

### Visualization Options

The 64-channel EMG visualization provides advanced analysis features:

```bash
# Run the EMG visualization tool
python md-emg-python/emg_plot_64.py

# Or use the streaming GUI for real-time visualization
python md-emg-python/streaming_gui.py
```

This provides:
- Multi-channel signal display
- Real-time decoding visualization
- Advanced signal processing views
- Customizable display options

### Key Modules

The system consists of these key modules:

**Advanced 64-Channel System (md-emg-python):**
- `emg_control_64.py` - Main control script for 64-channel EMG system
- `model_train.py` & `model_evaluate.py` - Machine learning model pipeline
- `streaming_gui.py` - Real-time visualization GUI
- `realtime_components/` - Modular real-time processing components
- `utils/` - Specialized utility functions for the 64-channel system

**VR Integration (md-emg-VR):**
- `TcpServerManager.cs` - TCP/IP communication interface
- `HandController.cs` - Hand movement control based on EMG signals
- `ManagerClosedLoop.cs` & `ManagerOpenLoop.cs` - VR feedback control modes
- `Unity Scenes` - Pre-configured environments for different use cases

See the [FEATURES_GUIDE.md](FEATURES_GUIDE.md) for detailed information on using the advanced features.

## System Components

### Advanced 64-Channel System
The md-emg-python module extends the system for research-grade analysis:

- **High-Density EMG**: Support for 64-channel EMG arrays with synchronized acquisition
- **Advanced Models**: LSTM, CRNN, and Transformer-based models for complex gesture recognition
- **Optimization Pipeline**: Automated hyperparameter tuning and model selection
- **Real-time Processing**: Optimized for high-throughput, low-latency processing
- **Research Tools**: Data analysis and visualization tools for scientific research

### VR Integration
The md-emg-VR module provides a Unity-based VR interface:

- **TCP/IP Communication**: Robust bidirectional communication between Python backend and Unity
- **Customizable Hand Model**: Fully articulated hand model with natural motion
- **Training Modes**: Various modes for rehabilitation and gesture training
- **Visual Feedback**: Real-time feedback on gesture recognition and performance
- **Session Management**: Tools for managing and analyzing training sessions

## Recent Updates and Features

The latest version includes several new features:

1. **64-Channel System Integration**
   - Support for high-density EMG arrays
   - Real-time signal processing optimizations
   - Advanced machine learning model implementations
   - Streaming visualization with dearpygui

2. **VR Hand Visualization**
   - Unity-based hand model with natural movement
   - TCP/IP communication interface
   - Multiple training and feedback modes
   - Customizable animation configurations

5. **Simulation Improvements**
   - More realistic gesture-specific signal patterns
   - Frequency-based signal simulation
   - Amplitude modulation for realistic envelopes
   - Customizable noise and artifact simulation

For a complete list of features, see the md-emg-python and md-emg-VR directories.

## Requirements and Compatibility

### Software Requirements
- **Python**: Python 3.8 or higher
- **Core Dependencies**: PyTorch, h5py, pandas, dearpygui, NumPy, scikit-learn
- **Unity**: Unity 2022.3 or higher (for VR integration)

### Hardware Compatibility
- **Sessantaquatro EMG System**: 64-channel high-density EMG acquisition
- **Delsys Trigno**: Wireless EMG acquisition
- **Standard EMG Systems**: Via compatible interfaces
- **No Hardware**: Fully functional simulation mode

### Operating Systems
- **Windows**: Fully supported
- **macOS**: Fully supported, including Apple Silicon
- **Linux**: Supported with minor platform-specific adaptations

## References and Research

This implementation is based on research in EMG analysis and gesture recognition:
- [Motor Unit Decomposition Techniques](https://ieeexplore.ieee.org/abstract/document/10210135)
- [Soft Robotic Glove Design](https://www.liebertpub.com/doi/full/10.1089/soro.2019.0105)
- [Deep Learning for EMG Classification](https://www.mdpi.com/1424-8220/21/4/1339)
- [Transformer Models for EMG Decoding](https://ieeexplore.ieee.org/document/9837495)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request