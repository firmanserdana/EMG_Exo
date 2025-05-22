"""
EMG Processing Implementation

This module implements the EMG signal processing pipeline.
"""

import numpy as np
import scipy.signal as signal
from scipy.fft import fft, fftfreq
import matplotlib.pyplot as plt
import h5py
import os
import time
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Union, Any

from emg_exo.core.processing.base import BaseEMGProcessor
from emg_exo.config import EMG_PROCESSING, RECORDING, logger


class EMGProcessor(BaseEMGProcessor):
    """Process EMG signals for feature extraction and analysis."""
    
    def __init__(self, channel_count: Optional[int] = None, sampling_rate: Optional[float] = None):
        """Initialize EMG processor.
        
        Args:
            channel_count: Number of EMG channels
            sampling_rate: Sampling rate in Hz
        """
        # Configure processing parameters
        self.window_size = EMG_PROCESSING["window_size"]
        self.window_overlap = EMG_PROCESSING["window_overlap"]
        self.bandpass_low = EMG_PROCESSING["bandpass_low"]
        self.bandpass_high = EMG_PROCESSING["bandpass_high"]
        self.notch_freq = EMG_PROCESSING["notch_freq"]
        self.notch_quality = EMG_PROCESSING["notch_quality"]
        self.highpass_cutoff = EMG_PROCESSING["highpass_cutoff"]
        self.lowpass_cutoff = EMG_PROCESSING["lowpass_cutoff"]
        self.feature_window = EMG_PROCESSING["feature_window"]
        self.feature_overlap = EMG_PROCESSING["feature_overlap"]
        self.features_enabled = EMG_PROCESSING["features_enabled"]
        self.decomposition_method = EMG_PROCESSING["decomposition_method"]
        
        # Set channel count and sampling rate
        self.channel_count = channel_count
        self.sampling_rate = sampling_rate
        
        # Initialize buffers
        self.raw_buffer = None
        self.processed_buffer = None
        self.feature_buffer = {}
        
        logger.info("EMG Processor initialized")
        
    def preprocess(self, emg_data: np.ndarray) -> np.ndarray:
        """Preprocess raw EMG data.
        
        Args:
            emg_data: Raw EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: Preprocessed EMG data of shape (channels, samples)
        """
        # Get shape info
        if emg_data is None:
            return None
            
        num_channels, num_samples = emg_data.shape
        
        # Update channel count and determine sampling rate if not specified
        if self.channel_count is None:
            self.channel_count = num_channels
            
        if self.sampling_rate is None:
            # Assume default from config
            self.sampling_rate = EMG_PROCESSING.get("sampling_rate", 2000)
            
        # Apply high-pass filter to remove DC offset and low-frequency noise
        processed_data = self._apply_highpass_filter(emg_data)
        
        # Apply low-pass filter to remove high-frequency noise
        processed_data = self._apply_lowpass_filter(processed_data)
        
        # Apply notch filter to remove power line interference (50/60Hz)
        processed_data = self._apply_notch_filter(processed_data)
        
        # Update processed buffer
        self.processed_buffer = processed_data
        
        return processed_data
    
    def _apply_highpass_filter(self, data: np.ndarray) -> np.ndarray:
        """Apply high-pass filter to remove DC offset and low-frequency noise.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: Filtered EMG data
        """
        # Design filter
        nyq = 0.5 * self.sampling_rate
        normal_cutoff = self.highpass_cutoff / nyq
        b, a = signal.butter(4, normal_cutoff, btype='high')
        
        # Apply filter
        filtered_data = np.zeros_like(data)
        for i in range(data.shape[0]):
            filtered_data[i] = signal.filtfilt(b, a, data[i])
            
        return filtered_data
    
    def _apply_lowpass_filter(self, data: np.ndarray) -> np.ndarray:
        """Apply low-pass filter to remove high-frequency noise.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: Filtered EMG data
        """
        # Design filter
        nyq = 0.5 * self.sampling_rate
        normal_cutoff = self.lowpass_cutoff / nyq
        b, a = signal.butter(4, normal_cutoff, btype='low')
        
        # Apply filter
        filtered_data = np.zeros_like(data)
        for i in range(data.shape[0]):
            filtered_data[i] = signal.filtfilt(b, a, data[i])
            
        return filtered_data
    
    def _apply_notch_filter(self, data: np.ndarray) -> np.ndarray:
        """Apply notch filter to remove power line interference.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: Filtered EMG data
        """
        # Design filter
        nyq = 0.5 * self.sampling_rate
        freq = self.notch_freq / nyq
        q = self.notch_quality
        b, a = signal.iirnotch(freq, q)
        
        # Apply filter
        filtered_data = np.zeros_like(data)
        for i in range(data.shape[0]):
            filtered_data[i] = signal.filtfilt(b, a, data[i])
            
        return filtered_data
    
    def extract_features(self, emg_data: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract features from EMG data.
        
        Args:
            emg_data: Preprocessed EMG data of shape (channels, samples)
            
        Returns:
            Dict[str, np.ndarray]: Dictionary of feature arrays
        """
        if emg_data is None:
            return {}
            
        # Initialize features dict
        features = {}
        
        # Extract time domain features
        if "rms" in self.features_enabled:
            features["rms"] = self._calculate_rms(emg_data)
            
        if "mav" in self.features_enabled:
            features["mav"] = self._calculate_mav(emg_data)
            
        if "zc" in self.features_enabled:
            features["zc"] = self._calculate_zc(emg_data)
            
        if "ssc" in self.features_enabled:
            features["ssc"] = self._calculate_ssc(emg_data)
            
        if "wl" in self.features_enabled:
            features["wl"] = self._calculate_wl(emg_data)
            
        if "var" in self.features_enabled:
            features["var"] = self._calculate_var(emg_data)
        
        # Extract frequency domain features
        if any(f in self.features_enabled for f in ["freq_mean", "freq_median", "freq_power"]):
            # Calculate power spectrum
            psd_data = self._calculate_psd(emg_data)
            
            if "freq_mean" in self.features_enabled:
                features["freq_mean"] = self._calculate_mean_frequency(psd_data)
                
            if "freq_median" in self.features_enabled:
                features["freq_median"] = self._calculate_median_frequency(psd_data)
                
            if "freq_power" in self.features_enabled:
                features["freq_power"] = self._calculate_power(psd_data)
                
        # Update feature buffer
        self.feature_buffer = features
        
        return features
    
    def _calculate_rms(self, data: np.ndarray) -> np.ndarray:
        """Calculate Root Mean Square (RMS) of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: RMS values of shape (channels,)
        """
        return np.sqrt(np.mean(np.square(data), axis=1))
    
    def _calculate_mav(self, data: np.ndarray) -> np.ndarray:
        """Calculate Mean Absolute Value (MAV) of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: MAV values of shape (channels,)
        """
        return np.mean(np.abs(data), axis=1)
    
    def _calculate_zc(self, data: np.ndarray) -> np.ndarray:
        """Calculate Zero Crossing (ZC) rate of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: ZC values of shape (channels,)
        """
        # Apply threshold to avoid noise
        threshold = 10  # microvolts
        
        zc = np.zeros(data.shape[0])
        for ch in range(data.shape[0]):
            # Count sign changes with threshold
            sign_changes = np.where(np.diff(np.signbit(data[ch])))[0]
            # Only count if the difference is above threshold
            valid_changes = 0
            for idx in sign_changes:
                if abs(data[ch, idx]) >= threshold or abs(data[ch, idx + 1]) >= threshold:
                    valid_changes += 1
            
            zc[ch] = valid_changes / data.shape[1]  # Normalize by signal length
            
        return zc
    
    def _calculate_ssc(self, data: np.ndarray) -> np.ndarray:
        """Calculate Slope Sign Changes (SSC) of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: SSC values of shape (channels,)
        """
        # Apply threshold to avoid noise
        threshold = 10  # microvolts
        
        ssc = np.zeros(data.shape[0])
        for ch in range(data.shape[0]):
            # Calculate first difference (slope)
            diff = np.diff(data[ch])
            
            # Count slope sign changes
            sign_changes = 0
            for i in range(1, len(diff)):
                if (diff[i] * diff[i-1] < 0) and (abs(diff[i]) >= threshold or abs(diff[i-1]) >= threshold):
                    sign_changes += 1
                    
            ssc[ch] = sign_changes / data.shape[1]  # Normalize by signal length
            
        return ssc
    
    def _calculate_wl(self, data: np.ndarray) -> np.ndarray:
        """Calculate Waveform Length (WL) of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: WL values of shape (channels,)
        """
        return np.sum(np.abs(np.diff(data)), axis=1)
    
    def _calculate_var(self, data: np.ndarray) -> np.ndarray:
        """Calculate Variance (VAR) of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            np.ndarray: VAR values of shape (channels,)
        """
        return np.var(data, axis=1)
    
    def _calculate_psd(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """Calculate Power Spectral Density (PSD) of EMG data.
        
        Args:
            data: EMG data of shape (channels, samples)
            
        Returns:
            Dict[str, np.ndarray]: Dictionary with 'freqs' and 'psd' keys
        """
        n = data.shape[1]
        
        # Calculate FFT
        fft_data = fft(data)
        
        # Calculate frequency bins
        freqs = fftfreq(n, 1/self.sampling_rate)
        
        # Calculate power spectrum (only positive frequencies)
        half_idx = n // 2
        freqs = freqs[:half_idx]
        psd = np.abs(fft_data[:, :half_idx]) ** 2 / n
        
        return {"freqs": freqs, "psd": psd}
    
    def _calculate_mean_frequency(self, psd_data: Dict[str, np.ndarray]) -> np.ndarray:
        """Calculate Mean Frequency of EMG data.
        
        Args:
            psd_data: Dictionary with 'freqs' and 'psd' keys
            
        Returns:
            np.ndarray: Mean frequency values of shape (channels,)
        """
        freqs = psd_data["freqs"]
        psd = psd_data["psd"]
        
        # Calculate mean frequency (centroid of the spectrum)
        mean_freq = np.zeros(psd.shape[0])
        
        for ch in range(psd.shape[0]):
            # Only consider 5-500Hz range for EMG
            mask = (freqs >= 5) & (freqs <= 500)
            if np.sum(psd[ch, mask]) > 0:
                mean_freq[ch] = np.sum(freqs[mask] * psd[ch, mask]) / np.sum(psd[ch, mask])
            
        return mean_freq
    
    def _calculate_median_frequency(self, psd_data: Dict[str, np.ndarray]) -> np.ndarray:
        """Calculate Median Frequency of EMG data.
        
        Args:
            psd_data: Dictionary with 'freqs' and 'psd' keys
            
        Returns:
            np.ndarray: Median frequency values of shape (channels,)
        """
        freqs = psd_data["freqs"]
        psd = psd_data["psd"]
        
        # Calculate median frequency (frequency that divides the power spectrum in two equal parts)
        median_freq = np.zeros(psd.shape[0])
        
        for ch in range(psd.shape[0]):
            # Only consider 5-500Hz range for EMG
            mask = (freqs >= 5) & (freqs <= 500)
            if np.sum(psd[ch, mask]) > 0:
                # Calculate cumulative sum of PSD
                cum_psd = np.cumsum(psd[ch, mask])
                # Find median point
                median_idx = np.argmax(cum_psd >= cum_psd[-1] / 2)
                # Get corresponding frequency
                median_freq[ch] = freqs[mask][median_idx]
            
        return median_freq
    
    def _calculate_power(self, psd_data: Dict[str, np.ndarray]) -> np.ndarray:
        """Calculate total power in the EMG signal.
        
        Args:
            psd_data: Dictionary with 'freqs' and 'psd' keys
            
        Returns:
            np.ndarray: Power values of shape (channels,)
        """
        freqs = psd_data["freqs"]
        psd = psd_data["psd"]
        
        # Calculate total power in relevant frequency bands
        power = np.zeros(psd.shape[0])
        
        for ch in range(psd.shape[0]):
            # Only consider 5-500Hz range for EMG
            mask = (freqs >= 5) & (freqs <= 500)
            power[ch] = np.sum(psd[ch, mask])
            
        return power
    
    def decompose_motor_units(self, emg_data: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """Decompose EMG data into motor unit activity.
        
        Args:
            emg_data: Preprocessed EMG data of shape (channels, samples)
            
        Returns:
            tuple: (components, mixing matrix, spike trains)
        """
        # This is a placeholder implementation
        # In a full implementation, this would use advanced techniques like FastICA
        
        if emg_data is None:
            return None, None, None
            
        try:
            # For now, we'll just return random components as a placeholder
            n_components = min(8, emg_data.shape[0])  # Assume up to 8 motor units
            
            # Random mixing matrix
            mixing = np.random.randn(emg_data.shape[0], n_components)
            
            # Random components (MU source signals)
            components = np.random.randn(n_components, emg_data.shape[1])
            
            # Create spike trains (binary activations)
            spike_trains = np.zeros_like(components)
            for i in range(n_components):
                # Create random spikes with physiological constraints
                spikes = np.zeros(emg_data.shape[1])
                # Minimum 20ms between spikes (refractory period)
                min_samples = int(0.02 * self.sampling_rate)
                
                # Add random spikes
                n_spikes = np.random.randint(5, 50)
                spike_positions = np.random.randint(0, emg_data.shape[1] - min_samples, n_spikes)
                spike_positions.sort()
                
                # Enforce minimum distance
                valid_positions = [spike_positions[0]]
                for pos in spike_positions[1:]:
                    if pos - valid_positions[-1] >= min_samples:
                        valid_positions.append(pos)
                
                # Set spikes
                spike_trains[i, valid_positions] = 1
            
            return components, mixing, spike_trains
            
        except Exception as e:
            logger.error(f"Error in motor unit decomposition: {str(e)}")
            return None, None, None
    
    def save_results(self, raw_emg: Optional[np.ndarray] = None, processed_emg: Optional[np.ndarray] = None, 
                   filename: Optional[str] = None) -> str:
        """Save EMG processing results.
        
        Args:
            raw_emg: Raw EMG data
            processed_emg: Processed EMG data
            filename: Output filename (default: auto-generated with timestamp)
            
        Returns:
            str: Path to saved file
        """
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"emg_processing_{timestamp}.h5"
        
        # Generate full path
        save_dir = RECORDING["save_dir"]
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, filename)
        
        try:
            # Save to HDF5 file
            with h5py.File(filepath, 'w') as f:
                # Create metadata
                f.attrs['timestamp'] = datetime.now().isoformat()
                f.attrs['sampling_rate'] = self.sampling_rate if self.sampling_rate else EMG_PROCESSING.get("sampling_rate", 2000)
                
                # Save raw EMG if available
                if raw_emg is not None and RECORDING["save_raw_emg"]:
                    f.create_dataset("raw_emg", data=raw_emg)
                
                # Save processed EMG if available
                if processed_emg is not None and RECORDING["save_processed_emg"]:
                    f.create_dataset("processed_emg", data=processed_emg)
                
                # Save features if available
                if self.feature_buffer:
                    features_group = f.create_group("features")
                    for name, data in self.feature_buffer.items():
                        features_group.create_dataset(name, data=data)
                
            logger.info(f"Saved EMG processing results to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving EMG processing results: {str(e)}")
            return ""
