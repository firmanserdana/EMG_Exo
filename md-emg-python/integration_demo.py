#!/usr/bin/env python3
"""
EMG-ESP32 Integration Demo
=========================

Demonstration script showing integration between EMG signal processing
and ESP32 pneumatic glove control. This script can be used to test
the complete pipeline from EMG acquisition to physical glove control.

Usage:
    python integration_demo.py                    # Full demo
    python integration_demo.py --esp32-only       # ESP32 control only
    python integration_demo.py --emg-only         # EMG processing only

Author: EMG-Exo Control System
"""

import os
import sys
import time
import yaml
import argparse
from multiprocessing import Queue, Value, Process
from threading import Thread

# Add the current directory to sys.path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from realtime_components.esp32_control import ESP32Controller, test_esp32_connection
from utils.general_utils import acquisition_arg_parser


def demo_esp32_only():
    """Demo ESP32 control without EMG"""
    print("ESP32 Pneumatic Glove Demo")
    print("=========================")
    
    # Load ESP32 configuration
    with open('config/esp32_control.yaml', 'r') as f:
        esp32_cfg = yaml.load(f, Loader=yaml.FullLoader)
    
    # Test connection
    esp32_ip = esp32_cfg['ip_address']
    esp32_port = esp32_cfg['port']
    
    print(f"Testing connection to ESP32 at {esp32_ip}:{esp32_port}")
    if not test_esp32_connection(esp32_ip, esp32_port):
        print("Failed to connect to ESP32. Please check configuration and try again.")
        return False
    
    # Interactive demonstration
    controller = ESP32Controller(esp32_ip, esp32_port)
    if controller.connect():
        try:
            print("\nESP32 Demo Sequence:")
            
            # Demo sequence
            demo_gestures = [
                (0, "Relax"),
                (1, "All Flex"),
                (2, "All Extend"), 
                (3, "2-Finger Pinch"),
                (5, "Thumb"),
                (6, "Index"),
                (0, "Relax")
            ]
            
            for gesture_id, gesture_name in demo_gestures:
                print(f"Executing: {gesture_name}")
                controller.set_gesture(gesture_id)
                time.sleep(2)
            
            print("Demo completed successfully!")
            return True
            
        except KeyboardInterrupt:
            print("\nDemo interrupted")
        finally:
            controller.emergency_stop()
            controller.disconnect()
    
    return False


def demo_emg_simulation():
    """Demo EMG simulation sending commands to ESP32"""
    print("EMG-ESP32 Integration Demo")
    print("==========================")
    
    # Load configurations
    with open('config/esp32_control.yaml', 'r') as f:
        esp32_cfg = yaml.load(f, Loader=yaml.FullLoader)
    
    # Test ESP32 connection
    esp32_ip = esp32_cfg['ip_address']
    esp32_port = esp32_cfg['port']
    
    print(f"Testing ESP32 connection to {esp32_ip}:{esp32_port}")
    controller = ESP32Controller(esp32_ip, esp32_port)
    
    if not controller.connect():
        print("Failed to connect to ESP32. Running simulation only.")
        controller = None
    else:
        print("ESP32 connected successfully!")
    
    try:
        print("\nSimulating EMG predictions and ESP32 responses:")
        print("(In real usage, these would come from live EMG signals)")
        
        # Simulate EMG predictions with task-specific gestures
        simulated_predictions = [
            (0, 0.95, "HandOpen"),
            (1, 0.87, "HandClose"),  # For open_close task
            (0, 0.92, "HandOpen"),
            (2, 0.83, "HookGrasp"),  # For grasp_patterns task
            (0, 0.91, "HandOpen"),
            (5, 0.78, "ThumbFlexion"),  # For single_fingers task
            (0, 0.94, "HandOpen"),
            (3, 0.86, "LateralGrasp"),  # For grasp_patterns task
            (0, 0.93, "HandOpen")
        ]
        
        for pred_id, confidence, pred_name in simulated_predictions:
            print(f"EMG Prediction: {pred_name} (ID: {pred_id}, Confidence: {confidence:.2f})")
            
            if controller:
                # Map to ESP32 gesture
                esp32_gesture = controller.gesture_mapping.get(pred_id, 0)
                if controller.set_gesture(esp32_gesture):
                    print(f"  → ESP32: Gesture {esp32_gesture} executed")
                else:
                    print(f"  → ESP32: Failed to execute gesture {esp32_gesture}")
            else:
                print(f"  → ESP32: Would execute gesture {pred_id} (simulation mode)")
            
            time.sleep(2.5)
        
        print("\nIntegration demo completed!")
        return True
        
    except KeyboardInterrupt:
        print("\nDemo interrupted")
    finally:
        if controller:
            controller.emergency_stop()
            controller.disconnect()
    
    return False


def full_integration_demo():
    """Full integration demo with both EMG and ESP32"""
    print("Full EMG-ESP32 Integration Demo")
    print("===============================")
    print("This demo shows the complete pipeline from EMG to ESP32 control")
    print("Note: This requires actual EMG hardware or simulation mode")
    
    # Check if EMG system is available
    try:
        with open('config/64_config.yaml', 'r') as f:
            emg_config = yaml.load(f, Loader=yaml.FullLoader)
        
        print(f"EMG System: {emg_config['ip_address']}:{emg_config['port']}")
        print("For full integration, run:")
        print("  python emg_control_64.py --decoding-active 1")
        print("  (Make sure ESP32 is enabled in config/esp32_control.yaml)")
        
    except FileNotFoundError:
        print("EMG configuration not found. Running ESP32 demo only.")
        return demo_esp32_only()
    
    return demo_emg_simulation()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='EMG-ESP32 Integration Demo')
    parser.add_argument('--esp32-only', action='store_true', 
                       help='Run ESP32 demo only')
    parser.add_argument('--emg-only', action='store_true',
                       help='Run EMG simulation only')
    parser.add_argument('--config', default='config/esp32_control.yaml',
                       help='ESP32 configuration file')
    
    args = parser.parse_args()
    
    # Change to script directory for relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    try:
        if args.esp32_only:
            success = demo_esp32_only()
        elif args.emg_only:
            success = demo_emg_simulation()
        else:
            success = full_integration_demo()
        
        if success:
            print("\n✓ Demo completed successfully!")
        else:
            print("\n✗ Demo failed or was interrupted")
            
    except Exception as e:
        print(f"\nError during demo: {e}")
        return False
    
    return True


if __name__ == "__main__":
    main()
