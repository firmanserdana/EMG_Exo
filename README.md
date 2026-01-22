# EMG-Controlled Hand Exoskeleton System

A comprehensive system for EMG-based hand control with support for functional assessments (Box and Block Test), SCI patient-specific processing, and real-time exoskeleton control via ESP32 pneumatic gloves.

## 🎯 Key Features

### Control Modes
- **FSM Control** - State-machine control for functional tests (BBT, peg test, pouring)
- **SCI Hybrid Control** - Trigger-based control with spasticity/fatigue handling
- **Synchronized Control** - Real-time gesture mirroring to Unity VR and ESP32
- **Proportional Control** - Standard EMG amplitude-based control

### Signal Processing
- **64-channel HD-sEMG** support via OTB Sessantaquattro
- **Spatial Filtering** - Laplacian, CAR, bipolar for artifact rejection
- **Adaptive Filtering** - LMS filter for same-hand EMI suppression
- **Motion Artifact Detection** - Automatic detection and blanking

### Machine Learning Models
- **CNN-LSTM** - Hybrid spatial-temporal model with electrode dropout robustness
- **LSTM/TFM/CTFM/CRNN** - Standard temporal models
- **Transfer Learning** - Pre-train on healthy subjects, fine-tune for patients

### SCI Patient Support
- Spasticity detection and management
- Fatigue compensation with adaptive thresholds
- Lower SNR handling with spatial filtering

## 📁 Project Structure

```
EMG_Exo/
├── md-emg-python/               # Main Python framework
│   ├── emg_control_64.py        # Main control script
│   ├── model_train.py           # Model training
│   ├── scripts/
│   │   └── bbt_calibration.py   # BBT calibration workflow
│   ├── config/
│   │   ├── functional_tests.yaml    # FSM control settings
│   │   ├── sci_patient.yaml         # SCI-specific settings
│   │   ├── esp32_control.yaml       # ESP32 configuration
│   │   └── models/CNNLSTM_cfg.yaml  # CNN-LSTM config
│   ├── models/
│   │   └── cnn_lstm_model.py    # CNN-LSTM implementation
│   ├── realtime_components/
│   │   ├── fsm_control.py       # FSM control loop
│   │   ├── sci_control.py       # SCI hybrid control
│   │   ├── esp32_control.py     # ESP32 communication
│   │   └── acquisition.py       # EMG acquisition
│   └── utils/
│       ├── signal_filtering.py  # Spatial/adaptive filters
│       └── transfer_learning.py # Transfer learning utilities
│
├── ESP32_Exo/                   # ESP32 firmware
│   ├── v1/                      # Basic Arduino sketches
│   └── v2/                      # TCP-based control
│       └── Bilateral_control_WIFI_V3/
│
└── md-emg-VR/                   # Unity VR hand visualization
```

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/firmanserdana/EMG_Exo.git
cd EMG_Exo/md-emg-python
pip install -r requirements.txt
```

### 2. Network Setup (Hotspot for ESP32 + Sessantaquattro)

Both the ESP32 glove and Sessantaquattro EMG amplifier need to be on the same network as your computer. The easiest way is to create a WiFi hotspot on your laptop.

#### Option A: Use the Setup Script (Linux)

```bash
# 1. Edit the script with your settings
nano md-emg-python/setup_hotspot.sh

# Configure these variables:
# - IFACE: Your WiFi interface (find with 'ip link', e.g., wlp3s0)
# - SSID: Hotspot name (e.g., "EMG_Lab")
# - PASS: Password (min 8 characters)
# - BOARD1_MAC/IP: Sessantaquattro MAC and desired IP
# - BOARD2_MAC/IP: ESP32 MAC and desired IP

# 2. Run the script
sudo bash md-emg-python/setup_hotspot.sh
```

#### Option B: Manual Setup (Any OS)

1. **Create a mobile hotspot** on your laptop:
   - **Linux**: Settings → Wi-Fi → Turn on Wi-Fi Hotspot
   - **Windows**: Settings → Network → Mobile hotspot
   - **macOS**: System Preferences → Sharing → Internet Sharing

2. **Connect devices to hotspot**:
   - **Sessantaquattro**: Use OTB software to configure WiFi settings
   - **ESP32**: Update `WiFi.begin("YOUR_SSID", "YOUR_PASSWORD")` in firmware

3. **Find device IPs**:
   ```bash
   # Scan network for connected devices
   arp -a
   # or
   nmap -sn 192.168.50.0/24
   ```

4. **Update configuration files**:
   ```bash
   # Edit config/64_config.yaml
   ip_address: "192.168.50.10"  # Sessantaquattro IP
   
   # Edit config/esp32_control.yaml
   ip: "192.168.50.11"  # ESP32 IP
   ```

#### Recommended Network Configuration

| Device | Static IP | Purpose |
|--------|-----------|---------|
| Laptop (Gateway) | 192.168.50.1 | Runs Python scripts |
| Sessantaquattro | 192.168.50.10 | 64-channel EMG amplifier |
| ESP32 Glove | 192.168.50.11 | Pneumatic hand control |

#### Verify Connections

```bash
# Test Sessantaquattro
ping 192.168.50.10

