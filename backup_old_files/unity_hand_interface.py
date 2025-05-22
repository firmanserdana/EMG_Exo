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

from ini import UNITY_INTERFACE, logger


class UnityHandInterface:
    """Interface to communicate with Unity hand visualization."""
    
    def __init__(self):
        """Initialize Unity communication interface."""
        # Communication settings
        self.host = UNITY_INTERFACE["host"]
        self.port = UNITY_INTERFACE["port"]
        self.protocol = UNITY_INTERFACE["protocol"]
        self.connected = False
        
        # Socket objects
        self.tcp_socket = None
        self.udp_socket = None
        
        # Thread for handling incoming messages
        self.receive_thread = None
        self.running = False
        
        # Callback for received messages
        self.message_callback = None
        
        logger.info(f"Unity Hand Interface initialized with {self.protocol.upper()} protocol")
    
    def connect(self):
        """Connect to Unity application.
        
        Returns:
            bool: True if connection established successfully
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
                
                logger.info(f"Connected to Unity via TCP: {self.host}:{self.port}")
                self.connected = True
                
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
                
                logger.info(f"UDP socket created for Unity communication: {self.host}:{self.port}")
                self.connected = True
                
            else:
                logger.error(f"Unsupported protocol: {self.protocol}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to Unity: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from Unity application."""
        self.running = False
        
        try:
            # Send disconnect message
            if self.connected:
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
                
            logger.info("Disconnected from Unity")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Unity: {str(e)}")
        
        self.connected = False
    
    def send_message(self, message):
        """Send a message to Unity application.
        
        Args:
            message (dict): Message to send (will be JSON-encoded)
            
        Returns:
            bool: True if message sent successfully
        """
        if not self.connected:
            logger.warning("Cannot send message: Not connected to Unity")
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
                logger.error("Invalid socket or protocol")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to Unity: {str(e)}")
            self.connected = False
            return False
    
    def set_message_callback(self, callback):
        """Set callback for received messages.
        
        Args:
            callback (function): Function to call when message is received
        """
        self.message_callback = callback
    
    def _receive_tcp(self):
        """Thread function to receive TCP messages from Unity."""
        logger.info("TCP receive thread started")
        
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
                logger.error("Connection reset by Unity")
                self.connected = False
                break
                
            except ConnectionAbortedError:
                logger.error("Connection aborted")
                self.connected = False
                break
                
            except Exception as e:
                logger.error(f"Error receiving TCP message: {str(e)}")
                time.sleep(0.5)
                
        logger.info("TCP receive thread ended")
    
    def _receive_udp(self):
        """Thread function to receive UDP messages from Unity."""
        logger.info("UDP receive thread started")
        
        if not self.udp_socket:
            logger.error("UDP socket not initialized")
            return
            
        # Configure socket for receiving
        try:
            self.udp_socket.bind(("0.0.0.0", self.port))
            self.udp_socket.settimeout(0.5)  # 500ms timeout for checking running flag
        except Exception as e:
            logger.error(f"Error binding UDP socket: {str(e)}")
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
                logger.error(f"Error receiving UDP message: {str(e)}")
                time.sleep(0.5)
                
        logger.info("UDP receive thread ended")
    
    def _receive_all(self, n):
        """Helper function to receive exactly n bytes via TCP.
        
        Args:
            n (int): Number of bytes to receive
            
        Returns:
            bytes: Received data or None if error/disconnect
        """
        if not self.tcp_socket:
            return None
            
        data = b''
        while len(data) < n:
            try:
                packet = self.tcp_socket.recv(n - len(data))
                if not packet:
                    # Connection closed
                    self.connected = False
                    return None
                data += packet
            except Exception as e:
                logger.error(f"Error in _receive_all: {str(e)}")
                return None
                
        return data
    
    def _handle_message(self, message_str):
        """Handle received message from Unity.
        
        Args:
            message_str (str): JSON message string
        """
        try:
            # Parse JSON message
            message = json.loads(message_str)
            
            # Log the message
            msg_type = message.get("type", "unknown")
            logger.debug(f"Received message from Unity: {msg_type}")
            
            # Call the callback if set
            if self.message_callback:
                self.message_callback(message)
                
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON message: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    def send_hand_control(self, dof_values):
        """Send hand control values to Unity.
        
        Args:
            dof_values (dict or list): Degrees of freedom values for hand
                If dict: keys are DoF names, values are position values (0-1)
                If list: values are in predefined order
                
        Returns:
            bool: True if message sent successfully
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
            logger.error(f"Error sending hand control: {str(e)}")
            return False
    
    def send_emg_data(self, emg_values):
        """Send EMG data to Unity for visualization.
        
        Args:
            emg_values (list or numpy.ndarray): EMG channel values
                
        Returns:
            bool: True if message sent successfully
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
            logger.error(f"Error sending EMG data: {str(e)}")
            return False
    
    def send_gesture_info(self, gesture_id, gesture_name, confidence):
        """Send gesture classification information to Unity.
        
        Args:
            gesture_id (int): ID of recognized gesture
            gesture_name (str): Name of recognized gesture
            confidence (float): Classification confidence (0-1)
                
        Returns:
            bool: True if message sent successfully
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
            logger.error(f"Error sending gesture info: {str(e)}")
            return False


if __name__ == "__main__":
    # Test script for Unity hand interface
    import random
    
    print("Testing Unity Hand Interface...")
    
    # Create interface
    interface = UnityHandInterface()
    
    # Connect to Unity (assumes Unity is listening)
    print("\nConnecting to Unity...")
    connected = interface.connect()
    
    if connected:
        print("Connected to Unity!")
        
        # Set a message callback
        def on_message(msg):
            print(f"Received from Unity: {msg['type']}")
            
        interface.set_message_callback(on_message)
        
        # Send some test messages
        print("\nSending test messages for 5 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 5.0:
            # Generate random DoF values
            dof_values = [random.uniform(0.0, 1.0) for _ in range(12)]
            
            # Send hand control message
            interface.send_hand_control(dof_values)
            
            # Generate random EMG values
            emg_values = [random.uniform(-1.0, 1.0) for _ in range(8)]
            
            # Send EMG data message
            interface.send_emg_data(emg_values)
            
            # Send random gesture info
            gesture_id = random.randint(0, 12)
            gesture_name = f"gesture_{gesture_id}"
            confidence = random.uniform(0.5, 1.0)
            
            interface.send_gesture_info(gesture_id, gesture_name, confidence)
            
            # Sleep briefly
            time.sleep(0.1)
            
        # Disconnect from Unity
        print("\nDisconnecting from Unity...")
        interface.disconnect()
        print("Disconnected.")
        
    else:
        print("Failed to connect to Unity.")
        print("Running simulated test...")
        
        # Generate random DoF values
        dof_values = [random.uniform(0.0, 1.0) for _ in range(12)]
        
        # Print the message we would send
        message = {
            "type": "hand_control",
            "timestamp": datetime.now().timestamp(),
            "data": {
                "thumb_flexion_1": dof_values[0],
                "thumb_flexion_2": dof_values[1],
                "thumb_flexion_3": dof_values[2],
                "index_flexion_1": dof_values[3],
                "index_flexion_2": dof_values[4],
                "index_flexion_3": dof_values[5],
                "middle_flexion_1": dof_values[6],
                "middle_flexion_2": dof_values[7],
                "middle_flexion_3": dof_values[8],
                "ring_little_flexion_1": dof_values[9],
                "ring_little_flexion_2": dof_values[10],
                "thumb_abduction": dof_values[11]
            }
        }
        
        print(f"\nSimulated hand control message: {json.dumps(message, indent=2)}")