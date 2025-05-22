#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main application for the EMG-controlled exoskeleton system.

This module provides the main entry point for the EMG-controlled exoskeleton
system, integrating EMG acquisition, processing, decoding, and control.
"""

import sys
import time
import logging
import argparse
from typing import Dict, Any, List, Optional

# Import core modules
from emg_exo.core.acquisition import create_emg_system
from emg_exo.core.processing import EMGProcessor
from emg_exo.core.decoder import EMGDecoder
from emg_exo.core.interface import UnityHandInterface
from emg_exo.config.config import configure_logging


class EMGExoApp:
    """Main application class for the EMG-controlled exoskeleton."""
    
    def __init__(self, emg_system_type: str = "sessantaquatro"):
        """Initialize the application.
        
        Args:
            emg_system_type: Type of EMG system to use ('sessantaquatro' or 'trigno')
        """
        # Configure logging
        self.logger = configure_logging()
        self.logger.info("Initializing EMG Exo Application")
        
        # Initialize core components
        self.emg = create_emg_system(emg_system_type)
        self.processor = EMGProcessor()
        self.decoder = EMGDecoder()
        self.unity_interface = UnityHandInterface()
        
        # Application state
        self.running = False
        
        self.logger.info(f"EMG Exo Application initialized with {emg_system_type} EMG system")
    
    def connect(self) -> bool:
        """Connect to hardware and interfaces.
        
        Returns:
            True if connections established successfully
        """
        self.logger.info("Connecting to hardware and interfaces...")
        
        # Connect to EMG system
        if not self.emg.connect():
            self.logger.error("Failed to connect to EMG system")
            return False
            
        # Connect to Unity interface
        if not self.unity_interface.connect():
            self.logger.warning("Failed to connect to Unity interface")
        else:
            self.logger.info("Connected to Unity interface")
            self.unity_interface.start_streaming()
            
        return True
    
    def disconnect(self) -> None:
        """Disconnect from hardware and interfaces."""
        self.logger.info("Disconnecting from hardware and interfaces...")
        
        # Stop the EMG system
        try:
            self.emg.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting from EMG system: {e}")
            
        # Stop the Unity interface
        try:
            self.unity_interface.stop_streaming()
            self.unity_interface.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting from Unity: {e}")
    
    def run(self) -> None:
        """Run the main application loop."""
        if not self.connect():
            self.logger.error("Failed to connect to required systems. Exiting.")
            return
            
        self.running = True
        self.logger.info("Starting main application loop")
        
        try:
            while self.running:
                # Acquire EMG data
                raw_data = self.emg.read()
                
                # Process EMG data
                processed = self.processor.preprocess(raw_data)
                features = self.processor.extract_features(processed)
                
                # Send raw EMG data to Unity if connected
                if self.unity_interface.is_connected():
                    self.unity_interface.send_emg_data(raw_data)
                
                # Decode gestures
                gesture_id, gesture_name, confidence = self.decoder.classify(features)
                
                # Log decoded gesture
                if gesture_id is not None and confidence > 0.5:
                    self.logger.info(f"Decoded: {gesture_name} (ID: {gesture_id}, Confidence: {confidence:.2f})")
                    
                    # Send to Unity interface
                    if self.unity_interface.is_connected():
                        self.unity_interface.send_gesture_info(gesture_id, gesture_name, confidence)
                
                # Sleep to maintain loop frequency
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
        finally:
            self.running = False
            self.disconnect()
            self.logger.info("Application shutdown complete")
    
    def train_decoder(self, acquisition_time: float = 2.0, rest_time: float = 1.0) -> None:
        """Train the gesture decoder interactively.
        
        Args:
            acquisition_time: Time to record each gesture in seconds
            rest_time: Rest time between gesture recordings
        """
        if not self.connect():
            self.logger.error("Failed to connect to required systems. Exiting.")
            return
            
        try:
            print("\nTraining data collection")
            print("======================")
            print(f"We'll collect {acquisition_time:.1f}s of data for each gesture.")
            print("Follow the prompts to perform each gesture when requested.")
            
            # Storage for collected data
            all_features = []
            all_labels = []
            
            # Collect data for each gesture
            for gesture_id, gesture_name in self.decoder.gestures.items():
                print(f"\nPrepare to perform: {gesture_name} (ID: {gesture_id})")
                print(f"Get ready... (3 seconds)")
                time.sleep(3)
                
                print(f"PERFORM THE GESTURE NOW! Recording for {acquisition_time:.1f} seconds...")
                
                # For each recording, collect multiple windows of data
                num_windows = int(acquisition_time * 10)  # 10 windows per second
                for i in range(num_windows):
                    # Get EMG data
                    raw_data = self.emg.read()
                    
                    # Process the data
                    processed = self.processor.preprocess(raw_data)
                    
                    # Extract features
                    features = self.processor.extract_features(processed)
                    feature_vector = self.decoder.extract_classification_features(features)
                    
                    # Save feature vector and label
                    all_features.append(feature_vector)
                    all_labels.append(gesture_id)
                    
                    # Brief pause between windows
                    time.sleep(0.1)
                
                print("Done recording this gesture.")
                print(f"Rest for {rest_time:.1f} seconds...")
                time.sleep(rest_time)
            
            print("\nTraining data collection complete!")
            print(f"Collected {len(all_features)} samples across {len(self.decoder.gestures)} gestures.")
            
            # Train the decoder
            print("\nTraining the classifier...")
            import numpy as np
            metrics = self.decoder.train(np.array(all_features), np.array(all_labels))
            
            print("\nTraining complete!")
            for clf_name, results in metrics.items():
                print(f"- {clf_name}: Accuracy = {results['accuracy']:.3f}, " +
                     f"CV = {results['cv_accuracy_mean']:.3f} ± {results['cv_accuracy_std']:.3f}")
            
        finally:
            # Clean up
            self.disconnect()


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="EMG-controlled exoskeleton application")
    parser.add_argument("--emg", choices=["sessantaquatro", "trigno"], default="sessantaquatro",
                       help="Type of EMG system to use")
    parser.add_argument("--train", action="store_true", help="Train the gesture classifier")
    
    args = parser.parse_args()
    
    # Create the application
    app = EMGExoApp(args.emg)
    
    if args.train:
        app.train_decoder()
    else:
        app.run()


if __name__ == "__main__":
    main()
