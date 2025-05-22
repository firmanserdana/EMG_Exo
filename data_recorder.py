#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
data_recorder.py - Module for recording and exporting EMG data
"""

import os
import numpy as np
import pandas as pd
import logging
import time
import csv
import json
from datetime import datetime
from utilities import ensure_directory_exists, generate_timestamp

logger = logging.getLogger('EMGRecorder')

class EMGDataRecorder:
    """Class for recording EMG data and related features for later analysis."""
    
    def __init__(self, data_dir="recorded_data"):
        """Initialize the EMG data recorder.
        
        Args:
            data_dir (str): Directory for saving recorded data
        """
        self.data_dir = data_dir
        self.session_dir = None
        self.recording = False
        self.raw_data = []
        self.features = []
        self.gestures = []
        self.timestamps = []
        self.sampling_rate = 0
        self.start_time = 0
        self.session_info = {}
        
        # Ensure the data directory exists
        ensure_directory_exists(self.data_dir)
        
    def start_recording(self, sampling_rate=1000, session_info=None):
        """Start a new recording session.
        
        Args:
            sampling_rate (int): EMG sampling rate in Hz
            session_info (dict): Optional metadata about the session
            
        Returns:
            bool: True if recording started successfully
        """
        if self.recording:
            logger.warning("Recording is already in progress")
            return False
        
        try:
            # Create a session directory with timestamp
            timestamp = generate_timestamp()
            self.session_dir = os.path.join(self.data_dir, f"session_{timestamp}")
            ensure_directory_exists(self.session_dir)
            
            # Initialize recording variables
            self.raw_data = []
            self.features = []
            self.gestures = []
            self.timestamps = []
            self.sampling_rate = sampling_rate
            self.start_time = time.time()
            
            # Store session info
            self.session_info = {
                "timestamp": timestamp,
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sampling_rate": sampling_rate
            }
            
            # Add custom session info if provided
            if session_info and isinstance(session_info, dict):
                self.session_info.update(session_info)
            
            # Save session info
            with open(os.path.join(self.session_dir, "session_info.json"), 'w') as f:
                json.dump(self.session_info, f, indent=2)
            
            self.recording = True
            logger.info(f"Started recording to {self.session_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}")
            return False
    
    def add_data(self, raw_data, features=None, gesture=None):
        """Add data to the current recording session.
        
        Args:
            raw_data (numpy.ndarray): Raw EMG data (channels x samples) or (samples x channels)
            features (dict, optional): Extracted features
            gesture (str, optional): Current gesture label
            
        Returns:
            bool: True if data was added successfully
        """
        if not self.recording:
            logger.warning("No active recording session")
            return False
            
        try:
            # Convert data format if needed
            if isinstance(raw_data, np.ndarray):
                # Store raw data
                self.raw_data.append(raw_data.copy())
                
            # Store timestamp
            self.timestamps.append(time.time() - self.start_time)
            
            # Store features if provided
            if features is not None:
                self.features.append(features)
                
            # Store gesture if provided
            if gesture is not None:
                self.gestures.append(gesture)
            else:
                self.gestures.append("unknown")
                
            return True
            
        except Exception as e:
            logger.error(f"Error adding data: {str(e)}")
            return False
    
    def stop_recording(self):
        """Stop the current recording session and save the data.
        
        Returns:
            str: Path to the saved data directory or None if error
        """
        if not self.recording:
            logger.warning("No active recording session")
            return None
            
        try:
            # Update session info with end time
            self.session_info["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.session_info["duration_seconds"] = time.time() - self.start_time
            self.session_info["samples_recorded"] = len(self.timestamps)
            
            # Save updated session info
            with open(os.path.join(self.session_dir, "session_info.json"), 'w') as f:
                json.dump(self.session_info, f, indent=2)
            
            # Save raw data
            if self.raw_data:
                self._save_raw_data()
            
            # Save features
            if self.features:
                self._save_features()
            
            # Save gestures
            self._save_gestures()
            
            logger.info(f"Saved recording to {self.session_dir}")
            self.recording = False
            return self.session_dir
            
        except Exception as e:
            logger.error(f"Error stopping recording: {str(e)}")
            self.recording = False
            return None
    
    def _save_raw_data(self):
        """Save raw EMG data to CSV and NPZ files."""
        # Save as compressed numpy format
        np_path = os.path.join(self.session_dir, "raw_data.npz")
        
        # Convert list of arrays to a single array if possible
        try:
            if all(arr.shape == self.raw_data[0].shape for arr in self.raw_data):
                combined_data = np.stack(self.raw_data)
                np.savez_compressed(np_path, 
                                   emg_data=combined_data, 
                                   timestamps=np.array(self.timestamps))
                logger.info(f"Saved raw data to {np_path}")
            else:
                # Save as separate arrays if shapes differ
                np.savez_compressed(np_path,
                                  emg_data=self.raw_data,
                                  timestamps=np.array(self.timestamps))
                logger.info(f"Saved raw data with varying shapes to {np_path}")
        except Exception as e:
            logger.error(f"Error saving raw data as NPZ: {str(e)}")
            
            # Fallback: save first few seconds to CSV
            try:
                # Take first array and save it as CSV
                if len(self.raw_data) > 0:
                    csv_path = os.path.join(self.session_dir, "raw_data_sample.csv")
                    sample_data = self.raw_data[0]
                    
                    # Save with timestamps as first column
                    # Create time points based on sampling rate
                    num_samples = sample_data.shape[1] if sample_data.ndim > 1 else len(sample_data)
                    time_points = np.linspace(0, num_samples/self.sampling_rate, num_samples)
                    
                    with open(csv_path, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        
                        # Write header
                        if sample_data.ndim > 1:
                            header = ["Time"] + [f"Ch{i+1}" for i in range(sample_data.shape[0])]
                        else:
                            header = ["Time", "Signal"]
                        writer.writerow(header)
                        
                        # Write data
                        if sample_data.ndim > 1:
                            for i in range(num_samples):
                                row = [time_points[i]] + [sample_data[ch][i] for ch in range(sample_data.shape[0])]
                                writer.writerow(row)
                        else:
                            for i in range(num_samples):
                                writer.writerow([time_points[i], sample_data[i]])
                    
                    logger.info(f"Saved sample raw data to {csv_path}")
            except Exception as inner_e:
                logger.error(f"Error saving raw data as CSV: {str(inner_e)}")
    
    def _save_features(self):
        """Save extracted features to a CSV file."""
        if not self.features:
            return
            
        try:
            # Convert list of feature dictionaries to a DataFrame
            features_path = os.path.join(self.session_dir, "features.csv")
            
            # Create a list to hold rows
            rows = []
            
            # Process each feature dictionary
            for i, feature_dict in enumerate(self.features):
                row = {"timestamp": self.timestamps[i]}
                
                # Flatten feature dictionary
                for feature_name, values in feature_dict.items():
                    if isinstance(values, list):
                        for j, value in enumerate(values):
                            row[f"{feature_name}_{j+1}"] = value
                    else:
                        row[feature_name] = values
                
                rows.append(row)
            
            # Convert to DataFrame and save
            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(features_path, index=False)
                logger.info(f"Saved features to {features_path}")
        except Exception as e:
            logger.error(f"Error saving features: {str(e)}")
            
            # Fallback: save as JSON
            try:
                json_path = os.path.join(self.session_dir, "features.json")
                with open(json_path, 'w') as f:
                    json.dump({
                        "timestamps": self.timestamps,
                        "features": self.features
                    }, f, indent=2, default=lambda x: x.tolist() if isinstance(x, np.ndarray) else str(x))
                logger.info(f"Saved features to {json_path}")
            except Exception as inner_e:
                logger.error(f"Error saving features as JSON: {str(inner_e)}")
    
    def _save_gestures(self):
        """Save gesture labels with timestamps."""
        try:
            # Create a DataFrame with timestamps and gestures
            gestures_path = os.path.join(self.session_dir, "gestures.csv")
            gestures_df = pd.DataFrame({
                "timestamp": self.timestamps,
                "gesture": self.gestures
            })
            gestures_df.to_csv(gestures_path, index=False)
            logger.info(f"Saved gestures to {gestures_path}")
        except Exception as e:
            logger.error(f"Error saving gestures: {str(e)}")
    
    def export_to_matlab(self):
        """Export recorded data to MATLAB format.
        
        Returns:
            str: Path to the exported file or None if error
        """
        if not self.session_dir or not os.path.exists(self.session_dir):
            logger.error("No recording session data available")
            return None
            
        try:
            from scipy.io import savemat
            
            mat_path = os.path.join(self.session_dir, "emg_data.mat")
            
            # Prepare data for MATLAB format
            mat_data = {
                "timestamps": np.array(self.timestamps),
                "sampling_rate": self.sampling_rate,
                "session_info": str(self.session_info)
            }
            
            # Add raw data if available
            if self.raw_data:
                # Try to combine raw data into a 3D array if possible
                if all(arr.shape == self.raw_data[0].shape for arr in self.raw_data):
                    mat_data["raw_data"] = np.stack(self.raw_data)
                else:
                    # Store as object array if shapes differ
                    mat_data["raw_data"] = np.array(self.raw_data, dtype=object)
            
            # Add gestures if available
            if self.gestures:
                mat_data["gestures"] = np.array(self.gestures)
            
            # Save to .mat file
            savemat(mat_path, mat_data)
            logger.info(f"Exported data to MATLAB format: {mat_path}")
            return mat_path
            
        except Exception as e:
            logger.error(f"Error exporting to MATLAB: {str(e)}")
            return None
