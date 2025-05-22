#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Delsys Trigno EMG Module
Handles communication with the Delsys Trigno EMG system and acquires data.
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

from ini import logger
from emg_acquisition import SessantaquatroEMG  # Import base class for compatibility


# Define Delsys Trigno system configuration
TRIGNO_CONFIG = {
    "host": "127.0.0.1",  # Default local IP address for the Trigno control utility
    "command_port": 50040,  # Default command port for the Trigno system
    "emg_port": 50041,     # Default EMG data port
    "aux_port": 50042,     # Default accelerometer/auxiliary data port
    "sampling_rate": 2000, # Default sampling rate in Hz
    "channels": 16,        # Default: Trigno system supports up to 16 sensors
    "resolution": 16,      # Bits of resolution
    "buffer_size": 8192,   # Network buffer size
}


class DelsysTrignoEMG(SessantaquatroEMG):
    """Class for communicating with the Delsys Trigno EMG system."""
    
    def __init__(self, host=None, command_port=None, emg_port=None, aux_port=None):
        """Initialize the Delsys Trigno EMG interface.
        
        Args:
            host (str): Host IP where Trigno Control Utility is running
            command_port (int): Port for sending commands
            emg_port (int): Port for EMG data
            aux_port (int): Port for auxiliary data
        """
        # Initialize with default sampling rate and channels
        super().__init__()
        
        # Override serial properties with network properties
        self.host = host or TRIGNO_CONFIG["host"]
        self.command_port = command_port or TRIGNO_CONFIG["command_port"]
        self.emg_port = emg_port or TRIGNO_CONFIG["emg_port"]
        self.aux_port = aux_port or TRIGNO_CONFIG["aux_port"]
        
        # Override other configuration
        self.sampling_rate = TRIGNO_CONFIG["sampling_rate"] 
        self.channels = TRIGNO_CONFIG["channels"]
        self.resolution = TRIGNO_CONFIG["resolution"]
        
        # Network sockets
        self.command_socket = None
        self.emg_socket = None
        self.aux_socket = None
        
        # Maintain compatibility with base class
        self.is_connected = False
        self.is_streaming = False
        self.acquisition_thread = None
        self.data_buffer = queue.Queue(maxsize=100)  # Buffer for 100 data chunks
        
        logger.info(f"Delsys Trigno EMG initialized (host: {self.host}, command port: {self.command_port})")
    
    def connect(self):
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
    
    def _close_sockets(self):
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
    
    def disconnect(self):
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
    
    def _send_command(self, command, wait_for_response=True):
        """Send a command to the Trigno Control Utility.
        
        Args:
            command (str): Command string to send
            wait_for_response (bool): Whether to wait for a response
            
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
            response = self.command_socket.recv(TRIGNO_CONFIG["buffer_size"]).decode().strip()
            return response
        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return None
    
    def configure_board(self):
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
    
    def start_streaming(self):
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
    
    def stop_streaming(self):
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
    
    def _acquisition_loop(self):
        """Thread function for continuous data acquisition."""
        logger.info("Delsys Trigno acquisition thread started")
        
        # Calculate expected acquisition rate
        samples_per_chunk = 32  # Process data in chunks
        samples_per_second = self.sampling_rate
        chunk_time = samples_per_chunk / samples_per_second
        
        # Prepare buffer for received data
        emg_buffer = bytearray(TRIGNO_CONFIG["buffer_size"])
        
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
                
                # Optional: Receive accelerometer/auxiliary data if needed
                # try:
                #     nbytes, addr = self.aux_socket.recvfrom_into(aux_buffer)
                #     if nbytes > 0:
                #         # Parse auxiliary data if needed
                #         pass
                # except socket.timeout:
                #     pass
                
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
    
    def _parse_emg_data(self, data_buffer, samples_per_chunk):
        """Parse EMG data from Delsys Trigno packet format.
        
        Args:
            data_buffer (bytearray): Raw binary data from the Trigno system
            samples_per_chunk (int): Number of samples expected in this chunk
            
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

    def simulate_data(self, duration=1.0, gesture=None):
        """Generate simulated EMG data for testing.
        This method overrides the base class to ensure compatibility.
        
        Args:
            duration (float): Duration of data in seconds
            gesture (str, optional): Specific gesture to simulate
            
        Returns:
            numpy.ndarray: Simulated EMG data array with shape (channels, samples)
        """
        # Use the same simulation method as the base class for consistency
        return super().simulate_data(duration, gesture)


if __name__ == "__main__":
    # Simple test script
    emg = DelsysTrignoEMG()
    
    print("Testing Delsys Trigno EMG acquisition...")
    try:
        if emg.connect():
            print("Connected to Delsys Trigno system")
            
            if emg.configure_board():
                print("System configured")
                
                print("Starting streaming...")
                if emg.start_streaming():
                    print("Streaming started")
                    
                    print("Acquiring data for 5 seconds...")
                    for i in range(10):
                        data = emg.get_data(blocking=True, timeout=1.0)
                        if data is not None:
                            print(f"Got data chunk: {data.shape}, mean={data.mean():.2f}, std={data.std():.2f}")
                        else:
                            print("No data received")
                    
                    print("Stopping streaming...")
                    emg.stop_streaming()
                    
            emg.disconnect()
            print("Disconnected from Delsys Trigno system")
            
        else:
            print("Failed to connect. Using simulated data instead.")
            
            # Test with simulated data
            print("Generating simulated data...")
            simulated_data = emg.simulate_data(duration=2.0)
            print(f"Simulated data shape: {simulated_data.shape}")
            print(f"Mean: {simulated_data.mean():.2f}, Std: {simulated_data.std():.2f}")
            
    except Exception as e:
        print(f"Error in test script: {str(e)}")
