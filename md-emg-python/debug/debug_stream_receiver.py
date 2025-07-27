import socket
import threading
import time
import numpy as np
import struct

def server_thread(host, port, stop_event):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(1)
    server_sock.settimeout(1.0)

    print(f"Server listening at {host}:{port}")

    try:
        while not stop_event.is_set():
            try:
                conn, addr = server_sock.accept()
                print(f"Connection from {addr}")
                listen_to_sender(conn, stop_event)
                conn.close()  # Close connection after client disconnects
                print("Connection closed. Waiting for new connection...")
            except socket.timeout:
                continue
    finally:
        server_sock.close()

def recvall(conn, n):
    """Helper function to receive n bytes or return None if EOF is hit"""
    data = bytearray()
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def listen_to_sender(conn, stop_event):
    header_size = struct.calcsize('!II8s')  # 2 ints + 8-char dtype string

    while not stop_event.is_set():
        try:
            # 1. Receive header
            header_bytes = recvall(conn, header_size)
            if not header_bytes:
                break
            rows, cols, dtype_bytes = struct.unpack('!II8s', header_bytes)
            dtype_str = dtype_bytes.decode('ascii').strip('\x00')
            shape = (rows, cols)
            dtype = np.dtype(dtype_str)

            # 2. Receive data
            n_bytes = rows * cols * dtype.itemsize
            data_bytes = recvall(conn, n_bytes)
            if not data_bytes:
                break
            arr = np.frombuffer(data_bytes, dtype=dtype).reshape(shape)
            print("Received array with shape:", arr.shape, "dtype:", arr.dtype)
            # Do something with arr
        except OSError:
            break

def main():
    print("Starting stream listener...")

    host = '127.0.0.1'
    port = 55001

    stop_event = threading.Event()
    server = threading.Thread(target=server_thread, args=(host, port, stop_event))
    server.start()

    time.sleep(1)  # Give the server time to start

    try:
        input("\nType enter to stop the server...")
        stop_event.set()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        stop_event.set()

    server.join()

if __name__ == "__main__":
    main()