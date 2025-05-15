#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Acquisition Module
Handles communication with the Sessantaquatro board and EMG signal acquisition.
"""

import time
import threading
import numpy as np
import serial
import logging
from queue import Queue
import pylsl

from ini import EMG_CONFIG, logger

class SessantaquatroEMG:
    """Class for handling communication with the Sessantaquatro EMG board."""
    
    def __init__(self, port=None, baudrate=None):
        """Initialize the EMG acquisition system."""
        self.port = port or EMG_CONFIG["port"]
        self.baudrate = baudrate or EMG_CONFIG["baudrate"]
        self.sampling_rate = EMG_CONFIG["sampling_rate"]
        self.channels = EMG_CONFIG["channels"]
        self.serial_conn = None
        self.is_streaming = False
        self.data_queue = Queue()
        self.thread = None
        self.lsl_outlet = None
        logger.info(f"EMG acquisition initialized with {self.channels} channels at {self.sampling_rate}Hz")
    
    def connect(self):
        """Establish connection with the Sessantaquatro board."""
        try:
            self.serial_conn = serial.Serial(
                self.port, 
                self.baudrate, 
                timeout=1
            )
            logger.info(f"Connected to Sessantaquatro board on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to Sessantaquatro board: {str(e)}")
            return False
    
    def disconnect(self):
        """Close connection with the Sessantaquatro board."""
        if self.serial_conn and self.serial_conn.is_open:
            self.stop_streaming()
            self.serial_conn.close()
            logger.info("Disconnected from Sessantaquatro board")
    
    def configure_board(self):
        """Send configuration commands to the board."""
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Cannot configure board: Not connected")
            return False
        
        try:
            # Example configuration commands (replace with actual commands)
            # These will depend on the specific protocol of the Sessantaquatro board
            self.serial_conn.write(b'SAMPLING_RATE:2048\n')
            time.sleep(0.1)
            self.serial_conn.write(b'CHANNELS:64\n')
            time.sleep(0.1)
            self.serial_conn.write(b'RESOLUTION:24\n')
            time.sleep(0.1)
            
            # Read acknowledgement
            response = self.serial_conn.readline().decode('utf-8').strip()
            if 'OK' in response:
                logger.info("Board configured successfully")
                return True
            else:
                logger.error(f"Board configuration failed: {response}")
                return False
        except Exception as e:
            logger.error(f"Error configuring board: {str(e)}")
            return False
    
    def _streaming_thread(self):
        """Thread function for continuous data acquisition."""
        buffer = np.zeros((self.channels, 0))
        bytes_per_sample = 3  # 24-bit resolution = 3 bytes
        bytes_per_frame = bytes_per_sample * self.channels
        
        logger.info("Starting EMG data streaming")
        
        while self.is_streaming:
            try:
                # Read a full frame of data
                raw_data = self.serial_conn.read(bytes_per_frame)
                
                if len(raw_data) < bytes_per_frame:
                    logger.warning(f"Incomplete data frame received: {len(raw_data)} bytes")
                    continue
                
                # Parse the raw data into EMG samples
                frame = np.zeros(self.channels)
                for ch in range(self.channels):
                    # Parse 24-bit values (adjust based on actual data format)
                    start_idx = ch * bytes_per_sample
                    value = int.from_bytes(
                        raw_data[start_idx:start_idx + bytes_per_sample],
                        byteorder='little',
                        signed=True
                    )
                    frame[ch] = value
                
                # Add the frame to our buffer
                buffer = np.column_stack((buffer, frame))
                
                # When buffer reaches certain size, process and push to queue
                if buffer.shape[1] >= self.sampling_rate // 10:  # Process 100ms blocks
                    self.data_queue.put(buffer.copy())
                    
                    # Also send to LSL if configured
                    if self.lsl_outlet:
                        for i in range(buffer.shape[1]):
                            self.lsl_outlet.push_sample(buffer[:, i])
                    
                    buffer = np.zeros((self.channels, 0))
                    
            except Exception as e:
                logger.error(f"Error in streaming thread: {str(e)}")
                if not self.is_streaming:
                    break  # Exit if streaming was stopped
                time.sleep(0.1)  # Brief pause before retrying
    
    def start_streaming(self):
        """Start continuous EMG data acquisition."""
        if self.is_streaming:
            logger.warning("Streaming is already active")
            return False
        
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Cannot start streaming: Not connected")
            return False
        
        # Set up LSL stream
        info = pylsl.StreamInfo(
            name='Sessantaquatro_EMG',
            type='EMG',
            channel_count=self.channels,
            nominal_srate=self.sampling_rate,
            channel_format='float32',
            source_id='sessantaquatro123'
        )
        
        # Add channel metadata
        channels = info.desc().append_child("channels")
        for c in range(self.channels):
            channels.append_child("channel") \
                .append_child_value("label", f"EMG{c+1}") \
                .append_child_value("unit", "uV") \
                .append_child_value("type", "EMG")
        
        self.lsl_outlet = pylsl.StreamOutlet(info)
        
        # Start the acquisition thread
        self.is_streaming = True
        self.thread = threading.Thread(target=self._streaming_thread)
        self.thread.daemon = True
        self.thread.start()
        logger.info("EMG streaming started")
        return True
    
    def stop_streaming(self):
        """Stop EMG data acquisition."""
        if not self.is_streaming:
            return
        
        self.is_streaming = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        
        logger.info("EMG streaming stopped")
    
    def get_data(self, blocking=True, timeout=None):
        """Retrieve acquired EMG data from the queue.
        
        Args:
            blocking (bool): If True, block until data is available
            timeout (float): Maximum time to wait for data
            
        Returns:
            numpy.ndarray or None: EMG data with shape (channels, samples)
        """
        try:
            return self.data_queue.get(block=blocking, timeout=timeout)
        except Exception:
            return None
    
    def flush_data(self):
        """Clear all data from the queue."""
        while not self.data_queue.empty():
            try:
                self.data_queue.get_nowait()
            except:
                break
        logger.info("Data queue flushed")

if __name__ == "__main__":
    # Simple test script
    import matplotlib.pyplot as plt
    
    emg = SessantaquatroEMG()
    if emg.connect():
        print("Connected to board")
        emg.configure_board()
        emg.start_streaming()
        
        # Collect for 5 seconds
        print("Collecting data for 5 seconds...")
        start_time = time.time()
        collected_data = []
        
        while time.time() - start_time < 5:
            data = emg.get_data(blocking=True, timeout=1.0)
            if data is not None:
                collected_data.append(data)
                print(f"Received data block: {data.shape}")
        
        emg.stop_streaming()
        emg.disconnect()
        
        # Plot some channels
        if collected_data:
            all_data = np.hstack(collected_data)
            plt.figure(figsize=(12, 8))
            for i in range(min(8, emg.channels)):  # Plot first 8 channels
                plt.subplot(8, 1, i+1)
                plt.plot(all_data[i, :])
                plt.title(f"Channel {i+1}")
                plt.tight_layout()
            plt.show()
    else:
        print("Failed to connect to board")