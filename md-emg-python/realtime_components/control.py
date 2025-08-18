"""
Control Loop for EMG Gesture Classification
==========================================

This module handles the control logic for routing EMG predictions to Unity and ESP32 devices.

Control Modes:
--------------
1. 'synchronized' (default): ESP32 follows Unity display for consistent user feedback
   - Unity receives EMG predictions
   - ESP32 shows the same gesture as Unity
   - Best for user studies where visual and haptic feedback should match

2. 'unity_only': Independent control systems  
   - Unity receives EMG predictions
   - ESP32 receives raw EMG predictions independently
   - Use when Unity and ESP32 should operate independently

3. 'esp32_only': ESP32 control only
   - Unity receives no events
   - ESP32 receives raw EMG predictions
   - Use for ESP32-only testing or when Unity is not needed

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
    
    print(f"Control mode: {control_mode}")
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
                print(f"   ⚠️  Low confidence prediction ({pred_prob:.2f} < {min_confidence}), skipping")
                prediction_valid = False
            
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
                unity_event_id = pred  # Direct EMG prediction to Unity
                esp32_gesture_id = pred  # Direct EMG prediction to ESP32 (independent)
                
            elif control_mode == 'esp32_only':
                # Only ESP32 gets controlled, Unity receives no events
                unity_event_id = None  # No Unity events
                esp32_gesture_id = pred  # Direct EMG prediction to ESP32
                
            else:  # synchronized mode (default)
                # ESP32 follows Unity display for synchronized feedback
                # Map for Unity (direct mapping for open_close task)
                if pred == 0:
                    unity_event_id = 0  # HandOpen -> Unity 0
                elif pred == 1:
                    unity_event_id = 1  # HandClose -> Unity 1 
                else:
                    unity_event_id = pred  # fallback for other tasks
                
                # ESP32 shows the same gesture as Unity (synchronized)
                esp32_gesture_id = unity_event_id
            
            # Send ESP32 prediction to ESP32 queue (if ESP32 is enabled)
            if pred_esp32_queue is not None and esp32_gesture_id is not None:
                esp32_data = (esp32_gesture_id, pred_prob, rcv_time)
                esp32_thread = threading.Thread(
                    target=send_to_esp32_async, 
                    args=(esp32_data, pred_esp32_queue),
                    daemon=True
                )
                esp32_thread.start()

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