# Test ESP32
python test_esp32.py 192.168.50.11
```

### 3. Basic EMG Control (Synchronized Mode)

```bash
# Standard acquisition + decoding + ESP32 control
python emg_control_64.py \
    --subj_type healthy \
    --subj 1 \
    --task open_close \
    --decoding_active 1 \
    --esp32_enabled 1
```

### 4. Box and Block Test (FSM Mode)

```bash
# Step 1: Calibrate (with arm movement for robustness)
python scripts/bbt_calibration.py --subj 1 --mode full_calibration

# Step 2: Run BBT with FSM control
python emg_control_64.py \
    --subj_type SCI \
    --subj 1 \
    --task open_close \
    --control_mode fsm \
    --functional_test box_and_block \
    --decoding_active 1 \
    --esp32_enabled 1
```

### 5. SCI Patient Mode

---

## 📋 Complete Workflow Summary

This section provides a step-by-step guide from initial setup to real-time control.

### Phase 1: Hardware Setup

```
┌─────────────────────────────────────────────────────────────┐
│  1. Create WiFi Hotspot on Laptop                           │
│     └── SSID: "Arlen" (or custom), Password: "12345678"     │
│                                                             │
│  2. Connect Devices to Hotspot                              │
│     ├── Sessantaquattro → 192.168.50.10                     │
│     └── ESP32 Glove     → 192.168.50.11                     │
│                                                             │
│  3. Verify Connections                                      │
│     ├── ping 192.168.50.10  (Sessantaquattro)               │
│     └── python test_esp32.py 192.168.50.11                  │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Data Recording (Open Loop Mode)

Data recording uses **Unity VR for visual cues** - the VR hand shows the gesture to perform while EMG is recorded.

```bash
# 1. Start Unity VR application (md-emg-VR)
#    - Select "Open Loop" mode
#    - Configure: dominant hand, grasping type, number of trials

# 2. Start Python EMG acquisition (in a separate terminal)
python emg_control_64.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close \
    --decoding_active 0 \
    --esp32_enabled 0

# 3. In Unity, press "Play" to start the recording session
#    - Unity shows visual cues (hand animations)
#    - Follow the hand movements shown on screen
#    - Events are automatically timestamped via TCP

# 4. Press Enter in Python terminal when session completes
# Data saved to: data/SCI/S0/raw/session_XX_emg.pkl
# Events saved to: data/SCI/S0/raw/session_XX_events.pkl
```

**Unity Open Loop Trial Flow:**
```
┌────────────────────────────────────────────────────────────────┐
│  1. trial_start         → Trial begins                         │
│  2. GUI shows gesture name (e.g., "HandClose")                 │
│  3. grasp_start         → Hand animation starts (follow this!) │
│  4. grasp_hold_start    → Hold the gesture                     │
│  5. grasp_hold_end      → Release                              │
│  6. grasp_released      → Hand returns to rest                 │
│  7. trial_end           → Trial complete, inter-trial interval │
│                                                                │
│  Repeat for all trials (typically 20-30 per class)             │
│  8. session_end         → All trials complete                  │
└────────────────────────────────────────────────────────────────┘
```

**Unity Configuration** (`md-emg-VR/Assets/Config/OpenLoopConfig.json`):
```json
{
  "trialsStartDelay": 2000,      // ms before first trial
  "trialIntervalDuration": 2500, // ms between trials
  "cueGraspStartInterval": 1500, // ms cue shown before animation
  "holdDuration": 2500           // ms to hold the gesture
}
```

**Recording Tips:**
- Follow the VR hand animation closely
- Keep your arm position consistent throughout
- The events file contains automatic timestamps for each gesture
- For BBT: record at different arm positions (down, forward, up)

### Phase 3: Data Labeling (Automatic from Unity Events)

When using Unity Open Loop mode, **labeling is automatic** - the events file contains timestamps for each gesture that are used during training.

```bash
# Events are automatically saved during recording:
# data/SCI/S0/raw/session_XX_events.pkl
#
# Contains events like:
# - trial_start, trial_end
# - grasp_start_0 (HandOpen), grasp_start_1 (HandClose)
# - grasp_hold_start, grasp_hold_end
# - session_start, session_end

# Optional: Verify events were recorded correctly
python utils/view_events.py --subj 0 --subj_type SCI --session 1
```

**Manual Labeling** (only if not using Unity):
```bash
# Option A: Use the GUI labeler
python utils/data_labeler.py --subj 0 --subj_type SCI

# Option B: Manual labeling in config
# Edit: config/subjects/SCI_S0_labels.yaml
```

