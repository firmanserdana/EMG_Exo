"""
Signal Filtering Module for EMG Processing
==========================================

This module provides various filtering techniques for EMG signal processing,
including specialized filters for exoskeleton artifact removal and SCI patient support.

Key Features:
- Standard filters: Notch, Bandpass
- Spatial filters: Laplacian (reduces EMI and improves SNR)
- Adaptive filters: LMS (removes correlated motor noise)
- Artifact handling: Blanking window, motion artifact detection
- SCI-specific: Spasticity detection, fatigue compensation
"""

import numpy as np
from scipy.signal import butter, lfilter, iirnotch, convolve2d
from scipy.signal.signaltools import lfilter_zi
from collections import deque


# =============================================================================
# Standard Filters
# =============================================================================

def butter_bandpass(lowcut, highcut, order, fs):
    """Create Butterworth bandpass filter coefficients."""
    nyq = fs / 2
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    zi = lfilter_zi(b, a)

    return b, a, zi


def butter_bandpass_filter(data, b_band, a_band, zi_band):
    """Apply Butterworth bandpass filter to data."""
    y, zi = lfilter(b_band, a_band, data, axis=0, zi=zi_band)

    return y, zi


def notch(notch_freq, Q, fs):
    """Create notch filter coefficients."""
    nyq = fs/2
    freq = notch_freq / nyq
    b, a = iirnotch(freq, Q)
    zi = lfilter_zi(b, a)

    return b, a, zi


def notch_filter(data, b_notch, a_notch, zi_notch):
    """Apply notch filter to data."""
    y, zi = lfilter(b_notch, a_notch, data, axis=0, zi=zi_notch)
    
    return y, zi


def butter_highpass(cutoff, order, fs):
    """Create Butterworth highpass filter for removing DC offset and low-freq artifacts."""
    nyq = fs / 2
    high = cutoff / nyq
    b, a = butter(order, high, btype='high')
    zi = lfilter_zi(b, a)
    return b, a, zi


def butter_highpass_filter(data, b_high, a_high, zi_high):
    """Apply Butterworth highpass filter to data."""
    y, zi = lfilter(b_high, a_high, data, axis=0, zi=zi_high)
    return y, zi


# =============================================================================
# Spatial Filters (for HD-sEMG)
# =============================================================================

class LaplacianFilter:
    """
    Spatial Laplacian filter for High-Density sEMG arrays.
    
    Reduces common-mode noise, EMI from motors, and improves spatial selectivity
    by focusing on superficial muscle fibers. Essential for same-hand exoskeleton
    setups where motor EMI is problematic.
    
    Parameters:
    -----------
    grid_shape : tuple
        Shape of the electrode grid (rows, cols). E.g., (8, 8) for 64 channels.
    filter_type : str
        'small' (4-neighbor) or 'large' (8-neighbor) Laplacian kernel.
    """
    
    def __init__(self, grid_shape=(8, 8), filter_type='small'):
        self.grid_shape = grid_shape
        self.filter_type = filter_type
        
        if filter_type == 'small':
            # 4-neighbor Laplacian (cross pattern)
            self.kernel = np.array([
                [0, -1, 0],
                [-1, 4, -1],
                [0, -1, 0]
            ], dtype=np.float32) / 4.0
        else:
            # 8-neighbor Laplacian (includes diagonals)
            self.kernel = np.array([
                [-1, -1, -1],
                [-1, 8, -1],
                [-1, -1, -1]
            ], dtype=np.float32) / 8.0
    
    def apply(self, data):
        """
        Apply Laplacian filter to multi-channel EMG data.
        
        Parameters:
        -----------
        data : np.ndarray
            EMG data of shape (n_samples, n_channels)
            
        Returns:
        --------
        filtered : np.ndarray
            Spatially filtered data of shape (n_samples, n_channels)
        """
        n_samples, n_channels = data.shape
        rows, cols = self.grid_shape
        
        if n_channels != rows * cols:
            # If channel count doesn't match grid, return original
            print(f"Warning: Channel count {n_channels} doesn't match grid {self.grid_shape}")
            return data
        
        filtered = np.zeros_like(data)
        
        for t in range(n_samples):
            # Reshape to 2D grid
            grid = data[t, :].reshape(rows, cols)
            
            # Apply 2D convolution with boundary handling
            filtered_grid = convolve2d(grid, self.kernel, mode='same', boundary='symm')
            
            # Reshape back to 1D
            filtered[t, :] = filtered_grid.flatten()
        
        return filtered


