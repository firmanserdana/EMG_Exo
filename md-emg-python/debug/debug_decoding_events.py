import socket
import threading
import time
import json
import argparse

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

def parse_args():
    parser = argparse.ArgumentParser(description="Send/receive decoding events with Unity over TCP")
    parser.add_argument("--host", default="127.0.0.1", help="Unity server host")
    parser.add_argument("--port", type=int, default=55000, help="Unity server port")
    parser.add_argument("--num-trials", type=int, default=200, help="Number of events to send")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-send events every 0.25s instead of waiting for Enter",
    )
    return parser.parse_args()


def main():
    print("Starting Unity event listener...")

    args = parse_args()
    host = args.host
    port = args.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Waiting for Unity server at {host}:{port} (Ctrl+C to stop)...")

    sock.settimeout(1.0)
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

    num_trials = args.num_trials
    grasp_ids = [(i % 2) for i in range(num_trials)]

    try:
        for trial in range(num_trials):
            if args.auto:
                time.sleep(0.25)
            else:
                input(f"Press Enter to send event for trial {trial + 1}/{num_trials}...")

            msg_json = {
                "eventName": "grasp_decoded",
                "eventID": grasp_ids[trial],
            }
                
            print(f"Sending event: {msg_json}")
            try:
                sock.sendall(json.dumps(msg_json).encode())
            except (BrokenPipeError, OSError):
                print("Connection lost while sending; stopping.")
                break
    except KeyboardInterrupt:
        print("\nStopped by user.")

    stop_event.set()
    sock.close()
    listener.join()

if __name__ == "__main__":
    main()