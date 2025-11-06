# Finger Proportional Control System

## Overview

The proportional control system enables continuous, speed and force-based control of individual fingers or the whole hand using EMG signals. This is an advanced control mode that goes beyond discrete gesture classification to provide smooth, proportional control.

## Features

### EMG Input Options
- **Raw EMG**: Direct use of filtered EMG signals (RMS, MAV, etc.)
- **Motor Unit Decomposition (MUD)**: Extract individual motor unit firing patterns for more detailed control

### Decoders
- **MLP (Multi-Layer Perceptron)**: Neural network-based regressor for smooth proportional control
- **KNN (K-Nearest Neighbors)**: Instance-based regressor for simple proportional control

### Control Modes
- **Individual Fingers**: Independent control of each finger (flexion/extension)
  - Thumb, Index, Middle, Ring, Pinky
  - Each finger has separate flexion and extension values
  
- **Whole Hand**: Synchronized control of all fingers
  - Single flexion/extension value applied to all fingers
  - Useful for grasp/release patterns

### Output Aspects
- **Speed**: Rate of finger movement (0-1, normalized)
- **Force**: Strength/pressure of movement (0-1, normalized)
- **Continuous values**: Smooth transitions between states

## Architecture

```
EMG Signals
    ↓
[Raw EMG] or [Motor Unit Decomposition]
    ↓
Feature Extraction
    ↓
[MLP Decoder] or [KNN Decoder]
    ↓
Proportional Values (0-1 per finger/direction)
    ↓
Control Mapper
    ├→ Unity Format (speed/force visualization)
    └→ ESP32 Format (pressure/speed control)
```

## Installation

The proportional control system is integrated into the existing EMG_Exo codebase:

```bash
cd /home/runner/work/EMG_Exo/EMG_Exo/md-emg-python
pip install -r requirements.txt  # Already installed
```

## Quick Start

### 1. Test the System

```bash
# Test all components
python test_proportional_control.py
```

### 2. Train a Decoder

First, prepare your training data in the format:
- `emg`: EMG signals (n_samples, n_timepoints, n_channels)
- `targets`: Target proportional values (n_samples, n_outputs)

```bash
# Train MLP decoder for individual finger control
python train_proportional_decoder.py \
  --decoder mlp \
  --config config/proportional_train.yaml

# Train KNN decoder for whole hand control
python train_proportional_decoder.py \
  --decoder knn \
  --config config/proportional_train.yaml
```

### 3. Run Proportional Control

```bash
# Individual finger control with MLP decoder
python emg_proportional_control.py \
  --decoder mlp \
  --control-mode individual_fingers \
  --subj-type healthy \
  --subj 0 \
  --session 0

# Whole hand control with KNN decoder and ESP32
python emg_proportional_control.py \
  --decoder knn \
  --control-mode whole_hand \
  --esp32-enabled 1 \
  --subj-type healthy \
  --subj 0 \
  --session 1

# With motor unit decomposition
python emg_proportional_control.py \
  --decoder mlp \
  --control-mode individual_fingers \
  --use-mud 1 \
  --esp32-enabled 1
```

## Configuration

### Proportional Control Configuration

Edit `config/proportional_control.yaml`:

```yaml
# Decoder settings
decoder_type: 'mlp'  # 'mlp' or 'knn'
use_motor_unit_decomposition: false

# Control mode
proportional_control_mode: 'individual_fingers'  # or 'whole_hand'
num_fingers: 5

# Feature extraction
feature_type: 'rms+mav+wl'
dec_win_length: 0.2  # seconds
dec_win_shift: 0.05  # seconds

# Output processing
smooth_window_size: 5
smooth_sigma: 1.5
min_activation_threshold: 0.1

# Control loop
min_update_interval: 0.05  # 20 Hz max
control_mode: 'synchronized'

# Motor unit decomposition
mud_settings:
  threshold_method: 'mad'
  spike_detection_threshold: 4.0
  template_window_ms: 5.0
  highpass_cutoff: 100
  lowpass_cutoff: 500
```

