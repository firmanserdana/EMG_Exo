"""
Delsys Trigno EMG acquisition module.

This module implements the interface for the Delsys Trigno EMG system.
"""

import numpy as np
import time
import threading
import queue
import socket
import struct
import os
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple, Union

from emg_exo.core.acquisition.base import BaseEMGSystem
from emg_exo.core.acquisition.sessantaquatro import SessantaquatroEMG 
from emg_exo.config import TRIGNO_CONFIG, logger

class DelsysTrignoEMG(BaseEMGSystem):
    """Class for communicating with the Delsys Trigno EMG system."""
    
    def __init__(self, host: Optional[str] = None, command_port: Optional[int] = None, 
                 emg_port: Optional[int] = None, aux_port: Optional[int] = None):
        """Initialize the Delsys Trigno EMG interface.
        
        Args:
            host: Host IP where Trigno Control Utility is running
            command_port: Port for sending commands
            emg_port: Port for EMG data
            aux_port: Port for auxiliary data
        """
        # Initialize properties
        self.host = host or TRIGNO_CONFIG["host"]
        self.command_port = command_port or TRIGNO_CONFIG["command_port"]
        self.emg_port = emg_port or TRIGNO_CONFIG["emg_port"]
        self.aux_port = aux_port or TRIGNO_CONFIG["aux_port"]
        
        # EMG system properties
        self.sampling_rate = TRIGNO_CONFIG["sampling_rate"] 
        self.channels = TRIGNO_CONFIG["channels"]
        self.resolution = TRIGNO_CONFIG["resolution"]
        
        # Network sockets
        self.command_socket = None
        self.emg_socket = None
        self.aux_socket = None
        
        # Data acquisition
        self.is_connected = False
        self.is_streaming = False
        self.acquisition_thread = None
        self.data_buffer = queue.Queue(maxsize=100)  # Buffer for 100 data chunks
        
        logger.info(f"Delsys Trigno EMG initialized (host: {self.host}, command port: {self.command_port})")
    
    def connect(self) -> bool:
        """Connect to the Delsys Trigno system.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Create command socket (TCP)
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.connect((self.host, self.command_port))
            
            # Create data sockets (UDP)
            self.emg_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.emg_socket.bind(('0.0.0.0', self.emg_port))
            self.emg_socket.settimeout(1.0)
            
            self.aux_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.aux_socket.bind(('0.0.0.0', self.aux_port))
            self.aux_socket.settimeout(1.0)
            
            # Test command communication
            if self._send_command("PING") == "OK":
                self.is_connected = True
                logger.info(f"Connected to Delsys Trigno system at {self.host}")
                return True
            else:
                logger.error("Failed to communicate with Delsys Trigno system")
                self._close_sockets()
                self.is_connected = False
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to Delsys Trigno system: {str(e)}")
            self._close_sockets()
            self.is_connected = False
            return False
    
    def _close_sockets(self) -> None:
        """Close all network sockets."""
        for sock in [self.command_socket, self.emg_socket, self.aux_socket]:
            if sock:
                try:
                    sock.close()
                except:
                    pass
        self.command_socket = None
        self.emg_socket = None
        self.aux_socket = None
    
    def disconnect(self) -> None:
        """Disconnect from the Delsys Trigno system."""
        if self.is_streaming:
            self.stop_streaming()
            
        if self.is_connected:
            try:
                self._send_command("QUIT")
            except:
                pass
                
        self._close_sockets()
        self.is_connected = False
        logger.info("Disconnected from Delsys Trigno system")
    
    def _send_command(self, command: str, wait_for_response: bool = True) -> Optional[str]:
        """Send a command to the Trigno Control Utility.
        
        Args:
            command: Command string to send
            wait_for_response: Whether to wait for a response
            
        Returns:
            str: Response from the system, or None if no response expected
        """
        if not self.command_socket:
            logger.error("Command socket not connected")
            return None
            
        try:
            # Send command
            self.command_socket.send(f"{command}\r\n".encode())
            
            if not wait_for_response:
                return None
            
            # Wait for response
            response = self.command_socket.recv(TRIGNO_CONFIG.get("buffer_size", 8192)).decode().strip()
            return response
        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return None
    
    def configure_board(self) -> bool:
        """Configure the Delsys Trigno system settings.
        
        Returns:
            bool: True if configuration successful
        """
        if not self.is_connected:
            logger.error("Cannot configure: Not connected to Delsys Trigno system")
            return False
            
        try:
            # Reset to default configuration
            response = self._send_command("RESET")
            if "OK" not in response:
                logger.error(f"Failed to reset Trigno system: {response}")
                return False
            
            # Set sampling rate
            response = self._send_command(f"RATE {self.sampling_rate}")
            if "OK" not in response:
                logger.error(f"Failed to set sampling rate: {response}")
                return False
            
            # Configure which sensors to use (enable all available)
            response = self._send_command("SENSOR ALL")
            if "OK" not in response:
                logger.error(f"Failed to configure sensors: {response}")
                return False
                
            logger.info("Delsys Trigno system configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring Delsys Trigno system: {str(e)}")
            return False
    
    def start_streaming(self) -> bool:
        """Start streaming EMG data from the Trigno system.
        
        Returns:
            bool: True if streaming started successfully
        """
        if not self.is_connected:
            logger.error("Cannot start streaming: Not connected to Delsys Trigno system")
            return False
            
        if self.is_streaming:
            logger.warning("Streaming is already active")
            return True
            
        try:
            # Clear buffer
            while not self.data_buffer.empty():
                self.data_buffer.get()
            
            # Send START command to begin data streaming
            response = self._send_command("START")
            if "OK" not in response:
                logger.error(f"Failed to start streaming: {response}")
                return False
                
            # Start acquisition thread
            self.is_streaming = True
            self.acquisition_thread = threading.Thread(target=self._acquisition_loop)
            self.acquisition_thread.daemon = True
            self.acquisition_thread.start()
            
            logger.info("Delsys Trigno EMG data streaming started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {str(e)}")
            return False
    
    def stop_streaming(self) -> None:
        """Stop streaming EMG data from the Trigno system."""
        if not self.is_streaming:
            return
            
        try:
            # Send stop command
            self._send_command("STOP")
            
            # Flag for thread termination
            self.is_streaming = False
            
            # Wait for thread to end
            if self.acquisition_thread:
                self.acquisition_thread.join(timeout=2.0)
                self.acquisition_thread = None
                
            logger.info("Delsys Trigno EMG data streaming stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {str(e)}")
    
    def _acquisition_loop(self) -> None:
        """Thread function for continuous data acquisition."""
        logger.info("Delsys Trigno acquisition thread started")
        
        # Calculate expected acquisition rate
        samples_per_chunk = 32  # Process data in chunks
        samples_per_second = self.sampling_rate
        chunk_time = samples_per_chunk / samples_per_second
        
        # Prepare buffer for received data
        buffer_size = TRIGNO_CONFIG.get("buffer_size", 8192)
        emg_buffer = bytearray(buffer_size)
        
        while self.is_streaming:
            try:
                start_time = time.time()
                
                # Receive EMG data packet
                try:
                    nbytes, addr = self.emg_socket.recvfrom_into(emg_buffer)
                    
                    if nbytes > 0:
                        # Parse the EMG data from the received packet
                        emg_data = self._parse_emg_data(emg_buffer[:nbytes], samples_per_chunk)
                        
                        if emg_data is not None:
                            # Put data in the queue
                            try:
                                self.data_buffer.put(emg_data, block=False)
                            except queue.Full:
                                # If queue is full, get one item then put the new one
                                self.data_buffer.get()
                                self.data_buffer.put(emg_data)
                except socket.timeout:
                    # Socket timeout, just continue
                    pass
                
                # Calculate and adjust sleep time to maintain target rate
                elapsed = time.time() - start_time
                sleep_time = max(0, chunk_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Error in Trigno acquisition loop: {str(e)}")
                if not self.is_streaming:
                    break
                time.sleep(0.1)
        
        logger.info("Delsys Trigno acquisition thread ended")
    
    def _parse_emg_data(self, data_buffer: bytes, samples_per_chunk: int) -> Optional[np.ndarray]:
        """Parse EMG data from Delsys Trigno packet format.
        
        Args:
            data_buffer: Raw binary data from the Trigno system
            samples_per_chunk: Number of samples expected in this chunk
            
        Returns:
            numpy.ndarray: EMG data array with shape (channels, samples)
        """
        try:
            # Check if we have enough data
            if len(data_buffer) < 4:
                logger.debug(f"Insufficient data: {len(data_buffer)} bytes")
                return None
                
            # Parse header (this is a placeholder - actual implementation depends on Trigno SDK documentation)
            # Assuming data format: [header(4 bytes)][sensor_data][sensor_data]...
            
            # Initialize array for parsed data
            emg_data = np.zeros((self.channels, samples_per_chunk), dtype=np.float32)
            
            # In this example, we assume each sensor data block contains sequential samples
            # for that sensor, but actual format depends on Delsys Trigno data protocol
            bytes_per_sample = 2  # Assuming 16-bit samples
            header_size = 4       # Assuming 4-byte header
            
            # Parse each channel
            for ch_idx in range(self.channels):
                for sample_idx in range(samples_per_chunk):
                    # Calculate offset in the data buffer
                    offset = header_size + (ch_idx * samples_per_chunk * bytes_per_sample) + (sample_idx * bytes_per_sample)
                    
                    # Check if we have enough data
                    if offset + bytes_per_sample > len(data_buffer):
                        continue
                        
                    # Parse 16-bit value (adjust byte order if needed)
                    value = struct.unpack("<h", data_buffer[offset:offset+bytes_per_sample])[0]
                    
                    # Convert to appropriate units (microvolts)
                    # Scaling factor needs to be adjusted based on Trigno system specifications
                    emg_data[ch_idx, sample_idx] = value * 0.01  
            
            return emg_data
            
        except Exception as e:
            logger.error(f"Error parsing Trigno EMG data: {str(e)}")
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
