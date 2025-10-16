"""
Proportional Control Loop for Unity and ESP32
============================================

This module implements the control loop for routing proportional EMG control
to Unity VR hand visualization and ESP32 pneumatic glove.

Features:
---------
- Proportional control with speed and force
- Per-finger control
- Unity VR integration
- ESP32 pneumatic glove integration
"""

import time
import json
import threading
from queue import Empty, Full


def ProportionalControlLoop(
    events_socket,
    control_params,
    prop_control_queue,
    stop_program,
    prop_esp32_queue=None,
    unity_events_queue=None
):
    """
    Control loop for proportional EMG control.
    
    Routes proportional control commands to Unity and ESP32 with
    continuous speed and force values.
    
    Args:
        events_socket: TCP socket for Unity communication
        control_params (dict): Control parameters
        prop_control_queue (Queue): Input queue with proportional control data
        stop_program (Value): Stop flag
        prop_esp32_queue (Queue, optional): Queue for ESP32 commands
        unity_events_queue (Queue, optional): Queue for Unity events
    """
    print('Starting the proportional control loop...')
    
    # Control mode
    control_mode = control_params.get('control_mode', 'synchronized')
    
    # Performance stats
    performance_stats = {
        'commands_processed': 0,
        'unity_updates_sent': 0,
        'esp32_updates_sent': 0,
        'errors_count': 0,
        'start_time': time.perf_counter()
    }
    
    # Last sent values to avoid redundant updates
    last_unity_data = None
    last_esp32_data = None
    
    # Update rate limiting
    min_update_interval = control_params.get('min_update_interval', 0.05)  # 20 Hz max
    last_unity_update = 0
    last_esp32_update = 0
    
    print(f"Control mode: {control_mode}")
    print(f"Min update interval: {min_update_interval}s ({1/min_update_interval:.1f} Hz max)")
    
    def send_to_unity_async(data, socket):
        """Send proportional control data to Unity."""
        try:
            # Create Unity event for proportional control
            event = {
                'event_type': 'proportional_control',
                'timestamp': data['timestamp'],
                'fingers': data['unity_format']['fingers']
            }
            
            socket.sendall((json.dumps(event) + '\n').encode())
            performance_stats['unity_updates_sent'] += 1
        except Exception as e:
            print(f"✗ Error sending to Unity: {e}")
            performance_stats['errors_count'] += 1
    
    def send_to_esp32_async(data, queue):
        """Send proportional control data to ESP32 queue."""
        try:
            # Format: (finger_control_dict, timestamp)
            esp32_data = (data['esp32_format'], data['timestamp'])
            queue.put(esp32_data, timeout=0.1)
            performance_stats['esp32_updates_sent'] += 1
        except Full:
            print(f"⚠ ESP32 queue full, update skipped")
            performance_stats['errors_count'] += 1
        except Exception as e:
            print(f"✗ Error sending to ESP32 queue: {e}")
            performance_stats['errors_count'] += 1
    
    def should_update(last_data, new_data, threshold=0.05):
        """Check if update is significant enough to send."""
        if last_data is None:
            return True
        
        # Compare finger control values
        max_diff = 0.0
        for finger in new_data.get('fingers', {}).values():
            for last_finger in last_data.get('fingers', {}).values():
                for key in ['flexion', 'extension', 'force']:
                    if key in finger and key in last_finger:
                        diff = abs(finger.get(key, 0) - last_finger.get(key, 0))
                        max_diff = max(max_diff, diff)
        
        return max_diff > threshold
    
    # Main control loop
    while not stop_program.value:
        try:
            data = prop_control_queue.get(timeout=0.1)
        except Empty:
            continue
        
        if data is None:
            break
        
        current_time = time.perf_counter()
        performance_stats['commands_processed'] += 1
        
        # Send to Unity
        if control_mode in ['synchronized', 'unity_only']:
            # Rate limiting
            if current_time - last_unity_update >= min_update_interval:
                # Check if update is significant
                if should_update(last_unity_data, data['unity_format']):
                    unity_thread = threading.Thread(
                        target=send_to_unity_async,
                        args=(data, events_socket),
                        daemon=True
                    )
                    unity_thread.start()
                    
                    last_unity_data = data['unity_format']
                    last_unity_update = current_time
        
        # Send to ESP32
        if prop_esp32_queue is not None and control_mode in ['synchronized', 'esp32_only']:
            # Rate limiting
            if current_time - last_esp32_update >= min_update_interval:
                # Check if update is significant
                if should_update(last_esp32_data, data['esp32_format']):
                    esp32_thread = threading.Thread(
                        target=send_to_esp32_async,
                        args=(data, prop_esp32_queue),
                        daemon=True
                    )
                    esp32_thread.start()
                    
                    last_esp32_data = data['esp32_format']
                    last_esp32_update = current_time
    
    # Print final statistics
    elapsed_time = time.perf_counter() - performance_stats['start_time']
    print(f"\nProportional Control Loop Statistics:")
    print(f"  Duration: {elapsed_time:.2f}s")
    print(f"  Commands processed: {performance_stats['commands_processed']}")
    print(f"  Unity updates sent: {performance_stats['unity_updates_sent']}")
    print(f"  ESP32 updates sent: {performance_stats['esp32_updates_sent']}")
    print(f"  Errors: {performance_stats['errors_count']}")
    
    if elapsed_time > 0:
        print(f"  Avg rate: {performance_stats['commands_processed']/elapsed_time:.2f} Hz")
    
    print('Proportional control loop stopped')


