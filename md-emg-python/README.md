# md-emg-python

Real-time EMG acquisition, decoding, and exoskeleton control for the Sessantaquattro 32-channel amplifier + ESP32 pneumatic glove system. Supports subject-specific model training and transfer learning from healthy subjects to SCI patients.

---

## System Architecture

```
Sessantaquattro ──WiFi──► Laptop (Hotspot) ◄──WiFi── ESP32
   32ch EMG              192.168.50.1              Glove Control
   1000 Hz                    │
                              ▼
                    EMG Processing → ML Decoding → Gesture Control
```

| Device | IP | Port | Role |
|--------|-----|------|------|
| Laptop (Hotspot) | 192.168.50.1 | — | Gateway, runs all Python code |
| Sessantaquattro | 192.168.50.10 | 45454 | EMG amplifier (connects TO laptop as TCP client) |
| ESP32 | 192.168.50.11 | 4210 | Glove controller (TCP server, laptop connects to it) |

---

## Prerequisites

Install Python dependencies (PyTorch must be installed separately for your CUDA version):

```bash
# Install PyTorch first (see https://pytorch.org for your platform)
pip install torch torchvision torchaudio

# Then install the rest
pip install -r requirements.txt
```

> `requirements.txt` includes: numpy, pandas, torch, scikit-learn, PyYAML, h5py, matplotlib, dearpygui, keyboard, einops, etc.
> `req.txt` is the same list minus PyTorch (if you install torch separately).

---

## Step-by-step Guide

### Step 0: Configure the WiFi Hotspot

The laptop creates a WiFi hotspot that both the Sessantaquattro and ESP32 connect to. All communication routes through this network.

**0.1. Edit `setup_hotspot.sh`** with your machine's WiFi interface and device MAC addresses:

```bash
# Find your WiFi interface name
ip link

# Edit the script — change IFACE, BOARD1_MAC, BOARD2_MAC to match your hardware
nano setup_hotspot.sh
```

Key variables to set:
- `IFACE` — your WiFi interface (e.g., `wlp3s0`)
- `SSID` / `PASS` — hotspot name and password (default: `Arlen` / `12345678`)
- `BOARD1_MAC` — Sessantaquattro MAC address
- `BOARD2_MAC` — ESP32 MAC address

**0.2. Start the hotspot:**

```bash
sudo bash setup_hotspot.sh
```

This creates a NetworkManager hotspot with static DHCP leases so devices always get the same IPs.

---

### Step 1: Connect the Devices

**1.1. Configure the Sessantaquattro** (one-time, via its web interface):

1. Connect to the Sessantaquattro's own WiFi AP
2. Open `http://192.168.1.1` in a browser
3. Set: WiFi Mode → **Station**, SSID → `Arlen`, Password → `12345678`
4. Set: TCP Server IP → `192.168.50.1`, Port → `45454`
5. Save and restart the device

The Sessantaquattro acts as a TCP **client** — it connects to the laptop. The laptop IP/port it connects to is set in `config/64_config.yaml`:
```yaml
ip_address: "192.168.50.10"
port: 45454
```

**1.2. Power on the ESP32 glove** — it should auto-connect to the hotspot. Its settings are in `config/esp32_control.yaml`:
```yaml
ip_address: "192.168.50.11"
port: 4210
```

**1.3. Auto-detect devices** (optional, updates config files automatically):

```bash
python scripts/auto_detect_devices.py
```

**1.4. Verify all connections:**

```bash
python scripts/connection_monitor.py
```

This scans the network, tests the Sessantaquattro TCP connection (by listening on port 45454), and tests the ESP32 TCP connection (by connecting to port 4210).

---

### Step 2: Create a Subject Configuration

Before recording, each subject needs a YAML config file at `config/subjects/{subj_type}/S{subj}.yaml`.

Example for SCI subject S1 — create `config/subjects/SCI/S1.yaml`:

```yaml
subj_identifier: "S1"
sleeve: true  # true if using EMG sleeve, false if bipolar electrodes

task_open_close:
  sessions_open_loop: []      # will be populated as you record sessions
  sessions_closed_loop: []
  invalid_sessions: []
  model_type: "LSTM"          # options: LSTM, TFM, CTFM, CRNN
  seq_len: 5
  num_class: 3                # rest + open + close

task_grasp_patterns:
  sessions_open_loop: []
  sessions_closed_loop: []
  invalid_sessions: []
  model_type: "LSTM"
  seq_len: 5

task_single_fingers:
  sessions_open_loop: []
  sessions_closed_loop: []
  invalid_sessions: []
  model_type: "LSTM"
  seq_len: 5
```

> **Important:** After recording sessions, you must update `sessions_open_loop` with the session numbers you want to use for training (e.g., `[0, 1, 2]`).

---

### Step 3: Record EMG Data

Recording is done with `emg_control_64.py` with decoding disabled. This runs a TCP event server on `localhost:55000` that receives grasp/event triggers from an external cue program (e.g., Unity VR).

**3.1. (Optional) Start the real-time visualization GUI** in a separate terminal:

```bash
python streaming_gui.py
```

This opens a DearPyGui window showing live EMG signals streamed over `localhost:55001`. Only works when `stream.enabled: true` in `config/emg_signal_processing.yaml`.

**3.2. Start recording:**

```bash
# Run from the md-emg-python/ directory
sudo python emg_control_64.py \
    --subj 1 \
    --subj_type SCI \
    --task open_close \
    --acquisition_type open_loop \
    --decoding_active 0
```

> `sudo` is needed for real-time process priority (`nice -20`). Without it, you get a warning but recording still works.

The script will:
1. Connect to the Sessantaquattro (TCP server on `192.168.50.1:45454`)
2. Open an events TCP server on `localhost:55000` (for receiving grasp cues)
3. Open a streaming socket on `localhost:55001` (if enabled)
4. Start acquiring EMG data at 1000 Hz, 32 channels
5. Wait for you to press **Enter** to stop

**3.3. Send grasp cues** from your experiment control software (Unity VR, or another program) to `localhost:55000`. Events like `grasp_start`, `grasp_hold_start`, `grasp_hold_end` are timestamped and saved.

**3.4. Press Enter** to stop. Data is saved automatically:
- `data/SCI/S1/raw/session_00.npy` — raw EMG data
- `data/SCI/S1/raw/session_00_events.pkl` — timestamped event list

Session numbers auto-increment (`session_00`, `session_01`, ...).

**3.5. Record multiple sessions** by repeating the command. Each run creates the next session file.

**3.6. Update the subject config** — add the recorded session numbers to `sessions_open_loop`:

```yaml
task_open_close:
  sessions_open_loop: [0, 1, 2, 3]   # <-- add your session numbers here
```

#### Key recording options

| Option | Default | Description |
|--------|---------|-------------|
| `--subj` | `0` | Subject number |
| `--subj_type` | `SCI` | `healthy` or `SCI` |
| `--task` | `open_close` | `open_close`, `grasp_patterns`, or `single_fingers` |
| `--acquisition_type` | `open_loop` | `open_loop`, `closed_loop`, or `both` |
| `--decoding_active` | `0` | `0` = record only, `1` = record + run model inference |
| `--esp32_enabled` | (from config) | `0` or `1` — override ESP32 glove control |
| `--is_mvc_session` | `0` | `1` to record a Maximum Voluntary Contraction session |
| `--session` | `0` | Manual session ID override |

---

### Step 4: Train a Model (Subject-Specific)

This trains a model directly on the recorded subject's data. Use this when you have enough recording sessions for the subject.

**4.1. Prepare the dataset and train:**

```bash
python model_train.py \
    --subj 1 \
    --subj_type SCI \
    --task open_close \
    --acquisition_type open_loop
```

