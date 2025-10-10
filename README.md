# EMG-Based Hand Control System

A comprehensive system for processing EMG signals, interpreting hand gestures with machine learning, and providing real-time feedback via visualization and VR interfaces.

![EMG Visualization Demo](https://via.placeholder.com/800x400?text=EMG+Visualization+Demo)

## System Overview

This application consists of four main components:

1. **EMG Acquisition**: Captures EMG signals from various hardware systems or generates simulated signals
2. **Signal Processing & Recognition**: Processes EMG signals, extracts features, and classifies gestures using advanced ML models
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
│   │   └── ...              # Processing components
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

## Quick Start Guide

### 1. Basic Setup
```bash
# Clone the repository
git clone https://github.com/firmanserdana/EMG_Exo.git
cd EMG_Exo

# Install requirements
pip install -r md-emg-python/requirements.txt
```

### 2. Run Complete System
```bash
# EMG acquisition + decoding + VR control
python emg_control_64.py --subj-type healthy --subj 0 --task grasp_patterns --decoding-active 1 

# Start Unity VR application (in parallel)
# Open md-emg-VR project in Unity Hub and click Play
```

### 3. Visualization Only
```bash
# Real-time EMG visualization
python emg_plot_64.py

# Streaming GUI
python streaming_gui.py
```

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions and [FEATURES_GUIDE.md](FEATURES_GUIDE.md) for advanced features.

### Documentation

- [API Documentation](API_DOCUMENTATION.md): Complete API reference

## Prerequisites

- Python 3.8 or higher
- PyTorch, h5py, dearpygui, and other dependencies in md-emg-python/requirements.txt
- Optional: Unity 2021.3.13f1 (project target). If using Unity 2022.3+, upgrade the project first.
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

## Main Applications

```bash
cd md-emg-python

# 1. Complete EMG Control System
python emg_control_64.py --decoding-active 1

# 2. EMG Signal Visualization
python emg_plot_64.py

# 3. Real-time Streaming GUI
python streaming_gui.py
```

### Advanced 64-Channel System

The md-emg-python folder contains scripts for advanced EMG processing with 64-channel systems:

```bash
# Complete EMG control with VR
python md-emg-python/emg_control_64.py --subj-type healthy --subj 0 --task grasp_patterns --decoding-active 1

# EMG visualization with real-time signal display
python md-emg-python/emg_plot_64.py

# Streaming GUI
python md-emg-python/streaming_gui.py

# Train a new gesture recognition model
python md-emg-python/model_train.py --config config/decoding_train_grasp_patterns.yaml

# Evaluate model performance
python md-emg-python/model_evaluate.py --model models/my_model.pkl
```

### Complete System Integration

The EMG-Exo system supports simultaneous output to Unity VR:

#### Full Integration Setup
```bash
# Step 1: Start the EMG processing system
python emg_control_64.py \
  --subj-type healthy \
  --subj 0 \
  --task grasp_patterns \
  --decoding-active 1

# Step 2: Start Unity VR (in parallel)
# Open md-emg-VR project in Unity Hub and click Play
```

#### Data Flow Architecture
```
EMG Signals → Acquisition → Processing → Decoding
                                          ↓
                                    Gesture Classification
                                          ↓
                           ┌──────────────┼──────────────┐
                           ↓              ↓              ↓
                    Unity VR Hand    Data Recording  Analysis
                    (Visualization)  (Logging)       (Evaluation)
```

#### Supported Output Modes
- **VR + Decoding**: `--decoding-active 1` (Unity running)
- **Visualization Only**: `emg_plot_64.py` or `streaming_gui.py`

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

#### Quick Setup

```yaml
# Network settings
port: 4210                   # TCP port for communication
timeout: 5                   # Connection timeout in seconds

# Control settings
gesture_hold_time: 0.5       # Minimum time between gesture changes

# Default pressure settings (0-100)
default_pressure:
  flexion: 60               # Default flexion pressure
  extension: 40             # Default extension pressure

# Default speed setting (0-4)
default_speed: 2            # Medium speed level
```

```bash
cd md-emg-python
```

```bash
python emg_control_64.py --decoding-active 1 
```

#### Command Line Arguments

- `--decoding-active 1`: Enable gesture decoding
- `--subj-type healthy`: Subject type ('healthy' or 'SCI')
- `--task grasp_patterns`: Task type ('open_close', 'single_fingers', 'grasp_patterns')

Example:
```bash
python emg_control_64.py --subj-type healthy --subj 0 --task open_close --decoding-active 1 

python emg_control_64.py --subj-type healthy --subj 0 --task grasp_patterns --decoding-active 1 

python emg_control_64.py --subj-type healthy --subj 0 --task single_fingers --decoding-active 1 
```


#### Connection Modes

**Persistent Mode** (Recommended):
- Faster response times and reduced latency
- Automatic reconnection if connection is lost
- Heartbeat mechanism to maintain connection stability

**Reconnect Mode** (Legacy):
- Establishes new connection for each command
- More robust against network issues
- Higher latency but more fault-tolerant
# Network settings
ip_address: "172.20.10.5"
port: 4210
timeout: 5

# Control settings
enabled: true
gesture_hold_time: 0.5

# Pressure settings (0-100)
default_pressure:
  flexion: 60     # Flexion pressure
  extension: 40   # Extension pressure

# Speed setting (0-4: Stop, Slow, Medium, Fast, Fastest)
default_speed: 2

# Task-specific gesture mappings (follows Unity VR OpenLoopConfig.json)
gesture_mapping_open_close:

gesture_mapping_grasp_patterns:

gesture_mapping_single_fingers:

auto_discovery:
  enabled: false
  ip_range: "192.168.1.1-254"
```



```python

    tcp_port=4210,
    connection_mode="persistent",
    heartbeat_interval=5.0
)

