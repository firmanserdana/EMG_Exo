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
import argparse
from realtime_components.esp32_control import ESP32Controller, test_esp32_connection


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
        
        controller = ESP32Controller(ip, timeout=2)
        if controller.connect():
            print("✓ Found ESP32!")
            found_devices.append(ip)
            controller.disconnect()
        else:
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
        test_esp32_connection(ip, port)
    
    else:
        # Interactive mode
        interactive_test()


if __name__ == "__main__":
    main()
