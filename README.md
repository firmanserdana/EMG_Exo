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

## Pretrained Models

All pretrained models live in `md-emg-python/models/pretrained/`. There are two sources:

### Direct pretraining (`pretrain_healthy.py`) — recommended

Trained with fixed architecture from `pretrain_healthy.py` using all 10 healthy subjects (S1-S10), 3 conditions (no glove, passive glove, active glove), and `ReduceLROnPlateau` scheduler.

| File | Task | Architecture | Val Acc | Epochs | LR |
|------|------|-------------|---------|--------|----|
| `pretrained_cnnlstm_open_close.pth` | open_close | CNNLSTM (conv 64→128, LSTM h=64, L=2) | **71.4%** | 121 | 0.001 |
| `pretrained_lstm_open_close.pth` | open_close | LSTM (h=128, L=2, bidir) | 63.2% | 48 | 0.0005 |
| `pretrained_cnnlstm_grasp_vs_rest.pth` | grasp_vs_rest | CNNLSTM (conv 64→128, LSTM h=64, L=2) | **100%** | 100 | 0.001 |
| `pretrained_lstm_grasp_vs_rest.pth` | grasp_vs_rest | LSTM (h=128, L=2, bidir) | **100%** | 42 | 0.001 |

**Re-create these models:**
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
