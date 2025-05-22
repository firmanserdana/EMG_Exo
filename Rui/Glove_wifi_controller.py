#!/usr/bin/env python3
"""
ESP32 Glove WiFi Controller - Simplified Version
===============================================

Simple WiFi controller for ESP32 pneumatic glove system.
Provides basic command interface for gesture, pressure, speed, and finger control.

Requirements:
1. Connect to ESP32_Glove WiFi network (password: 12345678)
2. Set glove to WiFi Control mode via web interface (192.168.4.1)
3. Run this script
"""

import socket
import time

class SimpleGloveController:
    def __init__(self, ip="192.168.4.1", port=4210):
        """
        Initialize the glove controller
        
        Args:
            ip (str): ESP32 IP address
            port (int): UDP port number
        """
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0)
        
        print(f"Glove Controller initialized for {ip}:{port}")
        
    def send_command(self, command):
        """
        Send a command to the glove
        
        Args:
            command (str): Command string to send
            
        Returns:
            bool: True if command sent successfully
        """
        try:
            self.sock.sendto(command.encode(), (self.ip, self.port))
            print(f"Sent: {command}")
            
            # Wait for acknowledgment
            try:
                response, addr = self.sock.recvfrom(1024)
                print(f"Response: {response.decode()}")
                return True
            except socket.timeout:
                print("No response received")
                return False
                
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    def set_gesture(self, gesture):
        """
        Set gesture (0-8)
        
        Gestures:
        0 = Relax
        1 = All Flexion
        2 = All Extension
        3 = 2-Finger Pinch
        4 = 3-Finger Pinch
        5 = Thumb only
        6 = Index only
        7 = Middle only
        8 = Peace sign
        """
        if 0 <= gesture <= 8:
            return self.send_command(f"g:{gesture}")
        else:
            print("Invalid gesture. Must be 0-8.")
            return False
    
    def set_pressure(self, flexion, extension):
        """
        Set pressure for flexion and extension (0-100)
        
        Args:
            flexion (int): Flexion pressure (0-100)
            extension (int): Extension pressure (0-100)
        """
        if 0 <= flexion <= 100 and 0 <= extension <= 100:
            return self.send_command(f"p:{flexion}:{extension}")
        else:
            print("Invalid pressure. Must be 0-100.")
            return False
    
    def set_speed(self, speed):
        """
        Set speed level (0-4)
        
        Args:
            speed (int): Speed level (0=stop, 1=slow, 4=fast)
        """
        if 0 <= speed <= 4:
            return self.send_command(f"s:{speed}")
        else:
            print("Invalid speed. Must be 0-4.")
            return False
    
    def set_finger_states(self, states):
        """
        Set individual finger states directly
        
        Args:
            states (str): 6-character string for finger states
                         Positions: [thumb][index][middle][ring][pinky][abduction]
                         Values: 0=relax, 1=flexion, 2=extension, 3=pinch
        
        Examples:
            "000000" = all fingers relaxed
            "111110" = all fingers flexed except abduction
            "123400" = thumb flex, index extend, middle pinch, others relax
        """
        if len(states) == 6 and all(c in '0123' for c in states):
            return self.send_command(f"f:{states}")
        else:
            print("Invalid finger states. Must be 6 digits (0-3).")
            return False
    
    def set_mode(self, mode):
        """
        Set control mode
        
        Args:
            mode (int): Control mode
                       0 = HTTP mode
                       1 = Serial mode
                       2 = Data Glove mode
                       3 = WiFi mode
        """
        if 0 <= mode <= 3:
            return self.send_command(f"m:{mode}")
        else:
            print("Invalid mode. Must be 0-3.")
            return False
    
    def stop_all(self):
        """Emergency stop - set all to relax state"""
        return self.send_command("stop")
    
    def close(self):
        """Close the connection"""
        self.sock.close()
        print("Connection closed")

def interactive_mode(glove):
    """
    Interactive command-line interface
    """
    print("\n=== Interactive Control Mode ===")
    print("Available commands:")
    print("  g [0-8]        - Set gesture")
    print("  p [flex] [ext] - Set pressure (0-100 each)")
    print("  s [0-4]        - Set speed level")
    print("  f [states]     - Set finger states (6 digits)")
    print("  m [0-3]        - Set mode")
    print("  stop           - Emergency stop")
    print("  help           - Show this help")
    print("  quit           - Exit program")
    print("\nExamples:")
    print("  g 3            - Set 2-finger pinch gesture")
    print("  p 50 30        - Set flexion=50, extension=30")
    print("  s 2            - Set speed level 2")
    print("  f 111100       - Flex first 4 fingers")
    print("  m 3            - Set to WiFi control mode")
    
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
                
            cmd = user_input.split()
            
            if cmd[0] == 'quit' or cmd[0] == 'q':
                break
            elif cmd[0] == 'help' or cmd[0] == 'h':
                print("Command format: [command] [parameters]")
                print("Type 'quit' to exit")
            elif cmd[0] == 'g' and len(cmd) == 2:
                glove.set_gesture(int(cmd[1]))
            elif cmd[0] == 'p' and len(cmd) == 3:
                glove.set_pressure(int(cmd[1]), int(cmd[2]))
            elif cmd[0] == 's' and len(cmd) == 2:
                glove.set_speed(int(cmd[1]))
            elif cmd[0] == 'f' and len(cmd) == 2:
                glove.set_finger_states(cmd[1])
            elif cmd[0] == 'm' and len(cmd) == 2:
                glove.set_mode(int(cmd[1]))
            elif cmd[0] == 'stop':
                glove.stop_all()
            else:
                print("Invalid command. Type 'help' for available commands.")
                
        except ValueError:
            print("Invalid parameters. Check your input format.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

def quick_test(glove):
    """
    Quick functionality test
    """
    print("\n=== Quick Test Sequence ===")
    
    test_commands = [
        ("m:3", "Set WiFi mode"),
        ("g:0", "Set relax gesture"),
        ("s:1", "Set speed level 1"),
        ("p:30:20", "Set pressure 30:20"),
        ("f:111100", "Flex first 4 fingers"),
        ("g:3", "Set pinch gesture"),
        ("stop", "Emergency stop")
    ]
    
    for command, description in test_commands:
        print(f"\nTesting: {description}")
        glove.send_command(command)
        time.sleep(1)
    
    print("\n=== Test Complete ===")

def main():
    print("ESP32 Glove WiFi Controller - Simple Version")
    print("=" * 45)
    print("Prerequisites:")
    print("1. Connect to ESP32_Glove WiFi (password: 12345678)")
    print("2. Open 192.168.4.1 and set to WiFi Control mode")
    print("3. Ensure ESP32 is running and responsive")
    
    # Initialize controller
    glove = SimpleGloveController()
    
    try:
        # Test connection
        print("\nTesting connection...")
        if glove.set_mode(3):  # Set to WiFi mode
            print("✓ Connection successful!")
            
            # Ask user what they want to do
            while True:
                print("\nWhat would you like to do?")
                print("1. Interactive control")
                print("2. Quick test")
                print("3. Exit")
                
                choice = input("Enter choice (1-3): ").strip()
                
                if choice == '1':
                    interactive_mode(glove)
                elif choice == '2':
                    quick_test(glove)
                elif choice == '3':
                    break
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
        else:
            print("✗ Connection failed!")
            print("Check WiFi connection and ESP32 status.")
            
    except KeyboardInterrupt:
        print("\nProgram interrupted")
    finally:
        glove.stop_all()
        glove.close()
        print("Program ended")

if __name__ == "__main__":
    main()