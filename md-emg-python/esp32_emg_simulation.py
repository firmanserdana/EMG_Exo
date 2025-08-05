#!/usr/bin/env python3
"""
ESP32 EMG System Simulation
Simulate the exact behavior of the EMG system to identify the connection issue
"""

import socket
import time
import threading
from queue import Queue, Empty
import multiprocessing

def simulate_esp32_control_loop():
    """Simulate the exact ESP32ControlLoop behavior"""
    
    print("Simulating ESP32 control loop...")
    
    # ESP32 configuration (matching your config)
    esp32_config = {
        'ip_address': '172.20.10.3',
        'port': 4210,
        'timeout': 10,
        'gesture_hold_time': 0.1,
        'default_pressure': {'flexion': 85, 'extension': 70},
        'default_speed': 4
    }
    
    # Gesture mapping for open_close task
    gesture_mapping = {
        0: 2,  # HandOpen -> ESP32 Extend
        1: 1,  # HandClose -> ESP32 All Flex
        2: 1,  # HandClose -> ESP32 All Flex
    }
    
    # Finger states mapping
    finger_states_map = {
        0: "000000",  # Relax
        1: "111110",  # All flex
        2: "222220",  # All extend
    }
    
    # Simulate prediction queue
    pred_queue = Queue()
    
    # Start prediction producer (simulates EMG decoding)
    def prediction_producer():
        """Simulate EMG predictions like the real system"""
        predictions = [
            (1, 0.65),  # HandClose, 65% confidence
            (1, 0.68),  # HandClose, 68% confidence  
            (1, 0.71),  # HandClose, 71% confidence
            (1, 0.72),  # HandClose, 72% confidence
            (0, 0.45),  # HandOpen, 45% confidence (low)
            (1, 0.69),  # HandClose, 69% confidence
        ]
        
        for i, (pred, prob) in enumerate(predictions):
            time.sleep(8.5)  # Match the ~8.5 second intervals from EMG logs
            pred_queue.put((pred, prob))
            print(f"Produced prediction: {pred} (prob: {prob})")
            
        # Signal end
        pred_queue.put(None)
    
    # Start producer thread
    producer_thread = threading.Thread(target=prediction_producer)
    producer_thread.start()
    
    # ESP32 Control Loop (simplified version)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(esp32_config['timeout'])
        
        print(f"Connecting to ESP32 at {esp32_config['ip_address']}:{esp32_config['port']}...")
        sock.connect((esp32_config['ip_address'], esp32_config['port']))
        
        # Get welcome message
        response = sock.recv(1024).decode().strip()
        print(f"ESP32 says: {response}")
        
        # Set initial parameters
        pressure_cmd = f"p:{esp32_config['default_pressure']['flexion']}:{esp32_config['default_pressure']['extension']}"
        print(f"Setting pressure: {pressure_cmd}")
        sock.send(f"{pressure_cmd}\n".encode())
        response = sock.recv(1024).decode().strip()
        print(f"Pressure response: {response}")
        
        speed_cmd = f"s:{esp32_config['default_speed']}"
        print(f"Setting speed: {speed_cmd}")
        sock.send(f"{speed_cmd}\n".encode())
        response = sock.recv(1024).decode().strip()
        print(f"Speed response: {response}")
        
        print("✓ ESP32 connection established")
        
        last_gesture = -1
        last_gesture_time = 0
        
        # Main control loop
        while True:
            try:
                # Get prediction with timeout (like real system)
                data = pred_queue.get(timeout=0.1)
                
                if data is None:
                    print("Prediction stream ended")
                    break
                    
                pred, pred_prob = data
                current_time = time.perf_counter()
                
                # Map EMG prediction to ESP32 gesture
                esp32_gesture = gesture_mapping.get(pred, 0)
                
                # Apply gesture hold time (like real system)
                if (esp32_gesture != last_gesture and 
                    current_time - last_gesture_time >= esp32_config['gesture_hold_time']):
                    
                    print(f"ESP32: Setting gesture {esp32_gesture} (EMG pred: {pred}, prob: {pred_prob:.2f})")
                    
                    # Send gesture command
                    gesture_cmd = f"g:{esp32_gesture}"
                    sock.send(f"{gesture_cmd}\n".encode())
                    
                    try:
                        sock.settimeout(2)
                        response = sock.recv(1024).decode().strip()
                        if response == "OK":
                            gesture_success = True
                        else:
                            print(f"⚠️ Unexpected gesture response: {response}")
                            gesture_success = False
                    except socket.timeout:
                        print("⚠️ Gesture command timeout")
                        gesture_success = False
                    
                    # Small delay
                    time.sleep(0.05)
                    
                    # Send finger state command
                    if esp32_gesture in finger_states_map:
                        finger_state = finger_states_map[esp32_gesture]
                        finger_cmd = f"f:{finger_state}"
                        sock.send(f"{finger_cmd}\n".encode())
                        
                        try:
                            sock.settimeout(2)
                            response = sock.recv(1024).decode().strip()
                            if response == "OK":
                                finger_success = True
                            else:
                                print(f"⚠️ Unexpected finger response: {response}")
                                finger_success = False
                        except socket.timeout:
                            print("⚠️ Finger command timeout")
                            finger_success = False
                        
                        print(f"ESP32: Sent gesture {esp32_gesture} + finger_state {finger_state} (success: {gesture_success and finger_success})")
                    
                    if gesture_success:
                        last_gesture = esp32_gesture
                        last_gesture_time = current_time
                    else:
                        print("Failed to send gesture to ESP32 - connection may be lost")
                        
            except Empty:
                # Timeout - continue loop (normal behavior)
                continue
            except (ConnectionResetError, BrokenPipeError) as e:
                print(f"✗ ESP32 connection lost: {e}")
                print("ESP32: Quick reconnect attempt...")
                
                # Try to reconnect (like real system)
                try:
                    sock.close()
                except:
                    pass
                
                time.sleep(0.1)
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(esp32_config['timeout'])
                sock.connect((esp32_config['ip_address'], esp32_config['port']))
                
                response = sock.recv(1024).decode().strip()
                print(f"ESP32 says: {response}")
                print("✓ ESP32 connection established")
                
            except Exception as e:
                print(f"ESP32 control loop error: {e}")
                break
                
    except Exception as e:
        print(f"ESP32 simulation failed: {e}")
    finally:
        try:
            sock.close()
        except:
            pass
        print("ESP32 simulation completed")

if __name__ == "__main__":
    print("ESP32 EMG System Simulation")
    print("="*50)
    simulate_esp32_control_loop()
