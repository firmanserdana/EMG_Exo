#!/usr/bin/env python3
"""
ESP32 Connection Test Tool
=========================

Test connectivity and functionality of ESP32-based pneumatic glove system.

Usage:
    python test_esp32.py                    # Interactive test
    python test_esp32.py <ip> <port>       # Direct test
    python test_esp32.py scan              # Auto-discover ESP32

Author: EMG-Exo Control System
"""

import sys
import time
import socket
import argparse
from realtime_components.esp32_control import ESP32Controller, test_esp32_connection


def basic_tcp_test(ip, port, timeout=5):
    """
    Basic TCP connectivity test without ESP32Controller overhead
    
    Args:
        ip (str): IP address to test
        port (int): Port to test
        timeout (float): Connection timeout
        
    Returns:
        bool: True if basic connection successful
    """
    print(f"Basic TCP test to {ip}:{port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        # Test connection
        print(f"Connecting to {ip}:{port}...", end=" ")
        result = sock.connect_ex((ip, port))
        
        if result == 0:
            print("✓ Connected!")
            
            # Try to read welcome message
            try:
                sock.settimeout(2)  # Short timeout for welcome message
                welcome = sock.recv(1024).decode().strip()
                if welcome:
                    print(f"Server says: {welcome}")
            except socket.timeout:
                print("No welcome message received")
            except:
                pass
            
            # Test basic command
            print("Testing basic command...", end=" ")
            try:
                sock.send(b"g:0\n")  # Send relax command
                sock.settimeout(3)
                response = sock.recv(1024).decode().strip()
                if response:
                    print(f"Response: {response}")
                    success = "OK" in response.upper()
                else:
                    print("No response")
                    success = False
            except Exception as e:
                print(f"Command failed: {e}")
                success = False
            
            sock.close()
            return success
        else:
            print(f"✗ Connection failed (error {result})")
            return False
            
    except socket.timeout:
        print("✗ Connection timeout")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def scan_for_esp32(ip_base="192.168.1", start=100, end=110):
    """
    Scan for ESP32 devices on the network
    
    Args:
        ip_base (str): IP address base (e.g., "192.168.1")
        start (int): Start IP range
        end (int): End IP range
        
    Returns:
        list: List of found ESP32 IP addresses
    """
    print(f"Scanning for ESP32 devices in range {ip_base}.{start}-{end}...")
    found_devices = []
    
    for i in range(start, end + 1):
        ip = f"{ip_base}.{i}"
        print(f"Testing {ip}...", end=" ")
        
        # Use basic TCP test first
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)  # Very short timeout for scanning
            result = sock.connect_ex((ip, 4210))
            sock.close()
            
            if result == 0:
                print("✓ Found device!")
                found_devices.append(ip)
            else:
                print("✗")
        except:
            print("✗")
    
    return found_devices


def interactive_test():
    """Run interactive ESP32 test"""
    print("ESP32 Glove Test Tool")
    print("====================")
    
    # Get connection details
    ip = input("Enter ESP32 IP address (default: 192.168.1.100): ").strip()
    if not ip:
        ip = "192.168.1.100"
    
    port_str = input("Enter TCP port (default: 4210): ").strip()
    port = int(port_str) if port_str.isdigit() else 4210
    
    # First, test basic TCP connectivity
    print(f"\nStep 1: Basic TCP connectivity test")
    print("=" * 40)
    tcp_success = basic_tcp_test(ip, port)
    
    if not tcp_success:
        print("\n✗ Basic TCP test failed!")
        print("\nTroubleshooting tips:")
        print("1. Check if ESP32 is powered on and connected to WiFi")
        print("2. Verify the IP address (check ESP32 serial output)")
        print("3. Try AP mode IP: 192.168.4.1")
        print("4. Check if port 4210 is open on your firewall")
        print("5. Ensure ESP32 and computer are on same network")
        return
    
    print(f"\n✓ Basic TCP test successful!")
    
    # Now test with ESP32Controller
    print(f"\nStep 2: ESP32Controller test")
    print("=" * 30)
    
    # Test connection
    if test_esp32_connection(ip, port):
        print("\n✓ ESP32 test completed successfully!")
        
        # Additional testing menu
        controller = ESP32Controller(ip, port)
        if controller.connect():
            print("\nAdditional test options:")
            print("1. Pressure test")
            print("2. Speed test") 
            print("3. Custom gesture")
            print("4. Exit")
            
            try:
                while True:
                    choice = input("\nSelect option (1-4): ").strip()
                    
                    if choice == "1":
                        pressure_test(controller)
                    elif choice == "2":
                        speed_test(controller)
                    elif choice == "3":
                        custom_gesture_test(controller)
                    elif choice == "4":
                        break
                    else:
                        print("Invalid choice. Please select 1-4.")
            except KeyboardInterrupt:
                print("\nTest interrupted")
            finally:
                controller.emergency_stop()
                controller.disconnect()
    else:
        print("\n✗ ESP32 test failed!")