This script:
1. Calls `dataset_preparation()` — reads all sessions listed in the subject config's `sessions_open_loop`, extracts features (RMS by default, 250ms windows, 150ms shift), creates labels from events, applies z-score normalization, and saves to `data/SCI/S1/open_loop_open_close_data.pkl`
2. Loads the prepared dataset, splits into train/valid/test (75/15/10%)
3. Trains the model type specified in the subject config (default: `LSTM`, 500 epochs max with early stopping at patience=50)
4. Saves model weights to `models-subjects/SCI/S1/open_close/LSTM_open_loop.pth`
5. Saves training results to `results-training/SCI/S1/open_close/`

**Training config** is in `config/decoding_train_open_close.yaml` (batch_size, epochs, learning rate, etc.).

**Model architecture config** is in `config/models/{MODEL_TYPE}_cfg.yaml` (hidden sizes, layers, dropout).

To continue training from an existing model:

```bash
python model_train.py \
    --subj 1 --subj_type SCI --task open_close \
    --acquisition_type open_loop --load_existing_model 1
```

---

### Step 5: Transfer Learning (Alternative to Step 4)

When you have very few sessions for a new subject (e.g., SCI patient with limited recording time), use transfer learning from a pre-trained healthy model instead.

#### 5a. Pre-train on Healthy Subjects (one-time)

Train a CNN-LSTM (or LSTM) on healthy subjects S1–S10 data:

```bash
python scripts/pretrain_healthy.py \
    --task open_close \
    --model_type CNNLSTM \
    --epochs 100 \
    --subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 \
    --conditions all
```

Options:
- `--model_type` — `LSTM` or `CNNLSTM`
- `--conditions` — `all`, `no_glove`, `passive_glove`, or `active_glove`
- `--window_ms` / `--overlap_ms` — window size (default: 200ms / 100ms)
- `--output_dir` — default: `models/pretrained/`

Output: `models/pretrained/pretrained_cnnlstm_open_close.pth`

#### 5b. Fine-tune on Target Subject (Quick Method)

For fast fine-tuning with minimal data (~10 trials):

```bash
python scripts/quick_finetune.py \
    --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
    --data_file data/SCI/S1/raw/session_00.npy \
    --events_file data/SCI/S1/raw/session_00_events.pkl \
    --output models-subjects/SCI/S1/open_close/CNNLSTM_finetuned.pth \
    --no_freeze
```

Options:
- `--freeze` (default) — only train the classifier layer (fastest, best for very small data)
- `--no_freeze` — train all layers (better accuracy, needs more data)
- `--epochs` — default: 30
- `--lr` — default: 0.001

#### 5c. Fine-tune on Target Subject (Full Method)

For more control over the fine-tuning process:

```bash
python scripts/transfer_learning.py \
    --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
    --subj 1 \
    --subj_type SCI \
    --freeze_features \
    --epochs 50 \
    --lr 0.0001
```

Options:
- `--freeze_features` — freeze feature extractor, only train classifier
- `--epochs` — default: 50
- `--lr` — default: 0.0001
- `--batch_size` — default: 32
- `--output_dir` — default: `models-subjects/`

Output: `models-subjects/SCI/S1/open_close/{model_type}_finetuned.pth`

#### Pretrained Models

All pretrained models live in `md-emg-python/models/pretrained/`. There are two sources:

#### Direct pretraining (`pretrain_healthy.py`) — recommended

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

#### Pipeline HPO models (`train_transfer_pipeline_cli.py`)

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

#### Which model to use?

- **For quick fine-tuning / real-time control:** Use `pretrained_cnnlstm_open_close.pth` (recommended — best generalization to SCI subjects)
- **For grasp detection:** Use `pretrained_cnnlstm_grasp_vs_rest.pth` (100% on healthy data)
- **For research / HPO comparison:** The `*_best.pth` files have Optuna-tuned architectures

#### Transfer learning to SCI subjects

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

---

### Step 6: Real-time Decoding (Online Control)

Once you have a trained model, run the system with decoding enabled. The model file must exist at `models-subjects/{subj_type}/S{subj}/{task}/{model_type}_{acquisition_type}.pth`.

**6.1. (Optional) Start the prediction visualization GUI:**