**Manual Label Format** (if needed):
```yaml
session_01:
  - [0.0, 5.0, "rest"]      # Start, End, Label
  - [5.0, 8.0, "close"]
  - [8.0, 12.0, "rest"]
  - [12.0, 15.0, "open"]
```

### Phase 4: Model Training

```bash
# Train LSTM model (default)
python model_train.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close \
    --model_type LSTM

# Train CNN-LSTM model (recommended for BBT)
python model_train.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close \
    --model_type CNNLSTM

# Model saved to: models-subjects/SCI/S0/open_close/LSTM_open_loop.pth
```

**Training Options:**
| Model Type | Best For | Training Time |
|------------|----------|---------------|
| `LSTM` | General use | ~5 min |
| `CNNLSTM` | BBT/FSM control | ~10 min |
| `TFM` | High accuracy | ~15 min |

### Phase 5: Model Evaluation (Optional)

```bash
# Evaluate trained model on held-out data
python model_evaluate.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close

# Results saved to: results-training/SCI/S0/open_close/
```

### Phase 6: Real-Time Control

```bash
# Option A: Synchronized Mode (general use)
python emg_control_64.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close \
    --decoding_active 1 \
    --esp32_enabled 1

# Option B: FSM Mode (Box and Block Test)
python emg_control_64.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close \
    --control_mode fsm \
    --functional_test box_and_block \
    --decoding_active 1 \
    --esp32_enabled 1

# Option C: SCI Hybrid Mode (trigger-based)
python emg_control_64.py \
    --subj 0 \
    --subj_type SCI \
    --task open_close \
    --control_mode sci_hybrid \
    --decoding_active 1 \
    --esp32_enabled 1
```

### Quick Reference: Full Pipeline Commands

```bash
# === STEP 1: Setup ===
sudo bash setup_hotspot.sh
ping 192.168.50.10 && python test_esp32.py 192.168.50.11

# === STEP 2: Record (with Unity VR cues) ===
# Terminal 1: Start Unity VR → Select "Open Loop" → Configure settings
# Terminal 2: Start Python acquisition
python emg_control_64.py --subj 0 --subj_type SCI --task open_close --decoding_active 0
# In Unity: Press "Play" to start recording with visual cues
# Follow the hand animations, events are auto-timestamped

# === STEP 3: Train (labels from Unity events) ===
python model_train.py --subj 0 --subj_type SCI --task open_close --model_type LSTM

# === STEP 4: Run ===
python emg_control_64.py --subj 0 --subj_type SCI --task open_close --decoding_active 1 --esp32_enabled 1
```

### Workflow Diagram

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    HARDWARE      │    │  RECORD EMG +    │    │      TRAIN       │
│    SETUP         │───▶│  UNITY VR CUES   │───▶│      MODEL       │
│                  │    │                  │    │                  │
│ • Hotspot        │    │ • Start Unity VR │    │ • LSTM           │
│ • Connect SQ     │    │ • Start Python   │    │ • CNN-LSTM       │
│ • Connect ESP32  │    │ • Follow visual  │    │ • Events → Labels│
│                  │    │   hand cues      │    │                  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                                       │
                              ┌─────────────────────────┘
                              ▼
┌──────────────────┐    ┌──────────────────┐
│   REAL-TIME      │    │    EVALUATE      │
│   CONTROL        │◀───│    (optional)    │
│                  │    │                  │
│ • FSM mode (BBT) │    │ • Accuracy       │
│ • Sync mode      │    │ • Confusion      │
│ • SCI hybrid     │    │   matrix         │
└──────────────────┘    └──────────────────┘
```

---

### 6. SCI Patient Mode

```bash
# SCI hybrid control with spasticity detection
python emg_control_64.py \
    --subj_type SCI \
    --subj 1 \
    --task open_close \
    --control_mode sci_hybrid \
    --decoding_active 1 \
    --esp32_enabled 1
```

## 📖 How-To Guides

### Train a New Model

```bash
# 1. Record training data
python emg_control_64.py --subj 1 --task open_close --decoding_active 0

# 2. Train model
python model_train.py --subj 1 --task open_close --model_type LSTM

# 3. Run with trained model
python emg_control_64.py --subj 1 --task open_close --decoding_active 1
```

### Use CNN-LSTM with Transfer Learning

```bash
# 1. Pre-train on healthy subjects (done once)
python scripts/bbt_calibration.py --subj 0 --subj_type healthy --mode full_calibration

# 2. Transfer to new patient with quick calibration
python scripts/bbt_calibration.py --subj 1 --subj_type SCI --mode quick_calibration \
    --pretrained models/pretrained/cnnlstm_healthy.pth
