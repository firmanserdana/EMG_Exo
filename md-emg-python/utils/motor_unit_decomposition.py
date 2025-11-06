"""
Motor Unit Decomposition (MUD) for EMG Signal Processing
========================================================

This module provides motor unit decomposition functionality for EMG signals.
MUD extracts individual motor unit firing patterns from raw EMG, providing
more detailed information for proportional control.

Features:
---------
- Spike detection and sorting
- Motor unit identification
- Firing rate estimation
- Feature extraction from motor unit activity

Methods:
--------
- Threshold-based spike detection
- Template matching for motor unit sorting
- Firing rate smoothing and estimation
"""

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d
from typing import Tuple, List, Dict, Optional


class MotorUnitDecomposer:
    """
    Motor unit decomposition using spike detection and template matching.
    
    Simplified implementation for real-time proportional control.
    """
    
    def __init__(self, fsample=2048, threshold_method='mad', 
                 spike_detection_threshold=4.0, template_window_ms=5.0):
        """
        Initialize motor unit decomposer.
        
        Args:
            fsample (int): Sampling frequency in Hz
            threshold_method (str): Method for threshold calculation ('mad' or 'std')
            spike_detection_threshold (float): Threshold multiplier for spike detection
            template_window_ms (float): Template window duration in milliseconds
        """
        self.fsample = fsample
        self.threshold_method = threshold_method
        self.spike_detection_threshold = spike_detection_threshold
        self.template_window_samples = int(template_window_ms * fsample / 1000)
        
        # Motor unit templates (learned during calibration)
        self.templates = {}
        self.num_motor_units = 0
        
        # Preprocessing filters
        self.highpass_cutoff = 100  # Hz
        self.lowpass_cutoff = 500   # Hz
        self.notch_freq = 50        # Hz (power line)
    
    def preprocess_signal(self, signal_data):
        """
        Preprocess EMG signal for spike detection.
        
        Args:
            signal_data (np.ndarray): Raw EMG signal (n_samples, n_channels)
        
        Returns:
            np.ndarray: Preprocessed signal
        """
        # Bandpass filter (100-500 Hz)
        sos_hp = signal.butter(4, self.highpass_cutoff, 'hp', fs=self.fsample, output='sos')
        sos_lp = signal.butter(4, self.lowpass_cutoff, 'lp', fs=self.fsample, output='sos')
        
        filtered = signal_data.copy()
        filtered = signal.sosfilt(sos_hp, filtered, axis=0)
        filtered = signal.sosfilt(sos_lp, filtered, axis=0)
        
        # Notch filter for power line interference
        sos_notch = signal.butter(4, [self.notch_freq - 2, self.notch_freq + 2], 
                                  'bandstop', fs=self.fsample, output='sos')
        filtered = signal.sosfilt(sos_notch, filtered, axis=0)
        
        return filtered
    
    def detect_spikes(self, signal_data, channel_idx=0):
        """
        Detect spikes in EMG signal using threshold crossing.
        
        Args:
            signal_data (np.ndarray): Preprocessed EMG signal (n_samples,) or (n_samples, n_channels)
            channel_idx (int): Channel index if multi-channel
        
        Returns:
            np.ndarray: Spike indices
        """
        # Extract single channel if needed
        if len(signal_data.shape) == 2:
            signal_1d = signal_data[:, channel_idx]
        else:
            signal_1d = signal_data
        
        # Calculate threshold based on noise level
        if self.threshold_method == 'mad':
            # Median Absolute Deviation (more robust to outliers)
            mad = np.median(np.abs(signal_1d - np.median(signal_1d)))
            threshold = self.spike_detection_threshold * mad / 0.6745
        else:
            # Standard deviation
            threshold = self.spike_detection_threshold * np.std(signal_1d)
        
        # Detect threshold crossings
        above_threshold = np.abs(signal_1d) > threshold
        spike_indices = np.where(np.diff(above_threshold.astype(int)) > 0)[0]
        
        # Remove spikes too close to edges
        min_idx = self.template_window_samples // 2
        max_idx = len(signal_1d) - self.template_window_samples // 2
        spike_indices = spike_indices[(spike_indices >= min_idx) & (spike_indices < max_idx)]
        
        # Enforce minimum inter-spike interval (refractory period ~ 2ms)
        min_isi_samples = int(2 * self.fsample / 1000)
        filtered_spikes = []
        last_spike = -min_isi_samples
        
        for spike_idx in spike_indices:
            if spike_idx - last_spike >= min_isi_samples:
                filtered_spikes.append(spike_idx)
                last_spike = spike_idx
        
        return np.array(filtered_spikes)
    
    def extract_spike_waveforms(self, signal_data, spike_indices, channel_idx=0):
        """
        Extract spike waveforms around detected spikes.
        
        Args:
            signal_data (np.ndarray): EMG signal
            spike_indices (np.ndarray): Spike time indices
            channel_idx (int): Channel index
        
        Returns:
            np.ndarray: Spike waveforms (n_spikes, template_window_samples)
        """
        if len(signal_data.shape) == 2:
            signal_1d = signal_data[:, channel_idx]
        else:
            signal_1d = signal_data
        
        half_window = self.template_window_samples // 2
        waveforms = []
        
        for spike_idx in spike_indices:
            start_idx = spike_idx - half_window
            end_idx = spike_idx + half_window
            
            if start_idx >= 0 and end_idx < len(signal_1d):
                waveform = signal_1d[start_idx:end_idx]
                waveforms.append(waveform)
        
        return np.array(waveforms)
    
    def estimate_firing_rates(self, spike_trains, window_size_ms=50.0, smooth_sigma_ms=20.0):
        """
        Estimate instantaneous firing rates from spike trains.
        
        Args:
            spike_trains (dict): Dictionary of spike trains per motor unit
                                 {unit_id: spike_times_array}
            window_size_ms (float): Window size for firing rate estimation (ms)
            smooth_sigma_ms (float): Gaussian smoothing sigma (ms)
        
        Returns:
            dict: Firing rates per motor unit {unit_id: firing_rate_array}
        """
        firing_rates = {}
        
        window_samples = int(window_size_ms * self.fsample / 1000)
        smooth_sigma_samples = smooth_sigma_ms * self.fsample / 1000
        
        for unit_id, spike_times in spike_trains.items():
            if len(spike_times) == 0:
                firing_rates[unit_id] = np.zeros(1)
                continue
            
            # Create binary spike train
            max_time = int(np.max(spike_times)) + window_samples
            spike_train_binary = np.zeros(max_time)
            spike_train_binary[spike_times.astype(int)] = 1
            
            # Convolve with window to get firing rate
            rate = np.convolve(spike_train_binary, 
                              np.ones(window_samples) / window_samples, 
                              mode='same')
            
            # Convert to Hz
            rate = rate * self.fsample
            
            # Smooth with Gaussian
            rate_smooth = gaussian_filter1d(rate, smooth_sigma_samples)
            
            firing_rates[unit_id] = rate_smooth
        
        return firing_rates
    
    def decompose_to_features(self, signal_data, n_units=5):
        """
        Decompose EMG signal and extract features for proportional control.
        
        Simplified approach: Use spike detection on multiple channels and
        estimate motor unit activity levels.
        
        Args:
            signal_data (np.ndarray): Raw EMG signal (n_samples, n_channels)
            n_units (int): Number of motor units to extract (simplified)
        
        Returns:
            np.ndarray: Motor unit activity features (n_channels * n_units,)
        """
        # Preprocess signal
        preprocessed = self.preprocess_signal(signal_data)
        
        n_samples, n_channels = preprocessed.shape
        
        # For each channel, estimate motor unit activity using amplitude and firing rate
        features = []
        
        for ch in range(n_channels):
            # Detect spikes
            spikes = self.detect_spikes(preprocessed, channel_idx=ch)
            
            if len(spikes) > 0:
                # Estimate firing rate
                spike_train = {0: spikes}
                firing_rate = self.estimate_firing_rates(spike_train, 
                                                         window_size_ms=100.0)
                
                # Get mean firing rate over the window
                mean_firing_rate = np.mean(firing_rate[0])
                
                # Get RMS amplitude
                rms_amplitude = np.sqrt(np.mean(preprocessed[:, ch] ** 2))
                
                # Combine features (normalized)
                features.append(mean_firing_rate / 50.0)  # Normalize firing rate (typical max ~50 Hz)
                features.append(rms_amplitude / np.max(np.abs(preprocessed[:, ch]) + 1e-6))
            else:
                # No spikes detected
                features.append(0.0)
                features.append(0.0)
        
        return np.array(features)


