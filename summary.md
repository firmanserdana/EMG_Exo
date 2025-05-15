# EMG-Based Exoskeleton Control System

A comprehensive system for processing EMG signals from the Sessantaquatro board, decomposing motor units, classifying hand gestures, and controlling hand movements.

## Architecture

The system consists of three main Python modules:

1. **EMG Acquisition** (`emg_acquisition.py`): Interfaces with the Sessantaquatro EMG board to acquire raw EMG signals.
2. **EMG Processing** (`emg_processing.py`): Processes raw signals with filters and extracts meaningful features.
3. **EMG Decoder** (`emg_decoder.py`): Classifies processed EMG signals into hand gestures using machine learning.

## EMG Acquisition Module

Handles communication with the Sessantaquatro EMG board via serial interface.

### Key Components:
- **SessantaquatroEMG** class manages board connectivity and configuration
- Implements asynchronous data acquisition using a producer-consumer pattern
- Supports configuration of sampling rate, channel count, and resolution
- Includes data simulation capabilities for testing without hardware

### Data Flow:
1. Connects to the EMG board on specified COM port
2. Configures board parameters (sampling rate, channels, resolution)
3. Streams data in separate thread to avoid blocking main application
4. Parses binary data packets into numerical EMG values
5. Stores data in thread-safe queue for consumption by processor

## EMG Processing Module

Processes raw EMG signals to extract meaningful features for gesture recognition.

### Key Components:
- **EMGProcessor** class implements signal processing pipeline
- Digital filters (high-pass, low-pass, notch) remove noise and artifacts
- Feature extraction methods compute time and frequency domain features
- Motor unit decomposition techniques separate individual motor unit activity
- Visualization tools for signals, envelopes, and activity detection

### Signal Processing Pipeline:
1. Applies bandpass filtering to remove DC offset and high-frequency noise
2. Removes power line interference with notch filter (50/60Hz)
3. Computes time-domain features (RMS, MAV, ZC, SSC, WL, VAR)
4. Calculates frequency-domain features (mean/median frequency, power)
5. Detects muscle activity with adaptive thresholding

## EMG Decoder Module

Classifies processed EMG features into hand gestures using machine learning.

### Key Components:
- **EMGDecoder** class implements classification logic
- Supports multiple classifiers (k-Nearest Neighbors, Multi-layer Perceptron)
- Training pipeline with cross-validation and performance metrics
- Model persistence for saving and loading trained classifiers
- Interactive training data collection functionality

### Supported Hand Gestures:
- Rest position
- Individual finger control (thumb, index, middle)
- Ring and little finger (combined)
- Various gestures (flexion, extension, pinch, abduction)

### Classification Workflow:
1. Extracts feature vector from EMG processor outputs
2. Normalizes features using StandardScaler
3. Applies trained classifiers to features
4. Returns gesture ID, name, and confidence score

## Configuration System

Centralized configuration in `ini.py` with settings for:
- EMG board parameters (port, baudrate, channels)
- Processing parameters (filter settings, buffer sizes)
- Decoding parameters (classifier selection, feature selection)
- Data recording and storage options

## Usage Examples

### Basic Usage:
```python
from emg_acquisition import SessantaquatroEMG
from emg_processing import EMGProcessor
from emg_decoder import EMGDecoder

# Initialize components
emg = SessantaquatroEMG(port="COM3")
processor = EMGProcessor(channel_count=64, sampling_rate=2048)
decoder = EMGDecoder()

# Connect to EMG board and start streaming
emg.connect()
emg.configure_board()
emg.start_streaming()

# Main processing loop
while True:
    # Get data from acquisition module
    raw_data = emg.get_data(blocking=True, timeout=0.5)
    if raw_data is not None:
        # Process the raw data
        processor.add_samples(raw_data)
        
        # Extract features
        features = processor.extract_features()
        
        # Classify gesture
        gesture_id, gesture_name, confidence = decoder.classify(features)
        
        print(f"Detected gesture: {gesture_name} (confidence: {confidence:.2f})")

Training the System:
# Initialize components
emg = SessantaquatroEMG()
processor = EMGProcessor()
decoder = EMGDecoder()

# Collect training data
X_train, y_train = decoder.collect_training_data(processor)

# Train the classifiers
metrics = decoder.train(X_train, y_train)

# Display training results
for name, results in metrics.items():
    print(f"{name} accuracy: {results['accuracy']:.3f}")
```

### Requirements
- Python 3.8+
- NumPy, SciPy, Matplotlib
- scikit-learn for machine learning
- pyserial for board communication

### Future Development
- Improve motor unit decomposition algorithms
- Add support for more gestures and complex movements
- Implement online learning for adaptation to user changes
- Develop more sophisticated feature extraction methods
- Enhance real-time performance and reduce latency


## Recommendations for Improvement

1. **Complete the Implementation**: Finish any TODOs and placeholder code, particularly in the data parsing functions.

2. **Robust Error Handling**: Add more comprehensive error handling and recovery mechanisms, especially for hardware communication.

3. **Validation and Testing**: Create a comprehensive test suite with both unit tests and integration tests.

4. **Performance Optimization**: Profile and optimize the code for real-time performance, particularly the feature extraction pipeline.

5. **Real Hardware Integration**: Test with actual Sessantaquatro hardware to verify assumptions.

6. **Documentation**: Create detailed hardware setup documentation and usage examples.

7. **Advanced Classification**: Consider implementing more sophisticated ensemble methods that weight classifiers based on performance.

8. **Adaptive Learning**: Implement online learning capabilities to adapt to changes in EMG patterns over time.

9. **Code Cleanup**: Remove debugging code and implement a proper logging strategy.

10. **Configuration Validation**: Add validation for configuration parameters to catch potential issues early.

This codebase shows a solid foundation for EMG-based gesture recognition and control, but would benefit from these improvements to enhance robustness and real-world applicability.## Recommendations for Improvement

1. **Complete the Implementation**: Finish any TODOs and placeholder code, particularly in the data parsing functions.

2. **Robust Error Handling**: Add more comprehensive error handling and recovery mechanisms, especially for hardware communication.

3. **Validation and Testing**: Create a comprehensive test suite with both unit tests and integration tests.

4. **Performance Optimization**: Profile and optimize the code for real-time performance, particularly the feature extraction pipeline.

5. **Real Hardware Integration**: Test with actual Sessantaquatro hardware to verify assumptions.

6. **Documentation**: Create detailed hardware setup documentation and usage examples.

7. **Advanced Classification**: Consider implementing more sophisticated ensemble methods that weight classifiers based on performance.

8. **Adaptive Learning**: Implement online learning capabilities to adapt to changes in EMG patterns over time.

9. **Code Cleanup**: Remove debugging code and implement a proper logging strategy.

10. **Configuration Validation**: Add validation for configuration parameters to catch potential issues early.

This codebase shows a solid foundation for EMG-based gesture recognition and control, but would benefit from these improvements to enhance robustness and real-world applicability.