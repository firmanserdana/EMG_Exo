"""
Control Loop for EMG Gesture Classification
==========================================

This module handles the control logic for routing EMG predictions to Unity.
Supports all tasks (open_close, grasp_patterns, single_fingers) with automatic gesture mapping.

Task Support:
-------------
- open_close: 0=HandOpen, 1=HandClose, 2=Rest
- grasp_patterns: 0=HandOpen, 2=HookGrasp, 3=LateralGrasp, 4=IndexPointing  
- single_fingers: 0=HandOpen, 5=ThumbFlexion, 6=IndexFlexion, 7=MRPFlexion
"""

import time
import json
from collections import deque

def ControlLoop(
    events_socket,
    control_params,
    pred_control_queue,
    stop_program,
):
    print('Starting the control loop...')
    
    # variables initialization
    use_consec_pred = control_params['use_consec_pred']
    last_ts = time.perf_counter() # last timestamp of the event received
    
    # Get task name for gesture mapping (if available)
    task_name = control_params.get('task', 'open_close')  # default to open_close
    
    # Map decoded model labels to Unity event IDs (rest handled separately)
    unity_event_mappings = {
        'open_close': {
            1: 0,  # HandOpen
            2: 1,  # HandClose
        },
        'grasp_patterns': {
            3: 2,  # HookGrasp
            4: 3,  # LateralGrasp
            5: 4,  # IndexPointing
        },
        'single_fingers': {
            6: 5,  # ThumbFlexion
            7: 6,  # IndexFlexion
            8: 7,  # MRPFlexion
        },
    }
    
    print(f"Task: {task_name}")
    print("  - Unity: Will receive EMG predictions")
    
    # Performance monitoring
    performance_stats = {
        'predictions_processed': 0,
        'unity_events_sent': 0,
        'errors_count': 0,
        'start_time': time.perf_counter()
    }
    
    # consecutive prediction control
    if use_consec_pred:
        num_consec_pred = control_params['num_consec_pred'] # default to 1 if not specified    
        last_predictions = deque([], maxlen=num_consec_pred)
    
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

            # Handle explicit rest predictions (label 0)
            if pred == 0:
                print("   → Rest prediction detected")
                if use_consec_pred:
                    last_predictions.clear()
                last_ts = rcv_time
                continue
            
            # Get Unity event ID from mapping
            task_unity_mapping = unity_event_mappings.get(task_name, {})
            unity_event_id = task_unity_mapping.get(pred)
            
            if unity_event_id is None:
                if pred in (0,):
                    unity_event_id = None
                else:
                    print(f"   ⚠️  No Unity mapping for prediction {pred} (task: {task_name}), using raw label")
                    unity_event_id = pred
            
            if use_consec_pred:
                last_predictions.append(pred)
                
                if len(last_predictions) == num_consec_pred:
                    if all(p == last_predictions[0] for p in last_predictions):
                        pred_confirmed = last_predictions[0]
                        unity_event_id = task_unity_mapping.get(pred_confirmed, pred_confirmed)
                        
                        print(f"   ✅ Consecutive prediction confirmed: {pred_confirmed}")
                        print(f"   → Sending Unity event: {unity_event_id}")
                        
                        # Send event to Unity
                        event = {"event": "prediction", "data": str(unity_event_id)}
                        try:
                            events_socket.sendall((json.dumps(event) + '\n').encode())
                            performance_stats['unity_events_sent'] += 1
                        except Exception as e:
                            print(f"   ✗ Error sending to Unity: {e}")
                            performance_stats['errors_count'] += 1
                        
                        last_predictions.clear()
                    else:
                        print(f"   ⚠️  Predictions not consistent: {list(last_predictions)}")
            else:
                # Send immediately without consecutive prediction check
                print(f"   → Sending Unity event: {unity_event_id}")
                
                event = {"event": "prediction", "data": str(unity_event_id)}
                try:
                    events_socket.sendall((json.dumps(event) + '\n').encode())
                    performance_stats['unity_events_sent'] += 1
                except Exception as e:
                    print(f"   ✗ Error sending to Unity: {e}")
                    performance_stats['errors_count'] += 1
            
            last_ts = rcv_time
        else:
            break
    
    # Print performance summary
    elapsed_time = time.perf_counter() - performance_stats['start_time']
    print("\n=== Control Loop Performance Summary ===")
    print(f"Total runtime: {elapsed_time:.2f}s")
    print(f"Predictions processed: {performance_stats['predictions_processed']}")
    print(f"Unity events sent: {performance_stats['unity_events_sent']}")
    print(f"Errors: {performance_stats['errors_count']}")
    if performance_stats['predictions_processed'] > 0:
        print(f"Average processing rate: {performance_stats['predictions_processed']/elapsed_time:.2f} pred/s")
    print("=====================================\n")
    
    print('Control loop stopped')