```

### Configure FSM Control Thresholds

Edit `config/functional_tests.yaml`:

```yaml
fsm_control:
  flexor_trigger_threshold: 0.40   # Lower = more sensitive
  extensor_trigger_threshold: 0.35
  lock_grasp_enabled: true         # Keep hand closed during transport
  lock_duration_min_ms: 300        # Minimum time before release
```

### Enable/Disable Features

All features can be toggled in `config/functional_tests.yaml`:

```yaml
features:
  use_fsm_control: true           # FSM vs proportional
  use_grasp_locking: true         # Lock during transport
  use_cnn_lstm: true              # CNN-LSTM vs standard LSTM
  use_transfer_learning: true     # Pre-trained weights
  use_dynamic_training: true      # Train with movement data
  use_electrode_dropout: true     # Dropout augmentation
  use_sci_mode: false             # SCI-specific processing
```

### Test ESP32 Connection

```bash
# Auto-discover ESP32 devices
python test_esp32.py scan

# Test specific IP
python test_esp32.py 192.168.4.1
```

## 🔧 Control Modes Explained

| Mode | Use Case | Key Feature |
|------|----------|-------------|
| `synchronized` | General use | Mirrors gestures to Unity + ESP32 |
| `fsm` | Functional tests (BBT) | Grasp locking, state-based control |
| `sci_hybrid` | SCI patients | Trigger-based, handles spasticity |
| `unity_only` | VR visualization | No ESP32 output |
| `esp32_only` | Hardware testing | No Unity output |

## 📊 Supported Tasks

| Task | Classes | Description |
|------|---------|-------------|
| `open_close` | 3 | Rest, Hand Close, Hand Open |
| `grasp_patterns` | 4 | Rest, Hook Grasp, Lateral Grasp, Index Point |
| `single_fingers` | 4 | Rest, Thumb, Index, MRP |

## 🏥 SCI Patient Features

When `--sci_mode 1` or `--subj_type SCI`:

1. **Spatial Filtering**: Laplacian filter reduces same-hand EMI
2. **Spasticity Detection**: Monitors for involuntary muscle activity
3. **Fatigue Compensation**: Adapts thresholds over session duration
4. **Lower SNR Handling**: Optimized for weaker/noisier signals

## 🧪 Functional Tests

### Box and Block Test (BBT)
- **FSM States**: IDLE → CLOSING → LOCKED_GRASP → OPENING
- **Grasp Locking**: Hand stays closed during transport phase
- **Trigger Detection**: Sharp EMG rise detection, not continuous amplitude

### Unity FSM Display

When using FSM mode, Unity shows real-time feedback:
- **State Indicator**: Color-coded current state (green=IDLE, blue=LOCKED, etc.)
- **Lock Indicator**: Pulsing visual when grasp is locked during transport
- **BBT Scoring**: Block count, grasp cycles, and session timer

To set up the Unity display, see [md-emg-VR/Assets/Config/FSM_DISPLAY_SETUP.md](md-emg-VR/Assets/Config/FSM_DISPLAY_SETUP.md).

### Calibration Protocol
1. Rest baseline (5 trials)
2. Grasp with arm down (3 trials)
3. Grasp with arm forward (3 trials)  
4. Grasp with arm up (3 trials)
5. Open gestures at each position

## 📝 Command Line Reference

```bash
python emg_control_64.py [OPTIONS]

Options:
  --subj_type         Subject type: healthy, SCI (default: SCI)
  --subj              Subject number (default: 0)
  --task              Task: open_close, grasp_patterns, single_fingers
  --decoding_active   Enable ML decoding: 0 or 1 (default: 0)
  --control_mode      Control mode: synchronized, fsm, sci_hybrid, 
                      unity_only, esp32_only (default: synchronized)
  --functional_test   Test type: box_and_block, peg_test, pouring, jar_opening
  --esp32_enabled     Enable ESP32: 0 or 1 (uses config if not specified)
  --sci_mode          Force SCI mode: 0 or 1
  --is_mvc_session    MVC calibration session: 0 or 1
```

## 📚 Configuration Files

| File | Purpose |
|------|---------|
| `config/functional_tests.yaml` | FSM control, BBT settings, feature toggles |
| `config/sci_patient.yaml` | SCI-specific filter and control settings |
| `config/esp32_control.yaml` | ESP32 network and gesture mapping |
| `config/models/CNNLSTM_cfg.yaml` | CNN-LSTM architecture and training |
| `config/64_config.yaml` | EMG amplifier connection settings |

## 🔬 Hardware Requirements

- **EMG**: OTB Sessantaquattro 64-channel amplifier
- **Electrodes**: 32-channel HD-sEMG grid (8x4 or 4x8)
- **Exoskeleton**: ESP32-controlled soft pneumatic hand
- **Optional**: Unity VR for visualization

## 📄 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📧 Contact

For questions or collaboration, open an issue on GitHub.
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