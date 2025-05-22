#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main Application for EMG-based Hand Control
Integrates all components: acquisition, processing, decomposition, decoding, and Unity control.
"""

import time
import os
import sys
import argparse
import threading
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import logging

# Import local modules
from emg_selector import get_emg_system, SUPPORTED_EMG_SYSTEMS
from emg_processing import EMGProcessor
from emg_decoder import EMGDecoder
from unity_hand_interface import UnityHandInterface
from ini import logger, EMG_CONFIG, TRIGNO_CONFIG, RECORDING, MODEL_DIR


class EMGExoApplication:
    """Main application class for EMG-controlled exoskeleton/hand."""
    
    def __init__(self, emg_system="sessantaquatro", system_args=None):
        """Initialize the application components.
        
        Args:
            emg_system (str): EMG acquisition system type to use
            system_args (dict): Additional arguments for the EMG system
        """
        # Create component instances
        system_args = system_args or {}
        self.emg = get_emg_system(emg_system, **system_args)
        self.processor = EMGProcessor()
        self.decoder = EMGDecoder()
        self.unity_interface = UnityHandInterface()
        self.emg_system_type = emg_system
        
        # Thread control
        self.is_running = False
        self.main_thread = None
        self.recording_mode = False
        self.decomposition_active = False
        self.current_gesture = None
        
        # Data storage
        self.recorded_data = []
        self.recorded_features = []
        self.recorded_labels = []
        
        logger.info(f"EMG Exo Application initialized with {emg_system} system")
        
    def start(self, recording=False, training=False, decomposition=False):
        """Start the application.
        
        Args:
            recording (bool): If True, record EMG data
            training (bool): If True, run in training mode
            decomposition (bool): If True, perform motor unit decomposition
            
        Returns:
            bool: True if started successfully
        """
        if self.is_running:
            logger.warning("Application is already running")
            return False
            
        self.recording_mode = recording
        self.decomposition_active = decomposition
        
        # Connect to EMG board
        if not self.emg.connect():
            logger.error("Failed to connect to EMG board")
            return False
            
        # Configure the board
        if not self.emg.configure_board():
            logger.error("Failed to configure EMG board")
            self.emg.disconnect()
            return False
            
        # Connect to Unity if not in training mode
        if not training:
            if not self.unity_interface.connect():
                logger.warning("Failed to connect to Unity; continuing without hand control")
            else:
                self.unity_interface.start_streaming()
                
        # Start EMG streaming
        if not self.emg.start_streaming():
            logger.error("Failed to start EMG streaming")
            self.cleanup()
            return False
            
        # Start the main processing loop
        self.is_running = True
        self.main_thread = threading.Thread(target=self._main_loop, args=(training,))
        self.main_thread.daemon = True
        self.main_thread.start()
        
        logger.info(f"Application started (recording: {recording}, training: {training}, decomposition: {decomposition})")
        return True
    
    def stop(self):
        """Stop the application and clean up resources."""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.main_thread:
            self.main_thread.join(timeout=3.0)
            
        self.cleanup()
        logger.info("Application stopped")
        
    def cleanup(self):
        """Release all resources."""
        # Stop EMG streaming
        self.emg.stop_streaming()
        self.emg.disconnect()
        
        # Stop Unity control
        self.unity_interface.stop_streaming()
        self.unity_interface.disconnect()
        
        # Save any remaining recorded data
        if self.recording_mode and self.recorded_data:
            self._save_recorded_data()
            
    def _main_loop(self, training_mode=False):
        """Main processing loop that runs in a separate thread."""
        logger.info("Main processing loop started")
        
        # For training mode, we need gesture labels
        if training_mode:
            self._train_mode_loop()
        else:
            self._normal_mode_loop()
        
        logger.info("Main processing loop ended")
    
    def _normal_mode_loop(self):
        """Normal operation mode: decode EMG and control Unity hand."""
        # Check if we have a trained model
        if not self._load_latest_model():
            logger.warning("No trained model found. Continuing with decomposition only.")
        
        while self.is_running:
            try:
                # Get data from EMG board
                emg_data = self.emg.get_data(blocking=True, timeout=0.5)
                
                if emg_data is None:
                    continue
                    
                # Preprocess EMG data
                processed_data = self.processor.preprocess(emg_data)
                
                # Perform motor unit decomposition if enabled
                if self.decomposition_active:
                    components, mixing, spike_trains = self.processor.decompose_motor_units(processed_data)
                    
                    # Record decomposition results if in recording mode
                    if self.recording_mode and components is not None:
                        self.processor.save_results(
                            raw_emg=emg_data, 
                            processed_emg=processed_data
                        )
                
                # Extract features for decoding
                features = self.processor.extract_features(processed_data)
                
                # Only try to decode if we have a trained model
                if self.decoder.trained:
                    # Prepare feature vector for classification
                    feature_vector = self.decoder.extract_classification_features(features)
                    
                    # Predict gesture
                    gesture, probabilities = self.decoder.predict(feature_vector, return_probabilities=True)
                    
                    # Get confidence from probabilities
                    confidence = 1.0
                    if probabilities and probabilities.get("MLP"):
                        confidence = probabilities["MLP"].get(gesture, 1.0)
                        
                    # Only update if gesture changed or confidence is high
                    if gesture != self.current_gesture or confidence > 0.8:
                        logger.info(f"Detected gesture: {gesture} (confidence: {confidence:.2f})")
                        self.current_gesture = gesture
                        
                        # Send to Unity interface
                        if self.unity_interface.is_connected:
                            self.unity_interface.map_decoded_gesture(gesture, confidence)
                
                # Record data if in recording mode
                if self.recording_mode and processed_data is not None:
                    self.recorded_data.append(emg_data.copy())
                    
                    # Save periodically
                    if len(self.recorded_data) >= 60:  # Save every ~6 seconds (10Hz chunks)
                        self._save_recorded_data()
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(0.1)
    
    def _train_mode_loop(self):
        """Training mode: collect labeled data for each gesture."""
        gestures = self.decoder.gesture_names
        current_gesture_idx = 0
        samples_per_gesture = 50  # Collect 50 samples per gesture
        
        logger.info("Training mode started")
        print("\nTraining Mode: Collecting data for each gesture")
        
        for gesture_idx, gesture in enumerate(gestures):
            # Skip if we've already collected this gesture
            if gesture_idx < current_gesture_idx:
                continue
                
            print(f"\n[{gesture_idx+1}/{len(gestures)}] Perform gesture: {gesture}")
            print("Get ready... (3 seconds)")
            time.sleep(3)
            
            print(f"START PERFORMING: {gesture}")
            
            # Reset sample counter
            samples_collected = 0
            
            while samples_collected < samples_per_gesture and self.is_running:
                try:
                    # Get data
                    emg_data = self.emg.get_data(blocking=True, timeout=0.5)
                    
                    if emg_data is None:
                        continue
                        
                    # Process data
                    processed_data = self.processor.preprocess(emg_data)
                    
                    # Extract features
                    features = self.processor.extract_features(processed_data)
                    feature_vector = self.decoder.extract_classification_features(features)
                    
                    if len(feature_vector) > 0:
                        # Store feature and label
                        self.recorded_features.append(feature_vector)
                        self.recorded_labels.append(gesture)
                        
                        samples_collected += 1
                        sys.stdout.write(f"\rCollecting samples: {samples_collected}/{samples_per_gesture}")
                        sys.stdout.flush()
                        
                except Exception as e:
                    logger.error(f"Error in training loop: {str(e)}")
                    time.sleep(0.1)
            
            print("\nCompleted gesture collection")
            current_gesture_idx += 1
            
        print("\nTraining data collection complete")
        logger.info("Training data collection complete")
        
        # Save the collected training data
        self._save_training_data()
        
        # Train the model
        self._train_model()
    
    def _save_recorded_data(self):
        """Save recorded EMG data to file."""
        if not self.recorded_data:
            return
            
        try:
            # Stack all data
            all_data = np.hstack(self.recorded_data)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.processor.save_results(
                raw_emg=all_data,
                filename=f"emg_recording_{timestamp}.h5"
            )
            
            # Clear the buffer
            self.recorded_data = []
            
        except Exception as e:
            logger.error(f"Error saving recorded data: {str(e)}")
    
    def _save_training_data(self):
        """Save collected training data."""
        if not self.recorded_features or not self.recorded_labels:
            logger.warning("No training data to save")
            return
            
        try:
            # Convert to numpy arrays
            X = np.array(self.recorded_features)
            y = np.array(self.recorded_labels)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{timestamp}.h5"
            path = os.path.join(RECORDING["save_dir"], filename)
            
            # Ensure directory exists
            os.makedirs(RECORDING["save_dir"], exist_ok=True)
            
            # Save to HDF5 file
            import h5py
            with h5py.File(path, 'w') as f:
                f.create_dataset("features", data=X)
                
                # Convert labels to ASCII strings
                labels_ascii = np.array([s.encode('ascii') for s in y])
                f.create_dataset("labels", data=labels_ascii, dtype='S100')
                
            logger.info(f"Training data saved to {path}")
            print(f"Training data saved to {path}")
            
            return path
            
        except Exception as e:
            logger.error(f"Error saving training data: {str(e)}")
            return None
    
    def _train_model(self):
        """Train classifier models using collected data."""
        if not self.recorded_features or not self.recorded_labels:
            logger.warning("No training data available for model training")
            return False
            
        try:
            # Convert to numpy arrays
            X = np.array(self.recorded_features)
            y = np.array(self.recorded_labels)
            
            print(f"\nTraining models on {len(X)} samples with {len(set(y))} gestures...")
            
            # Train the decoder
            results = self.decoder.train(X, y)
            
            # Check results
            success = all(r.get("success", False) for r in results.values())
            
            if success:
                # Save the trained models
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                saved_paths = self.decoder.save_models(f"trained_model_{timestamp}")
                
                print("\nTraining complete:")
                for clf_type, result in results.items():
                    print(f"- {clf_type} accuracy: {result['accuracy']:.3f}")
                    print(f"  Cross-validation: {result['cv_mean']:.3f} ± {result['cv_std']:.3f}")
                
                logger.info("Models trained successfully")
                return True
            else:
                logger.error("Model training failed")
                print("\nError: Model training failed")
                return False
                
        except Exception as e:
            logger.error(f"Error training models: {str(e)}")
            print(f"\nError training models: {str(e)}")
            return False
    
    def _load_latest_model(self):
        """Load the latest trained model."""
        try:
            # Find all model files
            import glob
            model_files = glob.glob(os.path.join(MODEL_DIR, "trained_model_*.pkl"))
            
            if not model_files:
                logger.warning("No trained models found")
                return False
                
            # Sort by modification time (most recent first)
            model_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # Group files by timestamp
            models = {}
            for file in model_files:
                # Extract timestamp from filename
                import re
                match = re.search(r'trained_model_(\d+)_(\w+)\.pkl', os.path.basename(file))
                if match:
                    timestamp = match.group(1)
                    clf_type = match.group(2)
                    
                    if timestamp not in models:
                        models[timestamp] = {}
                        
                    models[timestamp][clf_type] = {
                        "model": file,
                        "scaler": file.replace(".pkl", "_scaler.pkl")
                    }
            
            if not models:
                logger.warning("No valid model files found")
                return False
                
            # Use the most recent models
            latest_timestamp = max(models.keys())
            latest_models = models[latest_timestamp]
            
            # Load the models
            if self.decoder.load_models(latest_models):
                logger.info(f"Loaded models from timestamp {latest_timestamp}")
                return True
            else:
                logger.error("Failed to load models")
                return False
                
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            return False


def main():
    """Main entry point for the application."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="EMG-based Hand Control Application")
    parser.add_argument("--record", action="store_true", help="Record EMG data")
    parser.add_argument("--train", action="store_true", help="Run in training mode")
    parser.add_argument("--decompose", action="store_true", help="Enable motor unit decomposition")
    
    # EMG system selection
    parser.add_argument("--emg-system", choices=SUPPORTED_EMG_SYSTEMS, 
                        default="sessantaquatro", help="EMG acquisition system to use")
    
    # Sessantaquatro arguments
    parser.add_argument("--port", type=str, help="COM port for Sessantaquatro board")
    parser.add_argument("--baudrate", type=int, help="Baudrate for Sessantaquatro board")
    
    # Delsys Trigno arguments
    parser.add_argument("--host", type=str, help="Host IP for Delsys Trigno system")
    parser.add_argument("--command-port", type=int, help="Command port for Trigno system")
    parser.add_argument("--emg-port", type=int, help="EMG data port for Trigno system")
    parser.add_argument("--aux-port", type=int, help="Auxiliary data port for Trigno system")
    
    args = parser.parse_args()
    
    # Extract EMG system arguments
    system_args = {}
    if args.emg_system == "sessantaquatro":
        if args.port:
            system_args["port"] = args.port
            EMG_CONFIG["port"] = args.port  # For compatibility with existing code
        if args.baudrate:
            system_args["baudrate"] = args.baudrate
            EMG_CONFIG["baudrate"] = args.baudrate  # For compatibility with existing code
    elif args.emg_system == "delsys_trigno":
        if args.host:
            system_args["host"] = args.host
            TRIGNO_CONFIG["host"] = args.host
        if args.command_port:
            system_args["command_port"] = args.command_port
            TRIGNO_CONFIG["command_port"] = args.command_port
        if args.emg_port:
            system_args["emg_port"] = args.emg_port
            TRIGNO_CONFIG["emg_port"] = args.emg_port
        if args.aux_port:
            system_args["aux_port"] = args.aux_port
            TRIGNO_CONFIG["aux_port"] = args.aux_port
    
    # Create and start the application with the selected EMG system
    app = EMGExoApplication(emg_system=args.emg_system, system_args=system_args)
    
    try:
        if app.start(recording=args.record, 
                     training=args.train, 
                     decomposition=args.decompose):
            print(f"Application started with {args.emg_system} EMG system.")
            print("Press Ctrl+C to stop...")
            
            # Keep the main thread alive
            while True:
                time.sleep(1)
                
        else:
            print("Failed to start application.")
            return 1
            
    except KeyboardInterrupt:
        print("\nStopping application...")
    finally:
        app.stop()
        print("Application stopped.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())