class CommonAverageReference:
    """
    Common Average Reference (CAR) filter.
    
    Subtracts the average of all channels from each channel.
    Simple but effective for removing global noise.
    """
    
    def apply(self, data):
        """
        Apply CAR to multi-channel EMG data.
        
        Parameters:
        -----------
        data : np.ndarray
            EMG data of shape (n_samples, n_channels)
            
        Returns:
        --------
        filtered : np.ndarray
            CAR-filtered data
        """
        mean_signal = np.mean(data, axis=1, keepdims=True)
        return data - mean_signal


# =============================================================================
# Adaptive Filters (for motor artifact removal)
# =============================================================================

class LMSAdaptiveFilter:
    """
    Least Mean Squares (LMS) Adaptive Filter for motor noise cancellation.
    
    Uses the motor control signal (PWM, current) as a reference to adaptively
    subtract correlated noise from the EMG signal. Essential for same-hand
    exoskeleton setups.
    
    Parameters:
    -----------
    n_channels : int
        Number of EMG channels
    filter_order : int
        Order of the adaptive filter (number of taps)
    mu : float
        Step size / learning rate (0.001 - 0.1 typical)
    """
    
    def __init__(self, n_channels, filter_order=32, mu=0.01):
        self.n_channels = n_channels
        self.filter_order = filter_order
        self.mu = mu
        
        # Filter weights for each channel
        self.weights = np.zeros((n_channels, filter_order))
        
        # Reference signal buffer
        self.ref_buffer = deque(maxlen=filter_order)
        self.ref_buffer.extend([0.0] * filter_order)
    
    def update_reference(self, motor_signal):
        """
        Update the reference signal buffer with new motor control signal.
        
        Parameters:
        -----------
        motor_signal : float
            Current motor control value (e.g., PWM duty cycle, current)
        """
        self.ref_buffer.append(motor_signal)
    
    def apply(self, emg_sample):
        """
        Apply LMS filter to remove motor-correlated noise.
        
        Parameters:
        -----------
        emg_sample : np.ndarray
            Single EMG sample of shape (n_channels,)
            
        Returns:
        --------
        filtered : np.ndarray
            Filtered EMG sample
        """
        ref_vec = np.array(self.ref_buffer)
        
        filtered = np.zeros(self.n_channels)
        
        for ch in range(self.n_channels):
            # Estimate noise contribution
            noise_estimate = np.dot(self.weights[ch], ref_vec)
            
            # Subtract estimated noise
            filtered[ch] = emg_sample[ch] - noise_estimate
            
            # Update weights using LMS rule
            error = filtered[ch]
            self.weights[ch] += 2 * self.mu * error * ref_vec
        
        return filtered
    
    def reset(self):
        """Reset filter weights and buffer."""
        self.weights = np.zeros((self.n_channels, self.filter_order))
        self.ref_buffer.clear()
        self.ref_buffer.extend([0.0] * self.filter_order)


class BlankingFilter:
    """
    Blanking window filter for motor artifact suppression.
    
    Zeros out EMG samples during motor actuation events to prevent
    artifacts from corrupting the signal. Uses a blanking window
    that extends slightly before and after the motor event.
    
    Parameters:
    -----------
    pre_blank_ms : float
        Blanking duration before motor event (milliseconds)
    post_blank_ms : float
        Blanking duration after motor event (milliseconds)
    fsample : float
        Sampling frequency in Hz
    """
    
    def __init__(self, pre_blank_ms=5, post_blank_ms=20, fsample=1000):
        self.pre_blank_samples = int(pre_blank_ms * fsample / 1000)
        self.post_blank_samples = int(post_blank_ms * fsample / 1000)
        self.fsample = fsample
        
        # Blanking state
        self.blanking_counter = 0
        self.is_blanking = False
    
    def trigger_blank(self):
        """Trigger a blanking window (call when motor actuation starts)."""
        self.blanking_counter = self.post_blank_samples
        self.is_blanking = True
    
    def apply(self, data):
        """
        Apply blanking to EMG data.
        
        Parameters:
        -----------
        data : np.ndarray
            EMG sample(s)
            
        Returns:
        --------
        filtered : np.ndarray
            Data with blanked regions set to zero
        """
        if self.is_blanking:
            self.blanking_counter -= 1
            if self.blanking_counter <= 0:
                self.is_blanking = False
            return np.zeros_like(data)
        return data


# =============================================================================
# SCI-Specific Filters
# =============================================================================