def ESP32ProportionalControlLoop(prop_esp32_queue, esp32_controller, stop_program):
    """
    ESP32 control loop for proportional control.
    
    Receives proportional control commands and sends them to ESP32 glove.
    
    Args:
        prop_esp32_queue (Queue): Input queue with ESP32 commands
        esp32_controller: ESP32Controller instance
        stop_program (Value): Stop flag
    """
    print('Starting ESP32 proportional control loop...')
    
    # Stats
    commands_sent = 0
    errors = 0
    
    # Last sent pressures per finger to avoid redundant updates
    last_pressures = {}
    
    while not stop_program.value:
        try:
            data = prop_esp32_queue.get(timeout=0.1)
        except Empty:
            continue
        
        if data is None:
            break
        
        esp32_format, timestamp = data
        
        try:
            # Send proportional commands to ESP32
            # ESP32 format: {'control_type': 'proportional', 'fingers': {...}}
            
            fingers = esp32_format.get('fingers', {})
            
            # For each finger, send pressure and speed commands
            for finger_name, control in fingers.items():
                flexion_pressure = control.get('flexion_pressure', 0)
                extension_pressure = control.get('extension_pressure', 0)
                speed = control.get('speed', 2)
                
                # Check if significant change
                last_press = last_pressures.get(finger_name, {})
                flex_diff = abs(flexion_pressure - last_press.get('flex', 0))
                ext_diff = abs(extension_pressure - last_press.get('ext', 0))
                
                # Only send if significant change (threshold: 5%)
                if flex_diff > 5 or ext_diff > 5:
                    # Send pressure update
                    esp32_controller.set_pressure(flexion_pressure, extension_pressure)
                    esp32_controller.set_speed(speed)
                    
                    # Update last pressures
                    last_pressures[finger_name] = {
                        'flex': flexion_pressure,
                        'ext': extension_pressure
                    }
                    
                    commands_sent += 1
        
        except Exception as e:
            print(f"✗ Error in ESP32 proportional control: {e}")
            errors += 1
    
    print(f"\nESP32 Proportional Control Statistics:")
    print(f"  Commands sent: {commands_sent}")
    print(f"  Errors: {errors}")
    print('ESP32 proportional control loop stopped')
