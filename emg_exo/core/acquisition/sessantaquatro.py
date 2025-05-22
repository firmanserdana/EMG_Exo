"""
Sessantaquatro EMG acquisition module.

This module implements the interface for the Sessantaquatro EMG board.
"""

import numpy as np
import time
import threading
import queue
import serial
import os
import struct
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple, Union

from emg_exo.core.acquisition.base import BaseEMGSystem
from emg_exo.config import EMG_CONFIG, logger

class SessantaquatroEMG(BaseEMGSystem):
    """Class for communicating with the Sessantaquatro EMG board."""
    
    def __init__(self, port: Optional[str] = None, baudrate: Optional[int] = None):
        """Initialize the EMG board interface.
        
        Args:
            port: COM port for the board connection
            baudrate: Baudrate for serial communication
        """
        self.port = port or EMG_CONFIG["port"]
        self.baudrate = baudrate or EMG_CONFIG["baudrate"]
        self.sampling_rate = EMG_CONFIG["sampling_rate"]
        self.channels = EMG_CONFIG["channels"]
        self.resolution = EMG_CONFIG["resolution"]
        
        # Serial connection
        self.serial = None
        self.is_connected = False
        
        # Data acquisition
        self.is_streaming = False
        self.acquisition_thread = None
        self.data_buffer = queue.Queue(maxsize=100)  # Buffer for 100 data chunks
        
        logger.info(f"Sessantaquatro EMG initialized (port: {self.port}, baudrate: {self.baudrate})")
    
    def connect(self) -> bool:
        """Connect to the EMG board.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            
            # Test if connection is valid
            if not self.serial.is_open:
                self.serial.open()
                
            # Wait for device to initialize
            time.sleep(2)
            
            # Send a test command
            self.serial.write(b"TEST\r\n")
            response = self.serial.read(100)  # Read some bytes
            
            if len(response) > 0:
                self.is_connected = True
                logger.info(f"Connected to EMG board on port {self.port}")
                return True
            else:
                logger.error("No response from EMG board")
                self.serial.close()
                self.is_connected = False
                return False
                
        except serial.SerialException as e:
            logger.error(f"Error connecting to EMG board: {str(e)}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the EMG board."""
        if self.is_streaming:
            self.stop_streaming()
            
        if self.serial and self.serial.is_open:
            self.serial.close()
            
        self.is_connected = False
        logger.info("Disconnected from EMG board")
    
    def configure_board(self) -> bool:
        """Configure the EMG board settings.
        
        Returns:
            bool: True if configuration successful
        """
        if not self.is_connected:
            logger.error("Cannot configure: Not connected to EMG board")
            return False
            
        try:
            # Clear any pending data
            self.serial.reset_input_buffer()
            
            # Configure sampling rate
            self.serial.write(f"SET SAMPLING_RATE {self.sampling_rate}\r\n".encode())
            time.sleep(0.1)
            
            # Configure channels
            self.serial.write(f"SET CHANNELS {self.channels}\r\n".encode())
            time.sleep(0.1)
            
            # Configure resolution
            self.serial.write(f"SET RESOLUTION {self.resolution}\r\n".encode())
            time.sleep(0.1)
            
            # Configure reference mode
            self.serial.write(f"SET REFERENCE {EMG_CONFIG['reference'].upper()}\r\n".encode())
            time.sleep(0.1)
            
            # Check configuration
            self.serial.write(b"GET CONFIG\r\n")
            time.sleep(0.2)
            
            # Read response - this is simplified, actual protocol may differ
            response = self.serial.read_all().decode('ascii', errors='ignore')
            
            if "ERROR" in response:
                logger.error(f"Error configuring EMG board: {response}")
                return False
                
            logger.info("EMG board configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring EMG board: {str(e)}")
            return False
    
    def start_streaming(self) -> bool:
        """Start streaming EMG data from the board.
        
        Returns:
            bool: True if streaming started successfully
        """
        if not self.is_connected:
            logger.error("Cannot start streaming: Not connected to EMG board")
            return False
            
        if self.is_streaming:
            logger.warning("Streaming is already active")
            return True
            
        try:
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            while not self.data_buffer.empty():
                self.data_buffer.get()
            
            # Send streaming command
            self.serial.write(b"START STREAMING\r\n")
            time.sleep(0.1)
            
            # Check response
            response = self.serial.read_all().decode('ascii', errors='ignore')
            if "ERROR" in response:
                logger.error(f"Error starting streaming: {response}")
                return False
                
            # Start acquisition thread
            self.is_streaming = True
            self.acquisition_thread = threading.Thread(target=self._acquisition_loop)
            self.acquisition_thread.daemon = True
            self.acquisition_thread.start()
            
            logger.info("EMG data streaming started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {str(e)}")
            return False
    
    def stop_streaming(self) -> None:
        """Stop streaming EMG data from the board."""
        if not self.is_streaming:
            return
            
        try:
            # Send stop command
            self.serial.write(b"STOP STREAMING\r\n")
            
            # Flag for thread termination
            self.is_streaming = False
            
            # Wait for thread to end
            if self.acquisition_thread:
                self.acquisition_thread.join(timeout=2.0)
                self.acquisition_thread = None
                
            logger.info("EMG data streaming stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {str(e)}")
    
    def _acquisition_loop(self) -> None:
        """Thread function for continuous data acquisition."""
        logger.info("Acquisition thread started")
        
        # Calculate bytes per sample
        bytes_per_channel = int(np.ceil(self.resolution / 8))
        bytes_per_sample = bytes_per_channel * self.channels
        
        # Calculate expected acquisition rate
        samples_per_chunk = 32  # Process data in chunks
        samples_per_second = self.sampling_rate
        chunk_time = samples_per_chunk / samples_per_second
        
        while self.is_streaming:
            try:
                start_time = time.time()
                
                # Wait for enough data - account for header and footer
                timeout_time = start_time + chunk_time * 2
                while self.serial.in_waiting < (bytes_per_sample * samples_per_chunk + 16) and time.time() < timeout_time:
                    time.sleep(0.001)
                
                if self.serial.in_waiting < (bytes_per_sample * samples_per_chunk + 16):
                    logger.warning(f"Timeout waiting for data. Available: {self.serial.in_waiting} bytes")
                    continue
                
                # Read one chunk of raw data
                raw_data = self.serial.read(bytes_per_sample * samples_per_chunk + 16)
                
                # Parse the data 
                emg_data = self._parse_raw_data(raw_data, samples_per_chunk)
                
                if emg_data is not None:
                    # Put data in the queue
                    try:
                        self.data_buffer.put(emg_data, block=False)
                    except queue.Full:
                        # If queue is full, get one item then put the new one
                        self.data_buffer.get()
                        self.data_buffer.put(emg_data)
                
                # Calculate and adjust sleep time to maintain target rate
                elapsed = time.time() - start_time
                sleep_time = max(0, chunk_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Error in acquisition loop: {str(e)}")
                if not self.is_streaming:
                    break
                time.sleep(0.1)
        
        logger.info("Acquisition thread ended")
    
    def _parse_raw_data(self, raw_data: bytes, samples_per_chunk: int) -> Optional[np.ndarray]:
        """Parse raw binary data from the EMG board.
        
        Args:
            raw_data: Raw binary data from the board
            samples_per_chunk: Number of samples expected in this chunk
            
        Returns:
            numpy.ndarray: EMG data array with shape (channels, samples)
        """
        try:
            # Check that we have the right amount of data
            bytes_per_channel = int(np.ceil(self.resolution / 8))
            bytes_per_sample = bytes_per_channel * self.channels
            expected_data_size = bytes_per_sample * samples_per_chunk
            
            if len(raw_data) < expected_data_size:
                logger.error(f"Invalid data size: {len(raw_data)}, expected at least {expected_data_size}")
                return None
            
            # Initialize array for parsed data
            emg_data = np.zeros((self.channels, samples_per_chunk), dtype=np.float32)
            
            # Parse each sample
            for sample_idx in range(samples_per_chunk):
                offset = 8  # Assuming a header of 8 bytes
                offset += sample_idx * bytes_per_sample
                
                # Parse each channel
                for ch_idx in range(self.channels):
                    ch_offset = offset + ch_idx * bytes_per_channel
                    
                    if bytes_per_channel == 2:  # 16-bit values
                        value = struct.unpack("<h", raw_data[ch_offset:ch_offset+2])[0]
                        # Convert to microvolts
                        emg_data[ch_idx, sample_idx] = value * 0.0298
                        
                    elif bytes_per_channel == 3:  # 24-bit values
                        value_bytes = raw_data[ch_offset:ch_offset+3] + b'\x00'
                        value = struct.unpack("<i", value_bytes)[0] >> 8
                        # Convert to microvolts, assuming a scaling factor
                        emg_data[ch_idx, sample_idx] = value * 0.0018
                        
                    elif bytes_per_channel == 4:  # 32-bit values
                        value = struct.unpack("<i", raw_data[ch_offset:ch_offset+4])[0]
                        # Convert to microvolts, assuming a scaling factor
                        emg_data[ch_idx, sample_idx] = value * 0.00012
                        
            return emg_data
            
        except Exception as e:
            logger.error(f"Error parsing EMG data: {str(e)}")
            return None
    
    def get_data(self, blocking: bool = False, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Get a chunk of EMG data from the buffer.
        
        Args:
            blocking: If True, wait until data is available
            timeout: Maximum time to wait if blocking is True
            
        Returns:
            numpy.ndarray: EMG data array with shape (channels, samples)
                           or None if no data is available
        """
        if not self.is_streaming:
            return None
            
        try:
            if blocking:
                return self.data_buffer.get(block=True, timeout=timeout)
            else:
                if self.data_buffer.empty():
                    return None
                return self.data_buffer.get(block=False)
                
        except queue.Empty:
            return None
            
        except Exception as e:
            logger.error(f"Error getting EMG data: {str(e)}")
            return None

    def simulate_data(self, duration: float = 1.0, gesture: Optional[str] = None) -> np.ndarray:
        """Generate simulated EMG data for testing.
        
        Args:
            duration: Duration of data in seconds
            gesture: Specific gesture to simulate
            
        Returns:
            numpy.ndarray: Simulated EMG data array with shape (channels, samples)
        """
        samples = int(duration * self.sampling_rate)
        emg_data = np.random.normal(0, 20, (self.channels, samples))
        
        # Define gesture patterns
        gesture_patterns = {
            "rest": [],
            "thumb_flexion": [0, 1],
            "index_flexion": [2, 3],
            "middle_flexion": [4, 5],
            "ring_little_flexion": [6, 7],
            "thumb_extension": [0],
            "index_extension": [2],
            "middle_extension": [4],
            "thumb_pinch": [0, 2],
            "index_pinch": [2, 4],
            "middle_pinch": [4, 6]
        }
        
        # If a specific gesture is requested, activate those channels
        if gesture and gesture in gesture_patterns:
            active_channels = gesture_patterns[gesture]
            # Add stronger activity to channels for this gesture
            for ch in active_channels:
                if ch < self.channels:  # Make sure channel exists
                    # Generate a physiological EMG pattern
                    time_points = np.linspace(0, duration, samples)
                    
                    # Base frequency components (50-100Hz for EMG)
                    base_freq = 60 + ch * 5
                    signal = np.sin(2 * np.pi * base_freq * time_points)
                    signal += 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points)
                    signal += 0.3 * np.sin(2 * np.pi * base_freq * 3 * time_points)
                    
                    # Apply amplitude modulation for muscle contraction pattern
                    envelope = np.ones(samples)
                    ramp_samples = int(0.1 * samples)
                    envelope[:ramp_samples] = np.linspace(0, 1, ramp_samples)
                    envelope[-ramp_samples:] = np.linspace(1, 0, ramp_samples)
                    
                    # Apply envelope to signal
                    signal *= 400 * envelope
                    
                    # Add to channel data
                    emg_data[ch] += signal
        else:
            # Add synthetic EMG bursts to random channels
            for burst in range(min(5, self.channels)):
                ch = np.random.randint(0, self.channels)
                start = np.random.randint(0, samples - 200)
                end = start + 200
                
                # Generate a burst envelope
                envelope = np.hanning(end - start)
                
                # Apply envelope to random noise for realistic EMG
                burst_data = np.random.normal(0, 500, end - start) * envelope
                
                # Add burst to channel
                emg_data[ch, start:end] += burst_data
            
        logger.debug(f"Generated {duration}s of simulated EMG data")
        return emg_data
