import time
import json
from collections import deque

def ControlLoop(events_socket, control_params, pred_control_queue, stop_program, pred_esp32_queue=None):
    print('Starting the control loop...')
    
    # variables initialization
    use_consec_pred = control_params['use_consec_pred']
    last_ts = time.perf_counter() # last timestamp of the event received
    
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

            # print debug information
            pred_prob = data[1] # prediction probability            
            print(f"pred: {pred} - prob: {pred_prob:.2f} (time interval: {rcv_time - last_ts:.3f}s)")

            # Send prediction to ESP32 queue if available
            if pred_esp32_queue is not None:
                try:
                    pred_esp32_queue.put_nowait(data)  # Send prediction data to ESP32 controller
                except:
                    pass  # Queue might be full, skip this prediction

            if use_consec_pred:
                last_predictions.append(pred)

            if pred > 0: # check that the prediction is not the rest class
                pred -= 1 # adjust prediction to match the event ID (assuming 0 is rest class)
                
                if use_consec_pred:
                    # check if the last consecutive predictions are the same
                    if len(last_predictions) == num_consec_pred and all(p == last_predictions[0] for p in last_predictions):
                        event = {
                            "eventName": "grasp_decoded",
                            "eventID": int(pred),
                        }

                        events_socket.sendall(json.dumps(event).encode())
                        last_predictions.clear()  # clear the last predictions after sending the event
                else:
                    event = {
                        "eventName": "grasp_decoded",
                        "eventID": int(pred),
                    }

                    events_socket.sendall(json.dumps(event).encode())

            last_ts = rcv_time  # update the last timestamp
        else:
            break

    print('Control loop stopped')