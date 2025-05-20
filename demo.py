#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Processing and Gesture Recognition Demo
Without hardware dependencies (no Sessantaquatro+ or Unity required)
"""

import time
import os
import sys
import argparse
import threading
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.animation as animation
from matplotlib.widgets import Button
import logging

# Import local modules
from emg_acquisition import SessantaquatroEMG
from emg_processing import EMGProcessor
from emg_decoder import EMGDecoder
from ini import logger, EMG_CONFIG, DECODING, MODEL_DIR

# Ensure required directories exist
os.makedirs(MODEL_DIR, exist_ok=True)

class EMGDemo:
    """Demo application for EMG signal processing and gesture recognition."""
    
    def __init__(self, channel_count=8, simulate_training=True):
        """Initialize demo components.
        
        Args:
            channel_count (int): Number of EMG channels to simulate
            simulate_training (bool): Whether to use simulated training data
        """
        # Override config for simulated operation
        EMG_CONFIG["channels"] = channel_count
        EMG_CONFIG["sampling_rate"] = 1000  # Simplified for demo
        
        # Create component instances
        self.emg = SessantaquatroEMG()
        self.processor = EMGProcessor(channel_count=channel_count, 
                                     sampling_rate=EMG_CONFIG["sampling_rate"])
        self.decoder = EMGDecoder()
        
        # Thread control
        self.is_running = False
        self.main_thread = None
        self.animation = None
        
        # Data for visualization
        self.raw_data = None
        self.processed_data = None
        self.envelopes = None
        self.current_gesture = None
        self.gesture_confidence = 0.0
        self.simulate_training = simulate_training
        
        # Visualization
        self.fig = None
        self.emg_axes = None
        self.gesture_ax = None
        self.time_points = np.linspace(0, 1, EMG_CONFIG["sampling_rate"])
        
        logger.info("EMG Demo initialized")
        
    def start(self):
        """Start the demo application."""
        if self.is_running:
            logger.warning("Demo is already running")
            return False
        
        # Start the main processing loop
        self.is_running = True
        self.main_thread = threading.Thread(target=self._main_loop)
        self.main_thread.daemon = True
        self.main_thread.start()
        
        # Set up the visualization
        self._setup_visualization()
        
        logger.info("Demo started")
        return True
    
    def stop(self):
        """Stop the demo and clean up resources."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.main_thread:
            self.main_thread.join(timeout=3.0)
            
        logger.info("Demo stopped")
    
    def _setup_visualization(self):
        """Set up the visualization figures and plots."""
        self.fig, (self.emg_axes, self.gesture_ax) = plt.subplots(2, 1, 
                                                                 figsize=(10, 8),
                                                                 gridspec_kw={'height_ratios': [3, 1]})
        self.fig.canvas.manager.set_window_title('EMG Signal Processing and Gesture Recognition Demo')
        
        # EMG signals plot
        self.emg_lines = []
        for i in range(EMG_CONFIG["channels"]):
            line, = self.emg_axes.plot([], [], lw=1, label=f'Channel {i+1}')
            self.emg_lines.append(line)
        
        self.emg_axes.set_xlim(0, 1)
        self.emg_axes.set_ylim(-200, 200)
        self.emg_axes.set_title('EMG Signals')
        self.emg_axes.set_xlabel('Time (s)')
        self.emg_axes.set_ylabel('Amplitude (μV)')
        self.emg_axes.grid(True)
        self.emg_axes.legend(loc='upper right')
        
        # Gesture recognition plot
        self.gesture_text = self.gesture_ax.text(0.5, 0.5, 'Gesture: None', 
                                               ha='center', va='center', 
                                               fontsize=20)
        self.gesture_ax.set_title('Recognized Gesture')
        self.gesture_ax.set_axis_off()
        
        # Add train model button
        self.train_button_ax = plt.axes([0.8, 0.01, 0.15, 0.05])
        self.train_button = Button(self.train_button_ax, 'Train Model')
        self.train_button.on_clicked(self._train_model_callback)
        
        # Animation
        self.animation = animation.FuncAnimation(self.fig, self._update_plot, 
                                                interval=100, blit=True)
        plt.tight_layout()
        plt.show()
        
    def _update_plot(self, frame):
        """Update the visualization plots with new data."""
        updated_artists = []
        
        if self.raw_data is not None:
            for i, line in enumerate(self.emg_lines):
                if i < len(self.raw_data):
                    # Only show the most recent second of data
                    samples_to_show = min(len(self.raw_data[i]), EMG_CONFIG["sampling_rate"])
                    data_to_plot = self.raw_data[i][-samples_to_show:]
                    time_to_plot = self.time_points[:samples_to_show]
                    
                    line.set_data(time_to_plot, data_to_plot)
                updated_artists.append(line)
        
        # Update gesture text
        if self.current_gesture:
            self.gesture_text.set_text(f'Gesture: {self.current_gesture}\nConfidence: {self.gesture_confidence:.2f}')
        else:
            self.gesture_text.set_text('Gesture: None')
        updated_artists.append(self.gesture_text)
        
        return updated_artists
        
    def _main_loop(self):
        """Main processing loop that runs in a separate thread."""
        logger.info("Main processing loop started")
        
        # Train the model if needed and simulated training is enabled
        if self.simulate_training and not self.decoder.is_trained:
            self._train_model()
        
        while self.is_running:
            try:
                # Generate simulated EMG data
                emg_data = self.emg.simulate_data(duration=0.1)  # 100ms of data
                
                if emg_data is None:
                    continue
                
                # Store raw data for visualization
                if self.raw_data is None:
                    self.raw_data = [[] for _ in range(EMG_CONFIG["channels"])]
                
                for ch in range(EMG_CONFIG["channels"]):
                    self.raw_data[ch].extend(emg_data[ch])
                    # Keep only the recent data (last 5 seconds)
                    max_samples = 5 * EMG_CONFIG["sampling_rate"]
                    if len(self.raw_data[ch]) > max_samples:
                        self.raw_data[ch] = self.raw_data[ch][-max_samples:]
                
                # Process EMG data
                processed_data = self.processor.add_samples(emg_data.T)
                
                # Extract features
                features = self.processor.extract_features()
                
                # If decoder is trained, classify the gesture
                if self.decoder.is_trained and features:
                    # Extract a feature vector for classification
                    feature_vector = self._extract_feature_vector(features)
                    
                    # Classify the gesture
                    gesture_id, gesture_name, confidence = self.decoder.classify(feature_vector)
                    
                    if gesture_name != "unknown" and confidence > 0.3:
                        self.current_gesture = gesture_name
                        self.gesture_confidence = confidence
                        logger.info(f"Recognized gesture: {gesture_name} (confidence: {confidence:.2f})")
                
                # Calculate signal envelopes for visualization
                self.envelopes = self.processor.calculate_envelopes()
                
                # Sleep briefly to avoid high CPU usage
                time.sleep(0.02)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(0.1)
        
        logger.info("Main processing loop ended")
    
    def _train_model(self):
        """Train the gesture recognition model with simulated data."""
        try:
            logger.info("Training gesture recognition model with simulated data...")
            
            # Number of samples per gesture for training
            n_samples_per_gesture = 20
            n_gestures = len(self.decoder.gestures)
            
            # Create simulated feature vectors for training
            # In a real application, these would be calculated from actual EMG signals
            # For this demo, we'll create synthetic feature vectors
            
            # Determine feature vector size by extracting from a sample
            sample_data = self.emg.simulate_data(duration=0.5)
            self.processor.add_samples(sample_data.T)
            features = self.processor.extract_features()
            
            # Extract a feature vector to determine its size
            if not features:
                logger.error("Failed to extract features for training")
                return False
                
            feature_vector = self._extract_feature_vector(features)
            feature_size = len(feature_vector)
            
            # Create synthetic training data
            X_train = []
            y_train = []
            
            for gesture_id in self.decoder.gestures.keys():
                # Create distinct patterns for each gesture
                base_vector = np.zeros(feature_size)
                
                # Set some features to be strong indicators of this gesture
                indicator_indices = np.random.choice(feature_size, 3, replace=False)
                for idx in indicator_indices:
                    base_vector[idx] = 0.5 + 0.5 * gesture_id / n_gestures
                
                # Generate samples with variation
                for _ in range(n_samples_per_gesture):
                    # Add noise and variation to the base vector
                    sample = base_vector + np.random.normal(0, 0.1, feature_size)
                    X_train.append(sample)
                    y_train.append(gesture_id)
            
            # Convert to numpy arrays
            X_train = np.array(X_train)
            y_train = np.array(y_train)
            
            # Train the classifier
            metrics = self.decoder.train(X_train, y_train)
            
            if metrics:
                logger.info("Model trained successfully")
                for clf_name, results in metrics.items():
                    logger.info(f"- {clf_name}: Accuracy = {results['accuracy']:.3f}")
                return True
            else:
                logger.error("Failed to train model")
                return False
                
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return False
    
    def _extract_feature_vector(self, features):
        """Extract a feature vector from the feature dictionary.
        
        This is a simplified version of the decoder's feature extraction.
        
        Args:
            features (dict): Dictionary of features
            
        Returns:
            numpy.ndarray: Feature vector for classification
        """
        # Extract features and flatten into a vector
        feature_vector = []
        
        # Process each feature type
        for feature_name in features.keys():
            feature_values = features[feature_name]
            feature_vector.extend(feature_values)
            
        return np.array(feature_vector)
    
    def _train_model_callback(self, event):
        """Callback for the train model button."""
        threading.Thread(target=self._train_model).start()


def main():
    """Main entry point for the demo application."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="EMG Processing and Gesture Recognition Demo")
    parser.add_argument("--channels", type=int, default=8, 
                      help="Number of EMG channels to simulate (default: 8)")
    parser.add_argument("--disable-training", action="store_true",
                      help="Disable automatic model training")
    args = parser.parse_args()
    
    # Create demo application
    demo = EMGDemo(channel_count=args.channels, 
                  simulate_training=not args.disable_training)
    
    try:
        # Start the demo
        if demo.start():
            print("Demo started. Close the plot window to exit.")
        else:
            print("Failed to start demo.")
            return 1
            
    except KeyboardInterrupt:
        print("\nStopping demo...")
    finally:
        demo.stop()
        print("Demo stopped.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
