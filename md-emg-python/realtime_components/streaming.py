import struct

def StreamDataLoop(stream_socket, stream_queue, stop_program):
    print('Starting the streaming loop')

    while not stop_program.value:
        data = stream_queue.get()

        if data is not None:
            shape = data.shape
            dtype_str = str(data.dtype)

            shape_dim2 = shape[1] if len(shape) > 1 else 1

            # using 2 integers for shape (rows, cols) and 8 bytes for dtype string
            header = struct.pack('!II8s', shape[0], shape_dim2, dtype_str.encode('ascii'))

            try:
                stream_socket.sendall(header)
                stream_socket.sendall(data.tobytes())
            except Exception as e:
                print(f"Error sending data: {e}")
                break
        else:
            break

    print('Streaming loop stopped')