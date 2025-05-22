# EMG Processing and Classification System API

This document provides an overview of the API for the EMG Processing and Classification System.

## EMGProcessor Class

The `EMGProcessor` class handles signal processing and feature extraction for EMG signals.

### Key Methods

#### Initialization

```python
processor = EMGProcessor(channel_count=8, sampling_rate=2000)
```

- `channel_count`: Number of EMG channels to process
- `sampling_rate`: Sampling rate in Hz for the EMG signals

#### Data Processing

```python
processed_data = processor.add_samples(emg_data)
```

Adds new EMG data to the processing pipeline. Returns processed samples.
- `emg_data`: 2D array with shape (samples, channels) or (channels, samples)

```python
processed_data = processor.preprocess(emg_data)
```

Preprocess raw EMG data (applies filtering and returns processed data).
- `emg_data`: Raw EMG data with shape (samples, channels) or (channels, samples)

#### Feature Extraction

```python
features = processor.extract_features(window=None)
```

Extract features from the processed EMG data:
- `window`: Optional (start, end) tuple to specify window in samples

Returns a dictionary with features including:
- 'rms': Root Mean Square value for each channel
- 'mav': Mean Absolute Value for each channel
- 'zc': Zero Crossing rate for each channel
- 'ssc': Slope Sign Changes for each channel
- 'wl': Waveform Length for each channel
- 'var': Variance for each channel
- 'freq_mean', 'freq_median', 'freq_power': Frequency domain features

#### Signal Analysis

```python
envelopes = processor.calculate_envelopes(window_size=None, method='rms')
```

Calculate signal envelopes for each channel:
- `window_size`: Window size for envelope calculation (default: 100ms window)
- `method`: Envelope detection method ('rms', 'mav', or 'hilbert')

```python
activities = processor.detect_muscle_activity(threshold_factor=3.0, min_duration=0.2)
```

Detect muscle activity periods in the signal:
- `threshold_factor`: Multiplication factor for the standard deviation threshold
- `min_duration`: Minimum activity duration in seconds

#### Visualization

```python
fig = processor.plot_signals(raw=True, processed=True, envelopes=True, show=True)
```

Plot the EMG signals for visualization:
- `raw`: Whether to plot raw signals
- `processed`: Whether to plot processed signals
- `envelopes`: Whether to plot signal envelopes
- `show`: Whether to show the plot immediately

## EMGDecoder Class

The `EMGDecoder` class handles classification of EMG signals into hand gestures.

### Key Methods

#### Initialization

```python
decoder = EMGDecoder()
```

#### Training

```python
metrics = decoder.train(training_data, training_labels)
```

Train the classifiers on labeled EMG data:
- `training_data`: Feature vectors for training (2D array)
- `training_labels`: Class labels for training (1D array)

Returns a dictionary with training performance metrics.

#### Classification

```python
gesture_id, gesture_name, confidence = decoder.classify(features, method="best")
```

Classify EMG features into a gesture:
- `features`: Feature vector or dictionary of features
- `method`: Classification method to use ("best", "ensemble", or classifier name)

Returns:
- `gesture_id`: Numeric ID of recognized gesture
- `gesture_name`: Name of recognized gesture
- `confidence`: Classification confidence score (0-1)

#### Model Management

```python
success = decoder.save_models(model_dir=None)
```

Save trained models to disk.
- `model_dir`: Directory to save models (default: from configuration)

```python
success = decoder.load_models(models_info=None)
```

Load trained models from disk.
- `models_info`: Dictionary with model information, or None to load latest

## SessantaquatroEMG Class

The `SessantaquatroEMG` class handles communication with the Sessantaquatro EMG board.

### Key Methods

#### Initialization

```python
emg = SessantaquatroEMG(port=None, baudrate=None)
```

#### Connection

```python
success = emg.connect()
```

Connect to the EMG board.

```python
emg.disconnect()
```

Disconnect from the EMG board.

#### Configuration

```python
success = emg.configure_board()
```

Configure the EMG board settings.

#### Data Acquisition

```python
success = emg.start_streaming()
```

Start streaming EMG data from the board.

```python
emg.stop_streaming()
```

Stop streaming EMG data from the board.

```python
data = emg.get_data(blocking=False, timeout=None)
```

Get EMG data from the board:
- `blocking`: Whether to block until data is available
- `timeout`: Timeout in seconds when blocking

#### Simulation

```python
data = emg.simulate_data(duration=1.0, gesture=None)
```

Generate simulated EMG data for testing:
- `duration`: Duration of data in seconds
- `gesture`: Specific gesture to simulate

## Using the Demo Application

The `EMGDemo` class provides a visualization and demonstration of the system:

```python
demo = EMGDemo(channel_count=8, simulate_training=True)
demo.start()
```

This will:
1. Initialize the system components
2. Train a gesture recognition model with simulated data (if enabled)
3. Display real-time visualization of EMG signals and recognized gestures
4. Provide buttons to simulate different gestures and train the model
