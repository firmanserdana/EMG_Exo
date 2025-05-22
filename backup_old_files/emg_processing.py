#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Processing
Handles signal processing and feature extraction for EMG signals.
"""

import numpy as np
import scipy.signal as signal
from scipy.fft import fft, fftfreq
import matplotlib.pyplot as plt
from multiprocessing import Process, Queue
import time
import logging

from ini import EMG_PROCESSING, logger


class EMGProcessor:
    """Process EMG signals for feature extraction and analysis."""
    
    def __init__(self, channel_count=8, sampling_rate=2000):
        """Initialize EMG processor.
        
        Args:
            channel_count (int): Number of EMG channels
            sampling_rate (int): Sampling rate in Hz
        """
        # Configuration
        self.channel_count = channel_count
        self.sampling_rate = sampling_rate
        
        # Signal buffers for each channel
        self.buffer_size = int(EMG_PROCESSING["buffer_time"] * sampling_rate)
        self.raw_buffers = [[] for _ in range(channel_count)]
        self.processed_buffers = [[] for _ in range(channel_count)]
        
        # Processing settings from config
        self.hp_cutoff = EMG_PROCESSING["highpass_cutoff"]
        self.lp_cutoff = EMG_PROCESSING["lowpass_cutoff"]
        self.notch_freq = EMG_PROCESSING["notch_freq"]
        self.notch_quality = EMG_PROCESSING["notch_quality"]
        
        # Prepare filters
        self._prepare_filters()
        
        # Feature extraction settings
        self.feature_window = int(EMG_PROCESSING["feature_window"] * sampling_rate)
        self.feature_overlap = EMG_PROCESSING["feature_overlap"]
        self.features_enabled = EMG_PROCESSING["features_enabled"]
        
        logger.info(f"EMG Processor initialized with {channel_count} channels at {sampling_rate} Hz")
        logger.info(f"Buffer size: {self.buffer_size} samples ({EMG_PROCESSING['buffer_time']} seconds)")
        logger.info(f"Feature window: {self.feature_window} samples ({EMG_PROCESSING['feature_window']} seconds)")
    
    def _prepare_filters(self):
        """Prepare filter coefficients."""
        nyquist = 0.5 * self.sampling_rate
        
        # High-pass filter
        self.hp_b, self.hp_a = signal.butter(
            2, self.hp_cutoff / nyquist, btype='high', analog=False
        )
        
        # Low-pass filter
        self.lp_b, self.lp_a = signal.butter(
            4, self.lp_cutoff / nyquist, btype='low', analog=False
        )
        
        # Notch filter (for power line noise)
        self.notch_b, self.notch_a = signal.iirnotch(
            self.notch_freq, self.notch_quality, self.sampling_rate
        )
        
        # Filter states for continuous filtering
        self.hp_zi = [signal.lfilter_zi(self.hp_b, self.hp_a) for _ in range(self.channel_count)]
        self.lp_zi = [signal.lfilter_zi(self.lp_b, self.lp_a) for _ in range(self.channel_count)]
        self.notch_zi = [signal.lfilter_zi(self.notch_b, self.notch_a) for _ in range(self.channel_count)]
    
    def add_samples(self, samples):
        """Add EMG samples to the processing buffer.
        
        Args:
            samples: 2D array or list of lists, shape (n_samples, n_channels)
                EMG samples to process
                
        Returns:
            list: Processed samples for each channel
        """
        samples = np.asarray(samples)
        
        # Check if samples are in the right format
        if len(samples.shape) == 1 and self.channel_count == 1:
            # Single channel input as 1D array
            samples = samples.reshape(-1, 1)
        elif len(samples.shape) == 1:
            # Single sample for multiple channels
            samples = samples.reshape(1, -1)
        
        # Sanity check
        if samples.shape[1] != self.channel_count:
            logger.warning(f"Sample channel count mismatch: got {samples.shape[1]}, expected {self.channel_count}")
            # Try to adapt
            if samples.shape[1] > self.channel_count:
                samples = samples[:, :self.channel_count]
            else:
                # Pad with zeros
                padding = np.zeros((samples.shape[0], self.channel_count - samples.shape[1]))
                samples = np.hstack((samples, padding))
        
        # Process each channel
        processed_samples = []
        
        for ch in range(self.channel_count):
            # Get samples for this channel
            ch_samples = samples[:, ch]
            
            # Add to raw buffer and maintain buffer size
            self.raw_buffers[ch].extend(ch_samples)
            if len(self.raw_buffers[ch]) > self.buffer_size:
                self.raw_buffers[ch] = self.raw_buffers[ch][-self.buffer_size:]
            
            # Filter the new samples
            filtered_samples = self._filter_samples(ch_samples, ch)
            
            # Add to processed buffer and maintain buffer size
            self.processed_buffers[ch].extend(filtered_samples)
            if len(self.processed_buffers[ch]) > self.buffer_size:
                self.processed_buffers[ch] = self.processed_buffers[ch][-self.buffer_size:]
            
            processed_samples.append(filtered_samples)
        
        return processed_samples
    
    def _filter_samples(self, samples, channel):
        """Apply filters to the samples for a specific channel.
        
        Args:
            samples: 1D array, EMG samples for one channel
            channel (int): Channel index
            
        Returns:
            list: Filtered samples
        """
        samples = np.asarray(samples)
        
        # Apply high-pass filter with state
        samples, self.hp_zi[channel] = signal.lfilter(
            self.hp_b, self.hp_a, samples, zi=self.hp_zi[channel] * samples[0]
        )
        
        # Apply notch filter with state
        samples, self.notch_zi[channel] = signal.lfilter(
            self.notch_b, self.notch_a, samples, zi=self.notch_zi[channel] * samples[0]
        )
        
        # Apply low-pass filter with state
        samples, self.lp_zi[channel] = signal.lfilter(
            self.lp_b, self.lp_a, samples, zi=self.lp_zi[channel] * samples[0]
        )
        
        return samples.tolist()
    
    def extract_features(self, window=None):
        """Extract features from the processed EMG data.
        
        Args:
            window (tuple): Optional (start, end) tuple to specify window in samples
                If None, uses the entire buffer
                
        Returns:
            dict: Dictionary of features with keys:
                - 'rms': Root Mean Square value for each channel
                - 'mav': Mean Absolute Value for each channel
                - 'zc': Zero Crossing rate for each channel
                - 'ssc': Slope Sign Changes for each channel
                - 'wl': Waveform Length for each channel
                - 'var': Variance for each channel
                - 'freq_mean': Mean frequency for each channel
                - 'freq_median': Median frequency for each channel
                - 'freq_power': Total power for each channel
        """
        features = {}
        
        # Use default window if not specified
        if window is None:
            window = (0, len(self.processed_buffers[0]))
        
        for ch in range(self.channel_count):
            # Get data for this channel within window
            data = np.array(self.processed_buffers[ch][window[0]:window[1]])
            
            if len(data) == 0:
                continue  # Skip if no data
            
            # Time domain features
            if 'rms' in self.features_enabled:
                if 'rms' not in features:
                    features['rms'] = []
                features['rms'].append(np.sqrt(np.mean(data**2)))
            
            if 'mav' in self.features_enabled:
                if 'mav' not in features:
                    features['mav'] = []
                features['mav'].append(np.mean(np.abs(data)))
            
            if 'zc' in self.features_enabled:
                if 'zc' not in features:
                    features['zc'] = []
                # Zero crossings with threshold
                threshold = 0.01 * np.std(data)
                zero_crossings = np.sum(np.diff(np.signbit(data)) & (np.abs(np.diff(data)) > threshold))
                features['zc'].append(zero_crossings)
            
            if 'ssc' in self.features_enabled:
                if 'ssc' not in features:
                    features['ssc'] = []
                # Slope sign changes with threshold
                threshold = 0.01 * np.std(data)
                ssc = 0
                for i in range(1, len(data) - 1):
                    if ((data[i] > data[i-1] and data[i] > data[i+1]) or 
                        (data[i] < data[i-1] and data[i] < data[i+1])):
                        if (abs(data[i] - data[i-1]) > threshold or 
                            abs(data[i] - data[i+1]) > threshold):
                            ssc += 1
                features['ssc'].append(ssc)
            
            if 'wl' in self.features_enabled:
                if 'wl' not in features:
                    features['wl'] = []
                # Waveform length (sum of absolute changes)
                features['wl'].append(np.sum(np.abs(np.diff(data))))
            
            if 'var' in self.features_enabled:
                if 'var' not in features:
                    features['var'] = []
                features['var'].append(np.var(data))
            
            # Frequency domain features
            if any(f in self.features_enabled for f in ['freq_mean', 'freq_median', 'freq_power']):
                # Compute FFT
                # Apply window to reduce spectral leakage
                windowed_data = data * np.hanning(len(data))
                fft_values = fft(windowed_data)
                fft_magnitude = np.abs(fft_values[:len(data)//2])
                frequencies = fftfreq(len(data), 1/self.sampling_rate)[:len(data)//2]
                
                # Only consider frequencies in EMG range (typically 5-500 Hz)
                mask = (frequencies >= 5) & (frequencies <= 500)
                fft_magnitude = fft_magnitude[mask]
                frequencies = frequencies[mask]
                
                if len(frequencies) > 0:
                    if 'freq_mean' in self.features_enabled:
                        if 'freq_mean' not in features:
                            features['freq_mean'] = []
                        # Mean frequency
                        features['freq_mean'].append(np.average(frequencies, weights=fft_magnitude))
                    
                    if 'freq_median' in self.features_enabled:
                        if 'freq_median' not in features:
                            features['freq_median'] = []
                        # Median frequency
                        cum_sum = np.cumsum(fft_magnitude)
                        half_power = cum_sum[-1] / 2.0
                        median_idx = np.argmin(np.abs(cum_sum - half_power))
                        features['freq_median'].append(frequencies[median_idx])
                    
                    if 'freq_power' in self.features_enabled:
                        if 'freq_power' not in features:
                            features['freq_power'] = []
                        # Total power
                        features['freq_power'].append(np.sum(fft_magnitude**2))
        
        return features
    
    def extract_windowed_features(self, window_size=None, overlap=None, align_end=True):
        """Extract features from multiple windows with overlap.
        
        Args:
            window_size (int): Window size in samples
                If None, uses self.feature_window
            overlap (float): Overlap ratio between windows (0.0-1.0)
                If None, uses self.feature_overlap
            align_end (bool): If True, aligns windows to the end of the buffer
                
        Returns:
            list: List of feature dictionaries for each window
        """
        if window_size is None:
            window_size = self.feature_window
        
        if overlap is None:
            overlap = self.feature_overlap
        
        # Ensure we have enough data
        buffer_length = len(self.processed_buffers[0])
        if buffer_length < window_size:
            return []
        
        # Calculate step size between windows
        step = int(window_size * (1 - overlap))
        if step <= 0:
            step = 1  # Ensure at least 1 sample step
        
        # Calculate window positions
        if align_end:
            # Start from the end and work backward
            start_positions = list(range(buffer_length - window_size, -1, -step))
            start_positions.reverse()  # Order from oldest to newest
        else:
            # Start from the beginning
            start_positions = list(range(0, buffer_length - window_size + 1, step))
        
        # Extract features for each window
        windowed_features = []
        for start in start_positions:
            window = (start, start + window_size)
            features = self.extract_features(window)
            windowed_features.append(features)
        
        return windowed_features
    
    def calculate_envelopes(self, window_size=None, method='rms'):
        """Calculate signal envelopes for each channel.
        
        Args:
            window_size (int): Window size for envelope calculation
                If None, uses 100ms window
            method (str): Envelope detection method ('rms', 'mav', or 'hilbert')
                
        Returns:
            list: List of envelope values for each channel
        """
        if window_size is None:
            window_size = int(0.1 * self.sampling_rate)  # 100ms window
        
        envelopes = []
        
        for ch in range(self.channel_count):
            data = np.array(self.processed_buffers[ch])
            
            if len(data) == 0:
                envelopes.append([])
                continue
            
            if method == 'rms':
                # Root Mean Square envelope
                envelope = []
                for i in range(len(data)):
                    start = max(0, i - window_size // 2)
                    end = min(len(data), i + window_size // 2)
                    window_data = data[start:end]
                    if len(window_data) > 0:
                        envelope.append(np.sqrt(np.mean(window_data**2)))
                    else:
                        envelope.append(0)
            
            elif method == 'mav':
                # Mean Absolute Value envelope
                envelope = []
                for i in range(len(data)):
                    start = max(0, i - window_size // 2)
                    end = min(len(data), i + window_size // 2)
                    window_data = data[start:end]
                    if len(window_data) > 0:
                        envelope.append(np.mean(np.abs(window_data)))
                    else:
                        envelope.append(0)
            
            elif method == 'hilbert':
                # Hilbert transform envelope
                analytic_signal = signal.hilbert(data)
                envelope = np.abs(analytic_signal)
                
                # Apply low-pass filter to smooth the envelope
                b, a = signal.butter(2, 10 / (self.sampling_rate / 2), 'low')
                envelope = signal.filtfilt(b, a, envelope)
                envelope = envelope.tolist()
            
            else:
                logger.warning(f"Unknown envelope method: {method}")
                envelope = []
            
            envelopes.append(envelope)
        
        return envelopes
    
    def detect_muscle_activity(self, threshold_factor=3.0, min_duration=0.2):
        """Detect muscle activity in the signal.
        
        Args:
            threshold_factor (float): Multiplication factor for the standard deviation
                to use as activity threshold
            min_duration (float): Minimum activity duration in seconds
                
        Returns:
            list: List of activity segments for each channel,
                each segment is a tuple (start_idx, end_idx)
        """
        min_samples = int(min_duration * self.sampling_rate)
        activities = []
        
        for ch in range(self.channel_count):
            data = np.array(self.processed_buffers[ch])
            
            if len(data) == 0:
                activities.append([])
                continue
            
            # Calculate baseline noise
            noise_level = np.std(data[:int(0.1 * len(data))])
            threshold = threshold_factor * noise_level
            
            # Detect activity
            activity = np.abs(data) > threshold
            
            # Find segments
            segments = []
            in_segment = False
            start_idx = 0
            
            for i, active in enumerate(activity):
                if active and not in_segment:
                    # Start of segment
                    in_segment = True
                    start_idx = i
                elif not active and in_segment:
                    # End of segment
                    if i - start_idx >= min_samples:
                        segments.append((start_idx, i))
                    in_segment = False
            
            # Check for activity at end of buffer
            if in_segment and len(data) - start_idx >= min_samples:
                segments.append((start_idx, len(data)))
            
            activities.append(segments)
        
        return activities
    
    def plot_signals(self, raw=True, processed=True, envelopes=True, show=True):
        """Plot the EMG signals for visualization.
        
        Args:
            raw (bool): Whether to plot raw signals
            processed (bool): Whether to plot processed signals
            envelopes (bool): Whether to plot signal envelopes
            show (bool): Whether to show the plot immediately
                
        Returns:
            matplotlib.figure.Figure: The created figure
        """
        n_rows = self.channel_count
        time_raw = np.arange(len(self.raw_buffers[0])) / self.sampling_rate
        time_proc = np.arange(len(self.processed_buffers[0])) / self.sampling_rate
        
        fig, axes = plt.subplots(n_rows, 1, figsize=(10, n_rows * 2), sharex=True)
        if n_rows == 1:
            axes = [axes]  # Make sure axes is iterable
        
        for ch in range(self.channel_count):
            ax = axes[ch]
            
            if raw and len(self.raw_buffers[ch]) > 0:
                ax.plot(time_raw, self.raw_buffers[ch], 'b-', alpha=0.5, label='Raw')
            
            if processed and len(self.processed_buffers[ch]) > 0:
                ax.plot(time_proc, self.processed_buffers[ch], 'g-', alpha=0.7, label='Processed')
            
            if envelopes and len(self.processed_buffers[ch]) > 0:
                env_data = self.calculate_envelopes(method='rms')[ch]
                if len(env_data) > 0:
                    time_env = np.arange(len(env_data)) / self.sampling_rate
                    ax.plot(time_env, env_data, 'r-', linewidth=2, label='Envelope')
            
            ax.set_ylabel(f'CH {ch+1}')
            ax.grid(True, alpha=0.3)
            
            if ch == 0:
                ax.legend(loc='upper right')
        
        axes[-1].set_xlabel('Time (s)')
        fig.tight_layout()
        
        if show:
            plt.show()
        
        return fig
    
    def clear_buffers(self):
        """Clear all signal buffers."""
        self.raw_buffers = [[] for _ in range(self.channel_count)]
        self.processed_buffers = [[] for _ in range(self.channel_count)]
        
        # Reset filter states
        self.hp_zi = [signal.lfilter_zi(self.hp_b, self.hp_a) for _ in range(self.channel_count)]
        self.lp_zi = [signal.lfilter_zi(self.lp_b, self.lp_a) for _ in range(self.channel_count)]
        self.notch_zi = [signal.lfilter_zi(self.notch_b, self.notch_a) for _ in range(self.channel_count)]
    
    def start_background_processing(self, input_queue, output_queue, stop_event=None):
        """Start background processing worker in a separate process.
        
        Args:
            input_queue (Queue): Queue for incoming EMG samples
            output_queue (Queue): Queue for outgoing processed data
            stop_event (Event): Event to signal worker to stop
            
        Returns:
            Process: The background worker process
        """
        # Create process
        worker = Process(
            target=EMGProcessor._background_worker,
            args=(input_queue, output_queue, stop_event,
                  self.channel_count, self.sampling_rate,
                  EMG_PROCESSING)
        )
        
        # Start process
        worker.daemon = True
        worker.start()
        
        return worker
    
    @staticmethod
    def _background_worker(input_queue, output_queue, stop_event, 
                          channel_count, sampling_rate, config):
        """Background worker function for EMG processing.
        
        Args:
            input_queue (Queue): Queue for incoming EMG samples
            output_queue (Queue): Queue for outgoing processed data
            stop_event (Event): Event to signal worker to stop
            channel_count (int): Number of EMG channels
            sampling_rate (int): Sampling rate in Hz
            config (dict): Configuration dictionary
        """
        # Create processor
        processor = EMGProcessor(channel_count, sampling_rate)
        
        # Processing loop
        last_feature_time = time.time()
        
        while stop_event is None or not stop_event.is_set():
            try:
                # Get samples from queue (non-blocking)
                try:
                    samples = input_queue.get(block=False)
                    
                    # Process samples
                    processed = processor.add_samples(samples)
                    
                    # Put processed samples in output queue
                    output_queue.put(("processed", processed))
                    
                except Exception as e:
                    # Queue is empty or other error
                    if not isinstance(e, Queue.Empty):
                        logging.error(f"Error processing samples: {str(e)}")
                    
                    # Sleep a bit to avoid busy waiting
                    time.sleep(0.001)
                
                # Extract features periodically
                current_time = time.time()
                if current_time - last_feature_time >= config["feature_interval"]:
                    # Extract features
                    features = processor.extract_features()
                    
                    # Put features in output queue
                    output_queue.put(("features", features))
                    
                    # Calculate envelopes
                    envelopes = processor.calculate_envelopes()
                    
                    # Put envelopes in output queue
                    output_queue.put(("envelopes", envelopes))
                    
                    # Update last feature time
                    last_feature_time = current_time
            
            except Exception as e:
                logging.error(f"Error in EMG background worker: {str(e)}")
                time.sleep(0.1)
        
        logging.info("EMG background worker stopped")
    
    def preprocess(self, data):
        """Preprocess raw EMG data.
        
        Args:
            data (numpy.ndarray): Raw EMG data with shape (samples, channels) or (channels, samples)
                
        Returns:
            numpy.ndarray: Processed EMG data with shape (samples, channels)
        """
        # Convert to numpy array if not already
        data = np.asarray(data)
        
        # Check if data is in (channels, samples) format and transpose if needed
        if data.shape[0] == self.channel_count and data.shape[1] > data.shape[0]:
            data = data.T  # Transpose to (samples, channels)
        
        # Add the samples to our buffers and process them
        processed = self.add_samples(data)
        
        # Convert processed data to numpy array and return
        return np.array(processed).T  # Return in (samples, channels) format


if __name__ == "__main__":
    # Test script for EMG processor
    import matplotlib.pyplot as plt
    import numpy as np
    
    print("Testing EMG Processor...")
    
    # Create processor
    processor = EMGProcessor(channel_count=8, sampling_rate=2000)
    
    # Generate some test data
    duration = 1.0  # seconds
    num_samples = int(duration * processor.sampling_rate)
    time_points = np.linspace(0, duration, num_samples)
    
    # Generate signals for each channel
    channel_data = []
    
    for ch in range(processor.channel_count):
        # Base frequency for this channel
        base_freq = 50 + ch * 10  # Hz
        
        # Generate sinusoidal signal with noise
        signal = np.sin(2 * np.pi * base_freq * time_points)
        
        # Add muscle activation pattern
        if ch < 4:  # Only for first 4 channels
            # Create muscle activation envelope (contraction)
            envelope = np.zeros_like(time_points)
            start_idx = int(0.2 * num_samples)
            end_idx = int(0.8 * num_samples)
            ramp_samples = int(0.1 * num_samples)
            
            # Ramp up
            envelope[start_idx:start_idx+ramp_samples] = np.linspace(0, 1, ramp_samples)
            # Plateau
            envelope[start_idx+ramp_samples:end_idx-ramp_samples] = 1
            # Ramp down
            envelope[end_idx-ramp_samples:end_idx] = np.linspace(1, 0, ramp_samples)
            
            # Modulate signal amplitude
            signal *= (0.2 + 0.8 * envelope)
        
        # Add higher frequency components
        signal += 0.2 * np.sin(2 * np.pi * base_freq * 2 * time_points)
        signal += 0.1 * np.sin(2 * np.pi * base_freq * 3 * time_points)
        
        # Add noise
        noise = 0.1 * np.random.randn(num_samples)
        signal += noise
        
        # Add power line noise (50 Hz)
        signal += 0.1 * np.sin(2 * np.pi * 50 * time_points)
        
        channel_data.append(signal)
    
    # Transpose to get (samples, channels) format
    test_data = np.column_stack(channel_data)
    
    # Process the data
    print("\nProcessing test data...")
    processed = processor.add_samples(test_data)
    print(f"Processed {len(processed[0])} samples for {len(processed)} channels")
    
    # Extract features
    print("\nExtracting features...")
    features = processor.extract_features()
    for feature_name, values in features.items():
        print(f"{feature_name}: {values}")
    
    # Extract windowed features
    print("\nExtracting windowed features...")
    window_size = int(0.2 * processor.sampling_rate)  # 200 ms windows
    windowed_features = processor.extract_windowed_features(window_size=window_size, overlap=0.5)
    print(f"Extracted features for {len(windowed_features)} windows")
    
    # Calculate envelopes
    print("\nCalculating envelopes...")
    envelopes = processor.calculate_envelopes()
    print(f"Envelope length: {len(envelopes[0])} samples for {len(envelopes)} channels")
    
    # Detect muscle activity
    print("\nDetecting muscle activity...")
    activities = processor.detect_muscle_activity()
    for ch, segments in enumerate(activities):
        print(f"Channel {ch+1}: {len(segments)} activity segments")
        for i, (start, end) in enumerate(segments):
            duration = (end - start) / processor.sampling_rate
            print(f"  Segment {i+1}: {start}-{end} ({duration:.3f} seconds)")
    
    # Plot the signals
    print("\nPlotting signals...")
    processor.plot_signals()