```bash
python streaming_predictions_gui.py
```

**6.2. Run with decoding + ESP32 glove control:**

```bash
sudo python emg_control_64.py \
    --subj 1 \
    --subj_type SCI \
    --task open_close \
    --acquisition_type open_loop \
    --decoding_active 1 \
    --esp32_enabled 1 \
    --control_mode synchronized
```

This launches the full pipeline as parallel processes:
1. **Acquisition** — reads EMG from Sessantaquattro, filters (notch 50Hz + bandpass 15–450Hz), buffers
2. **Decoding** — extracts features, runs the trained model, outputs predictions
3. **Control** — maps predictions to gesture commands
4. **ESP32 Control** — sends gesture commands to the pneumatic glove via TCP
5. **Streaming** — sends live data to the GUI (if enabled)
6. **Data saving** — raw EMG + predictions are saved to disk

Press **Enter** to stop.

#### Control modes

| Mode | Description |
|------|-------------|
| `synchronized` | Sends predictions to both Unity VR and ESP32 simultaneously |
| `esp32_only` | Controls ESP32 glove only, no Unity |
| `unity_only` | Sends to Unity VR only, no ESP32 |
| `sci_hybrid` | SCI-specific: includes spatial filtering, spasticity detection, fatigue compensation |
| `fsm` | Finite state machine for functional tests (pair with `--functional_test`) |

#### ESP32 gesture mapping

Gesture mappings are defined in `config/esp32_control.yaml`. For `open_close` task:
- Prediction 0 (HandOpen) → ESP32 gesture 2 (Extend)
- Prediction 1 (HandClose) → ESP32 gesture 1 (All Flex)

---

## Stability During Functional Tasks (BBT)

During functional assessments like the Box and Block Test (BBT), the standard proportional/continuous decoding can be unstable — the patient must hold a sustained EMG contraction during the transport phase, and motion artifacts from shoulder/elbow movement often cause accidental drops. Two dedicated control modules address this.

> **EMG recording is not affected** by any of these stability methods. The raw data acquisition (Step 3) is always the same regardless of control mode. These features only change how predictions are interpreted and sent to the exoskeleton during online decoding (Step 6).

### FSM Control Mode (`--control_mode fsm`)

The Finite State Machine in [realtime_components/fsm_control.py](realtime_components/fsm_control.py) replaces proportional control with a state-based strategy:

```
IDLE ──flexor burst──► CLOSING ──trajectory done──► LOCKED_GRASP ──extensor burst──► OPENING ──done──► IDLE
```

**Key feature: Grasp Locking.** Once the hand closes, the FSM enters `LOCKED_GRASP` and **ignores all EMG fluctuations** during transport. The patient can relax during the carry phase without dropping the block. Only a deliberate extensor burst triggers release.

```bash
# Run with FSM control for BBT
sudo python emg_control_64.py \
    --subj 1 --subj_type SCI --task open_close \
    --decoding_active 1 --esp32_enabled 1 \
    --control_mode fsm --functional_test box_and_block
```

Configuration is in [config/functional_tests.yaml](config/functional_tests.yaml).

### SCI Hybrid Control Mode (`--control_mode sci_hybrid`)

The SCI control module in [realtime_components/sci_control.py](realtime_components/sci_control.py) adds on top of basic control:

- **Spasticity detection** — detects involuntary spasms and suppresses them instead of executing a gesture
- **Fatigue compensation** — adaptively boosts sensitivity as the patient fatigues (up to 2.5×)
- **Consecutive prediction filtering** — requires 4 identical predictions in a row before acting
- **Minimum confidence gate** — ignores predictions below 50% confidence
- **Hybrid trigger mode** — EMG triggers the action, but the robot executes a predefined trajectory

```bash
# Run with SCI hybrid control
sudo python emg_control_64.py \
    --subj 1 --subj_type SCI --task open_close \
    --decoding_active 1 --esp32_enabled 1 \
    --control_mode sci_hybrid
```

