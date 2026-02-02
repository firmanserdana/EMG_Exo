# EMG-Controlled Hand Exoskeleton System

Real-time EMG decoding and pneumatic exoskeleton control with transfer learning for SCI patients.

## Project Structure

```
EMG_Exo/
├── md-emg-python/       # Main Python framework (see md-emg-python/README.md)
├── ESP32_Exo/           # ESP32 glove firmware
└── md-emg-VR/           # Unity VR visualization
```

## Quick Start

```bash
cd md-emg-python

# 1. Setup network
sudo bash setup_hotspot.sh
python scripts/auto_detect_devices.py

# 2. Record EMG
python scripts/emg_control_64.py --subj 1 --subj_type SCI --task open_close --decoding_active 0

# 3. Fine-tune model
python scripts/quick_finetune.py \
    --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
    --data_file data/SCI/S1/raw/session_01.npy \
    --events_file data/SCI/S1/raw/session_01_events.pkl

# 4. Real-time control
python scripts/emg_control_64.py --subj 1 --subj_type SCI --decoding_active 1 --esp32_enabled 1
```

## Hardware

| Device | Purpose |
|--------|---------|
| Sessantaquattro | 32-channel EMG amplifier (192.168.50.10:45454) |
| ESP32 | Pneumatic glove controller (192.168.50.11:4210) |
| Laptop | WiFi hotspot + ML processing (192.168.50.1) |

## Features

- **CNN-LSTM decoding** with transfer learning from healthy subjects
- **SCI patient support** with spasticity detection and fatigue compensation
- **FSM control** for functional tests (Box and Block Test)
- **Real-time ESP32 control** for pneumatic exoskeleton

## Documentation

See [md-emg-python/README.md](md-emg-python/README.md) for detailed setup and usage.
