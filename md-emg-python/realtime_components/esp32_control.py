"""
ESP32 Glove Control Component
============================

Real-time control interface for ESP32-based pneumatic glove system.
Receives decoded gestures from EMG processing and translates them to ESP32 commands.

Author: EMG-Exo Control System
"""

import socket
import time
import json
import threading
from queue import Queue, Empty


class ESP32Controller:
    """ESP32 TCP client for real-time gesture control"""
    
    def __init__(self, esp32_ip="192.168.1.100", tcp_port=4210, timeout=5):
        """
        Initialize ESP32 controller
        
        Args:
            esp32_ip (str): ESP32 IP address
            tcp_port (int): TCP port number
            timeout (float): Connection timeout in seconds
        """
        self.esp32_ip = esp32_ip
        self.tcp_port = tcp_port
        self.timeout = timeout
        
        # TCP socket
        self.sock = None
        self.connected = False
        
        # Default gesture mapping (will be updated from config)
        self.gesture_mapping = {
            0: 2,  # Hand Open -> Extend
            1: 1,  # Fist -> All Flex
            2: 3,  # HookGrasp -> IMRP Flex
            3: 4,  # LateralGrasp -> 3-Finger Pinch
            4: 8,  # IndexPointing -> Index
            5: 5,  # ThumbFlexion -> Thumb
            6: 6,  # IndexFlexion -> Index
            7: 7,  # MRPFlexion -> MRP Flex
        }
        
        # Task-specific mappings (updated from config if available)
        self.task_mappings = {
            'open_close': {},
            'grasp_patterns': {},
            'single_fingers': {}
        }
        
    def update_gesture_mapping(self, task=None, gesture_mapping_config=None):
        """
        Update gesture mapping based on task and configuration
        
        Args:
            task (str): Task type ('open_close', 'grasp_patterns', 'single_fingers')
            gesture_mapping_config (dict): Configuration with gesture mappings
        """
        if gesture_mapping_config:
            # Update task-specific mappings
            if 'gesture_mapping_open_close' in gesture_mapping_config:
                self.task_mappings['open_close'] = gesture_mapping_config['gesture_mapping_open_close']
            if 'gesture_mapping_grasp_patterns' in gesture_mapping_config:
                self.task_mappings['grasp_patterns'] = gesture_mapping_config['gesture_mapping_grasp_patterns']
            if 'gesture_mapping_single_fingers' in gesture_mapping_config:
                self.task_mappings['single_fingers'] = gesture_mapping_config['gesture_mapping_single_fingers']
            
            # Update default mapping
            if 'gesture_mapping' in gesture_mapping_config:
                self.gesture_mapping.update(gesture_mapping_config['gesture_mapping'])
        
        # Use task-specific mapping if available
        if task and task in self.task_mappings and self.task_mappings[task]:
            self.gesture_mapping = self.task_mappings[task].copy()
            print(f"ESP32: Using {task} gesture mapping")
        else:
            print("ESP32: Using default gesture mapping")
        
        print(f"ESP32 Controller initialized for {self.esp32_ip}:{self.tcp_port}")
    
    def connect(self):
        """Connect to ESP32 TCP server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            
            print(f"Connecting to ESP32 at {self.esp32_ip}:{self.tcp_port}...")
            self.sock.connect((self.esp32_ip, self.tcp_port))
            
            # Test connection with relax gesture
            test_result = self.send_command("g:0")
            if test_result:
                self.connected = True
                print("✓ ESP32 connection established")
                return True
            else:
                print("✗ ESP32 connection test failed")
                self.disconnect()
                return False
                
        except socket.timeout:
            print("✗ ESP32 connection timeout")
            return False
        except ConnectionRefusedError:
            print("✗ ESP32 connection refused - device may not be running")
            return False
        except Exception as e:
            print(f"✗ ESP32 connection failed: {e}")
            return False
    
    def send_command(self, command):
        """
        Send command to ESP32
        
        Args:
            command (str): Command to send
            
        Returns:
            bool: True if command sent successfully
        """
        if not self.connected or not self.sock:
            return False
        
        try:
            # Send command with newline
            message = command + '\n'
            self.sock.sendall(message.encode())
            
            # Wait for response
            try:
                response = self.sock.recv(1024).decode().strip()
                if response == "OK":
                    return True
                else:
                    print(f"⚠️  ESP32 response: {response}")
                    return False
            except socket.timeout:
                print(f"⚠️  ESP32 command timeout: {command}")
                return False
                
        except BrokenPipeError:
            print("✗ ESP32 connection lost")
            self.connected = False
            return False
        except Exception as e:
            print(f"✗ ESP32 send failed: {e}")
            return False
    
    def set_gesture(self, gesture_id):
        """
        Set gesture on ESP32
        
        Args:
            gesture_id (int): Gesture ID (0-8)
        """
        if self.connected and 0 <= gesture_id <= 8:
            return self.send_command(f"g:{gesture_id}")
        return False
    
    def set_pressure(self, flexion, extension):
        """
        Set pressure levels
        
        Args:
            flexion (int): Flexion pressure (0-100)
            extension (int): Extension pressure (0-100)
        """
        if self.connected and 0 <= flexion <= 100 and 0 <= extension <= 100:
            return self.send_command(f"p:{flexion}:{extension}")
        return False
    
    def set_speed(self, speed_level):
        """
        Set speed level
        
        Args:
            speed_level (int): Speed level (0-4)
        """
        if self.connected and 0 <= speed_level <= 4:
            return self.send_command(f"s:{speed_level}")
        return False
    
    def emergency_stop(self):
        """Emergency stop all actions"""
        if self.connected:
            return self.send_command("stop")
        return False
    
    def disconnect(self):
        """Close connection"""
        try:
            if self.sock:
                self.sock.close()
            self.connected = False
            print("ESP32 connection closed")
        except:
            pass


def ESP32ControlLoop(esp32_params, pred_esp32_queue, stop_program, task=None):
    """
    ESP32 control loop process
    Receives decoded gestures and sends them to ESP32 glove
    
    Args:
        esp32_params (dict): ESP32 configuration parameters
        pred_esp32_queue (Queue): Queue for receiving gesture predictions
        stop_program (Value): Shared variable to stop the loop
        task (str): Task type for gesture mapping ('open_close', 'grasp_patterns', 'single_fingers')
    """
    print('Starting ESP32 control loop...')
    
    # Initialize ESP32 controller
    esp32_controller = ESP32Controller(
        esp32_ip=esp32_params['ip_address'],
        tcp_port=esp32_params['port'],
        timeout=esp32_params['timeout']
    )
    
    # Update gesture mapping based on task and configuration
    esp32_controller.update_gesture_mapping(task=task, gesture_mapping_config=esp32_params)
    
    # Try to connect to ESP32
    if not esp32_controller.connect():
        print("Failed to connect to ESP32, continuing without ESP32 control")
        return
    
    # Set initial parameters if specified
    if 'default_pressure' in esp32_params:
        flex_pressure = esp32_params['default_pressure']['flexion']
        ext_pressure = esp32_params['default_pressure']['extension']
        esp32_controller.set_pressure(flex_pressure, ext_pressure)
    
    if 'default_speed' in esp32_params:
        esp32_controller.set_speed(esp32_params['default_speed'])
    
    last_gesture = -1
    gesture_hold_time = esp32_params.get('gesture_hold_time', 0.5)  # Minimum time between gesture changes
    last_gesture_time = 0
    
    # Main control loop
    while not stop_program.value:
        try:
            # Get prediction data with timeout
            data = pred_esp32_queue.get(timeout=0.1)
            
            if data is not None:
                pred = data[0]  # prediction from the model
                pred_prob = data[1]  # prediction probability
                current_time = time.perf_counter()
                
                # Map EMG prediction to ESP32 gesture
                esp32_gesture = esp32_controller.gesture_mapping.get(pred, 0)
                
                # Apply gesture hold time to prevent rapid switching
                if (esp32_gesture != last_gesture and 
                    current_time - last_gesture_time >= gesture_hold_time):
                    
                    print(f"ESP32: Setting gesture {esp32_gesture} (EMG pred: {pred}, prob: {pred_prob:.2f})")
                    
                    if esp32_controller.set_gesture(esp32_gesture):
                        last_gesture = esp32_gesture
                        last_gesture_time = current_time
                    else:
                        print("Failed to send gesture to ESP32")
            else:
                break
                
        except Empty:
            # Timeout occurred, continue loop
            continue
        except Exception as e:
            print(f"ESP32 control loop error: {e}")
            break
    
    # Cleanup
    esp32_controller.emergency_stop()
    esp32_controller.disconnect()
    print('ESP32 control loop stopped')


def test_esp32_connection(esp32_ip="192.168.1.100", tcp_port=4210):
    """
    Test ESP32 connection and run a simple gesture sequence
    
    Args:
        esp32_ip (str): ESP32 IP address
        tcp_port (int): TCP port number
        
    Returns:
        bool: True if test successful
    """
    print(f"Testing ESP32 connection to {esp32_ip}:{tcp_port}")
    
    controller = ESP32Controller(esp32_ip, tcp_port)
    
    if not controller.connect():
        return False
    
    try:
        # Test gesture sequence
        test_gestures = [0, 1, 3, 5, 0]  # Relax, Flex, Pinch, Thumb, Relax
        gesture_names = ["Relax", "All Flex", "2-Finger Pinch", "Thumb", "Relax"]
        
        for i, gesture in enumerate(test_gestures):
            print(f"Testing gesture: {gesture_names[i]}")
            if controller.set_gesture(gesture):
                time.sleep(1.5)
            else:
                print(f"Failed to set gesture {gesture}")
                return False
        
        print("ESP32 test sequence completed successfully")
        return True
        
    except Exception as e:
        print(f"ESP32 test failed: {e}")
        return False
    finally:
        controller.emergency_stop()
        controller.disconnect()
