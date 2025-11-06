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

# open_close (2 classes: OPEN vs CLOSE)
.venv/bin/python scripts/pretrain_healthy.py --task open_close --model_type CNNLSTM \
    --subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --epochs 150 --lr 0.001 --batch_size 64

.venv/bin/python scripts/pretrain_healthy.py --task open_close --model_type LSTM \
    --subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --epochs 150 --lr 0.0005 --batch_size 64

# grasp_vs_rest (2 classes: REST vs GRASP)
.venv/bin/python scripts/pretrain_healthy.py --task grasp_vs_rest --model_type CNNLSTM \
    --subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --epochs 100 --lr 0.001 --batch_size 64

.venv/bin/python scripts/pretrain_healthy.py --task grasp_vs_rest --model_type LSTM \
    --subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --epochs 100 --lr 0.001 --batch_size 64
```

### Pipeline HPO models (`train_transfer_pipeline_cli.py`)

Trained with Optuna hyperparameter optimization. Uses custom architecture sizes (not the default). Saved as `*_best.pth` files.

| File | Task | Val Acc | Notes |
|------|------|---------|-------|
| `pretrained_cnnlstm_open_close_best.pth` | open_close | 70.0% | HPO arch (conv 96→160, h=96, L=2), 80 epochs |
| `pretrained_lstm_open_close_best.pth` | open_close | 79.1% | HPO arch (h=160, L=3), 80 epochs |

> **Note:** The `*_best.pth` files use custom architecture parameters stored in
> `model_hparams` inside the checkpoint. The `transfer_learning.py` loader
> automatically detects this and builds the correct architecture.
> The pipeline now saves with a `_pipeline` suffix to avoid overwriting
> the direct-pretraining models.

### Which model to use?

- **For quick fine-tuning / real-time control:** Use `pretrained_cnnlstm_open_close.pth` (recommended — best generalization to SCI subjects)
- **For grasp detection:** Use `pretrained_cnnlstm_grasp_vs_rest.pth` (100% on healthy data)
- **For research / HPO comparison:** The `*_best.pth` files have Optuna-tuned architectures

### Transfer learning to SCI subjects

```bash
# Quick fine-tune (freeze features, fast)
python scripts/quick_finetune.py \
    --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
    --data_file data/SCI/S3/raw/session_01.npy \
    --events_file data/SCI/S3/raw/session_01_events.pkl

# Full transfer learning (all layers, more control)
python scripts/transfer_learning.py \
    --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
    --subj 3 --subj_type SCI --epochs 50 --lr 0.0001

# Full pipeline: HPO → pretrain → evaluate → transfer on SCI
python scripts/train_transfer_pipeline_cli.py --run_all \
    --healthy_subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 \
    --sci_subjects S3,S4 --models LSTM,CNNLSTM \
    --n_trials 50 --hpo_epochs 25 --pretrain_epochs 80 --transfer_epochs 40
```

## Documentation

See [md-emg-python/README.md](md-emg-python/README.md) for detailed setup and usage.
