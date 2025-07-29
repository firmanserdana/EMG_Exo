import socket
import threading
import time
import json

def listen_to_unity(sock, stop_event):
    while not stop_event.is_set():
        try:
            data = sock.recv(1024)
            if not data:
                break
            print("Received from Unity:", data.decode())
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except socket.timeout:
            continue
        except OSError:
            break

def main():
    print("Starting Unity event listener...")

    host = '127.0.0.1'
    port = 56000

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Waiting for Unity server at {host}:{port} (Ctrl+C to stop)...")

    while True:
        try:
            sock.connect((host, port))
            print("Connected to Unity")
            break
        except (ConnectionRefusedError, OSError):
            try:
                time.sleep(.5)
            except KeyboardInterrupt:
                print("\nStopped by user.") 
                sock.close()
                return

    stop_event = threading.Event()
    listener = threading.Thread(target=listen_to_unity, args=(sock, stop_event))
    listener.start()

    num_trials = 200
    grasp_ids = [(i%2) for i in range(num_trials)]

    try:
        for trial in range(num_trials):
            input(f"Press Enter to send event for trial {trial + 1}/{num_trials}...")

            msg_json = {
                "eventName": "grasp_decoded",
                "eventID": grasp_ids[trial],
            }
                
            print(f"Sending event: {msg_json}")
            sock.sendall(json.dumps(msg_json).encode())
    except KeyboardInterrupt:
        print("\nStopped by user.")

    stop_event.set()
    sock.close()
    listener.join()

if __name__ == "__main__":
    main()