Configuration is in [config/sci_patient.yaml](config/sci_patient.yaml).

### Stability Enhancements (in FSM Control)

Three additional stability features are built into the FSM control and can be toggled in [config/functional_tests.yaml](config/functional_tests.yaml):

#### 1. Co-Contraction Rejection

During reaching and transport, patients often co-contract flexors and extensors simultaneously to stiffen the wrist/arm against gravity. This should not trigger a state change.

When both flexor and extensor RMS values spike at the same time (ratio close to 1.0), the trigger is rejected.

```yaml
# config/functional_tests.yaml → fsm_control
cocontraction_rejection_enabled: true
cocontraction_ratio_min: 0.60    # ext/flex ratio band that counts as co-contraction
cocontraction_ratio_max: 1.40
cocontraction_min_amplitude: 0.20  # both must exceed this to check
```

**When to tune:** If intentional grasps are being rejected, widen the ratio band (e.g., 0.4–1.6). If accidental triggers happen during transport, narrow it (0.7–1.3).

#### 2. Gravity-Compensated Dynamic Baselines

The default slow-EMA baseline (`alpha = 0.001`) cannot adapt fast enough when the patient lifts their arm — tonic EMG from fighting gravity raises the global activity level, causing false triggers.

The dynamic baseline uses a **sliding-window 5th-percentile** instead. This lets the threshold floor float up with postural activity, so only intentional bursts above the current gravity-fighting level register as triggers.

```yaml
# config/functional_tests.yaml → fsm_control
dynamic_baseline_enabled: true
dynamic_baseline_window_sec: 2.0   # 2-second sliding window
dynamic_baseline_percentile: 5.0   # 5th percentile as floor
```

**When to tune:** If reacting too slowly, shorten the window (1.0s). If still getting false triggers from posture, increase the percentile (10–15).

#### 3. Confidence-Gated Temporal Smoothing

When the FSM falls back to the CNN-LSTM model predictions (no raw EMG data available), transient misclassifications can break `LOCKED_GRASP`. This gate requires N consecutive predictions of the same class, all with confidence above a threshold, before the FSM accepts the trigger.

```yaml
# config/functional_tests.yaml → fsm_control
confidence_gating_enabled: true
confidence_min_threshold: 0.70   # minimum softmax probability
confidence_consec_required: 5    # 5 consecutive matching frames needed
```

**When to tune:** If the system feels sluggish, reduce `confidence_consec_required` (3) or lower `confidence_min_threshold` (0.5). If still flickering, increase both.

### Recommended Settings for BBT

| Scenario | co-contraction | dynamic baseline | confidence gate | control mode |
|----------|---------------|-----------------|----------------|-------------|
| Able-bodied, clean signals | off | off | off | `fsm` |
| Able-bodied, some artifacts | on (default) | on (default) | off | `fsm` |
| SCI, moderate signals | on (default) | on (default) | on (default) | `fsm` |
| SCI, weak/noisy signals | on (default) | on (default) | on (consec=7) | `sci_hybrid` |

### BBT Calibration Script

For clinical use, a dedicated calibration script collects movement-specific training data and runs transfer learning in one session:

```bash
# Full calibration: collect data + transfer learn + validate
python scripts/bbt_calibration.py --subj 1 --mode full_calibration

# Quick calibration: minimal trials for per-session adaptation
python scripts/bbt_calibration.py --subj 1 --mode quick_calibration

# Test robustness against electrode dropout
python scripts/bbt_calibration.py --subj 1 --mode test_robustness
```

---

## Project Structure

### Main Scripts

| Script | Purpose |
|--------|---------|
| `emg_control_64.py` | **Main entry point** — EMG acquisition, decoding, and exoskeleton control |
| `model_train.py` | Train a model on a subject's recorded data |
| `model_evaluate.py` | Evaluate a trained model offline on recorded data |
| `streaming_gui.py` | Real-time EMG signal visualization (DearPyGui) |
| `streaming_predictions_gui.py` | Real-time EMG + prediction visualization |
| `setup_hotspot.sh` | Create the WiFi hotspot |