class SpasticityDetector:
    """
    Spasticity and involuntary contraction detector for SCI patients.
    
    Detects stretch-reflex triggered spasms by monitoring for sudden,
    high-amplitude EMG bursts that follow exoskeleton movement. These
    should be suppressed to prevent positive feedback loops.
    
    Parameters:
    -----------
    n_channels : int
        Number of EMG channels
    fsample : float
        Sampling frequency in Hz
    threshold_factor : float
        Factor above baseline RMS to detect spasm (default 3.0 = 3x baseline)
    rise_time_ms : float
        Maximum rise time for spasm detection (milliseconds)
    refractory_ms : float
        Refractory period after spasm detection (milliseconds)
    """
    
    def __init__(self, n_channels, fsample=1000, threshold_factor=3.0, 
                 rise_time_ms=50, refractory_ms=500):
        self.n_channels = n_channels
        self.fsample = fsample
        self.threshold_factor = threshold_factor
        self.rise_time_samples = int(rise_time_ms * fsample / 1000)
        self.refractory_samples = int(refractory_ms * fsample / 1000)
        
        # Baseline tracking (adaptive)
        self.baseline_rms = np.ones(n_channels) * 0.01  # Small initial value
        self.baseline_alpha = 0.001  # Slow adaptation for baseline
        
        # Detection state
        self.recent_rms = deque(maxlen=self.rise_time_samples)
        self.refractory_counter = 0
        self.spasm_detected = False
        self.last_exo_movement_time = 0
    
    def notify_exo_movement(self, current_time):
        """
        Notify detector that exoskeleton has moved.
        Spasms detected shortly after this are likely reflexive.
        
        Parameters:
        -----------
        current_time : float
            Current timestamp
        """
        self.last_exo_movement_time = current_time
    
    def update(self, emg_sample, current_time):
        """
        Update detector with new EMG sample.
        
        Parameters:
        -----------
        emg_sample : np.ndarray
            Current EMG sample (n_channels,)
        current_time : float
            Current timestamp
            
        Returns:
        --------
        is_spasm : bool
            True if spasm detected (signal should be suppressed)
        confidence : float
            Confidence of spasm detection (0-1)
        """
        # Calculate current RMS
        current_rms = np.sqrt(np.mean(emg_sample ** 2))
        self.recent_rms.append(current_rms)
        
        # Update baseline (only when not in spasm)
        if not self.spasm_detected and self.refractory_counter == 0:
            self.baseline_rms = (1 - self.baseline_alpha) * self.baseline_rms + \
                               self.baseline_alpha * np.abs(emg_sample)
        
        # Refractory period handling
        if self.refractory_counter > 0:
            self.refractory_counter -= 1
            return self.spasm_detected, 0.5
        
        # Spasm detection criteria:
        # 1. Rapid rise in amplitude
        # 2. Amplitude exceeds threshold
        # 3. Occurred shortly after exoskeleton movement
        
        mean_baseline_rms = np.mean(self.baseline_rms)
        threshold = mean_baseline_rms * self.threshold_factor
        
        # Check for rapid rise
        if len(self.recent_rms) >= 2:
            rise_rate = (current_rms - self.recent_rms[0]) / len(self.recent_rms)
            rapid_rise = rise_rate > (threshold / self.rise_time_samples)
        else:
            rapid_rise = False
        
        # Check amplitude threshold
        above_threshold = current_rms > threshold
        
        # Check temporal proximity to exo movement (within 200ms)
        near_exo_movement = (current_time - self.last_exo_movement_time) < 0.2
        
        # Detect spasm
        if above_threshold and rapid_rise and near_exo_movement:
            self.spasm_detected = True
            self.refractory_counter = self.refractory_samples
            confidence = min(1.0, current_rms / threshold)
            return True, confidence
        
        self.spasm_detected = False
        return False, 0.0
    
    def reset(self):
        """Reset detector state."""
        self.baseline_rms = np.ones(self.n_channels) * 0.01
        self.recent_rms.clear()
        self.refractory_counter = 0
        self.spasm_detected = False