class MotorUnitFeatureExtractor:
    """
    Feature extraction from motor unit decomposition results.
    
    Extracts features suitable for proportional control:
    - Firing rate features
    - Amplitude features
    - Temporal features
    """
    
    def __init__(self, fsample=2048):
        """
        Initialize feature extractor.
        
        Args:
            fsample (int): Sampling frequency
        """
        self.fsample = fsample
    
    def extract_firing_rate_features(self, firing_rates):
        """
        Extract features from firing rate signals.
        
        Args:
            firing_rates (dict): Firing rates per motor unit
        
        Returns:
            np.ndarray: Firing rate features
        """
        features = []
        
        for unit_id, rate in firing_rates.items():
            # Mean firing rate
            features.append(np.mean(rate))
            
            # Peak firing rate
            features.append(np.max(rate))
            
            # Firing rate variability (coefficient of variation)
            if np.mean(rate) > 0:
                cv = np.std(rate) / np.mean(rate)
            else:
                cv = 0.0
            features.append(cv)
        
        return np.array(features)
    
    def extract_temporal_features(self, spike_trains):
        """
        Extract temporal features from spike trains.
        
        Args:
            spike_trains (dict): Spike trains per motor unit
        
        Returns:
            np.ndarray: Temporal features
        """
        features = []
        
        for unit_id, spikes in spike_trains.items():
            if len(spikes) < 2:
                features.extend([0.0, 0.0, 0.0])
                continue
            
            # Inter-spike intervals
            isi = np.diff(spikes) / self.fsample * 1000  # in ms
            
            # Mean ISI
            features.append(np.mean(isi))
            
            # ISI variability
            features.append(np.std(isi))
            
            # Spike count
            features.append(len(spikes))
        
        return np.array(features)


def get_mud_features(signal_data, fsample=2048, use_mud=True):
    """
    Get features from EMG signal using motor unit decomposition or raw signal.
    
    Args:
        signal_data (np.ndarray): Raw EMG signal (n_samples, n_channels)
        fsample (int): Sampling frequency
        use_mud (bool): Whether to use motor unit decomposition
    
    Returns:
        np.ndarray: Extracted features
    """
    if use_mud:
        # Use motor unit decomposition
        decomposer = MotorUnitDecomposer(fsample=fsample)
        features = decomposer.decompose_to_features(signal_data)
    else:
        # Use raw EMG features (RMS per channel)
        features = np.sqrt(np.mean(signal_data ** 2, axis=0))
    
    return features