### Scripts in `scripts/`

| Script | Purpose |
|--------|---------|
| `auto_detect_devices.py` | Scan network and auto-configure device IPs |
| `connection_monitor.py` | Test Sessantaquattro and ESP32 connections |
| `pretrain_healthy.py` | Pre-train LSTM/CNNLSTM on healthy subject data |
| `quick_finetune.py` | Fast transfer learning with minimal data |
| `transfer_learning.py` | Full transfer learning pipeline |
| `test_sci_transfer.py` | Evaluate transfer learning results |
| `bbt_calibration.py` | Box and Block Test calibration |

### Configuration Files (`config/`)

| File | Purpose |
|------|---------|
| `64_config.yaml` | Sessantaquattro IP and port |
| `esp32_control.yaml` | ESP32 IP, port, gesture mappings, pressure/speed settings |
| `emg_signal_processing.yaml` | Sampling rate, filters (notch/bandpass), streaming settings |
| `features_params.yaml` | Feature type (RMS/MAV/raw), window sizes, normalization |
| `decoding_params.yaml` | Prediction buffer size, consecutive prediction filtering |
| `decoding_train_open_close.yaml` | Training hyperparameters for open/close task |
| `decoding_train_grasp_patterns.yaml` | Training hyperparameters for grasp patterns task |
| `decoding_train_single_fingers.yaml` | Training hyperparameters for single fingers task |
| `tcp_server_events.yaml` | Events TCP server host/port (`localhost:55000`) |
| `streaming_gui.yaml` | GUI display settings |
| `sci_patient.yaml` | SCI-specific: spatial filters, spasticity, fatigue compensation |
| `subjects/{subj_type}/S{n}.yaml` | Per-subject: session list, model type, sequence length |
| `models/{MODEL}_cfg.yaml` | Model architecture hyperparameters |

### Data Layout

```
data/
├── healthy/
│   └── S0/
│       ├── raw/                    # Raw recorded sessions
│       │   ├── session_00.npy
│       │   ├── session_00_events.pkl
│       │   └── ...
│       ├── mvc/                    # MVC calibration data
│       └── open_loop_open_close_data.pkl   # Prepared training dataset
└── SCI/
    └── S1/
        ├── raw/
        │   ├── session_00.npy
        │   ├── session_00_events.pkl
        │   └── ...
        └── mvc/

models-subjects/                    # Trained model weights
├── healthy/S0/open_close/
│   └── LSTM_open_loop.pth
└── SCI/S1/open_close/
    └── LSTM_open_loop.pth

models/pretrained/                  # Pre-trained models for transfer learning
└── pretrained_cnnlstm_open_close.pth

results-training/                   # Training logs and plots
└── SCI/S1/open_close/
```

---

## Troubleshooting

**Sessantaquattro not connecting:**
- Verify TCP Server IP is set to `192.168.50.1` in the device web interface (`http://192.168.1.1`)
- Restart the Sessantaquattro after any config change
- Check the hotspot is running: `nmcli connection show --active`
- Run `python scripts/connection_monitor.py` to diagnose

**ESP32 not responding:**
- Test manually: `nc -v 192.168.50.11 4210`
- Check firewall: `sudo ufw allow 4210/tcp`
- Verify the ESP32 is connected to the hotspot: `arp -a | grep 192.168.50`

**"Failed to connect to the events server":**
- The events server expects something to connect on `localhost:55000`. Make sure your experiment cue software (Unity VR) is running and listening, or check `config/tcp_server_events.yaml`.

**Poor decoding accuracy:**
- Record more sessions (≥5 sessions with ≥10 grasps each)
- Check that `sessions_open_loop` in the subject config includes all valid sessions
- Try a different model type (`CNNLSTM` instead of `LSTM`)
- For transfer learning, try `--no_freeze` to train all layers
- Use `--freeze` (classifier-only) when you have very few trials

**Process priority warning:**
- Run with `sudo` for real-time priority, or ignore the warning (recording still works)
