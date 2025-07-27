import socket
import time

def socket_connect(host, port, timeout=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Waiting for socket server at {host}:{port} (press Ctrl+C to stop)")
    try:
        while True:
            try:
                sock.connect((host, port))
                if timeout is not None:
                    sock.settimeout(timeout)
                print("Connected to socket server")
                return sock
            except (ConnectionRefusedError, OSError):
                time.sleep(.1)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sock.close()
        return None
            
def socket_close(socket):
    """Close the socket connection if it exists."""
    if socket:
        try:
            socket.close()
            print("Socket closed successfully.")
        except OSError as e:
            print(f"Error closing socket: {e}")

def server_socket_open(host, port, timeout=None):
    """Open a server socket at the specified host and port."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(1)
    server_socket.settimeout(timeout)

    return server_socket

def recvall(conn, n):
    """Helper function to receive n bytes or return None if EOF is hit"""
    data = bytearray()
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data