if glove.connect():
    
    # Set gesture commands
    glove.set_gesture(1)        # Hand close (all fingers flex)
    time.sleep(2)
    glove.set_gesture(2)        # Hand open (all fingers extend)
    time.sleep(2)
    glove.set_gesture(0)        # Relax (all fingers neutral)
    
    # Adjust pressure settings (0-100%)
    glove.set_pressure(85, 70)  # Flexion: 85%, Extension: 70%
    
    # Change speed (0-4: Stop, Slow, Medium, Fast, Fastest)
    glove.set_speed(4)          # Maximum speed
    
    # Emergency stop (immediately stops all actuators)
    glove.emergency_stop()
    
    # Close connection
    glove.disconnect()
else:
```

## Troubleshooting

### EMG System Issues

1. **No EMG Signal Connection**
   ```bash
   # Check EMG device connection in config/64_config.yaml
   # Verify IP address and port settings
   ip_address: "172.20.10.4"  # Sessantaquatro default
   port: 45454                 # Default Sessantaquatro port
   ```

2. **Decoding Not Active**
   ```bash
   # Ensure decoding is enabled with correct flags
   python emg_control_64.py --subj-type healthy --subj 0 --task open_close --decoding-active 1 
   ```

3. **Gesture Mapping Issues**
   ```bash
   # Verify gesture mappings match your trained model
   # Check Unity VR OpenLoopConfig.json gesture IDs
   ```

4. **Model Loading Errors**
   ```bash
   # Check model file paths exist:
   ls models-subjects/healthy/  # Verify model files
   ls data/healthy/            # Verify training data
   
   # Train new model if missing:
   python model_train.py --config config/decoding_train_open_close.yaml
   ```

### Unity VR Issues

1. **TCP Connection Failed**
   ```bash
   # Check TCP server settings in config/tcp_server_events.yaml
   # Default Unity events: host: "127.0.0.1", port: 55000
   # Default Unity streaming: host: "localhost", port: 55001
   ```

2. **Hand Animation Not Updating**
   ```bash
   # Verify Unity TcpServerManager.cs is running in Unity scene
   # Check Unity console for connection status messages
   # Ensure EMG predictions are being sent with correct event format
   ```

3. **Gesture ID Mismatch**
   ```bash
   # Verify Unity OpenLoopConfig.json matches your EMG model classes
   # Check that grasp IDs align between Unity and your trained model
   # EMG system automatically maps based on --task parameter
   ```

## Recent Updates & Improvements

### Version 2.5 (Latest)

- ✅ **Persistent Connection Mode**: Maintains constant TCP connection for faster response
- ✅ **Improved Connection Stability**: Automatic reconnection with exponential backoff
- ✅ **Task-Specific Gesture Mapping**: Automatic mapping based on Unity VR gesture definitions
- ✅ **Heartbeat Mechanism**: Keep-alive packets to maintain connection stability
- ✅ **Reduced Latency**: Optimized gesture hold time for more responsive control
- ✅ **Fixed Gesture Mapping Bug**: Corrected EMG-to-Unity event ID mapping

**System Architecture Improvements:**
- ✅ **Multiprocess Error Handling**: Better process management and error recovery
- ✅ **Configuration Validation**: Comprehensive config file validation
- ✅ **Debug Logging**: Enhanced logging for troubleshooting and development
- ✅ **Connection Health Monitoring**: Real-time monitoring of all system connections

**Unity VR Enhancements:**
- ✅ **Corrected Event Protocol**: Fixed grasp_decoded event ID mapping
- ✅ **Bidirectional Communication**: Improved Unity-Python communication protocol
- ✅ **Real-time Feedback**: Enhanced visual feedback for gesture recognition

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

### Advanced 64-Channel EMG Processing (md-emg-python)
The core EMG processing system with comprehensive capabilities:

- **High-Density EMG**: Support for 64-channel EMG arrays with synchronized acquisition
- **Advanced ML Models**: LSTM, CRNN, and Transformer-based models for gesture recognition
- **Real-time Processing**: Optimized for low-latency, high-throughput processing
- **Streaming Visualization**: Real-time signal and prediction display with `streaming_gui.py`
- **Research Tools**: Data analysis, model optimization, and scientific visualization

### Unity VR Hand Visualization (md-emg-VR)
Immersive virtual hand control interface:

- **Real-time Hand Model**: Fully articulated hand with natural motion
- **TCP/IP Communication**: Bidirectional communication with Python backend
- **Training Modes**: Multiple modes for rehabilitation and gesture training
- **Visual Feedback**: Real-time gesture recognition feedback
- **Session Management**: Tools for training session analysis

### Configuration System
Flexible YAML-based configuration:

- **EMG Settings**: Device connection, signal processing parameters
- **ML Models**: Training parameters, model selection, optimization settings
- **Visualization**: Display options, streaming parameters

## Recent Updates and Features

The latest version includes several new features:

   - Real-time gesture control via TCP/IP communication
   - Configurable pressure and speed settings
   - Emergency stop and safety features
   - Comprehensive testing and debugging tools

2. **Enhanced Streaming Visualization**
   - `streaming_gui.py` with real-time prediction display
   - Multi-channel signal visualization with DearPyGUI
   - Live gesture recognition feedback
   - Performance monitoring and diagnostics

3. **64-Channel System Integration**
   - Support for high-density EMG arrays
   - Real-time signal processing optimizations
   - Advanced machine learning model implementations

4. **VR Hand Visualization**
   - Unity-based hand model with natural movement
   - TCP/IP communication interface
   - Multiple training and feedback modes
   - Customizable animation configurations

5. **Improved Configuration Management**
   - YAML-based configuration system
   - Command-line parameter overrides
   - Flexible gesture mapping customization
   - Network and device auto-discovery

For a complete list of features, see the md-emg-python and md-emg-VR directories.

## Integration Examples

### Complete Workflow Demo
```bash
# 1. Test all components individually
python emg_plot_64.py                        # Test EMG visualization

