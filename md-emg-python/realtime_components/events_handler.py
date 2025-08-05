import socket
import time
import json

# Thread for reading the Unity TCP events
def EventsLoop(events_socket, events_queue, stop_program, decoding_active=False, is_decoding=None):
    print('Starting the events loop')
    print(f'Events socket info: {events_socket}')
    print(f'Socket timeout: {events_socket.gettimeout()}')
    
    # Ensure socket has proper timeout settings
    if events_socket.gettimeout() is None:
        events_socket.settimeout(2.0)  # Set 2 second timeout if none set
        print('Set socket timeout to 2.0 seconds')
    
    buffer = ""  # Initialize buffer outside the loop to handle partial messages
    
    # reading events loop
    while not stop_program.value:
        try:
            data = events_socket.recv(1024)
            if not data:
                print("No data received from socket")
                continue
            
            print(f"Received raw data: {data}")  # Debug: show raw data

            timestamp = time.perf_counter()

            buffer += data.decode()
            print(f"Current buffer: {repr(buffer)}")  # Debug: show buffer content

            while '\n' in buffer:
                event_msg, buffer = buffer.split('\n', 1)
                print(f"Processing event message: {repr(event_msg)}")  # Debug: show message being processed

                try:
                    event_json = json.loads(event_msg)
                    print(f"Parsed JSON: {event_json}")  # Debug: show parsed JSON
                except json.JSONDecodeError:
                    print(f"Received invalid JSON data: {event_msg}")
                    continue

                event = event_json.get("event", "")
                event_id = event_json.get("event_id")
                print(f"Event: {event}, Event ID: {event_id}")  # Debug: show extracted event info

                if decoding_active:
                    if event == 'decoding_start':
                        is_decoding.value = True
                    elif event == 'decoding_stop':
                        is_decoding.value = False
                
                event_data = {
                    'event_type': event,
                    'data': event_json.get('data', ''),
                    'timestamp': timestamp
                }

                if event_id is not None:
                    event_data['event_type'] = f"{event}_{event_id}"

                print(f"Adding event to queue: {event_data}")  # Debug: show event being queued
                events_queue.put(event_data)  # Put the received data and timestamp in the queue
        except socket.timeout:
            print("Socket timeout - no data received")  # Debug: show timeout
            continue  # Timeout occurred, check stop_program and loop again
        except KeyboardInterrupt:
            break
        except OSError as e:
            # Handle "Resource temporarily unavailable" error on macOS
            if e.errno == 35:  # EAGAIN/EWOULDBLOCK on macOS
                print("No data available - continuing")  # Debug: show no data available
                time.sleep(0.1)  # Brief sleep to prevent busy waiting
                continue
            elif hasattr(e, 'winerror') and e.winerror == 10035:
                print("No data available - continuing")  # Debug: show no data available
                continue  # No data available, just try again
            print(f"Socket error: {e}")
            break

    print("Events loop stopped")