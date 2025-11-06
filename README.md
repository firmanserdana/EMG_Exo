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
- **Comparative Analysis Tools**:
  - Publication-ready figure generation for multi-condition comparisons
  - Raw EMG signal comparison across conditions
  - Heatmap visualization of channel activity patterns
  - PCA analysis for condition separability assessment
  - Time consumption analysis across experimental conditions
- **ESP32 Pneumatic Glove Integration**:
  - Real-time gesture control via TCP/IP communication with persistent connections
  - Task-specific gesture mapping (open_close, grasp_patterns, single_fingers)
  - **Button Control Mode**: Simple push button interface to toggle between gesture and relax state
  - Configurable pressure and speed settings with real-time adjustment
  - Emergency stop functionality and connection health monitoring
  - Improved connection stability with automatic reconnection
  - Heartbeat mechanism for maintaining persistent connections
  - Auto-discovery of ESP32 devices on network
  - **Automatic rest state return**: When decoding stops, the system automatically returns both Unity and ESP32 glove to rest/relax state
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
│   ├── emg_comparative_analysis.py  # Multi-condition analysis tool
│   ├── model_train.py       # ML model training pipeline
│   ├── model_evaluate.py    # Model evaluation utilities
│   ├── streaming_gui.py     # Real-time streaming interface
│   ├── test_esp32.py        # ESP32 connection test tool
│   ├── ANALYSIS_README.md   # Analysis tool documentation
│   ├── QUICK_START.md       # Quick start guide for analysis
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

# 3. Real-time Streaming GUI
python streaming_gui.py

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

# Streaming GUI
python md-emg-python/streaming_gui.py

# Train a new gesture recognition model
python md-emg-python/model_train.py --config config/decoding_train_grasp_patterns.yaml

# Evaluate model performance
python md-emg-python/model_evaluate.py --model models/my_model.pkl

# Test ESP32 glove connection and functionality
python md-emg-python/test_esp32.py

# Run complete integration demo
python md-emg-python/integration_demo.py

# Generate publication-ready comparative analysis figures
python md-emg-python/emg_comparative_analysis.py
```

### EMG Comparative Analysis

The system includes powerful tools for generating publication-ready figures comparing EMG data across multiple experimental conditions:

```bash
cd md-emg-python

# Quick start with example data (for testing)
python emg_comparative_analysis.py

# With your own data (see ANALYSIS_README.md for data format)
# Data should be in data/healthy/ organized by condition
python emg_comparative_analysis.py
```

**Generated Figures:**
- **Figure B**: Raw EMG signal comparison (6 objects × 3 conditions)
- **Figure C**: Channel activity heatmaps (6 objects × 3 conditions)
- **Figure C**: PCA analysis for condition separability
- **Time Analysis**: Task duration comparison with statistics

**Output Location:** `results-analysis/`

See `ANALYSIS_README.md` for detailed documentation or `QUICK_START.md` for a 5-minute tutorial.
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

Configure your ESP32 pneumatic glove in `config/esp32_control.yaml`:

```yaml
# Network settings
ip_address: "172.20.10.3"     # Your ESP32 IP address
port: 4210                    # TCP communication port
timeout: 10                   # Connection timeout (seconds)

# Control settings
enabled: true                 # Enable ESP32 control
connection_mode: "persistent" # "persistent" or "reconnect"
heartbeat_interval: 5.0       # Keep-alive interval (seconds)
gesture_hold_time: 0.1        # Minimum time between gestures

# Pressure settings (0-100)
default_pressure:
  flexion: 85                 # Pneumatic flexion pressure
  extension: 70               # Pneumatic extension pressure

# Speed setting (0-4: Stop, Slow, Medium, Fast, Fastest)
default_speed: 4

# Auto gesture mapping based on task type
# Maps EMG predictions to ESP32 gesture IDs automatically
```

#### Connection Modes

**Persistent Mode** (Recommended):
- Maintains constant TCP connection to ESP32
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

# Connect to ESP32 with persistent connection mode
glove = ESP32Controller(
    esp32_ip="172.20.10.3", 
    tcp_port=4210,
    connection_mode="persistent",
    heartbeat_interval=5.0
)

if glove.connect():
    print("✓ ESP32 glove connected")
    
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
    print("✗ Failed to connect to ESP32 glove")
```

#### ESP32 Testing and Diagnostics

```bash
# Test ESP32 connection
python test_esp32.py 172.20.10.3

# Auto-discover ESP32 devices on network
python test_esp32.py scan

# Run gesture sequence test
python test_esp32.py 172.20.10.3 --test-gestures

# Monitor ESP32 communication (debug mode)
python test_esp32.py 172.20.10.3 --debug
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

#### Button Control Mode

The ESP32 glove now supports a simple button-based control scheme for easy manual operation:

**Setup:**
```
1. Connect a push button between GPIO 33 (v2) or GPIO 32 (v1) and GND
2. Access web interface at http://192.168.4.1
3. Select "Force BUTTON Mode" 
4. Choose which gesture to activate from dropdown (1-8)
5. Press button to toggle between gesture and relax state
```

**Features:**
- Simple one-button control
- Toggle between selected gesture and relax state
- Configurable gesture selection via web interface
- 200ms debounce for reliable operation
- Works independently of other control modes

**See [BUTTON_CONTROL_MODE.md](BUTTON_CONTROL_MODE.md) for detailed documentation.**

```

