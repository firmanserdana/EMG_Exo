#!/usr/bin/env python3
"""
EMG-ESP32-Unity Integration Simulation
=====================================

Simulates the complete EMG control sequence as done in emg_control_64.py:
1. Connect to Unity VR (events server on port 55000)
2. Connect to Unity VR (streaming server on port 55001) 
3. Connect to ESP32 pneumatic glove (TCP server on port 4210)
4. Simulate gesture predictions and send commands to both systems
5. Test the complete integration pipeline

Author: EMG-Exo Control System
"""

import socket
import time
import json
import threading
from datetime import datetime

class UnityEventClient:
    """Unity events server client (port 55000)"""
    
    def __init__(self, host="127.0.0.1", port=55000, timeout=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.connected = False
        
    def connect(self):
        """Connect to Unity events server"""
        try:
            print(f"Connecting to Unity events server at {self.host}:{self.port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print("✓ Unity events server connected")
            return True
        except Exception as e:
            print(f"✗ Unity events connection failed: {e}")
            return False
    
    def send_event(self, event_type, data=""):
        """Send event to Unity"""
        if not self.connected:
            return False
        
        try:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "data": data
            }
            message = json.dumps(event) + "\n"
            self.sock.send(message.encode())
            print(f"Unity Event: {event_type} ({data})")
            return True
        except Exception as e:
            print(f"✗ Unity event send failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Unity events server"""
        if self.sock:
            self.sock.close()
        self.connected = False

class UnityStreamClient:
    """Unity streaming server client (port 55001)"""
    
    def __init__(self, host="127.0.0.1", port=55001, timeout=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.connected = False
        
    def connect(self):
        """Connect to Unity streaming server"""
        try:
            print(f"Connecting to Unity streaming server at {self.host}:{self.port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print("✓ Unity streaming server connected")
            return True
        except Exception as e:
            print(f"✗ Unity streaming connection failed: {e}")
            return False
    
    def send_stream_data(self, gesture_id, probability):
        """Send streaming gesture data to Unity"""
        if not self.connected:
            return False
        
        try:
            stream_data = {
                "gesture": gesture_id,
                "probability": probability,
                "timestamp": time.time()
            }
            message = json.dumps(stream_data) + "\n"
            self.sock.send(message.encode())
            print(f"Unity Stream: gesture {gesture_id}, prob {probability:.2f}")
            return True
        except Exception as e:
            print(f"✗ Unity stream send failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Unity streaming server"""
        if self.sock:
            self.sock.close()
        self.connected = False

class ESP32Controller:
    """ESP32 TCP client for pneumatic glove control"""
    
    def __init__(self, esp32_ip="172.20.10.3", tcp_port=4210, timeout=10):
        self.esp32_ip = esp32_ip
        self.tcp_port = tcp_port
        self.timeout = timeout
        self.sock = None
        self.connected = False
        
        # Gesture to finger states mapping (from ESP32 firmware)
        self.gesture_finger_mapping = {
            0: "000000",  # Relax
            1: "111110",  # HandClose (All flex)
            2: "222220",  # HandOpen (All extend)
            3: "011110",  # HookGrasp (IMRP Flexion)
            4: "333000",  # LateralGrasp (3-finger pinch)
            5: "100000",  # ThumbFlexion
            6: "010000",  # IndexFlexion
            7: "001110",  # MRPFlexion (Middle, Ring, Pinky)
            8: "121110",  # IndexPointing
        }
        
    def connect(self):
        """Connect to ESP32 TCP server"""
        try:
            print(f"Connecting to ESP32 at {self.esp32_ip}:{self.tcp_port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set socket options for better stability
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(self.timeout)
            
            self.sock.connect((self.esp32_ip, self.tcp_port))
            
            # Check for welcome message
            try:
                self.sock.settimeout(2)
                welcome = self.sock.recv(1024).decode().strip()
                if welcome:
                    print(f"ESP32 says: {welcome}")
            except socket.timeout:
                pass
            
            self.sock.settimeout(self.timeout)
            self.connected = True
            
            # Test connection with relax gesture
            print("Testing ESP32 commands...")
            if self.send_gesture(0):
                print("✓ ESP32 connection established")
                return True
            else:
                print("✗ ESP32 command test failed")
                self.connected = False
                return False
                
        except Exception as e:
            print(f"✗ ESP32 connection failed: {e}")
            return False
    
    def send_command(self, command):
        """Send raw command to ESP32"""
        if not self.connected:
            return False
        
        try:
            self.sock.send((command + "\n").encode())
            
            # Wait for response
            self.sock.settimeout(2)
            response = self.sock.recv(1024).decode().strip()
            self.sock.settimeout(self.timeout)
            
            success = response == "OK"
            if not success:
                print(f"ESP32 error response: {response}")
            
            return success
        except Exception as e:
            print(f"✗ ESP32 command failed: {e}")
            return False
    
    def send_gesture(self, gesture_id):
        """Send gesture command to ESP32 with backup finger states"""
        if not self.connected:
            return False
        
        try:
            # Send gesture command
            gesture_cmd = f"g:{gesture_id}"
            gesture_success = self.send_command(gesture_cmd)
            
            # Send backup finger states command
            finger_states = self.gesture_finger_mapping.get(gesture_id, "000000")
            finger_cmd = f"f:{finger_states}"
            finger_success = self.send_command(finger_cmd)
            
            overall_success = gesture_success and finger_success
            
            print(f"ESP32: Sent gesture {gesture_id} + finger_state {finger_states} (success: {overall_success})")
            return overall_success
            
        except Exception as e:
            print(f"✗ ESP32 gesture send failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ESP32"""
        if self.sock:
            self.sock.close()
        self.connected = False

class EMGSimulator:
    """Simulates EMG gesture predictions"""
    
    def __init__(self):
        self.gesture_names = [
            "Relax", "HandClose", "HandOpen", "HookGrasp", 
            "LateralGrasp", "ThumbFlexion", "IndexFlexion", 
            "MRPFlexion", "IndexPointing"
        ]
        
        # Simulation sequence - realistic gesture patterns
        self.simulation_sequence = [
            (0, 0.95),  # Relax
            (1, 0.87),  # HandClose
            (0, 0.92),  # Relax
            (2, 0.89),  # HandOpen
            (0, 0.93),  # Relax
            (3, 0.85),  # HookGrasp
            (0, 0.94),  # Relax
            (4, 0.82),  # LateralGrasp
            (0, 0.91),  # Relax
            (5, 0.86),  # ThumbFlexion
            (0, 0.88),  # Relax
            (6, 0.84),  # IndexFlexion
            (0, 0.90),  # Relax
            (7, 0.83),  # MRPFlexion
            (0, 0.89),  # Relax
            (8, 0.81),  # IndexPointing
            (0, 0.92),  # Relax
        ]
        
        self.current_step = 0
        
    def get_next_prediction(self):
        """Get next simulated prediction"""
        if self.current_step >= len(self.simulation_sequence):
            return None, None
        
        gesture_id, probability = self.simulation_sequence[self.current_step]
        self.current_step += 1
        
        return gesture_id, probability
    
    def get_gesture_name(self, gesture_id):
        """Get gesture name from ID"""
        if 0 <= gesture_id < len(self.gesture_names):
            return self.gesture_names[gesture_id]
        return "Unknown"

def main():
    """Main simulation function"""
    print("=== EMG-ESP32-Unity Integration Simulation ===")
    print("Simulating the complete EMG control sequence...\n")
    
    # Initialize components
    unity_events = UnityEventClient()
    unity_stream = UnityStreamClient()
    esp32 = ESP32Controller()
    emg_sim = EMGSimulator()
    
    print("1. Connecting to Unity VR systems...")
    
    # Connect to Unity events server
    unity_events_connected = unity_events.connect()
    
    # Connect to Unity streaming server
    unity_stream_connected = unity_stream.connect()
    
    print("\n2. Connecting to ESP32 pneumatic glove...")
    
    # Connect to ESP32
    esp32_connected = esp32.connect()
    
    # Check connection status
    if not (unity_events_connected or unity_stream_connected or esp32_connected):
        print("\n✗ No connections established. Please check:")
        print("  - Unity VR application is running with socket servers")
        print("  - ESP32 is powered on and connected to WiFi")
        print("  - Network connectivity is working")
        return
    
    print(f"\n3. Connection Status:")
    print(f"   Unity Events: {'✓ Connected' if unity_events_connected else '✗ Failed'}")
    print(f"   Unity Stream: {'✓ Connected' if unity_stream_connected else '✗ Failed'}")
    print(f"   ESP32 Glove:  {'✓ Connected' if esp32_connected else '✗ Failed'}")
    
    if unity_events_connected:
        unity_events.send_event("session_start", "EMG simulation started")
    
    print(f"\n4. Starting gesture simulation sequence...")
    print("   (This simulates real EMG predictions being sent to both systems)")
    
    try:
        step = 0
        while True:
            # Get next prediction
            gesture_id, probability = emg_sim.get_next_prediction()
            
            if gesture_id is None:
                print("\n✓ Simulation sequence completed!")
                break
            
            step += 1
            gesture_name = emg_sim.get_gesture_name(gesture_id)
            
            print(f"\n--- Step {step}: EMG Prediction ---")
            print(f"Predicted: {gesture_name} (ID: {gesture_id}) - Confidence: {probability:.2f}")
            
            # Send to Unity VR systems
            if unity_events_connected:
                unity_events.send_event("gesture_prediction", f"{gesture_name}:{probability:.2f}")
            
            if unity_stream_connected:
                unity_stream.send_stream_data(gesture_id, probability)
            
            # Send to ESP32 pneumatic glove
            if esp32_connected:
                esp32.send_gesture(gesture_id)
            
            # Simulate prediction interval (like real EMG processing)
            time.sleep(1.5)
            
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user")
    
    print(f"\n5. Cleaning up connections...")
    
    # Send session end event
    if unity_events_connected:
        unity_events.send_event("session_end", "EMG simulation completed")
    
    # Disconnect all systems
    unity_events.disconnect()
    unity_stream.disconnect()
    esp32.disconnect()
    
    print("✓ All connections closed")
    print("\n=== Simulation Complete ===")
    print("\nThis simulation demonstrated:")
    print("  • Unity VR event communication (port 55000)")
    print("  • Unity VR streaming communication (port 55001)")
    print("  • ESP32 pneumatic glove control (port 4210)")
    print("  • Complete EMG gesture prediction pipeline")

if __name__ == "__main__":
    main()
