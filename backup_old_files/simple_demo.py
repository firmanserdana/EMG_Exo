#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple EMG Processing and Gesture Recognition Demo
Without hardware dependencies (no Sessantaquatro+ or Unity required)
"""

import os
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button
import logging
import argparse
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

# Import our custom modules
from data_recorder import EMGDataRecorder
from emg_visualizer import EMGVisualizer

# Setup basic logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('EMGDemo')

class EMGSimulator:
    """Simple EMG signal simulator for demo purposes."""
    
    def __init__(self, channel_count=8, sampling_rate=1000):
        """Initialize the EMG simulator.
        
        Args:
            channel_count (int): Number of EMG channels
            sampling_rate (int): Sampling rate in Hz
        """
        self.channel_count = channel_count
        self.sampling_rate = sampling_rate
        
        # Define different gesture patterns
        self.gesture_patterns = {
            "rest": np.zeros(channel_count),
            "thumb_flexion": np.zeros(channel_count),
            "index_flexion": np.zeros(channel_count),
            "middle_flexion": np.zeros(channel_count),
            "ring_little_flexion": np.zeros(channel_count),
            "thumb_extension": np.zeros(channel_count)
        }
        
        # Set active channels for each gesture
        self.gesture_patterns["thumb_flexion"][0:2] = 1.0
        self.gesture_patterns["index_flexion"][2:4] = 1.0
        self.gesture_patterns["middle_flexion"][4:6] = 1.0
        self.gesture_patterns["ring_little_flexion"][6:8] = 1.0
        self.gesture_patterns["thumb_extension"][[0, 2, 4]] = 0.8
        
        # Current gesture
        self.current_gesture = "rest"
        self.gesture_change_time = 0
        self.gesture_duration = 4.0  # seconds
        
    def set_gesture(self, gesture_name):
        """Set the current gesture to simulate.
        
        Args:
            gesture_name (str): Name of the gesture
        """
        if gesture_name in self.gesture_patterns:
            self.current_gesture = gesture_name
            self.gesture_change_time = time.time()
            logger.info(f"Changed to gesture: {gesture_name}")
    
    def get_data(self, duration=0.1):
        """Generate simulated EMG data.
        
        Args:
            duration (float): Duration of data to generate in seconds
            
        Returns:
            numpy.ndarray: Simulated EMG data with shape (channels, samples)
        """
        samples = int(duration * self.sampling_rate)
        emg_data = np.random.normal(0, 0.05, (self.channel_count, samples))
        
        # Get the base pattern for current gesture
        pattern = self.gesture_patterns[self.current_gesture]
        
        # Scale the noise by the pattern (higher values for active channels)
        for ch in range(self.channel_count):
            if pattern[ch] > 0:
                # Add synthetic EMG burst
                base_freq = 40 + ch * 5  # Hz
                time_points = np.linspace(0, duration, samples)
                
                # Generate basic sine wave
                sine_wave = np.sin(2 * np.pi * base_freq * time_points)
                
                # Add higher frequency components for realism
                sine_wave += 0.3 * np.sin(2 * np.pi * base_freq * 2 * time_points)
                sine_wave += 0.2 * np.sin(2 * np.pi * base_freq * 3 * time_points)
                
                # Apply amplitude modulation for more realistic EMG envelope
                t_rel = time.time() - self.gesture_change_time
                if 0.2 < t_rel < self.gesture_duration - 0.2:
                    # Full activation during middle of gesture
                    amplitude = pattern[ch]
                elif t_rel < 0.2:
                    # Ramp up
                    amplitude = pattern[ch] * (t_rel / 0.2)
                elif t_rel > self.gesture_duration - 0.2:
                    # Ramp down
                    amplitude = pattern[ch] * (1.0 - (t_rel - (self.gesture_duration - 0.2)) / 0.2)
                    if t_rel > self.gesture_duration:
                        # Switch back to rest
                        self.set_gesture("rest")
                else:
                    amplitude = 0
                    
                emg_data[ch] *= (1.0 + 5.0 * amplitude)
                emg_data[ch] += amplitude * sine_wave * 0.5
                
        return emg_data

class EMGProcessor:
    """Simple EMG signal processor for demo purposes."""
    
    def __init__(self, channel_count=8, sampling_rate=1000):
        """Initialize EMG processor.
        
        Args:
            channel_count (int): Number of EMG channels
            sampling_rate (int): Sampling rate in Hz
        """
        self.channel_count = channel_count
        self.sampling_rate = sampling_rate
        
        # Signal buffers for each channel (store 5 seconds of data)
        self.buffer_size = 5 * sampling_rate
        self.raw_buffers = [[] for _ in range(channel_count)]
        
    def add_samples(self, data):
        """Add samples to the signal buffers.
        
        Args:
            data (numpy.ndarray): EMG data with shape (channels, samples)
                                 or (samples, channels)
            
        Returns:
            list: List of processed data for each channel
        """
        # Check shape and transpose if needed
        if isinstance(data, np.ndarray):
            if data.shape[0] == self.channel_count:
                # (channels, samples) format - transpose to (samples, channels)
                data = data.T
                
        # Process each channel
        for ch in range(self.channel_count):
            # Get samples for this channel
            if isinstance(data, np.ndarray):
                ch_samples = data[:, ch]
            else:
                ch_samples = data[ch]
                
            # Add to buffer
            self.raw_buffers[ch].extend(ch_samples)
            
            # Keep buffer size within limit
            if len(self.raw_buffers[ch]) > self.buffer_size:
                self.raw_buffers[ch] = self.raw_buffers[ch][-self.buffer_size:]
        
        return self.raw_buffers
    
    def calculate_envelopes(self, window_size=50):
        """Calculate amplitude envelopes for each channel.
        
        Args:
            window_size (int): Size of window for envelope calculation
            
        Returns:
            list: List of envelopes for each channel
        """
        envelopes = []
        
        for ch in range(self.channel_count):
            data = np.array(self.raw_buffers[ch])
            
            if len(data) < window_size:
                envelopes.append([])
                continue
            
            # Calculate RMS envelope
            envelope = []
            for i in range(0, len(data) - window_size + 1, window_size // 2):
                window_data = data[i:i+window_size]
                envelope.append(np.sqrt(np.mean(window_data**2)))
            
            envelopes.append(envelope)
            
        return envelopes
    
    def extract_features(self):
        """Extract features from the signal buffers.
        
        Returns:
            dict: Dictionary of extracted features
        """
        features = {}
        
        # Use the last second of data for feature extraction
        window_size = self.sampling_rate
        
        for ch in range(self.channel_count):
            # Get the most recent window of data
            data = np.array(self.raw_buffers[ch][-window_size:])
            
            if len(data) < window_size // 2:
                continue
                
            # RMS feature
            if 'rms' not in features:
                features['rms'] = []
            features['rms'].append(np.sqrt(np.mean(data**2)))
            
            # MAV (Mean Absolute Value) feature
            if 'mav' not in features:
                features['mav'] = []
            features['mav'].append(np.mean(np.abs(data)))
            
            # ZC (Zero Crossing) feature
            if 'zc' not in features:
                features['zc'] = []
            # Apply small threshold to avoid noise crossings
            threshold = 0.01 * np.std(data)
            zero_crossings = np.sum(np.abs(np.diff(np.signbit(data))) * (np.abs(np.diff(data)) > threshold))
            features['zc'].append(zero_crossings / len(data))
            
        return features

class GestureRecognizer:
    """Simple gesture recognizer for demo purposes."""
    
    def __init__(self):
        """Initialize gesture recognizer."""
        self.classifier = KNeighborsClassifier(n_neighbors=3, weights='distance')
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Define gesture mapping
        self.gestures = {
            0: "rest",
            1: "thumb_flexion",
            2: "index_flexion",
            3: "middle_flexion",
            4: "ring_little_flexion",
            5: "thumb_extension"
        }
        
        self.gesture_ids = {v: k for k, v in self.gestures.items()}
    
    def train(self, training_data, training_labels):
        """Train the classifier.
        
        Args:
            training_data (numpy.ndarray): Feature vectors for training
            training_labels (numpy.ndarray): Class labels for training
            
        Returns:
            float: Training accuracy
        """
        # Scale the data
        X = self.scaler.fit_transform(training_data)
        y = training_labels
        
        # Train the classifier
        self.classifier.fit(X, y)
        self.is_trained = True
        
        # Calculate training accuracy
        predicted = self.classifier.predict(X)
        accuracy = np.sum(predicted == y) / len(y)
        
        return accuracy
    
    def classify(self, feature_vector):
        """Classify a feature vector.
        
        Args:
            feature_vector (numpy.ndarray): Feature vector to classify
            
        Returns:
            tuple: (gesture_id, gesture_name, confidence)
        """
        if not self.is_trained:
            return None, "unknown", 0.0
            
        try:
            # Make sure input is 2D
            X = feature_vector.reshape(1, -1)
            
            # Scale the features
            X = self.scaler.transform(X)
            
            # Predict and get distances
            gesture_id = self.classifier.predict(X)[0]
            distances, indices = self.classifier.kneighbors(X)
            
            # Calculate confidence from distances
            if np.sum(distances) > 0:
                confidence = 1.0 / (1.0 + np.mean(distances))
            else:
                confidence = 1.0
                
            # Get gesture name
            gesture_name = self.gestures.get(gesture_id, "unknown")
            
            return gesture_id, gesture_name, confidence
            
        except Exception as e:
            logger.error(f"Classification error: {str(e)}")
            return None, "unknown", 0.0

class EMGDemo:
    """Demo application for EMG signal processing and gesture recognition."""
    
    def __init__(self, channel_count=8, auto_train=True, enable_recording=True, enhanced_viz=False):
        """Initialize demo application.
        
        Args:
            channel_count (int): Number of EMG channels
            auto_train (bool): Whether to automatically train the model
            enable_recording (bool): Whether to enable data recording
            enhanced_viz (bool): Whether to use enhanced visualization
        """
        # Create component instances
        self.emg = EMGSimulator(channel_count=channel_count)
        self.processor = EMGProcessor(channel_count=channel_count)
        self.recognizer = GestureRecognizer()
        
        # Thread control
        self.is_running = False
        self.current_gesture = None
        self.gesture_confidence = 0.0
        
        # Auto training
        self.auto_train = auto_train
        
        # Data recording
        self.enable_recording = enable_recording
        self.recorder = None
        if enable_recording:
            self.recorder = EMGDataRecorder(data_dir="emg_recordings")
            
        # Visualization options
        self.enhanced_viz = enhanced_viz
        self.visualizer = None
        if enhanced_viz:
            self.visualizer = EMGVisualizer(channel_count=channel_count)
        
        logger.info("EMG Demo initialized")
        
    def start(self):
        """Start the demo application."""
        # Train the model if auto-training is enabled
        if self.auto_train:
            self._train_model()
        
        # Start recording if enabled
        if self.enable_recording and self.recorder:
            session_info = {
                "description": "EMG simple demo recording",
                "channel_count": self.emg.channel_count,
                "sampling_rate": self.emg.sampling_rate
            }
            success = self.recorder.start_recording(
                sampling_rate=self.emg.sampling_rate,
                session_info=session_info
            )
            if success:
                logger.info("Data recording started")
            else:
                logger.warning("Failed to start data recording")
        
        # Set up the visualization
        if self.enhanced_viz and self.visualizer:
            # Use enhanced visualization
            self.visualizer.setup()
            self.visualizer.start_animation(interval=50)
            self.visualizer.show()
        else:
            # Use standard visualization
            self._setup_visualization()
            plt.show()
        
        logger.info("Demo started")
        
    def stop(self):
        """Stop the demo application and clean up resources."""
        # Stop recording if active
        if self.enable_recording and self.recorder and self.recorder.recording:
            saved_path = self.recorder.stop_recording()
            if saved_path:
                logger.info(f"Saved recording to {saved_path}")
                
        # Close visualizer if using enhanced mode
        if self.enhanced_viz and self.visualizer:
            self.visualizer.close()
            
        logger.info("Demo stopped")
        
    def _setup_visualization(self):
        """Set up the visualization figures."""
        # Create figure and subplots
        self.fig = plt.figure(figsize=(12, 8))
        self.fig.suptitle('EMG Signal Processing and Gesture Recognition Demo', fontsize=16)
        
        # EMG signals subplot
        self.emg_ax = plt.subplot(2, 1, 1)
        self.emg_ax.set_title('EMG Signals')
        self.emg_ax.set_ylabel('Amplitude')
        self.emg_ax.set_xlim(0, 1000)
        self.emg_ax.set_ylim(-1.5, 1.5)
        
        # Create line plots for each channel
        self.emg_lines = []
        for ch in range(self.emg.channel_count):
            line, = self.emg_ax.plot([], [], lw=1, label=f'Channel {ch+1}')
            self.emg_lines.append(line)
        
        self.emg_ax.legend(loc='upper right')
        
        # Gesture control buttons
        self.button_axes = []
        self.buttons = []
        
        # Gesture recognition result
        self.gesture_ax = plt.subplot(2, 1, 2)
        self.gesture_ax.set_title('Recognized Gesture')
        self.gesture_text = self.gesture_ax.text(0.5, 0.5, 'Gesture: None\nConfidence: 0.00', 
                                              ha='center', va='center', fontsize=24)
        self.gesture_ax.set_axis_off()
        
        # Add gesture control buttons
        button_width = 0.15
        button_height = 0.05
        button_spacing = 0.02
        
        gestures = ["thumb_flexion", "index_flexion", "middle_flexion", 
                  "ring_little_flexion", "thumb_extension"]
        
        for i, gesture in enumerate(gestures):
            button_ax = plt.axes([0.1 + i*(button_width + button_spacing), 0.02, 
                                button_width, button_height])
            button = Button(button_ax, gesture.replace('_', ' ').title())
            button.on_clicked(lambda event, g=gesture: self._set_gesture(g))
            
            self.button_axes.append(button_ax)
            self.buttons.append(button)
        
        # Add train model button
        train_button_ax = plt.axes([0.8, 0.02, 0.15, 0.05])
        train_button = Button(train_button_ax, 'Train Model')
        train_button.on_clicked(lambda event: self._train_model())
        
        self.button_axes.append(train_button_ax)
        self.buttons.append(train_button)
        
        # Add recording control buttons if recording is enabled
        if self.enable_recording and self.recorder:
            record_button_ax = plt.axes([0.6, 0.02, 0.15, 0.05])
            record_button = Button(record_button_ax, 'Start Recording')
            record_button.on_clicked(lambda event: self._toggle_recording())
            
            export_button_ax = plt.axes([0.4, 0.02, 0.15, 0.05])
            export_button = Button(export_button_ax, 'Export Data')
            export_button.on_clicked(lambda event: self._export_data())
            
            self.button_axes.extend([record_button_ax, export_button_ax])
            self.buttons.extend([record_button, export_button])
        
        # Animation
        self.anim = animation.FuncAnimation(self.fig, self._update_plot, 
                                          interval=50, blit=True)
    
    def _update_plot(self, frame):
        """Update the visualization with new data."""
        # Generate new EMG data
        emg_data = self.emg.get_data(duration=0.05)
        
        # Process the data
        self.processor.add_samples(emg_data)
        
        # If using the enhanced visualizer, update it
        if self.enhanced_viz and self.visualizer:
            # Add data to the visualizer
            self.visualizer.add_data(emg_data)
            
            # We'll skip the rest of this method since the visualizer handles updates
            return []
        
        # Standard visualization update
        updated_artists = []
        
        # Update EMG signal plots
        x_data = np.arange(1000)
        for ch in range(self.emg.channel_count):
            data = self.processor.raw_buffers[ch][-1000:]
            if len(data) > 0:
                # Pad with zeros if needed
                if len(data) < 1000:
                    padded_data = np.zeros(1000)
                    padded_data[-len(data):] = data
                    data = padded_data
                
                self.emg_lines[ch].set_data(x_data, data)
            updated_artists.append(self.emg_lines[ch])
        
        # Extract features and classify gesture
        features = self.processor.extract_features()
        if features and self.recognizer.is_trained:
            # Create feature vector
            feature_vector = np.array([])
            for feature_name in ['rms', 'mav', 'zc']:
                if feature_name in features:
                    feature_vector = np.append(feature_vector, features[feature_name])
            
            # Only classify if we have features
            if len(feature_vector) > 0:
                gesture_id, gesture_name, confidence = self.recognizer.classify(feature_vector)
                
                if gesture_name != "unknown" and confidence > 0.3:
                    self.current_gesture = gesture_name
                    self.gesture_confidence = confidence
                    
                    # Update gesture text
                    self.gesture_text.set_text(
                        f"Gesture: {gesture_name.replace('_', ' ').title()}\n"
                        f"Confidence: {confidence:.2f}"
                    )
                    
                    # If recording is enabled, record this data with the detected gesture
                    if self.enable_recording and self.recorder and self.recorder.recording:
                        self.recorder.add_data(emg_data, features, gesture_name)
        
        updated_artists.append(self.gesture_text)
        return updated_artists
    
    def _set_gesture(self, gesture_name):
        """Set the current gesture for simulation."""
        self.emg.set_gesture(gesture_name)
    
    def _toggle_recording(self):
        """Toggle recording on/off."""
        if not self.enable_recording or not self.recorder:
            logger.error("Recording is not enabled")
            return
            
        if self.recorder.recording:
            # Stop recording
            saved_path = self.recorder.stop_recording()
            if saved_path:
                logger.info(f"Stopped recording. Data saved to {saved_path}")
                
                # Update gesture text to show recording stopped
                if not self.enhanced_viz:
                    self.gesture_text.set_text("Recording stopped\nData saved")
                else:
                    self.visualizer.set_status_message("Recording stopped. Data saved.", duration=5.0)
        else:
            # Start recording
            session_info = {
                "description": "EMG gesture recording",
                "channel_count": self.emg.channel_count,
                "sampling_rate": self.emg.sampling_rate,
                "current_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            success = self.recorder.start_recording(
                sampling_rate=self.emg.sampling_rate,
                session_info=session_info
            )
            
            if success:
                logger.info("Started recording")
                # Update gesture text to show recording started
                if not self.enhanced_viz:
                    self.gesture_text.set_text("Recording started")
                else:
                    self.visualizer.set_status_message("Recording started", duration=3.0)
            else:
                logger.error("Failed to start recording")
    
    def _export_data(self):
        """Export recorded data to MATLAB format."""
        if not self.enable_recording or not self.recorder:
            logger.error("Recording is not enabled")
            return
            
        if self.recorder.recording:
            logger.warning("Please stop recording before exporting data")
            message = "Stop recording first"
        else:
            exported_path = self.recorder.export_to_matlab()
            if exported_path:
                logger.info(f"Data exported to {exported_path}")
                message = f"Data exported"
            else:
                logger.error("Failed to export data")
                message = "Export failed"
                
        # Show message
        if not self.enhanced_viz:
            self.gesture_text.set_text(message)
        else:
            self.visualizer.set_status_message(message, duration=3.0)
    
    def _train_model(self):
        """Train the gesture recognition model with simulated data."""
        logger.info("Training gesture recognition model...")
        
        # Get all available gestures
        gestures = self.recognizer.gestures
        
        # Generate training data for each gesture
        X_train = []
        y_train = []
        
        # Number of samples per gesture
        n_samples = 20
        
        for gesture_id, gesture_name in gestures.items():
            logger.info(f"Generating training data for gesture: {gesture_name}")
            
            # Set the gesture for simulation
            self.emg.set_gesture(gesture_name)
            
            # Generate samples
            for i in range(n_samples):
                # Generate data
                data = self.emg.get_data(duration=0.5)
                
                # Process data
                self.processor.add_samples(data)
                
                # Extract features
                features = self.processor.extract_features()
                
                # Skip if no features
                if not features:
                    continue
                
                # Create feature vector
                feature_vector = np.array([])
                for feature_name in ['rms', 'mav', 'zc']:
                    if feature_name in features:
                        feature_vector = np.append(feature_vector, features[feature_name])
                
                # Add to training data
                if len(feature_vector) > 0:
                    X_train.append(feature_vector)
                    y_train.append(gesture_id)
                
                # Small delay
                time.sleep(0.01)
        
        # Reset to rest gesture
        self.emg.set_gesture("rest")
        
        # Train the model
        if X_train and y_train:
            X_train = np.array(X_train)
            y_train = np.array(y_train)
            
            logger.info(f"Training with {len(X_train)} samples for {len(set(y_train))} gestures")
            
            accuracy = self.recognizer.train(X_train, y_train)
            logger.info(f"Model trained with accuracy: {accuracy:.2f}")
            
            # Update gesture text
            self.gesture_text.set_text(f"Model Trained\nAccuracy: {accuracy:.2f}")
            
        else:
            logger.error("Failed to generate training data")

def main():
    """Main entry point for the demo application."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Simple EMG Gesture Recognition Demo")
    parser.add_argument("--channels", type=int, default=8, 
                      help="Number of EMG channels to simulate (default: 8)")
    parser.add_argument("--no-train", action="store_true",
                      help="Disable automatic model training")
    parser.add_argument("--no-record", action="store_true",
                      help="Disable data recording")
    parser.add_argument("--enhanced-viz", action="store_true",
                      help="Use enhanced visualization")
    args = parser.parse_args()
    
    # Create demo application
    demo = EMGDemo(
        channel_count=args.channels, 
        auto_train=not args.no_train,
        enable_recording=not args.no_record,
        enhanced_viz=args.enhanced_viz
    )
    
    try:
        # Start the demo
        demo.start()
    except KeyboardInterrupt:
        print("\nExiting demo...")
    finally:
        # Ensure resources are cleaned up
        demo.stop()
    
    return 0

if __name__ == "__main__":
    main()
