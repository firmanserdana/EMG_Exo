import socket
import time
import json

# Thread for reading the Unity TCP events
def EventsLoop(events_socket, events_queue, stop_program, decoding_active=False, is_decoding=None):
    print('Starting the events loop')

    # reading events loop
    while not stop_program.value:
        try:
            data = events_socket.recv(1024)
            if not data:
                continue

            timestamp = time.perf_counter()

            buffer = data.decode()

            while '\n' in buffer:
                event_msg, buffer = buffer.split('\n', 1)

                try:
                    event_json = json.loads(event_msg)
                except json.JSONDecodeError:
                    print(f"Received invalid JSON data: {event_msg}")
                    continue

                event = event_json.get("event", "")
                event_id = event_json.get("event_id")

                if decoding_active:
                    if event == 'decoding_start':
                        is_decoding.value = True
                    elif event == 'decoding_stop':
                        is_decoding.value = False
                
                if event_id is not None:
                    event = f"{event}_{event_id}"

                events_queue.put((event, timestamp))  # Put the received data and timestamp in the queue
        except socket.timeout:
            continue  # Timeout occurred, check stop_program and loop again
        except KeyboardInterrupt:
            break
        except OSError as e:
            if hasattr(e, 'winerror') and e.winerror == 10035:
                continue  # No data available, just try again
            print(f"Socket error: {e}")
            break

    print("Events loop stopped") 