#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Unity Hand Interface Module
Handles communication with Unity for controlling the 3D hand model.
"""

import socket
import time
import json
import threading
import numpy as np
import logging
from queue import Queue
import os

from ini import HAND_CONTROL, DOF_CONFIG, logger

class UnityHandInterface:
    """Class for sending commands to control a 3D hand model in Unity."""
    
    def __init__(self, ip_address=None, port=None):
        """Initialize the Unity hand interface.
        
        Args:
            ip_address (str): IP address of the Unity application
            port (int): Port number for communication
        """
        self.ip_address = ip_address or HAND_CONTROL["ip_address"]
        self.port = port or HAND_CONTROL["port"]
        self.protocol = HAND_CONTROL["protocol"]
        self.update_rate = HAND_CONTROL["update_rate"]
        self.command_delay = HAND_CONTROL["command_delay"]
        
        self.socket = None
        self.is_connected = False
        self.is_streaming = False
        self.thread = None
        self.command_queue = Queue()
        
        # Track hand state
        self.hand_state = {
            "thumb_flexion": 0.0,
            "thumb_extension": 0.0,
            "thumb_pinching": 0.0,
            "index_flexion": 0.0,
            "index_extension": 0.0,
            "index_pinching": 0.0,
            "middle_flexion": 0.0,
            "middle_extension": 0.0,
            "middle_pinching": 0.0,
            "ring_little_flexion": 0.0,
            "ring_little_extension": 0.0,
            "thumb_abduction": 0.0
        }
        
        logger.info(f"Unity hand interface initialized ({self.ip_address}:{self.port})")
    
    def connect(self):
        """Establish connection with the Unity application.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Create socket based on protocol
            if self.protocol.upper() == "UDP":
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:  # TCP
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.ip_address, self.port))
                
            self.is_connected = True
            logger.info(f"Connected to Unity at {self.ip_address}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Unity: {str(e)}")
            return False
    
    def disconnect(self):
        """Close connection with the Unity application."""
        if self.is_streaming:
            self.stop_streaming()
            
        if self.socket:
            try:
                if self.protocol.upper() != "UDP":
                    # Send disconnect message for TCP
                    self.socket.sendall(json.dumps({"command": "disconnect"}).encode('utf-8'))
                self.socket.close()
            except:
                pass
            
        self.is_connected = False
        self.socket = None
        logger.info("Disconnected from Unity")
    
    def _streaming_thread(self):
        """Thread function for continuous command streaming."""
        logger.info("Starting Unity command streaming")
        
        last_update_time = time.time()
        
        while self.is_streaming:
            try:
                # Check if it's time for an update
                current_time = time.time()
                if current_time - last_update_time >= 1.0 / self.update_rate:
                    last_update_time = current_time
                    
                    # Get command from queue if available, otherwise use current state
                    try:
                        command = self.command_queue.get_nowait()
                        # Update hand state with new command
                        if isinstance(command, dict):
                            for key, value in command.items():
                                if key in self.hand_state:
                                    self.hand_state[key] = value
                    except:
                        # No new commands, use current state
                        pass
                    
                    # Send current hand state
                    self._send_hand_state()
                    
                # Small delay to prevent CPU hogging
                time.sleep(0.001)
                    
            except Exception as e:
                logger.error(f"Error in streaming thread: {str(e)}")
                if not self.is_streaming:
                    break
                time.sleep(0.1)  # Brief pause before retrying
    
    def _send_hand_state(self):
        """Send the current hand state to Unity."""
        if not self.is_connected:
            logger.warning("Cannot send command: Not connected")
            return False
            
        try:
            # Prepare the command packet
            command_packet = {
                "timestamp": time.time(),
                "command": "set_hand_state",
                "parameters": self.hand_state
            }
            
            # Serialize the command
            data = json.dumps(command_packet).encode('utf-8')
            
            # Send command based on protocol
            if self.protocol.upper() == "UDP":
                self.socket.sendto(data, (self.ip_address, self.port))
            else:  # TCP
                self.socket.sendall(data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error sending hand state: {str(e)}")
            # Connection might be lost
            if "Broken pipe" in str(e) or "Connection reset" in str(e):
                self.is_connected = False
            return False
    
    def start_streaming(self):
        """Start continuous command streaming to Unity.
        
        Returns:
            bool: True if streaming started successfully
        """
        if self.is_streaming:
            logger.warning("Command streaming is already active")
            return False
            
        if not self.is_connected:
            if not self.connect():
                logger.error("Cannot start streaming: Failed to connect")
                return False
                
        # Start the streaming thread
        self.is_streaming = True
        self.thread = threading.Thread(target=self._streaming_thread)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Unity command streaming started")
        return True
    
    def stop_streaming(self):
        """Stop command streaming to Unity."""
        if not self.is_streaming:
            return
            
        self.is_streaming = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
            
        logger.info("Unity command streaming stopped")
    
    def queue_command(self, command):
        """Add a command to the streaming queue.
        
        Args:
            command (dict): Command parameters for the hand state
            
        Returns:
            bool: True if command was queued
        """
        if not isinstance(command, dict):
            logger.error("Invalid command format: must be a dictionary")
            return False
            
        # Validate command parameters
        valid_keys = set(self.hand_state.keys())
        command_keys = set(command.keys())
        
        if not command_keys.issubset(valid_keys):
            invalid_keys = command_keys - valid_keys
            logger.warning(f"Invalid command parameters: {invalid_keys}")
            
        # Filter out invalid keys
        filtered_command = {k: v for k, v in command.items() if k in valid_keys}
        
        # Add to queue
        self.command_queue.put(filtered_command)
        return True
    
    def send_gesture(self, gesture_name, intensity=1.0):
        """Send a predefined gesture to Unity.
        
        Args:
            gesture_name (str): Name of the gesture to send
            intensity (float): Intensity of the gesture (0.0 to 1.0)
            
        Returns:
            bool: True if gesture was sent
        """
        intensity = max(0.0, min(1.0, intensity))  # Clamp to [0, 1]
        
        # Define predefined gestures
        gestures = {
            "rest": {k: 0.0 for k in self.hand_state.keys()},
            
            "open_hand": {
                "thumb_extension": 1.0,
                "index_extension": 1.0,
                "middle_extension": 1.0,
                "ring_little_extension": 1.0,
                "thumb_abduction": 0.5,
            },
            
            "power_grip": {
                "thumb_flexion": 0.8,
                "index_flexion": 1.0,
                "middle_flexion": 1.0,
                "ring_little_flexion": 1.0,
            },
            
            "precision_grip": {
                "thumb_flexion": 0.6,
                "thumb_pinching": 0.9,
                "index_flexion": 0.7,
                "index_pinching": 0.9,
                "middle_flexion": 0.3,
                "ring_little_flexion": 0.3,
            },
            
            "index_point": {
                "thumb_flexion": 0.6,
                "index_extension": 1.0,
                "middle_flexion": 0.9,
                "ring_little_flexion": 0.9,
            },
            
            "thumbs_up": {
                "thumb_extension": 1.0,
                "thumb_abduction": 0.8,
                "index_flexion": 1.0,
                "middle_flexion": 1.0,
                "ring_little_flexion": 1.0,
            },
            
            "thumb_flexion": {
                "thumb_flexion": 1.0,
            },
            
            "index_flexion": {
                "index_flexion": 1.0,
            },
            
            "middle_flexion": {
                "middle_flexion": 1.0,
            },
            
            "ring_little_flexion": {
                "ring_little_flexion": 1.0,
            },
        }
        
        # Check if gesture exists
        if gesture_name not in gestures:
            logger.warning(f"Unknown gesture: {gesture_name}")
            return False
            
        # Get the gesture and scale by intensity
        gesture = gestures[gesture_name]
        scaled_gesture = {k: v * intensity for k, v in gesture.items()}
        
        # Send the gesture
        return self.queue_command(scaled_gesture)
    
    def map_decoded_gesture(self, decoded_gesture, confidence=1.0):
        """Map a decoded gesture from the EMG decoder to Unity hand control.
        
        Args:
            decoded_gesture (str): Gesture name from the EMG decoder
            confidence (float): Confidence level (0.0 to 1.0)
            
        Returns:
            bool: True if gesture was mapped and sent
        """
        # Direct mappings from decoded gestures to Unity gestures
        direct_mappings = {
            "thumb_flexion": "thumb_flexion",
            "thumb_extension": "open_hand",
            "index_flexion": "index_flexion",
            "index_extension": "open_hand",
            "middle_flexion": "middle_flexion",
            "middle_extension": "open_hand",
            "ring_little_flexion": "ring_little_flexion",
            "ring_little_extension": "open_hand",
            "power_grip": "power_grip",
            "precision_grip": "precision_grip",
            "rest": "rest",
            "open_hand": "open_hand",
        }
        
        # Check for direct mapping
        if decoded_gesture in direct_mappings:
            return self.send_gesture(direct_mappings[decoded_gesture], confidence)
        
        # Handle custom or complex gestures
        if decoded_gesture == "thumb_pinching":
            return self.queue_command({"thumb_pinching": confidence})
            
        if decoded_gesture == "index_pinching":
            return self.queue_command({"index_pinching": confidence})
            
        if decoded_gesture == "middle_pinching":
            return self.queue_command({"middle_pinching": confidence})
            
        if decoded_gesture == "thumb_abduction":
            return self.queue_command({"thumb_abduction": confidence})
            
        logger.warning(f"No mapping for gesture: {decoded_gesture}")
        return False
        
    def reset_hand(self):
        """Reset the hand to its default position (rest).
        
        Returns:
            bool: True if command was sent
        """
        return self.send_gesture("rest")

    def send_test_sequence(self):
        """Send a test sequence of gestures to Unity.
        
        Returns:
            bool: True if test sequence started
        """
        if not self.is_connected:
            if not self.connect():
                logger.error("Cannot send test sequence: Failed to connect")
                return False
                
        if not self.is_streaming:
            if not self.start_streaming():
                logger.error("Cannot send test sequence: Failed to start streaming")
                return False
                
        # Define test sequence
        test_sequence = [
            ("rest", 1.0),
            ("open_hand", 1.0),
            ("power_grip", 1.0),
            ("open_hand", 1.0),
            ("precision_grip", 1.0),
            ("open_hand", 1.0),
            ("thumb_flexion", 1.0),
            ("index_flexion", 1.0),
            ("middle_flexion", 1.0),
            ("ring_little_flexion", 1.0),
            ("open_hand", 1.0),
            ("rest", 1.0),
        ]
        
        # Run test sequence in a separate thread
        def _run_sequence():
            logger.info("Starting test sequence")
            for gesture, intensity in test_sequence:
                if not self.is_streaming:
                    break
                logger.info(f"Sending gesture: {gesture}")
                self.send_gesture(gesture, intensity)
                time.sleep(1.0)  # Hold each gesture for 1 second
            logger.info("Test sequence complete")
            
        thread = threading.Thread(target=_run_sequence)
        thread.daemon = True
        thread.start()
        
        return True


if __name__ == "__main__":
    # Simple test script
    interface = UnityHandInterface()
    
    if interface.connect():
        print("Connected to Unity")
        
        # Start command streaming
        interface.start_streaming()
        
        print("Running test sequence...")
        interface.send_test_sequence()
        
        # Keep running for a while
        try:
            for i in range(15):  # Run for 15 seconds
                time.sleep(1)
                print(f"Running... {i+1}/15")
        except KeyboardInterrupt:
            print("Test interrupted")
            
        # Clean up
        interface.stop_streaming()
        interface.disconnect()
        print("Disconnected from Unity")
    else:
        print("Failed to connect to Unity")