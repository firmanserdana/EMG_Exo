#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple demo application for the EMG Exo system.

This demo illustrates basic usage of the EMG acquisition, processing, and visualization
without requiring physical hardware.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import argparse

# Import core modules
from emg_exo.core.acquisition import create_emg_system
from emg_exo.core.processing import EMGProcessor
from emg_exo.config.config import configure_logging


class EMGExoSimpleDemo:
    """Simple demonstration of EMG acquisition and processing."""
    
    def __init__(self, emg_system_type="simulation"):
        """Initialize the demo.
        
        Args:
            emg_system_type: Type of EMG system to use ('sessantaquatro', 'trigno', or 'simulation')
        """
        # Configure logging
        self.logger = configure_logging()
        self.logger.info("Initializing EMG Exo Simple Demo")
        
        # Initialize EMG system and processor
        self.emg = create_emg_system(emg_system_type)
        self.processor = EMGProcessor()
        
        # Visualization setup
        self.fig, self.axes = plt.subplots(3, 1, figsize=(10, 8))
        self.fig.suptitle("EMG Signal Visualization Demo")
        
        # Data buffers (store a few seconds of data)
        buffer_size = 1000
        self.raw_buffer = np.zeros((buffer_size, 8))  # Show 8 channels
        self.filtered_buffer = np.zeros((buffer_size, 8))
        self.envelope_buffer = np.zeros((buffer_size, 8))
        
        # Animation for real-time plotting
        self.anim = None
        
    def connect(self):
        """Connect to EMG system."""
        self.logger.info("Connecting to EMG system...")
        return self.emg.connect()
        
    def disconnect(self):
        """Disconnect from EMG system."""
        self.logger.info("Disconnecting from EMG system...")
        self.emg.disconnect()
    
    def update_plot(self, frame):
        """Update the visualization plots with new data."""
        try:
            # Get EMG data
            raw_data = self.emg.read()
            
            if raw_data is None or len(raw_data) == 0:
                return
            
            # Process the data
            filtered_data = self.processor.preprocess(raw_data)
            features = self.processor.extract_features(filtered_data)
            envelopes = features.get('rms', np.zeros_like(raw_data))
            
            # Update buffers (roll and append new data)
            self.raw_buffer = np.roll(self.raw_buffer, -1, axis=0)
            self.filtered_buffer = np.roll(self.filtered_buffer, -1, axis=0)
            self.envelope_buffer = np.roll(self.envelope_buffer, -1, axis=0)
            
            # Add new data to buffer (take first 8 channels)
            channels_to_show = min(8, raw_data.shape[0])
            self.raw_buffer[-1, :channels_to_show] = raw_data[:channels_to_show]
            self.filtered_buffer[-1, :channels_to_show] = filtered_data[:channels_to_show]
            self.envelope_buffer[-1, :channels_to_show] = envelopes[:channels_to_show]
            
            # Clear axes
            for ax in self.axes:
                ax.clear()
            
            # Plot data
            time_axis = np.arange(-self.raw_buffer.shape[0] + 1, 1) / self.emg.sampling_rate
            
            # Raw EMG
            self.axes[0].set_title("Raw EMG Signal")
            for i in range(channels_to_show):
                self.axes[0].plot(time_axis, self.raw_buffer[:, i] - i*0.5, 
                                 label=f"Ch {i+1}")
            
            # Filtered EMG
            self.axes[1].set_title("Filtered EMG Signal")
            for i in range(channels_to_show):
                self.axes[1].plot(time_axis, self.filtered_buffer[:, i] - i*0.5, 
                                 label=f"Ch {i+1}")
            
            # Signal envelope
            self.axes[2].set_title("EMG Envelope (RMS)")
            for i in range(channels_to_show):
                self.axes[2].plot(time_axis, self.envelope_buffer[:, i], 
                                 label=f"Ch {i+1}")
                
            # Axis labels
            self.axes[2].set_xlabel("Time (s)")
            for ax in self.axes:
                ax.set_ylabel("Amplitude")
                ax.grid(True)
            
            # Add legend to last plot
            self.axes[2].legend(loc='upper right')
            
        except Exception as e:
            self.logger.error(f"Error updating plot: {e}")
    
    def run_demo(self):
        """Run the demonstration."""
        if not self.connect():
            self.logger.error("Failed to connect to EMG system.")
            return
            
        try:
            # Set up animation
            self.anim = FuncAnimation(
                self.fig, self.update_plot, interval=50, blit=False)
            
            # Display plot
            plt.tight_layout()
            plt.show()
            
        finally:
            # Clean up
            self.disconnect()
            if self.anim:
                self.anim.event_source.stop()


def main():
    """Main entry point for the simple demo application."""
    parser = argparse.ArgumentParser(description="EMG Exo Simple Demonstration")
    parser.add_argument("--emg", choices=["sessantaquatro", "trigno", "simulation"], 
                       default="simulation", help="Type of EMG system to use")
    
    args = parser.parse_args()
    
    # Create and run the demo
    demo = EMGExoSimpleDemo(args.emg)
    demo.run_demo()


if __name__ == "__main__":
    main()
