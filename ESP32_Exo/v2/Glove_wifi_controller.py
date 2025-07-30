#!/usr/bin/env python3
"""
ESP32 Glove TCP Controller
=========================

TCP client for controlling ESP32 pneumatic glove system.
Supports gesture control, pressure adjustment, speed setting and direct finger control.

Usage:
1. Ensure ESP32 and computer are connected to the same WiFi network
2. Run this script
3. Use interactive commands or programming interface to control the glove

Author: ESP32 Glove Control System
Version: 2.0 TCP Edition
"""

import socket
import time
import threading
import sys

class ESP32GloveTCPController:
    def __init__(self, esp32_ip="192.168.1.100", tcp_port=4210, timeout=5):
        """
        Initialize ESP32 glove TCP controller
        
        Args:
            esp32_ip (str): ESP32 IP address
            tcp_port (int): TCP port number
            timeout (float): Connection timeout (seconds)
        """
        self.esp32_ip = esp32_ip
        self.tcp_port = tcp_port
        self.timeout = timeout
        
        # TCP socket
        self.sock = None
        self.connected = False
        
        print(f"ESP32 Glove TCP Controller initialized")
        print(f"Target address: {esp32_ip}:{tcp_port}")
        print(f"Timeout setting: {timeout} seconds")
    
    def connect(self):
        """Connect to ESP32 TCP server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            
            print(f"Connecting to {self.esp32_ip}:{self.tcp_port}...")
            self.sock.connect((self.esp32_ip, self.tcp_port))
            
            # Test connection with a simple command
            test_result = self.send_command("g:0")  # Set to relax gesture
            if test_result:
                self.connected = True
                print(f"✓ Successfully connected to ESP32")
                return True
            else:
                print("✗ Connection test failed")
                self.disconnect()
                return False
                
        except socket.timeout:
            print("✗ Connection timeout")
            return False
        except ConnectionRefusedError:
            print("✗ Connection refused - ESP32 may not be running or wrong IP")
            return False
        except Exception as e:
            print(f"✗ Connection failed: {e}")
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
            print("⚠️  Not connected to ESP32, please call connect() first")
            return False
        
        try:
            # Send command with newline
            message = command + '\n'
            self.sock.sendall(message.encode())
            
            # Wait for response
            try:
                response = self.sock.recv(1024).decode().strip()
                if response == "OK":
                    print(f"✓ Command executed: {command}")
                    return True
                else:
                    print(f"⚠️  ESP32 response: {response}")
                    return False
            except socket.timeout:
                print(f"⚠️  Command timeout: {command}")
                return False
                
        except BrokenPipeError:
            print("✗ Connection lost")
            self.connected = False
            return False
        except Exception as e:
            print(f"✗ Send failed: {e}")
            return False
    
    def set_gesture(self, gesture_id):
        """
        Set gesture
        
        Args:
            gesture_id (int): Gesture ID (0-8)
                0: Relax       1: All Flex     2: All Extend
                3: 2-Finger    4: 3-Finger     5: Thumb
                6: Index       7: Middle       8: Peace
        """
        if 0 <= gesture_id <= 8:
            return self.send_command(f"g:{gesture_id}")
        else:
            print("Error: Gesture ID must be between 0-8")
            return False
    
    def set_pressure(self, flexion, extension):
        """
        Set pressure
        
        Args:
            flexion (int): Flexion pressure (0-100)
            extension (int): Extension pressure (0-100)
        """
        if 0 <= flexion <= 100 and 0 <= extension <= 100:
            return self.send_command(f"p:{flexion}:{extension}")
        else:
            print("Error: Pressure values must be between 0-100")
            return False
    
    def set_speed(self, speed_level):
        """
        Set speed level
        
        Args:
            speed_level (int): Speed level (0-4)
                0: Stop  1: Slow  2: Medium  3: Fast  4: Fastest
        """
        if 0 <= speed_level <= 4:
            return self.send_command(f"s:{speed_level}")
        else:
            print("Error: Speed level must be between 0-4")
            return False
    
    def set_finger_states(self, states):
        """
        Set finger states directly
        
        Args:
            states (str): 6-digit string, each digit represents finger/action state
                Position: [Thumb][Index][Middle][Ring][Pinky][Abduction]
                State: 0=Relax 1=Flex 2=Extend 3=Pinch
                
        Examples:
            "000000" - All fingers relaxed
            "111110" - First 5 fingers flexed, no abduction
            "123400" - Thumb flex, Index extend, Middle pinch, others relax
        """
        if len(states) == 6 and all(c in '0123' for c in states):
            return self.send_command(f"f:{states}")
        else:
            print("Error: Finger states must be 6-digit string with digits 0-3")
            return False
    
    def emergency_stop(self):
        """Emergency stop all actions"""
        return self.send_command("stop")
    
    def disconnect(self):
        """Close connection"""
        try:
            if self.sock:
                self.sock.close()
            self.connected = False
            print("Connection closed")
        except:
            pass

class InteractiveController:
    """Interactive control interface"""
    
    def __init__(self):
        self.glove = None
        self.gesture_names = [
            "Relax", "All Flex", "All Extend", "2-Finger Pinch", "3-Finger Pinch",
            "Thumb", "Index", "Middle", "Peace"
        ]
    
    def start(self):
        """Start interactive interface"""
        print("\n" + "="*50)
        print("     ESP32 Pneumatic Glove Control System")
        print("              TCP Interactive Interface")
        print("="*50)
        
        # Get ESP32 IP address
        while True:
            ip = input("\nEnter ESP32 IP address (default: 192.168.1.100): ").strip()
            if not ip:
                ip = "192.168.1.100"
            
            # Simple IP format validation
            parts = ip.split('.')
            if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                break
            else:
                print("Invalid IP address format, please try again")
        
        # Create controller and connect
        self.glove = ESP32GloveTCPController(ip)
        
        print(f"\nConnecting to {ip}...")
        if not self.glove.connect():
            print("Connection failed! Please check:")
            print("1. ESP32 is running normally")
            print("2. Network connection is stable")
            print("3. IP address is correct")
            print("4. ESP32 TCP server is enabled")
            return
        
        # Show help information
        self.show_help()
        
        # Main control loop
        try:
            while True:
                command = input("\n> ").strip().lower()
                
                if not command:
                    continue
                
                if command in ['quit', 'exit', 'q']:
                    break
                elif command in ['help', 'h']:
                    self.show_help()
                elif command == 'test':
                    self.run_test_sequence()
                elif command == 'status':
                    self.show_status()
                else:
                    self.process_command(command)
                    
        except KeyboardInterrupt:
            print("\nProgram interrupted by user")
        finally:
            if self.glove:
                self.glove.emergency_stop()
                self.glove.disconnect()
            print("Program ended")
    
    def show_help(self):
        """Show help information"""
        print("\n" + "-"*50)
        print("Available Commands:")
        print("-"*50)
        print("Gesture Control:")
        for i, name in enumerate(self.gesture_names):
            print(f"  g{i} - {name}")
        print("\nPressure Control:")
        print("  p <flex> <ext> - Set pressure (0-100)")
        print("  Example: p 60 40")
        print("\nSpeed Control:")
        print("  s <level> - Set speed (0-4)")
        print("  Example: s 2")
        print("\nDirect Finger Control:")
        print("  f <states> - 6-digit state code (0123)")
        print("  Example: f 111100")
        print("\nOther Commands:")
        print("  stop   - Emergency stop")
        print("  test   - Run test sequence")
        print("  status - Show current status")
        print("  help   - Show this help")
        print("  quit   - Exit program")
        print("-"*50)
    
    def show_status(self):
        """Show current system status"""
        print("\n" + "-"*30)
        print("Current System Status:")
        print("-"*30)
        print(f"Connected: {'Yes' if self.glove.connected else 'No'}")
        print(f"ESP32 IP: {self.glove.esp32_ip}")
        print(f"TCP Port: {self.glove.tcp_port}")
        print("Check web interface for real-time values")
        print("-"*30)
    
    def process_command(self, command):
        """Process user command"""
        parts = command.split()
        
        if not parts:
            return
        
        cmd = parts[0]
        
        try:
            if cmd.startswith('g') and len(cmd) == 2:
                # Gesture command g0, g1, g2, ...
                gesture_id = int(cmd[1])
                if 0 <= gesture_id <= 8:
                    print(f"Setting gesture: {self.gesture_names[gesture_id]}")
                    self.glove.set_gesture(gesture_id)
                else:
                    print("Gesture ID must be between 0-8")
            
            elif cmd == 'p' and len(parts) == 3:
                # Pressure command p 60 40
                flex = int(parts[1])
                ext = int(parts[2])
                print(f"Setting pressure: Flexion={flex}, Extension={ext}")
                self.glove.set_pressure(flex, ext)
            
            elif cmd == 's' and len(parts) == 2:
                # Speed command s 2
                speed = int(parts[1])
                print(f"Setting speed level: {speed}")
                self.glove.set_speed(speed)
            
            elif cmd == 'f' and len(parts) == 2:
                # Finger states command f 111100
                states = parts[1]
                print(f"Setting finger states: {states}")
                self.glove.set_finger_states(states)
            
            elif cmd == 'stop':
                # Emergency stop
                print("Executing emergency stop")
                self.glove.emergency_stop()
            
            else:
                print("Unknown command, type 'help' for available commands")
        
        except ValueError:
            print("Parameter format error, please check input")
        except Exception as e:
            print(f"Command execution error: {e}")
    
    def run_test_sequence(self):
        """Run test sequence"""
        print("\nStarting test sequence...")
        
        if not self.glove.connected:
            print("Not connected to ESP32!")
            return
        
        test_commands = [
            ("Relax state", lambda: self.glove.set_gesture(0)),
            ("Set medium pressure", lambda: self.glove.set_pressure(50, 40)),
            ("Set medium speed", lambda: self.glove.set_speed(2)),
            ("All flex", lambda: self.glove.set_gesture(1)),
            ("Wait 2 seconds", lambda: time.sleep(2)),
            ("All extend", lambda: self.glove.set_gesture(2)),
            ("Wait 2 seconds", lambda: time.sleep(2)),
            ("2-finger pinch", lambda: self.glove.set_gesture(3)),
            ("Wait 2 seconds", lambda: time.sleep(2)),
            ("Peace gesture", lambda: self.glove.set_gesture(8)),
            ("Wait 2 seconds", lambda: time.sleep(2)),
            ("Return to relax", lambda: self.glove.set_gesture(0)),
        ]
        
        for desc, action in test_commands:
            print(f"  {desc}...")
            action()
            time.sleep(0.5)
        
        print("Test sequence complete")

def auto_find_esp32():
    """Automatically find ESP32 device"""
    print("Searching for ESP32 device...")
    
    # Common ESP32 IP address ranges
    ip_ranges = [
        "192.168.1.",
        "192.168.4.",
        "192.168.0.",
        "10.0.0."
    ]
    
    for ip_base in ip_ranges:
        print(f"Scanning {ip_base}x...")
        for i in range(1, 255):
            ip = ip_base + str(i)
            controller = ESP32GloveTCPController(ip, timeout=1)
            if controller.connect():
                controller.disconnect()
                return ip
            # Print progress every 50 IPs
            if i % 50 == 0:
                print(f"  Scanned up to {ip}")
    
    return None

def main():
    """Main function"""
    print("ESP32 Pneumatic Glove Control System")
    print("TCP Client Controller")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "auto":
            # Auto search mode
            esp32_ip = auto_find_esp32()
            if esp32_ip:
                print(f"Found ESP32 device: {esp32_ip}")
                controller = InteractiveController()
                # Set the found IP
                controller.glove = ESP32GloveTCPController(esp32_ip)
                if controller.glove.connect():
                    controller.show_help()
                    # Continue with interactive mode
                    try:
                        while True:
                            command = input("\n> ").strip().lower()
                            if command in ['quit', 'exit', 'q']:
                                break
                            elif command in ['help', 'h']:
                                controller.show_help()
                            elif command == 'test':
                                controller.run_test_sequence()
                            else:
                                controller.process_command(command)
                    except KeyboardInterrupt:
                        print("\nProgram interrupted")
                    finally:
                        controller.glove.emergency_stop()
                        controller.glove.disconnect()
                else:
                    print("Failed to connect to found device")
            else:
                print("No ESP32 device found")
        elif sys.argv[1] == "demo":
            # Demo mode
            run_demo()
        elif len(sys.argv) == 3:
            # Direct IP mode: python script.py <ip> <port>
            ip = sys.argv[1]
            port = int(sys.argv[2]) if sys.argv[2].isdigit() else 4210
            controller = ESP32GloveTCPController(ip, port)
            if controller.connect():
                print("Direct connection established")
                # Run quick demo
                run_demo_with_controller(controller)
            else:
                print("Failed to connect directly")
    else:
        # Interactive mode
        controller = InteractiveController()
        controller.start()

def run_demo():
    """Run demo program"""
    print("\n=== Demo Program ===")
    
    # Get IP from user
    ip = input("Enter ESP32 IP address (default: 192.168.1.100): ").strip()
    if not ip:
        ip = "192.168.1.100"
    
    # Create controller
    glove = ESP32GloveTCPController(ip)
    
    if not glove.connect():
        print("Connection failed, demo ended")
        return
    
    run_demo_with_controller(glove)

def run_demo_with_controller(glove):
    """Run demo with provided controller"""
    try:
        print("Starting demo sequence...")
        
        # Demo various gestures
        gestures = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        gesture_names = ["Relax", "All Flex", "All Extend", "2-Finger", "3-Finger", 
                        "Thumb", "Index", "Middle", "Peace"]
        
        for i, gesture in enumerate(gestures):
            print(f"Demo gesture: {gesture_names[i]}")
            glove.set_gesture(gesture)
            time.sleep(2)
        
        # Demo pressure adjustment
        print("Demo pressure adjustment...")
        for pressure in [20, 50, 80]:
            print(f"Setting pressure: {pressure}")
            glove.set_pressure(pressure, pressure//2)
            glove.set_gesture(1)  # Flex gesture
            time.sleep(1.5)
        
        # Demo speed adjustment
        print("Demo speed adjustment...")
        for speed in [1, 2, 3, 4]:
            print(f"Setting speed: {speed}")
            glove.set_speed(speed)
            glove.set_gesture(2)  # Extend gesture
            time.sleep(1)
        
        print("Demo complete")
        
    finally:
        glove.emergency_stop()
        glove.disconnect()

# Programming interface class
class GloveAPI:
    """Simplified programming interface"""
    
    def __init__(self, esp32_ip="192.168.1.100", tcp_port=4210):
        self.controller = ESP32GloveTCPController(esp32_ip, tcp_port)
        self.connected = False
    
    def connect(self):
        """Connect to ESP32"""
        self.connected = self.controller.connect()
        return self.connected
    
    def gesture(self, id):
        """Set gesture (0-8)"""
        return self.controller.set_gesture(id)
    
    def pressure(self, flex, ext):
        """Set pressure (0-100, 0-100)"""
        return self.controller.set_pressure(flex, ext)
    
    def speed(self, level):
        """Set speed (0-4)"""
        return self.controller.set_speed(level)
    
    def fingers(self, states):
        """Set finger states (6-digit string)"""
        return self.controller.set_finger_states(states)
    
    def stop(self):
        """Emergency stop"""
        return self.controller.emergency_stop()
    
    def close(self):
        """Close connection"""
        self.controller.disconnect()

if __name__ == "__main__":
    main()