#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
emg_visualizer.py - Enhanced visualization for EMG signals
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, Slider, CheckButtons
import logging
from scipy import signal
import time

logger = logging.getLogger('EMGVisualizer')

class EMGVisualizer:
    """Enhanced visualization for EMG signals with multiple view options."""
    
    def __init__(self, channel_count=8, sampling_rate=1000):
        """Initialize the EMG visualizer.
        
        Args:
            channel_count (int): Number of EMG channels
            sampling_rate (int): Sampling rate in Hz
        """
        self.channel_count = channel_count
        self.sampling_rate = sampling_rate
        self.time_window = 1.0  # seconds to display
        
        # Figure and axes
        self.fig = None
        self.axes = []
        
        # View modes
        self.view_mode = "time"  # time, spectrogram, envelope
        self.envelope_window_size = 50
        self.spectrogram_resolution = 256
        self.visible_channels = list(range(channel_count))
        
        # Data
        self.raw_data = [[] for _ in range(channel_count)]
        self.envelope_data = [[] for _ in range(channel_count)]
        self.spectrogram_data = [None for _ in range(channel_count)]
        
        # Plot elements
        self.signal_lines = []
        self.envelope_lines = []
        self.spectrogram_images = []
        self.gesture_text = None
        self.status_text = None
        
        # Animation
        self.animation = None
        self.artists_to_update = []
        
        # Time axis data for plotting
        samples_to_show = int(self.time_window * sampling_rate)
        self.time_points = np.linspace(0, self.time_window, samples_to_show)
        
        # Color maps
        self.colors = plt.cm.tab10(np.linspace(0, 1, 10))
        self.spectrogram_cmap = 'viridis'
        
        # Status messages
        self.status_message = ""
        self.status_time = 0
        self.status_duration = 3.0  # seconds to show status messages
    
    def setup(self, figure_size=(12, 8)):
        """Set up the visualization.
        
        Args:
            figure_size (tuple): Width, height of the figure in inches
            
        Returns:
            matplotlib.Figure: The created figure
        """
        # Create figure
        self.fig = plt.figure(figsize=figure_size)
        self.fig.canvas.manager.set_window_title('EMG Signal Visualization')
        
        # Main layout
        gs = plt.GridSpec(3, 4, height_ratios=[2, 1, 0.3], figure=self.fig)
        
        # Signal axes
        self.signal_ax = self.fig.add_subplot(gs[0, :])
        self.signal_ax.set_title('EMG Signals')
        self.signal_ax.set_ylabel('Amplitude')
        self.signal_ax.set_xlabel('Time (s)')
        self.signal_ax.grid(True)
        
        # Initialize signal lines
        self.signal_lines = []
        for ch in range(self.channel_count):
            line, = self.signal_ax.plot([], [], label=f'Ch {ch+1}', 
                                       color=self.colors[ch % len(self.colors)])
            self.signal_lines.append(line)
        
        self.signal_ax.legend(loc='upper right', fontsize='x-small')
        
        # Envelope axes
        self.envelope_ax = self.fig.add_subplot(gs[1, :2])
        self.envelope_ax.set_title('Signal Envelopes')
        self.envelope_ax.set_ylabel('RMS Amplitude')
        self.envelope_ax.set_xlabel('Time (s)')
        self.envelope_ax.grid(True)
        
        # Initialize envelope lines
        self.envelope_lines = []
        for ch in range(self.channel_count):
            line, = self.envelope_ax.plot([], [], label=f'Ch {ch+1}', 
                                         color=self.colors[ch % len(self.colors)])
            self.envelope_lines.append(line)
        
        # Spectrogram axes
        self.spec_ax = self.fig.add_subplot(gs[1, 2:])
        self.spec_ax.set_title('Spectrogram')
        self.spec_ax.set_ylabel('Frequency (Hz)')
        self.spec_ax.set_xlabel('Time (s)')
        
        # Information panel
        self.info_ax = self.fig.add_subplot(gs[2, :2])
        self.info_ax.set_title('Information')
        self.info_ax.set_axis_off()
        
        self.gesture_text = self.info_ax.text(0.05, 0.6, 'Gesture: None', 
                                            fontsize=12)
        self.status_text = self.info_ax.text(0.05, 0.2, '', fontsize=10, 
                                           color='blue')
        
        # Control panel
        self.control_ax = self.fig.add_subplot(gs[2, 2:])
        self.control_ax.set_title('Controls')
        self.control_ax.set_axis_off()
        
        # Add channel visibility checkboxes
        check_ax = plt.axes([0.7, 0.02, 0.15, 0.12])
        channel_labels = [f'Ch {ch+1}' for ch in range(min(8, self.channel_count))]
        visibility = [True] * min(8, self.channel_count)
        self.channel_check = CheckButtons(check_ax, channel_labels, visibility)
        self.channel_check.on_clicked(self._update_channel_visibility)
        
        # Add view mode buttons
        mode_ax_time = plt.axes([0.53, 0.08, 0.12, 0.05])
        self.time_button = Button(mode_ax_time, 'Time')
        self.time_button.on_clicked(lambda event: self.set_view_mode('time'))
        
        mode_ax_env = plt.axes([0.53, 0.03, 0.12, 0.05])
        self.env_button = Button(mode_ax_env, 'Envelope')
        self.env_button.on_clicked(lambda event: self.set_view_mode('envelope'))
        
        # Apply tight layout to prevent overlapping
        plt.tight_layout(pad=0.5, h_pad=1.5, w_pad=1.5)
        
        # Initialize artists to update
        self.artists_to_update = self.signal_lines + self.envelope_lines + [self.gesture_text, self.status_text]
        
        return self.fig
    
    def add_data(self, raw_data):
        """Add new data to the visualizer.
        
        Args:
            raw_data (numpy.ndarray): Raw EMG data (channels, samples) or (samples, channels)
            
        Returns:
            bool: True if data was added successfully
        """
        try:
            # Check data shape and transpose if needed
            if isinstance(raw_data, np.ndarray):
                if raw_data.ndim == 2:
                    if raw_data.shape[0] == self.channel_count:
                        # (channels, samples) format
                        data = raw_data
                    else:
                        # (samples, channels) format - transpose
                        data = raw_data.T
                else:
                    # One channel only
                    data = raw_data.reshape(1, -1)
            else:
                # List of arrays or similar
                data = np.array(raw_data)
            
            # Add raw data to buffers
            for ch in range(min(self.channel_count, data.shape[0])):
                self.raw_data[ch].extend(data[ch])
                
                # Keep buffer to a reasonable size
                max_samples = int(5.0 * self.sampling_rate)  # 5 seconds of data
                if len(self.raw_data[ch]) > max_samples:
                    self.raw_data[ch] = self.raw_data[ch][-max_samples:]
            
            # Calculate envelopes
            self._calculate_envelopes()
            
            # Calculate spectrograms
            if self.view_mode == 'spectrogram':
                self._calculate_spectrograms()
            
            return True
        except Exception as e:
            logger.error(f"Error adding data to visualizer: {str(e)}")
            return False
    
    def _calculate_envelopes(self):
        """Calculate RMS envelopes for all channels."""
        for ch in range(self.channel_count):
            data = self.raw_data[ch]
            if len(data) < self.envelope_window_size:
                continue
                
            # Calculate envelope using RMS method
            envelope = []
            for i in range(0, len(data) - self.envelope_window_size + 1, self.envelope_window_size // 2):
                window = data[i:i + self.envelope_window_size]
                rms = np.sqrt(np.mean(np.square(window)))
                envelope.append(rms)
            
            self.envelope_data[ch] = envelope
    
    def _calculate_spectrograms(self):
        """Calculate spectrograms for all channels."""
        for ch in range(self.channel_count):
            data = self.raw_data[ch]
            
            # Need enough data to compute a meaningful spectrogram
            if len(data) < self.sampling_rate // 2:
                continue
                
            try:
                # Calculate spectrogram
                f, t, Sxx = signal.spectrogram(
                    data,
                    fs=self.sampling_rate,
                    window='hann',
                    nperseg=self.spectrogram_resolution,
                    noverlap=self.spectrogram_resolution // 2,
                    scaling='spectrum'
                )
                
                # Convert to dB
                Sxx = 10 * np.log10(Sxx + 1e-10)
                
                self.spectrogram_data[ch] = (f, t, Sxx)
            except Exception as e:
                logger.error(f"Error calculating spectrogram for channel {ch}: {str(e)}")
    
    def update(self, frame=None):
        """Update the visualization with current data.
        
        Returns:
            list: Updated artists
        """
        if not self.fig:
            logger.warning("Visualization not set up. Call setup() first.")
            return []
            
        try:
            # Update based on view mode
            if self.view_mode == 'time':
                self._update_time_view()
            elif self.view_mode == 'envelope':
                self._update_envelope_view()
            elif self.view_mode == 'spectrogram':
                self._update_spectrogram_view()
                
            # Update status text
            if self.status_message and time.time() - self.status_time < self.status_duration:
                self.status_text.set_text(self.status_message)
                self.status_text.set_visible(True)
            else:
                self.status_text.set_visible(False)
                
            return self.artists_to_update
            
        except Exception as e:
            logger.error(f"Error updating visualization: {str(e)}")
            return []
    
    def _update_time_view(self):
        """Update the time-domain signal view."""
        samples_to_show = int(self.time_window * self.sampling_rate)
        
        for ch in range(self.channel_count):
            if ch in self.visible_channels and self.signal_lines[ch].get_visible():
                data = self.raw_data[ch]
                if len(data) > 0:
                    # Show the most recent data
                    recent_data = data[-samples_to_show:]
                    
                    # Create time points
                    t = np.linspace(0, len(recent_data) / self.sampling_rate, len(recent_data))
                    
                    # Update line
                    self.signal_lines[ch].set_data(t, recent_data)
                else:
                    self.signal_lines[ch].set_data([], [])
        
        # Adjust y-axis to fit data
        self.signal_ax.relim()
        self.signal_ax.autoscale_view()
    
    def _update_envelope_view(self):
        """Update the envelope view."""
        for ch in range(self.channel_count):
            if ch in self.visible_channels and self.envelope_lines[ch].get_visible():
                env_data = self.envelope_data[ch]
                if len(env_data) > 0:
                    # Create time points
                    t = np.linspace(0, len(env_data) * (self.envelope_window_size / 2) / self.sampling_rate, len(env_data))
                    
                    # Update line
                    self.envelope_lines[ch].set_data(t, env_data)
                else:
                    self.envelope_lines[ch].set_data([], [])
        
        # Adjust y-axis to fit data
        self.envelope_ax.relim()
        self.envelope_ax.autoscale_view()
    
    def _update_spectrogram_view(self):
        """Update the spectrogram view."""
        # Find first visible channel with data
        for ch in self.visible_channels:
            if self.spectrogram_data[ch] is not None:
                f, t, Sxx = self.spectrogram_data[ch]
                
                # Clear previous spectrogram
                self.spec_ax.clear()
                
                # Plot spectrogram
                self.spec_ax.pcolormesh(t, f, Sxx, shading='gouraud', cmap=self.spectrogram_cmap)
                self.spec_ax.set_ylabel('Frequency (Hz)')
                self.spec_ax.set_xlabel('Time (s)')
                self.spec_ax.set_title(f'Spectrogram - Channel {ch+1}')
                
                # Limit frequency display to a reasonable range
                max_freq = min(500, self.sampling_rate / 2)
                self.spec_ax.set_ylim(0, max_freq)
                
                break
    
    def set_view_mode(self, mode):
        """Set the visualization mode.
        
        Args:
            mode (str): One of 'time', 'envelope', 'spectrogram'
        """
        if mode in ['time', 'envelope', 'spectrogram']:
            self.view_mode = mode
            self.set_status_message(f"View mode: {mode.capitalize()}")
            
            if mode == 'spectrogram':
                self._calculate_spectrograms()
    
    def _update_channel_visibility(self, label):
        """Update the visibility of channels based on checkboxes."""
        ch_num = int(label.split(' ')[1]) - 1
        
        if ch_num < self.channel_count:
            if ch_num in self.visible_channels:
                self.visible_channels.remove(ch_num)
                self.signal_lines[ch_num].set_visible(False)
                self.envelope_lines[ch_num].set_visible(False)
            else:
                self.visible_channels.append(ch_num)
                self.signal_lines[ch_num].set_visible(True)
                self.envelope_lines[ch_num].set_visible(True)
    
    def set_gesture(self, gesture, confidence=None):
        """Set the current recognized gesture.
        
        Args:
            gesture (str): Name of the recognized gesture
            confidence (float, optional): Confidence level (0-1)
        """
        if gesture:
            # Format the text
            if confidence is not None:
                text = f"Gesture: {gesture}\nConfidence: {confidence:.2f}"
            else:
                text = f"Gesture: {gesture}"
                
            self.gesture_text.set_text(text)
    
    def set_status_message(self, message, duration=3.0):
        """Set a temporary status message.
        
        Args:
            message (str): Status message to display
            duration (float): How long to display the message in seconds
        """
        self.status_message = message
        self.status_time = time.time()
        self.status_duration = duration
    
    def start_animation(self, interval=50):
        """Start the animation for real-time updates.
        
        Args:
            interval (int): Update interval in milliseconds
            
        Returns:
            matplotlib.animation.FuncAnimation: Animation object
        """
        if self.fig and not self.animation:
            self.animation = animation.FuncAnimation(
                self.fig, self.update, 
                interval=interval, blit=True
            )
        return self.animation
    
    def show(self, block=True):
        """Show the visualization.
        
        Args:
            block (bool): Whether to block execution
        """
        if not self.fig:
            self.setup()
            
        plt.show(block=block)
    
    def close(self):
        """Close the visualization."""
        if self.fig:
            plt.close(self.fig)
            self.fig = None
            self.animation = None