## Troubleshooting

### ESP32 Connection Issues

1. **Connection Refused (Most Common)**
   ```bash
   # Auto-discover ESP32 devices on your network
   python test_esp32.py scan
   
   # Test specific IP address
   python test_esp32.py 172.20.10.3
   
   # Update config file with correct IP
   # Edit config/esp32_control.yaml -> ip_address: "YOUR_ESP32_IP"
   ```

2. **Timeout Errors**
   ```yaml
   # In config/esp32_control.yaml, increase timeout:
   timeout: 10              # Increase from 5 to 10 seconds
   connection_mode: "persistent"  # Use persistent mode for better stability
   ```

3. **Gesture Commands Not Working**
   ```bash
   # Test individual gesture commands
   python test_esp32.py 172.20.10.3 --test-gestures
   
   # Enable debug mode to see detailed communication
   python test_esp32.py 172.20.10.3 --debug
   
   # Check if heartbeat interference is occurring
   # Set heartbeat_interval: 0 to disable heartbeat
   ```

4. **Connection Drops During Use**
   ```yaml
   # In config/esp32_control.yaml:
   connection_mode: "persistent"  # Maintain constant connection
   heartbeat_interval: 5.0        # Keep-alive heartbeat
   gesture_hold_time: 0.1         # Reduce hold time for responsive updates
   ```

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
   python emg_control_64.py --subj-type healthy --subj 0 --task open_close --decoding-active 1 --esp32-enabled 1
   ```

3. **Gesture Mapping Issues**
   ```bash
   # Verify gesture mappings match your trained model
   # Check Unity VR OpenLoopConfig.json gesture IDs
   # ESP32 mapping automatically adapts to --task parameter
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

**Enhanced ESP32 Integration:**
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
- **Multi-output Control**: Simultaneous VR and ESP32 control
- **Streaming Visualization**: Real-time signal and prediction display with `streaming_gui.py`
- **Research Tools**: Data analysis, model optimization, and scientific visualization

### ESP32 Pneumatic Glove Integration
Real-time physical hand assistance system with enhanced connectivity:

- **Persistent TCP/IP Communication**: Robust wireless connection with automatic reconnection
- **Task-Adaptive Gesture Mapping**: Automatic translation from EMG predictions to physical gestures based on task type
- **Advanced Pressure Control**: Configurable flexion/extension pressure settings (0-100%) with real-time adjustment
- **Variable Speed Control**: Adjustable movement speed (5 levels: Stop, Slow, Medium, Fast, Fastest)
- **Connection Health Monitoring**: Real-time connection status with heartbeat mechanism
- **Safety Features**: Emergency stop and automatic fault recovery
- **Automatic Rest State**: System automatically returns to rest/relax state (gesture 0) when decoding stops
- **Comprehensive Testing**: Auto-discovery, diagnostic tools, and debug modes
- **Configuration Management**: YAML-based configuration with validation

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
   - `streaming_gui.py` with real-time prediction display
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
# Example: Custom integration with persistent ESP32 connection
from realtime_components.esp32_control import ESP32Controller
import yaml
import time

# Load ESP32 configuration
with open('config/esp32_control.yaml') as f:
    esp32_config = yaml.load(f, Loader=yaml.FullLoader)

# Initialize ESP32 controller with persistent connection
glove = ESP32Controller(
    esp32_ip=esp32_config['ip_address'], 
    tcp_port=esp32_config['port'],
    connection_mode="persistent",
    heartbeat_interval=5.0
)

# Connect and run custom gesture sequence
if glove.connect():
    print("✓ ESP32 connected with persistent mode")
    
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
    print("✓ ESP32 disconnected")
else:
    print("✗ Failed to connect to ESP32")
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
  --subj_type healthy \
  --subj 0 \
  --task open_close \
  --decoding_active 1 \
  --acquisition_type closed_loop \
  --esp32_enabled 1 \
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

### ESP32 Control Tools
```bash
# Auto-discover ESP32 devices on network
python test_esp32.py scan

# Test specific ESP32 device
python test_esp32.py 172.20.10.3

# Run gesture sequence test
python test_esp32.py 172.20.10.3 --test-gestures

# Debug mode with detailed logging
python test_esp32.py 172.20.10.3 --debug

# Complete integration demos
python complete_integration_test.py         # Full EMG+Unity+ESP32 demo
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
| `config/esp32_control.yaml` | ESP32 glove configuration | IP, connection mode, gesture mapping |
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
- **ESP32 Pneumatic Gloves**: TCP/IP communication via WiFi
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