### Training Configuration

Edit `config/proportional_train.yaml`:

```yaml
# Data
data_file: 'data/healthy/proportional_training_data.npz'
fsample: 2048

# Model architecture (MLP)
hidden_dims: [256, 128, 64]
dropout: 0.3
activation: 'relu'

# Training
batch_size: 32
num_epochs: 100
learning_rate: 0.001
early_stopping_patience: 15

# KNN parameters
n_neighbors: 5
weights: 'distance'
```

## Unity Integration

### Using ProportionalHandController

The Unity hand controller supports proportional control with visual feedback:

```csharp
// In Unity, the ProportionalHandController handles proportional events
public class ProportionalHandController : MonoBehaviour
{
    // Receives proportional control events from Python
    public void HandleProportionalControlEvent(Dictionary<string, object> eventData)
    {
        // Extracts finger control values
        // Updates hand visualization with speed and force
        // Provides visual feedback (color based on force)
    }
}
```

**Event Format from Python:**
```json
{
    "event_type": "proportional_control",
    "timestamp": 1234567.89,
    "fingers": {
        "thumb": {
            "flexion_speed": 0.7,
            "extension_speed": 0.3,
            "force": 0.8
        },
        "index": {
            "flexion_speed": 0.5,
            "extension_speed": 0.2,
            "force": 0.6
        },
        ...
    }
}
```

### Visual Feedback

- **Finger Position**: Interpolated between extended and flexed based on net flexion
- **Color Coding**: Fingers change color based on force level (white → red)
- **Smooth Animation**: Exponential smoothing for natural movement

## ESP32 Integration

### Proportional Pressure Control

The ESP32 proportional control converts normalized values to hardware commands:

```python
# ESP32 format conversion
esp32_format = {
    'control_type': 'proportional',
    'fingers': {
        'thumb': {
            'flexion_pressure': 85,      # 0-100%
            'extension_pressure': 70,    # 0-100%
            'speed': 4,                  # 0-4 discrete levels
            'force': 90                  # 0-100%
        },
        ...
    }
}
```

### Hardware Mapping

| Normalized Value (0-1) | ESP32 Pressure | ESP32 Speed |
|------------------------|----------------|-------------|
| 0.0                    | 0%             | 0 (Stop)    |
| 0.25                   | 25%            | 1 (Slow)    |
| 0.5                    | 50%            | 2 (Medium)  |
| 0.75                   | 75%            | 3 (Fast)    |
| 1.0                    | 100%           | 4 (Fastest) |

## Motor Unit Decomposition

### What is MUD?

Motor unit decomposition extracts individual motor unit firing patterns from raw EMG signals. This provides more detailed information about muscle activation.

### Features Extracted

When `use_motor_unit_decomposition: true`:
- Spike detection using threshold crossing
- Firing rate estimation
- Motor unit activity levels
- Temporal spike patterns

### When to Use MUD

**Use MUD when:**
- You need fine-grained control
- High-density EMG arrays are available (64+ channels)
- Training data includes motor unit labels
- Computational resources are sufficient

**Use Raw EMG when:**
- Standard EMG hardware (< 16 channels)
- Real-time performance is critical
- Simpler feature extraction is preferred
- Training data is limited

## Data Format

### Training Data Format

Your training data should be saved as `.npz` or `.pkl`:

```python
# Example data structure
data = {
    'emg': np.array,  # Shape: (n_samples, n_timepoints, n_channels)
    'targets': np.array  # Shape: (n_samples, n_outputs)
}

# For individual_fingers mode: n_outputs = 10 (5 fingers × 2 directions)
# For whole_hand mode: n_outputs = 2 (flexion + extension)

# Save as NPZ
np.savez('training_data.npz', emg=emg_signals, targets=target_values)

# Or save as PKL
import pickle
with open('training_data.pkl', 'wb') as f:
    pickle.dump(data, f)
```

### Target Value Guidelines

