#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Delsys Trigno Demo Script
This script demonstrates how to use the Delsys Trigno EMG system with the EMG_Exo framework.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
import argparse
from matplotlib.animation import FuncAnimation

from delsys_trigno_emg import DelsysTrignoEMG
from emg_processing import EMGProcessor
from ini import TRIGNO_CONFIG

def real_time_plot(emg, processor, duration=30):
    """Real-time plotting of EMG data.
    
    Args:
        emg: EMG acquisition object
        processor: EMG processing object
        duration: Duration of plotting in seconds
    """
    # Initialize plot
    plt.ion()  # Interactive mode
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Determine which channels to show (up to 8 for readability)
    display_channels = min(8, emg.channels)
    channel_colors = plt.cm.viridis(np.linspace(0, 1, display_channels))
    
    # Set up raw EMG plot
    lines_raw = [ax1.plot([], [], color=channel_colors[i])[0] for i in range(display_channels)]
    ax1.set_title('Raw EMG')
    ax1.set_ylim(-500, 500)
    ax1.set_xlim(0, 1)
    ax1.set_ylabel('Amplitude (μV)')
    ax1.grid(True)
    
    # Set up processed EMG plot
    lines_processed = [ax2.plot([], [], color=channel_colors[i])[0] for i in range(display_channels)]
    ax2.set_title('Processed EMG')
    ax2.set_ylim(-500, 500)
    ax2.set_xlim(0, 1)
    ax2.set_ylabel('Amplitude (μV)')
    ax2.set_xlabel('Time (s)')
    ax2.grid(True)
    
    # Legend for both plots
    ax1.legend([f'Ch {i+1}' for i in range(display_channels)], loc='upper right')
    
    # Adjust layout
    plt.tight_layout()
    
    # Buffer for showing 2 seconds of data
    samples_to_show = int(2.0 * emg.sampling_rate)
    time_vector = np.linspace(0, 2, samples_to_show)
    
    # Data buffers
    raw_buffers = [np.zeros(samples_to_show) for _ in range(display_channels)]
    processed_buffers = [np.zeros(samples_to_show) for _ in range(display_channels)]
    
    start_time = time.time()
    try:
        while (time.time() - start_time) < duration:
            # Get EMG data
            emg_data = emg.get_data(blocking=True, timeout=0.1)
            
            if emg_data is not None:
                # Process data
                processed_data = processor.preprocess(emg_data)
                
                # Update buffers with new data
                samples_received = emg_data.shape[1]
                for ch in range(display_channels):
                    # Shift old data and add new data
                    raw_buffers[ch] = np.roll(raw_buffers[ch], -samples_received)
                    raw_buffers[ch][-samples_received:] = emg_data[ch, :]
                    
                    processed_buffers[ch] = np.roll(processed_buffers[ch], -samples_received)
                    processed_buffers[ch][-samples_received:] = processed_data[ch, :]
                
                # Update plots
                for i, line in enumerate(lines_raw):
                    line.set_data(time_vector, raw_buffers[i])
                    
                for i, line in enumerate(lines_processed):
                    line.set_data(time_vector, processed_buffers[i])
                
                # Redraw
                fig.canvas.draw_idle()
                fig.canvas.flush_events()
                
    except KeyboardInterrupt:
        print("Plot interrupted")
    finally:
        plt.ioff()
        plt.show()

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Delsys Trigno Demo")
    parser.add_argument("--host", type=str, default=TRIGNO_CONFIG["host"],
                       help=f"Host IP for Delsys Trigno system (default: {TRIGNO_CONFIG['host']})")
    parser.add_argument("--command-port", type=int, default=TRIGNO_CONFIG["command_port"],
                       help=f"Command port (default: {TRIGNO_CONFIG['command_port']})")
    parser.add_argument("--emg-port", type=int, default=TRIGNO_CONFIG["emg_port"],
                       help=f"EMG data port (default: {TRIGNO_CONFIG['emg_port']})")
    parser.add_argument("--aux-port", type=int, default=TRIGNO_CONFIG["aux_port"],
                       help=f"Auxiliary data port (default: {TRIGNO_CONFIG['aux_port']})")
    parser.add_argument("--duration", type=int, default=30,
                       help="Duration of demo in seconds (default: 30)")
    parser.add_argument("--simulate", action="store_true",
                       help="Use simulated data instead of connecting to hardware")
    args = parser.parse_args()
    
    # Initialize EMG and Processor
    emg = DelsysTrignoEMG(
        host=args.host,
        command_port=args.command_port,
        emg_port=args.emg_port,
        aux_port=args.aux_port
    )
    processor = EMGProcessor(
        channel_count=emg.channels,
        sampling_rate=emg.sampling_rate
    )
    
    try:
        if args.simulate:
            print("Using simulated EMG data")
            # Set the emg object to simulation mode
            emg.is_connected = True
        else:
            # Connect to the Delsys Trigno system
            print("Connecting to Delsys Trigno system...")
            if not emg.connect():
                print("Failed to connect to Delsys Trigno system. Switching to simulation mode.")
                emg.is_connected = True
            else:
                print("Connected to Delsys Trigno system")
                
                # Configure the system
                print("Configuring Delsys Trigno system...")
                if not emg.configure_board():
                    print("Failed to configure Delsys Trigno system. Switching to simulation mode.")
                    emg.disconnect()
                    emg.is_connected = True
                else:
                    print("Delsys Trigno system configured")
        
        # Start streaming
        print("Starting EMG data streaming...")
        if args.simulate or emg.start_streaming():
            print("EMG data streaming started")
            print(f"Displaying real-time EMG data for {args.duration} seconds...")
            
            # Display real-time EMG data
            real_time_plot(emg, processor, duration=args.duration)
            
            # Stop streaming
            if not args.simulate:
                emg.stop_streaming()
                print("EMG data streaming stopped")
        else:
            print("Failed to start EMG data streaming")
            
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    finally:
        if not args.simulate and emg.is_connected:
            emg.stop_streaming()
            emg.disconnect()
            print("Disconnected from Delsys Trigno system")
    
    print("Demo completed")

if __name__ == "__main__":
    main()
