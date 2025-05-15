#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Signal Processing Module
Handles preprocessing and motor unit decomposition of EMG signals.
"""

import numpy as np
from scipy import signal
import scipy.io as sio
import time
from sklearn.decomposition import FastICA, PCA
import matplotlib.pyplot as plt
from mne.decoding import UnsupervisedSpatialFilter
import logging
import h5py
import os
from datetime import datetime

from ini import EMG_PROCESSING, RECORDING, logger

class EMGProcessor:
    """Class for processing EMG signals and performing motor unit decomposition."""
    
    def __init__(self):
        """Initialize the EMG processor."""
        self.window_size = EMG_PROCESSING["window_size"]
        self.window_overlap = EMG_PROCESSING["window_overlap"]
        self.bp_low = EMG_PROCESSING["bandpass_low"]
        self.bp_high = EMG_PROCESSING["bandpass_high"]
        self.notch_freq = EMG_PROCESSING["notch_freq"]
        self.decomp_method = EMG_PROCESSING["decomposition_method"]
        self.save_dir = RECORDING["save_dir"]
        
        # Buffer to store raw data
        self.raw_buffer = None
        
        # Components from decomposition
        self.components = None
        self.mixing_matrix = None
        
        # Motor unit spike trains
        self.spike_trains = []
        
        logger.info("EMG processor initialized")
        
    def preprocess(self, emg_data):
        """Preprocess raw EMG data.
        
        Args:
            emg_data (numpy.ndarray): Raw EMG data with shape (channels, samples)
            
        Returns:
            numpy.ndarray: Preprocessed EMG data
        """
        if emg_data is None or emg_data.size == 0:
            logger.warning("Empty data received for preprocessing")
            return None
        
        channels, samples = emg_data.shape
        logger.debug(f"Preprocessing data with shape {emg_data.shape}")
        
        # Apply filters
        processed_data = np.zeros_like(emg_data)
        
        for ch in range(channels):
            # Bandpass filter
            b, a = signal.butter(4, [self.bp_low, self.bp_high], 
                                btype='bandpass', fs=2048)
            processed_data[ch, :] = signal.filtfilt(b, a, emg_data[ch, :])
            
            # Notch filter for power line interference
            b_notch, a_notch = signal.iirnotch(self.notch_freq, 30, 2048)
            processed_data[ch, :] = signal.filtfilt(b_notch, a_notch, 
                                                   processed_data[ch, :])
        
        # Add to buffer for continuous processing
        if self.raw_buffer is None:
            self.raw_buffer = processed_data
        else:
            self.raw_buffer = np.hstack((self.raw_buffer, processed_data))
            
        # Trim buffer if it gets too large
        buffer_max = 10 * self.window_size  # Keep at most 10 windows
        if self.raw_buffer.shape[1] > buffer_max:
            self.raw_buffer = self.raw_buffer[:, -buffer_max:]
        
        return processed_data
        
    def extract_features(self, processed_data):
        """Extract features from preprocessed EMG data.
        
        Args:
            processed_data (numpy.ndarray): Preprocessed EMG data
            
        Returns:
            dict: Dictionary of extracted features
        """
        if processed_data is None or processed_data.size == 0:
            return {}
        
        channels, samples = processed_data.shape
        features = {}
        
        # Root Mean Square (RMS)
        features['rms'] = np.sqrt(np.mean(processed_data**2, axis=1))
        
        # Mean Absolute Value (MAV)
        features['mav'] = np.mean(np.abs(processed_data), axis=1)
        
        # Waveform Length (WL)
        features['wl'] = np.sum(np.abs(np.diff(processed_data, axis=1)), axis=1)
        
        # Zero Crossings (ZC)
        zero_crossings = np.zeros(channels)
        for ch in range(channels):
            # Count zero crossings with threshold to avoid noise
            threshold = 0.01 * np.std(processed_data[ch, :])
            zero_crossings[ch] = np.sum(
                np.diff(np.signbit(processed_data[ch, :])) & 
                (np.abs(np.diff(processed_data[ch, :])) > threshold)
            )
        features['zc'] = zero_crossings
        
        # Slope Sign Changes (SSC)
        ssc = np.zeros(channels)
        for ch in range(channels):
            threshold = 0.01 * np.std(processed_data[ch, :])
            diff_data = np.diff(processed_data[ch, :])
            ssc[ch] = np.sum(
                ((diff_data[:-1] * diff_data[1:]) < 0) & 
                ((np.abs(diff_data[:-1]) > threshold) | 
                 (np.abs(diff_data[1:]) > threshold))
            )
        features['ssc'] = ssc
        
        # Auto-Regressive (AR) coefficients
        ar_order = 4
        ar_coeffs = np.zeros((channels, ar_order))
        for ch in range(channels):
            try:
                ar_coeffs[ch, :], _ = signal.lpc(processed_data[ch, :], ar_order)
            except:
                ar_coeffs[ch, :] = np.zeros(ar_order)
        features['ar'] = ar_coeffs
        
        return features
        
    def decompose_motor_units(self, preprocessed_data, n_components=None):
        """Decompose EMG signals into motor unit action potentials.
        
        Args:
            preprocessed_data (numpy.ndarray): Preprocessed EMG data
            n_components (int): Number of components (motor units) to extract
            
        Returns:
            tuple: (components, mixing_matrix, spike_trains)
        """
        if preprocessed_data is None or preprocessed_data.size == 0:
            logger.warning("Empty data received for decomposition")
            return None, None, None
        
        channels, samples = preprocessed_data.shape
        
        # Default to channels/2 components if not specified
        if n_components is None:
            n_components = min(channels // 2, 20)  # Max 20 motor units by default
            
        logger.info(f"Decomposing {channels} channels into {n_components} motor units")
        
        try:
            # Choose decomposition method
            if self.decomp_method == "FastICA":
                # FastICA for blind source separation
                ica = FastICA(n_components=n_components, random_state=42)
                components = ica.fit_transform(preprocessed_data.T)
                mixing_matrix = ica.mixing_
                
            elif self.decomp_method == "PCA":
                # PCA for dimensionality reduction
                pca = PCA(n_components=n_components)
                components = pca.fit_transform(preprocessed_data.T)
                mixing_matrix = pca.components_
                
            elif self.decomp_method == "CKC":
                # Implement Convolution Kernel Compensation method
                # This is a more specialized EMG decomposition method
                # For now we'll use MNE's UnsupervisedSpatialFilter as a placeholder
                usf = UnsupervisedSpatialFilter(PCA(n_components=n_components))
                components = usf.fit_transform(preprocessed_data.T)
                mixing_matrix = usf.estimator.components_
            
            else:
                logger.error(f"Unknown decomposition method: {self.decomp_method}")
                return None, None, None
            
            # Store components and mixing matrix
            self.components = components
            self.mixing_matrix = mixing_matrix
            
            # Estimate spike trains from components
            spike_trains = self._extract_spike_trains(components)
            self.spike_trains = spike_trains
            
            logger.info(f"Successfully decomposed {n_components} motor units")
            return components, mixing_matrix, spike_trains
            
        except Exception as e:
            logger.error(f"Error during motor unit decomposition: {str(e)}")
            return None, None, None
    
    def _extract_spike_trains(self, components):
        """Extract spike trains from decomposed components.
        
        Args:
            components (numpy.ndarray): Decomposed components
            
        Returns:
            list: List of spike trains for each motor unit
        """
        if components is None:
            return []
        
        samples, n_components = components.shape
        spike_trains = []
        
        for i in range(n_components):
            # Normalize the component
            comp = components[:, i]
            comp_norm = (comp - np.mean(comp)) / np.std(comp)
            
            # Apply threshold for spike detection
            # Typically spikes are identified as peaks above 3-5 standard deviations
            threshold = 3.0
            spike_candidate_indices = signal.find_peaks(comp_norm, height=threshold)[0]
            
            # Apply refractory period constraint (no spikes within 30ms = ~60 samples at 2kHz)
            refractory = 60  
            if len(spike_candidate_indices) > 0:
                valid_spikes = [spike_candidate_indices[0]]
                for j in range(1, len(spike_candidate_indices)):
                    if spike_candidate_indices[j] - valid_spikes[-1] > refractory:
                        valid_spikes.append(spike_candidate_indices[j])
                
                # Convert to binary spike train
                spike_train = np.zeros(samples)
                spike_train[valid_spikes] = 1
            else:
                spike_train = np.zeros(samples)
                
            spike_trains.append(spike_train)
            
        return spike_trains
    
    def save_results(self, raw_emg=None, processed_emg=None, filename=None):
        """Save processing results to file.
        
        Args:
            raw_emg (numpy.ndarray): Raw EMG data
            processed_emg (numpy.ndarray): Processed EMG data
            filename (str): Optional filename, will be auto-generated if None
            
        Returns:
            str: Path to the saved file
        """
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"emg_processing_{timestamp}.h5"
        
        file_path = os.path.join(self.save_dir, filename)
        
        try:
            with h5py.File(file_path, 'w') as f:
                # Save timestamps
                f.attrs['timestamp'] = datetime.now().isoformat()
                f.attrs['decomposition_method'] = self.decomp_method
                
                # Save raw data if provided and configured
                if RECORDING["save_raw_emg"] and raw_emg is not None:
                    f.create_dataset('raw_emg', data=raw_emg)
                
                # Save processed data if provided and configured
                if RECORDING["save_processed_emg"] and processed_emg is not None:
                    f.create_dataset('processed_emg', data=processed_emg)
                
                # Save decomposition results if available
                if RECORDING["save_decomposed_mus"]:
                    if self.components is not None:
                        f.create_dataset('components', data=self.components)
                    if self.mixing_matrix is not None:
                        f.create_dataset('mixing_matrix', data=self.mixing_matrix)
                    if self.spike_trains and len(self.spike_trains) > 0:
                        spike_train_data = np.vstack(self.spike_trains)
                        f.create_dataset('spike_trains', data=spike_train_data)
            
            logger.info(f"Results saved to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            return None
    
    def plot_decomposition(self, n_components=5):
        """Plot decomposition results for visualization.
        
        Args:
            n_components (int): Number of components to plot
        """
        if self.components is None or self.spike_trains is None:
            logger.warning("No decomposition results to plot")
            return
        
        # Limit to available components
        n_components = min(n_components, len(self.spike_trains))
        
        plt.figure(figsize=(12, 8))
        
        # Plot a subset of components
        for i in range(n_components):
            plt.subplot(n_components, 1, i+1)
            
            # Get component and spike train
            component = self.components[:, i]
            spike_train = self.spike_trains[i]
            
            # Plot the component
            plt.plot(component, 'b-', linewidth=0.5)
            
            # Mark the spikes
            spike_indices = np.where(spike_train > 0)[0]
            plt.plot(spike_indices, component[spike_indices], 'r*')
            
            plt.title(f"Motor Unit {i+1}")
            plt.tight_layout()
        
        plt.show()

if __name__ == "__main__":
    # Simple test script
    import matplotlib.pyplot as plt
    
    # Generate synthetic EMG data for testing
    channels = 64
    samples = 2048 * 5  # 5 seconds at 2048 Hz
    
    # Create synthetic EMG with some "motor units" firing
    emg_data = np.random.normal(0, 0.5, (channels, samples))
    
    # Add simulated motor unit spikes
    for i in range(5):  # 5 synthetic motor units
        # Firing rate between 8-20 Hz
        firing_rate = 8 + 12 * i / 5
        isis = np.random.normal(2048/firing_rate, 2048/firing_rate/10, 
                               int(samples * firing_rate / 2048 * 1.2))
        spike_times = np.cumsum(isis).astype(int)
        spike_times = spike_times[spike_times < samples]
        
        # MU shape
        mu_shape = signal.gaussian(50, 5)
        
        # Different weights for channels
        weights = np.random.normal(0, 1, channels)
        
        # Add to each channel
        for t in spike_times:
            if t + len(mu_shape) < samples:
                for ch in range(channels):
                    emg_data[ch, t:t+len(mu_shape)] += weights[ch] * mu_shape * (2 + i)
    
    # Process the synthetic data
    processor = EMGProcessor()
    processed_data = processor.preprocess(emg_data)
    features = processor.extract_features(processed_data)
    
    components, mixing, spikes = processor.decompose_motor_units(processed_data, n_components=10)
    
    # Plot results
    processor.plot_decomposition(n_components=5)
    
    # Save results
    processor.save_results(raw_emg=emg_data, processed_emg=processed_data)
    
    print("EMG processing test completed")