class FatigueCompensator:
    """
    Fatigue compensation for SCI patients.
    
    SCI patients fatigue rapidly. This module tracks the decline in EMG
    amplitude over time and adjusts the decoding threshold accordingly
    to maintain consistent control.
    
    Parameters:
    -----------
    n_channels : int
        Number of EMG channels
    window_sec : float
        Window size for fatigue estimation (seconds)
    fsample : float
        Sampling frequency in Hz
    compensation_rate : float
        Maximum compensation factor (e.g., 2.0 = can double sensitivity)
    """
    
    def __init__(self, n_channels, window_sec=30, fsample=1000, compensation_rate=2.0):
        self.n_channels = n_channels
        self.window_samples = int(window_sec * fsample)
        self.fsample = fsample
        self.max_compensation = compensation_rate
        
        # Track amplitude history
        self.amplitude_history = deque(maxlen=self.window_samples)
        
        # Initial baseline (set during first few seconds)
        self.initial_baseline = None
        self.baseline_samples = int(5 * fsample)  # 5 second baseline
        self.baseline_buffer = []
        
        # Compensation factor
        self.compensation_factor = 1.0
    
    def update(self, emg_rms):
        """
        Update fatigue tracker with new RMS value.
        
        Parameters:
        -----------
        emg_rms : float
            Current RMS value of EMG signal
            
        Returns:
        --------
        compensation_factor : float
            Factor to multiply prediction confidence by
        fatigue_level : float
            Estimated fatigue level (0-1, where 1 = fully fatigued)
        """
        # Build initial baseline
        if self.initial_baseline is None:
            self.baseline_buffer.append(emg_rms)
            if len(self.baseline_buffer) >= self.baseline_samples:
                self.initial_baseline = np.mean(self.baseline_buffer)
                self.baseline_buffer = []  # Free memory
            return 1.0, 0.0
        
        # Track amplitude
        self.amplitude_history.append(emg_rms)
        
        if len(self.amplitude_history) < 100:
            return 1.0, 0.0
        
        # Calculate current mean amplitude
        current_amplitude = np.mean(list(self.amplitude_history)[-100:])
        
        # Estimate fatigue as amplitude drop
        if self.initial_baseline > 0:
            amplitude_ratio = current_amplitude / self.initial_baseline
            fatigue_level = max(0, 1 - amplitude_ratio)
            
            # Calculate compensation (inverse of amplitude drop, capped)
            if amplitude_ratio > 0.1:  # Prevent extreme compensation
                self.compensation_factor = min(self.max_compensation, 
                                              1.0 / amplitude_ratio)
            else:
                self.compensation_factor = self.max_compensation
        else:
            fatigue_level = 0.0
            self.compensation_factor = 1.0
        
        return self.compensation_factor, fatigue_level
    
    def reset(self):
        """Reset fatigue tracker."""
        self.amplitude_history.clear()
        self.initial_baseline = None
        self.baseline_buffer = []
        self.compensation_factor = 1.0


class MotionArtifactDetector:
    """
    Detects motion artifacts from electrode movement/pressure changes.
    
    Motion artifacts typically appear as low-frequency, high-amplitude
    signals that differ from voluntary EMG patterns.
    
    Parameters:
    -----------
    n_channels : int
        Number of EMG channels
    fsample : float
        Sampling frequency
    artifact_threshold : float
        Threshold for artifact detection (in units of baseline std)
    """
    
    def __init__(self, n_channels, fsample=1000, artifact_threshold=5.0):
        self.n_channels = n_channels
        self.fsample = fsample
        self.artifact_threshold = artifact_threshold
        
        # Low-pass filter for detecting low-frequency artifacts
        self.b_lp, self.a_lp, self.zi_lp = self._create_lowpass(cutoff=20, fs=fsample)
        self.zi_lp = np.transpose(np.array([self.zi_lp for _ in range(n_channels)]))
        
        # Baseline statistics
        self.baseline_std = np.ones(n_channels) * 0.01
        self.alpha = 0.001
    
    def _create_lowpass(self, cutoff, fs, order=2):
        """Create lowpass filter for artifact detection."""
        nyq = fs / 2
        low = cutoff / nyq
        b, a = butter(order, low, btype='low')
        zi = lfilter_zi(b, a)
        return b, a, zi
    
    def detect(self, data):
        """
        Detect motion artifacts in EMG data.
        
        Parameters:
        -----------
        data : np.ndarray
            EMG data (n_samples, n_channels)
            
        Returns:
        --------
        is_artifact : np.ndarray
            Boolean array indicating artifact samples
        artifact_mask : np.ndarray
            Soft mask (0-1) for artifact suppression
        """
        # Apply lowpass to isolate low-frequency component
        lf_component, self.zi_lp = lfilter(self.b_lp, self.a_lp, data, axis=0, zi=self.zi_lp)
        
        # Detect artifacts as samples where LF component exceeds threshold
        lf_amplitude = np.abs(lf_component)
        threshold = self.baseline_std * self.artifact_threshold
        
        is_artifact = np.any(lf_amplitude > threshold, axis=1)
        
        # Create soft mask
        artifact_mask = np.ones(len(data))
        artifact_mask[is_artifact] = 0.0
        
        # Update baseline (only on clean samples)
        clean_mask = ~is_artifact
        if np.any(clean_mask):
            clean_std = np.std(data[clean_mask], axis=0)
            self.baseline_std = (1 - self.alpha) * self.baseline_std + self.alpha * clean_std
        
        return is_artifact, artifact_mask
    
    def reset(self):
        """Reset detector state."""
        self.baseline_std = np.ones(self.n_channels) * 0.01