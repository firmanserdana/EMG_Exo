#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Unity Hand Interface
Handles communication with Unity hand visualization via TCP/UDP.
"""

import socket
import threading
import time
import json
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Any, Callable, Optional, Union

from emg_exo.core.interface.base import BaseHandInterface
from emg_exo.config.config import HAND_CONTROL


class UnityHandInterface(BaseHandInterface):
    """Interface to communicate with Unity hand visualization."""
    
    def __init__(self):
        """Initialize Unity communication interface."""
        # Communication settings
        self.host = HAND_CONTROL.get("host", "127.0.0.1")
        self.port = HAND_CONTROL.get("port", 25001)
        self.protocol = HAND_CONTROL.get("protocol", "tcp")
        self._connected = False
        
        # Socket objects
        self.tcp_socket = None
        self.udp_socket = None
        
        # Thread for handling incoming messages
        self.receive_thread = None
        self.running = False
        
        # Callback for received messages
        self.message_callback = None
        
        # Setup logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Unity Hand Interface initialized with {self.protocol.upper()} protocol")
    
    def connect(self) -> bool:
        """Connect to Unity application.
        
        Returns:
            True if connection established successfully
        """
        try:
            if self.protocol.lower() == "tcp":
                # Create TCP socket
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tcp_socket.settimeout(5.0)  # 5 second timeout
                self.tcp_socket.connect((self.host, self.port))
                self.tcp_socket.settimeout(None)  # Remove timeout after connection
                
                # Start receive thread
                self.running = True
                self.receive_thread = threading.Thread(target=self._receive_tcp)
                self.receive_thread.daemon = True
                self.receive_thread.start()
                
                self.logger.info(f"Connected to Unity via TCP: {self.host}:{self.port}")
                self._connected = True
                
            elif self.protocol.lower() == "udp":
                # Create UDP socket
                self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
                # Send a test message to establish connection
                test_message = {"type": "handshake", "data": "Hello from Python"}
                self.send_message(test_message)
                
                # Start receive thread
                self.running = True
                self.receive_thread = threading.Thread(target=self._receive_udp)
                self.receive_thread.daemon = True
                self.receive_thread.start()
                
                self.logger.info(f"UDP socket created for Unity communication: {self.host}:{self.port}")
                self._connected = True
                
            else:
                self.logger.error(f"Unsupported protocol: {self.protocol}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to Unity: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Unity application."""
        self.running = False
        
        try:
            # Send disconnect message
            if self._connected:
                try:
                    disconnect_message = {"type": "disconnect", "data": "Disconnecting"}
                    self.send_message(disconnect_message)
                    time.sleep(0.1)  # Give time for message to be sent
                except:
                    pass
            
            # Close TCP socket
            if self.tcp_socket:
                self.tcp_socket.close()
                self.tcp_socket = None
                
            # Close UDP socket
            if self.udp_socket:
                self.udp_socket.close()
                self.udp_socket = None
                
            # Wait for receive thread to terminate
            if self.receive_thread and self.receive_thread.is_alive():
                self.receive_thread.join(2.0)
                
            self.logger.info("Disconnected from Unity")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from Unity: {str(e)}")
        
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to Unity.
        
        Returns:
            True if connected
        """
        return self._connected
    
    def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to Unity application.
        
        Args:
            message: Message to send (will be JSON-encoded)
            
        Returns:
            True if message sent successfully
        """
        if not self._connected:
            self.logger.warning("Cannot send message: Not connected to Unity")
            return False
            
        try:
            # Convert message to JSON string
            json_message = json.dumps(message)
            data = json_message.encode('utf-8')
            
            if self.protocol.lower() == "tcp" and self.tcp_socket:
                # Add message length as header for TCP
                length = len(data)
                header = length.to_bytes(4, byteorder='big')
                
                # Send header and data
                self.tcp_socket.sendall(header + data)
                
            elif self.protocol.lower() == "udp" and self.udp_socket:
                # Send directly via UDP
                self.udp_socket.sendto(data, (self.host, self.port))
                
            else:
                self.logger.error("Invalid socket or protocol")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending message to Unity: {str(e)}")
            self._connected = False
            return False
    
    def set_message_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for received messages.
        
        Args:
            callback: Function to call when message is received
        """
        self.message_callback = callback
    
    def _receive_tcp(self) -> None:
        """Thread function to receive TCP messages from Unity."""
        self.logger.info("TCP receive thread started")
        
        while self.running:
            try:
                if not self.tcp_socket:
                    time.sleep(0.1)
                    continue
                    
                # Read message length (4-byte header)
                header = self._receive_all(4)
                if not header:
                    time.sleep(0.1)
                    continue
                    
                length = int.from_bytes(header, byteorder='big')
                
                # Read message data
                data = self._receive_all(length)
                if not data:
                    time.sleep(0.1)
                    continue
                    
                # Decode and parse message
                message = data.decode('utf-8')
                self._handle_message(message)
                
            except ConnectionResetError:
                self.logger.error("Connection reset by Unity")
                self._connected = False
                break
                
            except ConnectionAbortedError:
                self.logger.error("Connection aborted")
                self._connected = False
                break
                
            except Exception as e:
                self.logger.error(f"Error receiving TCP message: {str(e)}")
                time.sleep(0.5)
                
        self.logger.info("TCP receive thread ended")
    
    def _receive_udp(self) -> None:
        """Thread function to receive UDP messages from Unity."""
        self.logger.info("UDP receive thread started")
        
        if not self.udp_socket:
            self.logger.error("UDP socket not initialized")
            return
            
        # Configure socket for receiving
        try:
            self.udp_socket.bind(("0.0.0.0", self.port))
            self.udp_socket.settimeout(0.5)  # 500ms timeout for checking running flag
        except Exception as e:
            self.logger.error(f"Error binding UDP socket: {str(e)}")
            return
            
        while self.running:
            try:
                # Receive data with timeout
                data, addr = self.udp_socket.recvfrom(4096)
                
                # Decode and parse message
                message = data.decode('utf-8')
                self._handle_message(message)
                
            except socket.timeout:
                # This is normal, just loop and check running flag
                continue
                
            except Exception as e:
                self.logger.error(f"Error receiving UDP message: {str(e)}")
                time.sleep(0.5)
                
        self.logger.info("UDP receive thread ended")
    
    def _receive_all(self, n: int) -> Optional[bytes]:
        """Helper function to receive exactly n bytes via TCP.
        
        Args:
            n: Number of bytes to receive
            
        Returns:
            Received data or None if error/disconnect
        """
        if not self.tcp_socket:
            return None
            
        data = b''
        while len(data) < n:
            try:
                packet = self.tcp_socket.recv(n - len(data))
                if not packet:
                    # Connection closed
                    self._connected = False
                    return None
                data += packet
            except Exception as e:
                self.logger.error(f"Error in _receive_all: {str(e)}")
                return None
                
        return data
    
    def _handle_message(self, message_str: str) -> None:
        """Handle received message from Unity.
        
        Args:
            message_str: JSON message string
        """
        try:
            # Parse JSON message
            message = json.loads(message_str)
            
            # Log the message
            msg_type = message.get("type", "unknown")
            self.logger.debug(f"Received message from Unity: {msg_type}")
            
            # Call the callback if set
            if self.message_callback:
                self.message_callback(message)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON message: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
    
    def send_hand_control(self, dof_values: Union[Dict[str, float], List[float], np.ndarray]) -> bool:
        """Send hand control values to Unity.
        
        Args:
            dof_values: Degrees of freedom values for hand
                If dict: keys are DoF names, values are position values (0-1)
                If list: values are in predefined order
                
        Returns:
            True if message sent successfully
        """
        try:
            # Convert list to dict if necessary
            if isinstance(dof_values, list) or isinstance(dof_values, np.ndarray):
                # Define DoF order
                dof_names = [
                    "thumb_flexion_1", "thumb_flexion_2", "thumb_flexion_3",
                    "index_flexion_1", "index_flexion_2", "index_flexion_3",
                    "middle_flexion_1", "middle_flexion_2", "middle_flexion_3",
                    "ring_little_flexion_1", "ring_little_flexion_2",
                    "thumb_abduction"
                ]
                
                # Convert to dict with limited length
                dof_dict = {}
                for i, name in enumerate(dof_names):
                    if i < len(dof_values):
                        dof_dict[name] = float(dof_values[i])
                    else:
                        dof_dict[name] = 0.0
            else:
                # Already a dict
                dof_dict = dof_values
            
            # Create message
            message = {
                "type": "hand_control",
                "timestamp": datetime.now().timestamp(),
                "data": dof_dict
            }
            
            # Send the message
            return self.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending hand control: {str(e)}")
            return False
    
    def send_emg_data(self, emg_values: Union[List[float], np.ndarray]) -> bool:
        """Send EMG data to Unity for visualization.
        
        Args:
            emg_values: EMG channel values
                
        Returns:
            True if message sent successfully
        """
        try:
            # Convert to list if numpy array
            if isinstance(emg_values, np.ndarray):
                emg_list = emg_values.tolist()
            else:
                emg_list = list(emg_values)
            
            # Create message
            message = {
                "type": "emg_data",
                "timestamp": datetime.now().timestamp(),
                "data": emg_list
            }
            
            # Send the message
            return self.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending EMG data: {str(e)}")
            return False
    
    def send_gesture_info(self, gesture_id: Optional[int], gesture_name: str, confidence: float) -> bool:
        """Send gesture classification information to Unity.
        
        Args:
            gesture_id: ID of recognized gesture
            gesture_name: Name of recognized gesture
            confidence: Classification confidence (0-1)
                
        Returns:
            True if message sent successfully
        """
        try:
            # Create message
            message = {
                "type": "gesture_info",
                "timestamp": datetime.now().timestamp(),
                "data": {
                    "id": gesture_id if gesture_id is not None else -1,
                    "name": gesture_name,
                    "confidence": float(confidence)
                }
            }
            
            # Send the message
            return self.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending gesture info: {str(e)}")
            return False
    
    def start_streaming(self) -> bool:
        """Start streaming data to Unity.
        
        Returns:
            True if streaming started successfully
        """
        if not self._connected:
            self.logger.error("Cannot start streaming: Not connected to Unity")
            return False
        
        message = {
            "type": "control",
            "data": {"command": "start_streaming"}
        }
        
        return self.send_message(message)
    
    def stop_streaming(self) -> bool:
        """Stop streaming data to Unity.
        
        Returns:
            True if streaming stopped successfully
        """
        if not self._connected:
            return False
            
        message = {
            "type": "control",
            "data": {"command": "stop_streaming"}
        }
        
        return self.send_message(message)
    
    def map_decoded_gesture(self, gesture_info: tuple) -> bool:
        """Map decoded gesture info to Unity.
        
        Args:
            gesture_info: Tuple of (gesture_id, gesture_name, confidence)
            
        Returns:
            True if message sent successfully
        """
        if len(gesture_info) != 3:
            self.logger.error("Invalid gesture info format")
            return False
            
        gesture_id, gesture_name, confidence = gesture_info
        return self.send_gesture_info(gesture_id, gesture_name, confidence)
