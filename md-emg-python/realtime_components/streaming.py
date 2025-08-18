import struct
import socket
from queue import Empty

def StreamDataLoop(stream_socket, stream_queue, stop_program):
    """
    Streams data from a queue over a TCP socket.

    This loop retrieves numpy arrays from a queue, packs them into a binary
    format with a header containing shape and dtype, and sends them over
    the provided socket.
    """
    print('Starting the streaming loop...')

    while not stop_program.value:
        try:
            # Use a timeout to prevent blocking indefinitely
            data = stream_queue.get(timeout=0.1)

            if data is not None:
                shape = data.shape
                dtype_str = str(data.dtype)

                # Ensure shape has two dimensions for packing
                shape_dim1 = shape[0]
                shape_dim2 = shape[1] if len(shape) > 1 else 1

                # Pack header: shape (2 integers) and dtype (8-byte string)
                header = struct.pack('!II8s', shape_dim1, shape_dim2, dtype_str.encode('ascii'))

                # Send header followed by the raw byte data
                stream_socket.sendall(header)
                stream_socket.sendall(data.tobytes())
        
        except Empty:
            # Queue was empty, continue to check stop_program
            continue
        except (socket.error, BrokenPipeError) as e:
            print(f"Streaming socket error: {e}. Stopping loop.")
            break
        except Exception as e:
            print(f"An unexpected error occurred in StreamDataLoop: {e}")
            break

    print('Streaming loop stopped.')