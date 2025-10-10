"""
Control Loop for EMG Gesture Classification
==========================================

This module handles the control logic for routing EMG predictions to Unity and ESP32 devices.
Supports all tasks (open_close, grasp_patterns, single_fingers) with automatic gesture mapping.

Control Modes:
--------------
1. 'synchronized' (default): ESP32 follows Unity display for consistent user feedback
   - Unity receives EMG predictions directly
   - ESP32 gets mapped gestures to match Unity display
   - Uses task-specific mapping to ensure visual-haptic consistency
   - Best for user studies where visual and haptic feedback must match

2. 'unity_only': Independent control systems  
   - Unity receives EMG predictions directly
   - ESP32 receives raw EMG predictions independently
   - Use when Unity and ESP32 should operate separately

3. 'esp32_only': ESP32 control only
   - Unity receives no events
   - ESP32 receives raw EMG predictions
   - Use for ESP32-only testing or when Unity is not needed

Task Support:
-------------
- open_close: 0=HandOpen, 1=HandClose, 2=Rest
- grasp_patterns: 0=HandOpen, 2=HookGrasp, 3=LateralGrasp, 4=IndexPointing  
- single_fingers: 0=HandOpen, 5=ThumbFlexion, 6=IndexFlexion, 7=MRPFlexion

Automatic gesture mapping ensures ESP32 shows correct gestures for each task.

Usage:
------
Add --control_mode argument to emg_control_64.py:
  python emg_control_64.py --control_mode synchronized  # default
  python emg_control_64.py --control_mode unity_only
  python emg_control_64.py --control_mode esp32_only
"""

import time
import json
import threading
from collections import deque
from queue import Full