Target values should be normalized to [0, 1]:
- **0.0**: No activation / fully extended
- **0.5**: Moderate activation / mid-range
- **1.0**: Full activation / fully flexed

## Performance Metrics

### Decoder Performance

After training, you'll see:
```
Test MSE: 0.0123
Test MAE: 0.0891
Mean correlation: 0.8765
```

**Good performance:**
- MSE < 0.02
- MAE < 0.10
- Correlation > 0.75

### Real-time Performance

Expected latencies:
- **Feature Extraction**: 5-10 ms
- **MLP Decoding**: 2-5 ms
- **KNN Decoding**: 5-15 ms
- **Total Loop**: 20-50 ms (20-50 Hz)

## Troubleshooting

### Issue: Jittery Control

**Solution:**
- Increase `smooth_window_size` (e.g., 10)
- Increase `smooth_sigma` (e.g., 2.5)
- Increase `min_update_interval` (e.g., 0.1)

### Issue: Delayed Response

**Solution:**
- Decrease `smooth_window_size` (e.g., 3)
- Decrease `dec_win_length` (e.g., 0.1)
- Use KNN instead of MLP for faster inference

### Issue: Weak Activation

**Solution:**
- Decrease `min_activation_threshold` (e.g., 0.05)
- Increase `speedMultiplier` in Unity (e.g., 1.5)
- Increase `pressure_range` in ESP32 config

### Issue: Poor Decoder Accuracy

**Solution:**
- Collect more training data
- Use motor unit decomposition
- Increase model capacity (more hidden units)
- Add data augmentation
- Check feature normalization

## API Reference

### Python API

```python
# Load and use a trained decoder
from models.proportional_decoders import load_proportional_decoder

decoder = load_proportional_decoder('model.pth', decoder_type='mlp')
output = decoder(features_tensor)

# Map to finger control
from models.proportional_decoders import ProportionalControlMapper

mapper = ProportionalControlMapper(control_mode='individual_fingers')
finger_control = mapper.decode_output(output)
unity_format = mapper.to_unity_format(finger_control)
esp32_format = mapper.to_esp32_format(finger_control)

# Motor unit decomposition
from utils.motor_unit_decomposition import get_mud_features

features = get_mud_features(emg_signal, fsample=2048, use_mud=True)
```

### Unity API

```csharp
// Access the proportional controller
ProportionalHandController handController;

// Set control for specific finger
handController.SetFingerControl("thumb", flexion: 0.8f, extension: 0.2f, force: 0.9f);

// Set control for all fingers
handController.SetAllFingersControl(flexion: 0.6f, extension: 0.1f, force: 0.7f);

// Get finger state
float flexion, extension, force;
handController.GetFingerState(0, out flexion, out extension, out force);

// Reset all fingers
handController.ResetFingers();
```

## Examples

### Example 1: Basic Proportional Control

```bash
# Train MLP decoder
python train_proportional_decoder.py --decoder mlp --config config/proportional_train.yaml

# Run proportional control
python emg_proportional_control.py --decoder mlp --control-mode individual_fingers
```

### Example 2: With Motor Unit Decomposition

```bash
# Update config
# Set use_motor_unit_decomposition: true in config/proportional_control.yaml

# Run with MUD
python emg_proportional_control.py --decoder mlp --use-mud 1
```

### Example 3: Full System (Unity + ESP32)

```bash
# 1. Start Unity VR application
# Open md-emg-VR project and click Play

# 2. Run proportional control with ESP32
python emg_proportional_control.py \
  --decoder mlp \
  --control-mode individual_fingers \
  --esp32-enabled 1 \
  --subj 0 \
  --session 0
```

## Citation

If you use this proportional control system in your research, please cite:

```
@article{emg_proportional_control_2024,
  title={Proportional EMG Control for Hand Exoskeletons},
  author={EMG-Exo Team},
  year={2024}
}
```

## Support

For issues or questions:
1. Check this documentation
2. Run `python test_proportional_control.py` to verify installation
3. Review the configuration files
4. Open an issue on GitHub