# 2. Run full integration
python emg_control_64.py --decoding-active 1 

# 3. Start Unity VR (optional, in parallel)
# Open md-emg-VR project and click Play
```

### Custom Integration
```python
import yaml
import time


    connection_mode="persistent",
    heartbeat_interval=5.0
)

# Connect and run custom gesture sequence
if glove.connect():
    
    # Set custom pressure and speed
    glove.set_pressure(85, 70)  # High pressure for visible movement
    glove.set_speed(4)          # Maximum speed
    
    # Run gesture sequence
    gestures = [
        (0, "Relax"),
        (1, "Hand Close"), 
        (2, "Hand Open"),
        (3, "Hook Grasp"),
        (0, "Relax")
    ]
    
    for gesture_id, description in gestures:
        print(f"Executing: {description}")
        glove.set_gesture(gesture_id)
        time.sleep(3)  # Hold gesture for 3 seconds
    
    glove.disconnect()
else:
```

```

## Command Reference

### EMG Control System
```bash
# Basic EMG acquisition and decoding
python emg_control_64.py --decoding-active 1

python emg_control_64.py --decoding-active 1 

# Full parameter specification
python emg_control_64.py \
  --subj_type healthy \
  --subj 0 \
  --task open_close \
  --decoding_active 1 \
  --acquisition_type closed_loop \
   \
  --session 0
```

### Visualization Tools
```bash
# Real-time EMG signal plotting
python emg_plot_64.py

# Streaming GUI with predictions
python streaming_gui.py

# Legacy streaming interface
python streaming_gui.py
```

### Model Training and Evaluation
```bash
# Train new gesture recognition model
python model_train.py --config config/decoding_train_open_close.yaml
python model_train.py --config config/decoding_train_grasp_patterns.yaml
python model_train.py --config config/decoding_train_single_fingers.yaml

# Evaluate model performance with confusion matrix
python model_evaluate.py --model models-subjects/healthy/LSTM_open_loop.pth

# Plot and analyze EMG acquisition data
python plot_acquisition.py
```

### Configuration Files
| File | Purpose | Key Settings |
|------|---------|--------------|
| `config/64_config.yaml` | EMG acquisition settings | IP address, sampling rate, channels |
| `config/tcp_server_events.yaml` | Unity VR communication | Event server settings |
| `config/emg_signal_processing.yaml` | Signal processing parameters | Filtering, feature extraction |
| `config/decoding_params.yaml` | ML model settings | Model type, buffer size |
| `config/subjects/` | Subject-specific settings | Model files, sequence length |

## Requirements and Compatibility

### Software Requirements
- **Python**: Python 3.8 or higher (tested with 3.8-3.11)
- **Core Dependencies**: PyTorch, h5py, pandas, dearpygui, NumPy, scikit-learn, PyYAML
- **Unity**: Unity 2022.3 or higher (for VR integration)
- **Operating System**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+

### Hardware Compatibility
- **Sessantaquatro EMG System**: 64-channel high-density EMG acquisition (primary)
- **Delsys Trigno**: Wireless EMG acquisition (legacy support)
- **No Hardware**: Fully functional simulation mode for development and testing

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