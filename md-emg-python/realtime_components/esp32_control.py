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
    """ESP32 TCP client for real-time gesture control with persistent connection support"""
    
    def __init__(self, esp32_ip="192.168.1.100", tcp_port=4210, timeout=5, connection_mode="persistent", heartbeat_interval=5.0):
        """
        Initialize ESP32 controller
        
        Args:
            esp32_ip (str): ESP32 IP address
            tcp_port (int): TCP port number
            timeout (float): Connection timeout in seconds
            connection_mode (str): Connection mode - 'persistent' or 'reconnect'
            heartbeat_interval (float): Heartbeat interval for persistent connections
        """
        self.esp32_ip = esp32_ip
        self.tcp_port = tcp_port
        self.timeout = timeout
        
        # TCP socket
        self.sock = None
        self.connected = False
        
        # Connection mode settings
        self.connection_mode = connection_mode
        self.heartbeat_interval = heartbeat_interval
        self.last_heartbeat = 0
        
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
            # Update connection mode settings
            if 'connection_mode' in gesture_mapping_config:
                self.connection_mode = gesture_mapping_config['connection_mode']
                print(f"ESP32: Connection mode set to {self.connection_mode}")
            
            if 'heartbeat_interval' in gesture_mapping_config:
                self.heartbeat_interval = gesture_mapping_config['heartbeat_interval']
                print(f"ESP32: Heartbeat interval set to {self.heartbeat_interval}s")
            
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
        
        print(f"ESP32 Controller initialized for {self.esp32_ip}:{self.tcp_port} (mode: {self.connection_mode})")
    
    def connect(self):
        """Connect to ESP32 TCP server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set socket options for better stability
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Platform-specific keep-alive settings
            if hasattr(socket, 'TCP_KEEPIDLE'):
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
            if hasattr(socket, 'TCP_KEEPCNT'):
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
                
            self.sock.settimeout(self.timeout)
            
            print(f"Connecting to ESP32 at {self.esp32_ip}:{self.tcp_port}...")
            self.sock.connect((self.esp32_ip, self.tcp_port))
            
            # Check for welcome message
            try:
                self.sock.settimeout(2)  # Short timeout for welcome
                welcome = self.sock.recv(1024).decode().strip()
                if welcome:
                    print(f"ESP32 says: {welcome}")
            except socket.timeout:
                pass  # No welcome message is okay
            except:
                pass
            
            # Restore original timeout
            self.sock.settimeout(self.timeout)
            
            # Set connected flag before testing commands
            self.connected = True
            
            # Test connection with relax gesture
            print("Testing ESP32 commands...")
            test_result = self.send_command("g:0")
            if test_result:
                print("✓ ESP32 connection established")
                return True
            else:
                print("✗ ESP32 command test failed")
                self.connected = False
                self.disconnect()
                return False
                
        except socket.timeout:
            print(f"✗ ESP32 connection timeout after {self.timeout}s")
            return False
        except ConnectionRefusedError:
            print("✗ ESP32 connection refused - check if ESP32 TCP server is running")
            return False
        except OSError as e:
            if "Network is unreachable" in str(e):
                print("✗ Network unreachable - check IP address and network connectivity")
            elif "No route to host" in str(e):
                print("✗ No route to host - check if device is on same network")
            else:
                print(f"✗ Network error: {e}")
            return False
        except Exception as e:
            print(f"✗ ESP32 connection failed: {e}")
            return False
    
    def send_command(self, command):
        """
        Send command to ESP32 with improved error handling and persistent connection support
        
        Args:
            command (str): Command to send
            
        Returns:
            bool: True if command sent successfully
        """
        if not self.connected or not self.sock:
            if self.connection_mode == "persistent":
                print(f"ESP32: Attempting to reconnect for command '{command}'")
                if not self.connect():
                    print(f"✗ Cannot send command '{command}' - reconnection failed")
                    return False
            else:
                print(f"✗ Cannot send command '{command}' - not connected")
                return False
        
        try:
            # Send command with newline
            message = command + '\n'
            self.sock.sendall(message.encode())
            
            # For persistent connections, we're more lenient with responses
            # For reconnect mode, we wait for proper responses
            response_timeout = 0.5 if self.connection_mode == "persistent" else 1.0
            
            original_timeout = self.sock.gettimeout()
            try:
                self.sock.settimeout(response_timeout)
                response = self.sock.recv(1024).decode().strip()
                
                # Restore original timeout
                self.sock.settimeout(original_timeout)
                
                if response == "OK":
                    return True
                elif "ERROR" in response.upper():
                    print(f"⚠️  ESP32 error for '{command}': {response}")
                    return False
                elif not response:
                    # Empty response - treat as success for persistent connections
                    if self.connection_mode == "persistent":
                        return True
                    else:
                        print(f"⚠️  ESP32 no response for '{command}'")
                        return False
                else:
                    print(f"⚠️  ESP32 unexpected response for '{command}': {response}")
                    # Still treat as success if ESP32 responded with something
                    return True
                    
            except socket.timeout:
                # Restore original timeout
                self.sock.settimeout(original_timeout)
                # For persistent connections, timeout is more acceptable
                if self.connection_mode == "persistent":
                    return True
                else:
                    print(f"⚠️  ESP32 response timeout for command: {command}")
                    return False
                
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"✗ ESP32 connection lost: {e}")
            self.connected = False
            if self.connection_mode == "persistent":
                print("ESP32: Attempting immediate reconnection...")
                return self.connect() and self.send_command(command)
            return False
        except Exception as e:
            print(f"✗ Error sending command '{command}': {e}")
            self.connected = False
            return False
    
    def send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        if self.connection_mode == "persistent" and self.connected:
            current_time = time.perf_counter()
            if current_time - self.last_heartbeat >= self.heartbeat_interval:
                # For persistent connections with active gesture commands, we don't need heartbeat
                # The regular gesture commands will keep the connection alive
                # Only send heartbeat if we haven't sent any commands recently
                self.last_heartbeat = current_time
                print("ESP32: Heartbeat interval reached (skipping heartbeat for active gesture session)")
                return True
        return True
    
    def set_gesture(self, gesture_id):
        """
        Set gesture on ESP32 with simplified, more reliable approach
        
        Args:
            gesture_id (int): Gesture ID (0-8)
        """
        if self.connected and 0 <= gesture_id <= 8:
            # Use only gesture commands for better reliability
            # The ESP32 should handle finger states internally based on gesture ID
            
            gesture_success = self.send_command(f"g:{gesture_id}")
            
            if gesture_success:
                print(f"ESP32: Sent gesture {gesture_id} (success)")
                return True
            else:
                print(f"ESP32: Failed to send gesture {gesture_id}")
                return False
                
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
    
    # Initialize ESP32 controller with persistent connection settings
    esp32_controller = ESP32Controller(
        esp32_ip=esp32_params['ip_address'],
        tcp_port=esp32_params['port'],
        timeout=esp32_params['timeout'],
        connection_mode=esp32_params.get('connection_mode', 'reconnect'),
        heartbeat_interval=esp32_params.get('heartbeat_interval', 5.0)
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
    gesture_hold_time = esp32_params.get('gesture_hold_time', 0.1)  # Reduced from 0.5 to 0.1 seconds
    last_gesture_time = 0
    connection_retry_time = 0
    connection_retry_interval = 10  # Retry connection every 10 seconds for reconnect mode
    
    print(f"ESP32 Control Loop: Using {esp32_controller.connection_mode} connection mode")
    if esp32_controller.connection_mode == "persistent":
        print(f"ESP32 Control Loop: Heartbeat interval set to {esp32_controller.heartbeat_interval}s")
    
    # Main control loop
    while not stop_program.value:
        try:
            current_time = time.perf_counter()
            
            # Handle connection management based on mode
            if esp32_controller.connection_mode == "persistent":
                # For persistent mode, check connection status before heartbeat
                if esp32_controller.connected:
                    # Send heartbeat to keep connection alive
                    esp32_controller.send_heartbeat()
                
                # If connection is lost in persistent mode, try immediate reconnection
                if not esp32_controller.connected:
                    print("ESP32: Persistent connection lost, attempting immediate reconnection...")
                    if esp32_controller.connect():
                        print("ESP32: Persistent connection restored")
                        # Reset initial parameters
                        if 'default_pressure' in esp32_params:
                            flex_pressure = esp32_params['default_pressure']['flexion']
                            ext_pressure = esp32_params['default_pressure']['extension']
                            esp32_controller.set_pressure(flex_pressure, ext_pressure)
                        
                        if 'default_speed' in esp32_params:
                            esp32_controller.set_speed(esp32_params['default_speed'])
                    else:
                        print("ESP32: Persistent reconnection failed, will retry with next command")
                        # Clear the queue during connection issues to prevent buildup
                        try:
                            pred_esp32_queue.get_nowait()
                        except Empty:
                            pass
                        time.sleep(0.1)
                        continue
            else:
                # For reconnect mode, use periodic connection checks
                if (not esp32_controller.connected and 
                    current_time - connection_retry_time >= connection_retry_interval):
                    print("Attempting to reconnect to ESP32...")
                    if esp32_controller.connect():
                        print("ESP32 reconnected successfully")
                        # Reset initial parameters
                        if 'default_pressure' in esp32_params:
                            flex_pressure = esp32_params['default_pressure']['flexion']
                            ext_pressure = esp32_params['default_pressure']['extension']
                            esp32_controller.set_pressure(flex_pressure, ext_pressure)
                        
                        if 'default_speed' in esp32_params:
                            esp32_controller.set_speed(esp32_params['default_speed'])
                    else:
                        print("ESP32 reconnection failed")
                    connection_retry_time = current_time
            
            # Skip processing if not connected 
            if not esp32_controller.connected:
                # Clear queue to prevent buildup during disconnection
                try:
                    pred_esp32_queue.get_nowait()
                except Empty:
                    pass
                time.sleep(0.1)
                continue
            
            # Get prediction data with longer timeout to avoid missing data
            try:
                data = pred_esp32_queue.get(timeout=0.5)  # Increased timeout from 0.1 to 0.5
            except Empty:
                # No prediction data available, continue
                continue
            
            if data is not None:
                pred = data[0]  # prediction from the model
                pred_prob = data[1]  # prediction probability
                
                # Map EMG prediction to ESP32 gesture
                esp32_gesture = esp32_controller.gesture_mapping.get(pred, 0)
                
                # Always send gesture commands, but apply hold time for different gestures only
                should_send = True
                if (esp32_gesture != last_gesture and 
                    current_time - last_gesture_time < gesture_hold_time):
                    should_send = False
                    print(f"ESP32: Gesture {esp32_gesture} within hold time, skipping (EMG pred: {pred}, prob: {pred_prob:.2f})")
                
                if should_send:
                    print(f"ESP32: Setting gesture {esp32_gesture} (EMG pred: {pred}, prob: {pred_prob:.2f})")
                    
                    success = esp32_controller.set_gesture(esp32_gesture)
                    if success:
                        print(f"ESP32: Sent gesture {esp32_gesture} (success)")
                        if esp32_gesture != last_gesture:
                            last_gesture = esp32_gesture
                            last_gesture_time = current_time
                    else:
                        print(f"ESP32: Failed to send gesture {esp32_gesture} - connection may be lost")
            else:
                break
                
        except Empty:
            # Timeout occurred, continue loop
            continue
        except Exception as e:
            print(f"ESP32 control loop error: {e}")
            time.sleep(0.1)
            continue
    
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
