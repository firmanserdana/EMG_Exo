import socket
import time
import json

# Thread for reading the Unity TCP events
def EventsLoop(
    events_socket,
    events_queue,
    stop_program,
    decoding_active=False,
    is_decoding=None,
    broadcast_queue=None,
):
    """
    Listens for and processes events from a TCP socket (e.g., Unity).

    This loop continuously reads data from the provided socket, parses JSON event
    messages, and puts them into a queue for other components to process.
    """
    print('Starting the events loop...')
    
    # Set a default timeout to prevent the loop from blocking indefinitely
    if events_socket.gettimeout() is None:
        events_socket.settimeout(1.0)
    
    buffer = ""
    
    while not stop_program.value:
        try:
            # Read data from the socket
            data = events_socket.recv(1024)
            if not data:
                # Connection closed by the other end
                print("Events socket connection closed.")
                break

            timestamp = time.perf_counter()
            buffer += data.decode('utf-8')

            # Process all complete JSON messages in the buffer
            while '\n' in buffer:
                event_msg, buffer = buffer.split('\n', 1)
                if not event_msg:
                    continue

                try:
                    event_json = json.loads(event_msg)
                    event = event_json.get("event")
                    if not event:
                        continue

                    # Handle decoding state changes if applicable
                    if decoding_active and is_decoding is not None:
                        if event == 'decoding_start':
                            is_decoding.value = True
                        elif event == 'decoding_stop':
                            is_decoding.value = False
                    
                    # Prepare event data for the queue
                    event_data = {
                        'event_type': event,
                        'data': event_json.get('data', ''),
                        'timestamp': timestamp
                    }
                    
                    # Append event_id to event_type if it exists
                    event_id = event_json.get("event_id")
                    if event_id is not None:
                        event_data['event_type'] = f"{event}_{event_id}"

                    events_queue.put(event_data)
                    
                    if broadcast_queue is not None:
                        try:
                            broadcast_queue.put(event_data.copy(), timeout=0.01)
                        except Exception:
                            # Non-blocking best effort broadcast; ignore if queue is full/unavailable
                            pass

                except json.JSONDecodeError:
                    print(f"Received invalid JSON data: {event_msg}")
                    continue

        except socket.timeout:
            # No data received, continue to check the stop_program flag
            continue
        except OSError as e:
            # Handle non-blocking socket errors
            if e.errno in [35, 10035]:  # EAGAIN/EWOULDBLOCK
                time.sleep(0.01) # Brief sleep to prevent busy-waiting
                continue
            print(f"Events loop socket error: {e}")
            break
        except Exception as e:
            print(f"An unexpected error occurred in EventsLoop: {e}")
            break

    print("Events loop stopped.")