def ControlLoop(events_socket, control_params, pred_control_queue, stop_program, pred_esp32_queue=None):
    print('Starting the control loop...')
    
    # variables initialization
    use_consec_pred = control_params['use_consec_pred']
    last_ts = time.perf_counter() # last timestamp of the event received
    
    # Control mode configuration
    # unity_only: only send to Unity, ESP32 follows raw EMG prediction
    # esp32_only: only send to ESP32, Unity not updated
    # synchronized: ESP32 follows Unity display (default)
    control_mode = control_params.get('control_mode', 'synchronized')  # default to synchronized
    
    # Get task name for gesture mapping (if available)
    task_name = control_params.get('task', 'open_close')  # default to open_close
    
    # Define Unity event ID to ESP32 gesture mapping for synchronized mode
    # This ensures ESP32 shows the same gesture as Unity regardless of task
    def get_esp32_gesture_for_unity_event(unity_event_id, task):
        """
        Map Unity event ID to ESP32 gesture for synchronized mode.
        This ensures both Unity and ESP32 show the same gesture to the user.
        """
        # Task-specific mappings from Unity event ID to ESP32 gesture
        unity_to_esp32_mappings = {
            'open_close': {
                0: 2,  # HandOpen (Unity 0) -> ESP32 Extend (2) 
                1: 1,  # HandClose (Unity 1) -> ESP32 Flex (1)
                2: 0   # Rest (Unity 2) -> ESP32 Relax (0)
            },
            'grasp_patterns': {
                0: 0,  # HandOpen (Unity 0) -> ESP32 Relax (0)
                2: 3,  # HookGrasp (Unity 2) -> ESP32 2-Finger Pinch (3)
                3: 4,  # LateralGrasp (Unity 3) -> ESP32 3-Finger Pinch (4) 
                4: 6   # IndexPointing (Unity 4) -> ESP32 Index (6)
            },
            'single_fingers': {
                0: 0,  # HandOpen (Unity 0) -> ESP32 Relax (0)
                5: 5,  # ThumbFlexion (Unity 5) -> ESP32 Thumb (5)
                6: 6,  # IndexFlexion (Unity 6) -> ESP32 Index (6)
                7: 7   # MRPFlexion (Unity 7) -> ESP32 Middle (7)
            }
        }
        
        # Get mapping for the current task
        task_mapping = unity_to_esp32_mappings.get(task, {})
        
        # Return mapped ESP32 gesture, fallback to unity_event_id if no mapping found
        return task_mapping.get(unity_event_id, unity_event_id)
    
    print(f"Control mode: {control_mode}")
    print(f"Task: {task_name}")
    if control_mode == 'unity_only':
        print("  - Unity: Will receive EMG predictions")
        print("  - ESP32: Will follow raw EMG predictions independently")
    elif control_mode == 'esp32_only':
        print("  - Unity: No events will be sent")
        print("  - ESP32: Will follow raw EMG predictions") 
    elif control_mode == 'synchronized':
        print("  - Unity: Will receive EMG predictions")
        print("  - ESP32: Will follow Unity display (synchronized)")
    else:
        print(f"  - Warning: Unknown control mode '{control_mode}', using synchronized mode")
        control_mode = 'synchronized'
    
    # Performance monitoring
    performance_stats = {
        'predictions_processed': 0,
        'unity_events_sent': 0,
        'esp32_commands_sent': 0,
        'errors_count': 0,
        'start_time': time.perf_counter()
    }
    
    # consecutive prediction control
    if use_consec_pred:
        num_consec_pred = control_params['num_consec_pred'] # default to 1 if not specified    
        last_predictions = deque([], maxlen=num_consec_pred)
    
    # Rest state tracking - Track last sent gesture to avoid duplicate rest commands
    last_sent_gesture = None  # Track the last gesture sent to ESP32

    def send_to_esp32_async(data, queue):
        """Asynchronously send data to ESP32 queue to avoid blocking Unity communication"""
        try:
            queue.put(data, timeout=0.1)  # Use timeout instead of put_nowait for better handling
            print(f"✓ Sent prediction {data[0]} to ESP32 queue (async)")
            performance_stats['esp32_commands_sent'] += 1
        except Full:
            print(f"⚠ ESP32 queue full, prediction {data[0]} skipped")
            performance_stats['errors_count'] += 1
        except Exception as e:
            print(f"✗ Error sending to ESP32 queue: {e}")
            performance_stats['errors_count'] += 1

    def send_to_unity_async(event, socket):
        """Asynchronously send event to Unity to avoid blocking ESP32 communication"""
        try:
            socket.sendall((json.dumps(event) + '\n').encode())
            print(f"✓ Sent Unity event: {event} (async)")
            performance_stats['unity_events_sent'] += 1
        except Exception as e:
            print(f"✗ Error sending to Unity: {e}")
            performance_stats['errors_count'] += 1

    # decoding loop
    while not stop_program.value:
        data = pred_control_queue.get()
        rcv_time = time.perf_counter()

        if data is not None:
            pred = data[0] # prediction from the model
            pred_prob = data[1] # prediction probability            
            performance_stats['predictions_processed'] += 1
            
            # Add prediction confidence threshold and timing checks
            min_confidence = 0.4  # Minimum confidence threshold
            min_time_between_preds = 0.1  # Minimum time between predictions (100ms)
            
            # Check if prediction meets confidence and timing criteria
            prediction_valid = True
            
            if pred_prob < min_confidence:
                print(f"   ⚠️  Low confidence prediction ({pred_prob:.2f} < {min_confidence}), sending rest state")
                prediction_valid = False
                
                # Send rest state (gesture 0) to ESP32 immediately on low confidence
                # This releases force on the soft exo for user safety
                if pred_esp32_queue is not None and last_sent_gesture not in (0, None):
                    # Only send if we haven't already sent rest state (avoid duplicates)
                    rest_data = (0, 1.0, rcv_time)  # gesture 0 (Relax), full confidence
                    esp32_thread = threading.Thread(
                        target=send_to_esp32_async,
                        args=(rest_data, pred_esp32_queue),
                        daemon=True
                    )
                    esp32_thread.start()
                    last_sent_gesture = 0
                    print(f"   ✓ Sent rest state (gesture 0) to ESP32 due to low confidence")
            
            if rcv_time - last_ts < min_time_between_preds:
                print(f"   ⚠️  Prediction too soon ({rcv_time - last_ts:.3f}s < {min_time_between_preds}s), skipping")
                prediction_valid = False
            
            print(f"pred: {pred} - prob: {pred_prob:.2f} (time interval: {rcv_time - last_ts:.3f}s) {'✅' if prediction_valid else '❌'}")

            # Only process prediction if it's valid
            if not prediction_valid:
                continue  # Skip this prediction
            
            # Control mode-specific mapping logic
            if control_mode == 'unity_only':
                # Unity gets EMG predictions, ESP32 gets raw EMG independently
                # Account for rest class offset in model predictions
                if pred == 1:  # Model's HandOpen (class 1) -> Unity HandOpen (ID 0)
                    unity_event_id = 0
                elif pred == 2:  # Model's HandClose (class 2) -> Unity HandClose (ID 1)
                    unity_event_id = 1
                else:  # Rest class
                    unity_event_id = None
                    
                esp32_gesture_id = pred  # Direct EMG prediction to ESP32 (independent)
                
            elif control_mode == 'esp32_only':
                # Only ESP32 gets controlled, Unity receives no events
                unity_event_id = None  # No Unity events
                esp32_gesture_id = pred  # Direct EMG prediction to ESP32
                
            else:  # synchronized mode (default)
                # ESP32 follows Unity display for synchronized feedback
                # Account for rest class offset in model predictions
                # Model outputs: 0=Rest, 1=HandOpen, 2=HandClose
                # Unity expects: 0=HandOpen, 1=HandClose
                if pred == 1:  # Model's HandOpen (class 1) -> Unity HandOpen (ID 0)
                    unity_event_id = 0
                elif pred == 2:  # Model's HandClose (class 2) -> Unity HandClose (ID 1)
                    unity_event_id = 1
                else:  # Rest class (pred == 0) - no Unity event
                    unity_event_id = None
                
                # ESP32 gets mapped gesture to match Unity display
                if unity_event_id is not None:
                    esp32_gesture_id = get_esp32_gesture_for_unity_event(unity_event_id, task_name)
                else:
                    esp32_gesture_id = None
            
            # Send ESP32 prediction to ESP32 queue (if ESP32 is enabled)
            if pred_esp32_queue is not None and esp32_gesture_id is not None:
                esp32_data = (esp32_gesture_id, pred_prob, rcv_time)
                esp32_thread = threading.Thread(
                    target=send_to_esp32_async, 
                    args=(esp32_data, pred_esp32_queue),
                    daemon=True
                )
                esp32_thread.start()
                last_sent_gesture = esp32_gesture_id  # Track the last sent gesture

            if use_consec_pred:
                last_predictions.append(pred)
                print(f"Consecutive predictions buffer: {list(last_predictions)}")

            # For open_close task: both class 0 (HandOpen) and class 1 (HandClose) are valid gestures
            # Only skip rest class for other tasks
            is_rest_class = False  # For open_close, no prediction is considered "rest"
            
            if not is_rest_class:  # Send all predictions for open_close task
                gesture_display = f"Unity ID: {unity_event_id if unity_event_id is not None else 'None'}, ESP32 gesture: {esp32_gesture_id if esp32_gesture_id is not None else 'None'}"
                print(f"Active prediction detected: {pred} -> {gesture_display}")
                
                if use_consec_pred:
                    # check if the last consecutive predictions are the same
                    if len(last_predictions) == num_consec_pred and all(p == last_predictions[0] for p in last_predictions):
                        # Send to Unity only if not in esp32_only mode
                        if control_mode != 'esp32_only' and unity_event_id is not None:
                            event = {
                                "eventName": "grasp_decoded",
                                "eventID": int(unity_event_id),
                            }

                            # Send to Unity in parallel (non-blocking)
                            unity_thread = threading.Thread(
                                target=send_to_unity_async,
                                args=(event, events_socket),
                                daemon=True
                            )
                            unity_thread.start()
                        last_predictions.clear()  # clear the last predictions after sending the event
                else:
                    # Send to Unity only if not in esp32_only mode
                    if control_mode != 'esp32_only' and unity_event_id is not None:
                        event = {
                            "eventName": "grasp_decoded",
                            "eventID": int(unity_event_id),
                        }

                        # Send to Unity in parallel (non-blocking)
                        unity_thread = threading.Thread(
                            target=send_to_unity_async,
                            args=(event, events_socket),
                            daemon=True
                        )
                        unity_thread.start()

            last_ts = rcv_time  # update the last timestamp
        else:
            # Decoding has stopped - send rest commands to both Unity and ESP32
            print('\n🔄 Decoding stopped - sending rest state commands...')
            
            # Send rest state to ESP32 (gesture 0 = Relax) if ESP32 is enabled
            # Only send if we haven't already sent rest state (avoid duplicates)
            if pred_esp32_queue is not None and last_sent_gesture != 0:
                try:
                    # Send relax gesture (0) to ESP32
                    esp32_rest_data = (0, 1.0, time.perf_counter())  # gesture 0, full confidence, timestamp
                    pred_esp32_queue.put(esp32_rest_data, timeout=1.0)
                    last_sent_gesture = 0
                    print('✓ Sent relax command (gesture 0) to ESP32')
                except Exception as e:
                    print(f'⚠️  Failed to send rest command to ESP32: {e}')
            elif pred_esp32_queue is not None and last_sent_gesture == 0:
                print('✓ ESP32 already in rest state (gesture 0), skipping duplicate command')
            
            # Send rest state to Unity if not in esp32_only mode
            # For Unity, we don't send an event - the hand will remain in last state
            # This is normal behavior as Unity doesn't have a dedicated rest visualization
            if control_mode != 'esp32_only':
                print('  Unity hand will remain in last gesture state (normal behavior)')
            
            break

    # Print performance statistics
    duration = time.perf_counter() - performance_stats['start_time']
    print(f'\n📊 Control Loop Performance Summary:')
    print(f'   • Duration: {duration:.2f}s')
    print(f'   • Predictions processed: {performance_stats["predictions_processed"]}')
    print(f'   • Unity events sent: {performance_stats["unity_events_sent"]}')
    print(f'   • ESP32 commands sent: {performance_stats["esp32_commands_sent"]}')
    print(f'   • Errors: {performance_stats["errors_count"]}')
    if duration > 0:
        print(f'   • Processing rate: {performance_stats["predictions_processed"]/duration:.2f} pred/s')

    print('Control loop stopped')