# EMG-Based Hand Control System

A comprehensive system for processing EMG signals, interpreting hand gestures with machine learning, and providing real-time feedback via visualization and VR interfaces. The system supports hardware-based acquisition with various EMG systems as well as ESP32-based pneumatic gloves for physical hand assistance.

![EMG Visualization Demo](https://via.placeholder.com/800x400?text=EMG+Visualization+Demo)

## System Overview

This application consists of five main components:

1. **EMG Acquisition**: Captures EMG signals from various hardware systems or generates simulated signals
2. **Signal Processing & Recognition**: Processes EMG signals, extracts features, and classifies gestures using advanced ML models
3. **Visualization & Data Recording**: Real-time visualization of EMG signals and comprehensive data recording
4. **VR Integration**: Unity-based VR interface for real-time hand control and feedback
5. **ESP32 Physical Control**: Real-time control of pneumatic gloves for physical hand assistance

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
- **ESP32 Pneumatic Glove Integration**:
  - Real-time gesture control via TCP/IP communication
  - Automatic gesture mapping from EMG predictions
  - Configurable pressure and speed settings
  - Emergency stop functionality
  - Auto-discovery of ESP32 devices on network
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
│   ├── test_esp32.py        # ESP32 connection test tool
│   ├── config/              # Configuration files
│   │   ├── 64_config.yaml   # 64-channel system configuration
│   │   ├── esp32_control.yaml # ESP32 glove configuration
│   │   └── ...              # Other configuration files
│   ├── realtime_components/ # Real-time processing modules
│   │   ├── esp32_control.py # ESP32 glove control component
│   │   └── ...              # Other components
│   ├── utils/               # Utility functions
│   └── models/              # ML model implementations
│
├── ESP32_Exo/               # ESP32 glove control system
│   ├── v1/                  # Version 1 (Arduino IDE files)
│   │   ├── Bilateral_control_WIFI.ino
│   │   ├── Glove_wifi_controller.py
│   │   └── ...              # Other Arduino sketches
│   └── v2/                  # Version 2 (TCP-based control)
│       ├── Glove_wifi_controller.py
│       └── Bilateral_control_WIFI_V3/
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

### 2. Test ESP32 Connection (Optional)
```bash
cd md-emg-python
python test_esp32.py scan               # Auto-discover ESP32 devices
python test_esp32.py 172.20.10.5       # Test specific IP address
```

### 3. Run Complete System
```bash
# EMG acquisition + decoding + VR + ESP32 control
python emg_control_64.py --subj-type healthy --subj 0 --task grasp_patterns --decoding-active 1 --esp32-enabled 1

# Start Unity VR application (in parallel)
# Open md-emg-VR project in Unity Hub and click Play
```

### 4. Visualization Only
```bash
# Real-time EMG visualization
python emg_plot_64.py

# Streaming GUI with prediction display
python streaming_predictions_gui.py
```

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions and [FEATURES_GUIDE.md](FEATURES_GUIDE.md) for advanced features.

### Documentation

- [API Documentation](API_DOCUMENTATION.md): Complete API reference

## Prerequisites

- Python 3.8 or higher
- PyTorch, h5py, dearpygui, and other dependencies in md-emg-python/requirements.txt
- Optional: Unity 2022.3 or higher for VR integration
- Optional: Sessantaquatro EMG board or other hardware for physical acquisition
- Optional: ESP32-based pneumatic glove for physical hand assistance

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

4. For ESP32 glove integration, ensure your ESP32 device is running the compatible firmware (see `ESP32_Exo/` folder)

## Usage

## Main Applications

```bash
cd md-emg-python

# 1. Complete EMG Control System (with ESP32 support)
python emg_control_64.py --decoding-active 1 --esp32-enabled 1

# 2. EMG Signal Visualization
python emg_plot_64.py

# 3. Real-time Streaming with Predictions
python streaming_predictions_gui.py

# 4. ESP32 Glove Testing
python test_esp32.py

# 5. Integration Demo
python integration_demo.py
```

### Advanced 64-Channel System

The md-emg-python folder contains scripts for advanced EMG processing with 64-channel systems:

```bash
# Complete EMG control with all outputs (VR + ESP32)
python md-emg-python/emg_control_64.py --subj-type healthy --subj 0 --task grasp_patterns --decoding-active 1 --esp32-enabled 1

# EMG visualization with real-time signal display
python md-emg-python/emg_plot_64.py

# Streaming GUI with prediction visualization
python md-emg-python/streaming_predictions_gui.py

# Train a new gesture recognition model
python md-emg-python/model_train.py --config config/decoding_train_grasp_patterns.yaml

# Evaluate model performance
python md-emg-python/model_evaluate.py --model models/my_model.pkl

# Test ESP32 glove connection and functionality
python md-emg-python/test_esp32.py

# Run complete integration demo
python md-emg-python/integration_demo.py
```

### Complete System Integration

The EMG-Exo system supports simultaneous output to multiple targets:

#### Full Integration Setup
```bash
# Step 1: Configure ESP32 (edit config/esp32_control.yaml)
# Set your ESP32 IP address and enable control

# Step 2: Start the EMG processing system
python emg_control_64.py \
  --subj-type healthy \
  --subj 0 \
  --task grasp_patterns \
  --decoding-active 1 \
  --esp32-enabled 1

# Step 3: Start Unity VR (in parallel)
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
                    Unity VR Hand    ESP32 Glove    Data Recording
                    (Visualization)  (Physical)     (Analysis)
```

#### Supported Output Modes
- **VR Only**: `--decoding-active 1` (ESP32 disabled in config)
- **ESP32 Only**: `--decoding-active 1 --esp32-enabled 1` (Unity not started)
- **Both VR + ESP32**: Full integration mode (both systems active)
- **Visualization Only**: `emg_plot_64.py` or `streaming_predictions_gui.py`

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

### ESP32 Pneumatic Glove Integration

The system now supports real-time control of ESP32-based pneumatic gloves for physical hand assistance:

#### Quick Setup

1. **Configure ESP32 settings** in `md-emg-python/config/esp32_control.yaml`:
```yaml
# Network settings
ip_address: "172.20.10.5"    # Your ESP32 IP address
port: 4210                   # TCP port for communication
timeout: 5                   # Connection timeout in seconds

# Control settings
enabled: true                # Enable ESP32 control
gesture_hold_time: 0.5       # Minimum time between gesture changes

# Default pressure settings (0-100)
default_pressure:
  flexion: 60               # Default flexion pressure
  extension: 40             # Default extension pressure

# Default speed setting (0-4)
default_speed: 2            # Medium speed level
```

2. **Test ESP32 connection**:
```bash
cd md-emg-python
python test_esp32.py                    # Interactive test
python test_esp32.py 172.20.10.5        # Direct IP test
python test_esp32.py scan               # Auto-discover ESP32
```

3. **Run with ESP32 control enabled**:
```bash
python emg_control_64.py --decoding-active 1 --esp32-enabled 1
```

#### Command Line Arguments

Key parameters for EMG control with ESP32:
- `--decoding-active 1`: Enable gesture decoding
- `--esp32-enabled 1`: Enable ESP32 glove control (overrides config file)
- `--subj-type healthy`: Subject type ('healthy' or 'SCI')
- `--task grasp_patterns`: Task type ('open_close', 'single_fingers', 'grasp_patterns')

Example:
```bash
# Open/Close task with ESP32 control
python emg_control_64.py --subj-type healthy --subj 0 --task open_close --decoding-active 1 --esp32-enabled 1

# Grasp Patterns task with ESP32 control  
python emg_control_64.py --subj-type healthy --subj 0 --task grasp_patterns --decoding-active 1 --esp32-enabled 1

# Single Fingers task with ESP32 control
python emg_control_64.py --subj-type healthy --subj 0 --task single_fingers --decoding-active 1 --esp32-enabled 1
```

**Note:** The ESP32 gesture mapping automatically adapts based on the `--task` parameter to match Unity VR gesture definitions.

#### ESP32 Gesture Mapping

The system automatically maps EMG predictions to ESP32 gestures based on the task type, following Unity VR OpenLoopConfig.json:

**Open/Close Task:**
| EMG ID | Unity Label | ESP32 Gesture | Description |
|--------|-------------|---------------|-------------|
| 0 | HandOpen | Relax | All fingers relaxed/open |
| 1 | HandClose | All Flex | All fingers closed/flexed |

**Grasp Patterns Task:**
| EMG ID | Unity Label | ESP32 Gesture | Description |
|--------|-------------|---------------|-------------|
| 0 | HandOpen | Relax | All fingers relaxed/open |
| 2 | HookGrasp | 2-Finger Pinch | Hook/pinch grasp |
| 3 | LateralGrasp | 3-Finger Pinch | Lateral/key grasp |
| 4 | IndexPointing | Index | Index finger pointing |

**Single Fingers Task:**
| EMG ID | Unity Label | ESP32 Gesture | Description |
|--------|-------------|---------------|-------------|
| 0 | HandOpen | Relax | All fingers relaxed/open |
| 5 | ThumbFlexion | Thumb | Thumb movement |
| 6 | IndexFlexion | Index | Index finger movement |
| 7 | MRPFlexion | Middle | Middle finger movement |

#### ESP32 Configuration Options

```yaml
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
  0: 0  # HandOpen -> ESP32 Relax
  1: 1  # HandClose -> ESP32 All Flex

gesture_mapping_grasp_patterns:
  0: 0  # HandOpen -> ESP32 Relax
  2: 3  # HookGrasp -> ESP32 2-Finger Pinch
  3: 4  # LateralGrasp -> ESP32 3-Finger Pinch
  4: 6  # IndexPointing -> ESP32 Index

gesture_mapping_single_fingers:
  0: 0  # HandOpen -> ESP32 Relax
  5: 5  # ThumbFlexion -> ESP32 Thumb
  6: 6  # IndexFlexion -> ESP32 Index
  7: 7  # MRPFlexion -> ESP32 Middle

# Auto-discovery for finding ESP32 on network
auto_discovery:
  enabled: false
  ip_range: "192.168.1.1-254"
```

#### Standalone ESP32 Control

You can also control the ESP32 glove directly without EMG processing:

```python
# Direct ESP32 control example
from realtime_components.esp32_control import ESP32Controller

# Connect to ESP32 (using IP from config file)
glove = ESP32Controller("172.20.10.5", 4210)
if glove.connect():
    # Set gesture
    glove.set_gesture(3)        # 2-finger pinch
    
    # Adjust pressure settings
    glove.set_pressure(60, 40)  # Flexion: 60%, Extension: 40%
    
    # Change speed
    glove.set_speed(2)          # Medium speed
    
    # Emergency stop
    glove.emergency_stop()
    
    # Disconnect
    glove.disconnect()
```

#### ESP32 Testing Tools
```bash
# Interactive testing with menu
python test_esp32.py

# Direct IP testing
python test_esp32.py 172.20.10.5

# Network scanning for ESP32 devices
python test_esp32.py scan

# Run integration demo
python integration_demo.py --esp32-only
```

```

## Troubleshooting

### ESP32 Connection Issues

1. **Connection Refused**
   ```bash
   # Check ESP32 IP address
   python test_esp32.py scan
   
   # Update config file with correct IP
   # Edit config/esp32_control.yaml
   ```

2. **Timeout Errors**
   ```yaml
   # Increase timeout in config/esp32_control.yaml
   timeout: 10  # Increase from 5 to 10 seconds
   ```

3. **Gesture Commands Not Working**
   ```bash
   # Test individual commands
   python test_esp32.py 172.20.10.5
   # Use interactive testing mode to debug
   ```

### EMG System Issues

1. **No EMG Signal**
   ```bash
   # Check EMG device connection in config/64_config.yaml
   # Verify IP address and port settings
   ```

2. **Decoding Not Active**
   ```bash
   # Ensure decoding is enabled
   python emg_control_64.py --decoding-active 1
   ```

3. **Model Loading Errors**
   ```bash
   # Check model file paths in config files
   # Verify trained models exist in models-subjects/ directory
   ```

### Unity VR Issues

1. **TCP Connection Failed**
   ```bash
   # Check TCP server settings in config/tcp_server_events.yaml
   # Default: host: "127.0.0.1", port: 55000
   ```

2. **Hand Animation Not Updating**
   ```bash
   # Verify Unity TcpServerManager.cs is running
   # Check console output for connection status
   ```

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
- **Multi-output Control**: Simultaneous VR and ESP32 control
- **Streaming Visualization**: Real-time signal and prediction display with `streaming_predictions_gui.py`
- **Research Tools**: Data analysis, model optimization, and scientific visualization

### ESP32 Pneumatic Glove Integration
Real-time physical hand assistance system:

- **TCP/IP Communication**: Robust wireless connection to ESP32 devices
- **Gesture Mapping**: Automatic translation from EMG predictions to physical gestures
- **Pressure Control**: Configurable flexion/extension pressure settings (0-100%)
- **Speed Control**: Adjustable movement speed (5 levels: Stop, Slow, Medium, Fast, Fastest)
- **Safety Features**: Emergency stop and connection monitoring
- **Testing Tools**: Comprehensive testing and debugging utilities

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
- **ESP32 Settings**: Network, gesture mapping, pressure/speed defaults
- **ML Models**: Training parameters, model selection, optimization settings
- **Visualization**: Display options, streaming parameters

## Recent Updates and Features

The latest version includes several new features:

1. **ESP32 Pneumatic Glove Integration**
   - Real-time gesture control via TCP/IP communication
   - Configurable pressure and speed settings
   - Auto-discovery of ESP32 devices on network
   - Emergency stop and safety features
   - Comprehensive testing and debugging tools

2. **Enhanced Streaming Visualization**
   - `streaming_predictions_gui.py` with real-time prediction display
   - Multi-channel signal visualization with DearPyGUI
   - Live gesture recognition feedback
   - Performance monitoring and diagnostics

3. **64-Channel System Integration**
   - Support for high-density EMG arrays
   - Real-time signal processing optimizations
   - Advanced machine learning model implementations
   - Multi-output control (VR + ESP32 + Data recording)

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
python test_esp32.py scan                    # Find ESP32 devices
python integration_demo.py --esp32-only      # Test ESP32 control
python emg_plot_64.py                        # Test EMG visualization

# 2. Run full integration
python integration_demo.py                   # Complete system demo
python emg_control_64.py --decoding-active 1 --esp32-enabled 1

# 3. Start Unity VR (optional, in parallel)
# Open md-emg-VR project and click Play
```

### Custom Integration
```python
# Example: Custom integration with specific settings
from realtime_components.esp32_control import ESP32Controller
import yaml

# Load custom ESP32 configuration
with open('config/esp32_control.yaml') as f:
    esp32_config = yaml.load(f, Loader=yaml.FullLoader)

# Initialize ESP32 controller
glove = ESP32Controller(
    esp32_config['ip_address'], 
    esp32_config['port']
)

# Connect and run custom gesture sequence
if glove.connect():
    gestures = [0, 1, 3, 5, 0]  # Rest, Flex, Pinch, Thumb, Rest
    for gesture in gestures:
        glove.set_gesture(gesture)
        time.sleep(2)
    glove.disconnect()
```

```

## Command Reference

### EMG Control System
```bash
# Basic EMG acquisition and decoding
python emg_control_64.py --decoding-active 1

# With ESP32 control enabled
python emg_control_64.py --decoding-active 1 --esp32-enabled 1

# Full parameter specification
python emg_control_64.py \
  --subj-type healthy \
  --subj 0 \
  --task grasp_patterns \
  --decoding-active 1 \
  --acquisition-type open_loop \
  --esp32-enabled 1 \
  --session 0
```

### Visualization Tools
```bash
# Real-time EMG signal plotting
python emg_plot_64.py

# Streaming GUI with predictions
python streaming_predictions_gui.py

# Legacy streaming interface
python streaming_gui.py
```

### ESP32 Control Tools
```bash
# Interactive testing
python test_esp32.py

# Direct IP testing
python test_esp32.py <ip_address> [port]

# Network scanning
python test_esp32.py scan

# Integration demos
python integration_demo.py                 # Full demo
python integration_demo.py --esp32-only    # ESP32 only
python integration_demo.py --emg-only      # EMG simulation
```

### Model Training and Evaluation
```bash
# Train new model
python model_train.py --config config/decoding_train_grasp_patterns.yaml

# Evaluate model performance  
python model_evaluate.py --model models/trained_model.pkl

# Plot acquisition data
python plot_acquisition.py
```

### Configuration Files
| File | Purpose |
|------|---------|
| `config/64_config.yaml` | EMG acquisition settings |
| `config/esp32_control.yaml` | ESP32 glove configuration |
| `config/tcp_server_events.yaml` | Unity VR communication |
| `config/emg_signal_processing.yaml` | Signal processing parameters |
| `config/decoding_params.yaml` | ML model settings |

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