def pressure_test(controller):
    """Test pressure settings"""
    print("\nPressure Test")
    print("=============")
    
    pressures = [(30, 20), (50, 30), (70, 40), (90, 50)]
    
    for flex, ext in pressures:
        print(f"Setting pressure: Flex={flex}%, Ext={ext}%")
        controller.set_pressure(flex, ext)
        controller.set_gesture(1)  # Flex gesture
        time.sleep(2)
        controller.set_gesture(0)  # Relax
        time.sleep(1)


def speed_test(controller):
    """Test speed settings"""
    print("\nSpeed Test")
    print("==========")
    
    speeds = [1, 2, 3, 4]  # Slow to fastest
    speed_names = ["Slow", "Medium", "Fast", "Fastest"]
    
    for speed, name in zip(speeds, speed_names):
        print(f"Setting speed: {name} (level {speed})")
        controller.set_speed(speed)
        controller.set_gesture(1)  # Flex
        time.sleep(1.5)
        controller.set_gesture(2)  # Extend
        time.sleep(1.5)
        controller.set_gesture(0)  # Relax
        time.sleep(1)


def custom_gesture_test(controller):
    """Test custom gesture input"""
    print("\nCustom Gesture Test")
    print("===================")
    print("Available gestures:")
    gestures = {
        0: "Relax", 1: "All Flex", 2: "All Extend", 3: "2-Finger Pinch",
        4: "3-Finger Pinch", 5: "Thumb", 6: "Index", 7: "Middle", 8: "Peace"
    }
    
    for id, name in gestures.items():
        print(f"  {id}: {name}")
    
    try:
        gesture_id = int(input("\nEnter gesture ID (0-8): "))
        if 0 <= gesture_id <= 8:
            print(f"Setting gesture: {gestures[gesture_id]}")
            controller.set_gesture(gesture_id)
            input("Press Enter to relax...")
            controller.set_gesture(0)
        else:
            print("Invalid gesture ID")
    except ValueError:
        print("Invalid input")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='ESP32 Glove Test Tool')
    parser.add_argument('command', nargs='?', help='Command: scan, or IP address')
    parser.add_argument('port', nargs='?', type=int, default=4210, help='TCP port (default: 4210)')
    
    args = parser.parse_args()
    
    if args.command == 'scan':
        # Auto-discover mode
        found_devices = scan_for_esp32()
        if found_devices:
            print(f"\nFound {len(found_devices)} ESP32 device(s):")
            for device in found_devices:
                print(f"  - {device}")
            
            if len(found_devices) == 1:
                print(f"\nTesting {found_devices[0]}...")
                test_esp32_connection(found_devices[0], 4210)
        else:
            print("\nNo ESP32 devices found")
    
    elif args.command and args.command not in ['scan']:
        # Direct IP test mode
        ip = args.command
        port = args.port
        print(f"Testing ESP32 at {ip}:{port}")
        
        # Run both basic and full tests
        print(f"\nStep 1: Basic TCP connectivity test")
        print("=" * 40)
        tcp_success = basic_tcp_test(ip, port)
        
        if tcp_success:
            print(f"\n✓ Basic TCP test successful!")
            print(f"\nStep 2: ESP32Controller test")
            print("=" * 30)
            test_esp32_connection(ip, port)
        else:
            print(f"\n✗ Basic TCP test failed - skipping ESP32Controller test")
    
    else:
        # Interactive mode
        interactive_test()


if __name__ == "__main__":
    main()
