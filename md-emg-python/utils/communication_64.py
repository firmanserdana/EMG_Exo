#!python3
# -------------------------------------------------------
# Module to connect to Sessantaquattro Bio signal data logger
#
import datetime
import multiprocessing
import socket  # we will need this for establishing the communication with Sessantaquattro
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation

CONVERSION_FACTOR = 0.000286  # conversion factor needed to get values in mV

# Convert integer to bytes
def integer_to_bytes(command):
    return int(command).to_bytes(2, byteorder="big")


# Convert byte-array value to an integer value and apply two's complement
def convert_bytes_to_int(bytes_value, bytes_in_sample):
    value = None
    if bytes_in_sample == 2:
        # Combine 2 bytes to a 16 bit integer value
        value = \
            bytes_value[0] * 256 + \
            bytes_value[1]
        # See if the value is negative and make the two's complement
        if value >= 32768:
            value -= 65536
    elif bytes_in_sample == 3:
        # Combine 3 bytes to a 24 bit integer value
        value = \
            bytes_value[0] * 65536 + \
            bytes_value[1] * 256 + \
            bytes_value[2]
        # See if the value is negative and make the two's complement
        if value >= 8388608:
            value -= 16777216
    else:
        raise Exception(
            "Unknown bytes_in_sample value. Got: {}, "
            "but expecting 2 or 3".format(bytes_in_sample))
    return value


# Create the binary command which is sent to Sessantaquattro
# to start or stop the communication with wanted data logging setup
def create_bin_command(start, num_channels):
    rec = 0
    trig = 0
    ext = 0
    hpf = 1
    hres = 1

    # (mode = 2 for 64 channels) | (mode = 1 for 8 channels)
    mode = 1 if num_channels == 8 else 2 

    # (nch = 3 for 32/64 channels) | (nch = 2 for 20 channels) | (nch = 1 for 8 channels)
    nch = 3 if (num_channels == 32 or num_channels == 64) else (2 if num_channels == 20 else 1)

    fsamp = 1 # (fsamp 1 for 1000Hz) | (fsamp 0 for 500Hz)
    getset = 0

    command = 0
    command = command + start
    command = command + rec * 2
    command = command + trig * 4
    command = command + ext * 16
    command = command + hpf * 64
    command = command + hres * 128
    command = command + mode * 256
    command = command + nch * 2048
    command = command + fsamp * 8192
    command = command + getset * 32768

    num_channels_command = None
    sample_frequency = None
    bytes_in_sample = None

    if nch == 0:
        if mode == 1:
            num_channels_command = 8
        else:
            num_channels_command = 12
    elif nch == 1:
        if mode == 1:
            num_channels_command = 12
        else:
            num_channels_command = 20
    elif nch == 2:
        if mode == 1:
            num_channels_command = 20
        else:
            num_channels_command = 36
    elif nch == 3:
        if mode == 1:
            num_channels_command = 36
        else:
            num_channels_command = 68
    else:
        raise Exception('Wrong value for nch. Got: {0}', nch)

    if fsamp == 0:
        if mode == 3:
            sample_frequency = 2000
        else:
            sample_frequency = 500
    elif fsamp == 1:
        if mode == 3:
            sample_frequency = 4000
        else:
            sample_frequency = 1000
    elif fsamp == 2:
        if mode == 3:
            sample_frequency = 8000
        else:
            sample_frequency = 2000
    elif fsamp == 3:
        if mode == 3:
            sample_frequency = 16000
        else:
            sample_frequency = 4000
    else:
        raise Exception('Wrong value for fsamp. Got: {fsamp}', fsamp)

    if hres == 1:
        bytes_in_sample = 3 # 24 bit
    else:
        bytes_in_sample = 2 # 16 bit

    if (
            not num_channels_command or
            not sample_frequency or
            not bytes_in_sample):
        raise Exception(
            "Could not set number_of_channels "
            "and/or and/or bytes_in_sample")

    return (integer_to_bytes(command),
            num_channels_command,
            sample_frequency,
            bytes_in_sample)


# Convert channels from bytes to integers
def bytes_to_integers(
        sample_from_channels_as_bytes,
        number_of_channels,
        bytes_in_sample,
        output_milli_volts):
    number_of_channels *= 2 # double the number of channels taken at each call for keeping up with the sampling rate

    # Validate we have enough bytes
    expected_bytes = number_of_channels * bytes_in_sample
    if sample_from_channels_as_bytes is None:
        raise Exception("No data received from Sessantaquattro")
    if len(sample_from_channels_as_bytes) < expected_bytes:
        raise Exception(f"Incomplete data: received {len(sample_from_channels_as_bytes)} bytes, expected {expected_bytes}")

    channel_values = []
    # Separate channels from byte-string. One channel has
    # "bytes_in_sample" many bytes in it.
    for channel_index in range(number_of_channels):
        channel_start = channel_index * bytes_in_sample
        channel_end = (channel_index + 1) * bytes_in_sample
        channel = sample_from_channels_as_bytes[channel_start:channel_end]

        # Convert channel's byte value to integer
        value = convert_bytes_to_int(channel, bytes_in_sample)

        # Convert bio measurement channels to milli volts if needed
        # The 4 last channels (Auxiliary and Accessory-channels)
        # are not to be converted to milli volts
        if output_milli_volts and channel_index < (number_of_channels - 4):
            value *= CONVERSION_FACTOR
        channel_values.append(value)
    return channel_values


#     Read raw byte stream from data logger. Read one sample from each
#     channel. Each channel has 'bytes_in_sample' many bytes in it.
def read_raw_bytes(connection, number_of_all_channels, bytes_in_sample):
    try:
        buffer_size = number_of_all_channels * bytes_in_sample * 2 # x2 for two samples per read
        new_bytes = b''
        
        # Loop until we have all bytes (recv may return partial data)
        while len(new_bytes) < buffer_size:
            chunk = connection.recv(buffer_size - len(new_bytes))
            if not chunk:
                raise Exception("Connection closed by Sessantaquattro")
            new_bytes += chunk
            
    except KeyboardInterrupt:
        return None
    except socket.error as e:
        raise Exception(f"Socket error: {e}")
    except Exception as e:
        raise Exception(f"An error occurred while reading bytes: {e}")

    return new_bytes


# Connect to Sessantaquattro's TCP socket and send start command
# Note: Python acts as TCP SERVER, Sessantaquattro connects as CLIENT
# The ip_address should be the Sessantaquattro's configured TCP server IP (your laptop's IP on the hotspot)
def connect_to_sq(ip_address, port, num_channels):    
    try:
        # Create a socket which is used to connect to Sessantaquattro
        sq_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sq_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sq_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        
        # Bind to all interfaces or the hotspot interface
        # The Sessantaquattro connects TO us, so we need to listen on our IP
        # Try to bind to the specific IP first, fallback to all interfaces
        bind_ip = ip_address
        try:
            sq_socket.bind((bind_ip, port))
        except OSError:
            # If binding to specific IP fails, try binding to all interfaces
            bind_ip = '0.0.0.0'
            sq_socket.bind((bind_ip, port))
        
        sq_socket.listen(1) 
        sq_socket.settimeout(30)  # Increased timeout for connection

        print(f'Waiting for connection on {bind_ip}:{port}...')

        conn, addr = sq_socket.accept()
        print(f'Connection from address: {addr}')

        # Create start command and get basic setup information
        start_command,num_channels_64,fsample,bytes_in_sample = create_bin_command(start=1,num_channels=num_channels)

        conn.send(start_command)
    except socket.timeout:
        print("Connection timed out. Make sure Sessantaquattro is running and the IP address and port are correct.")
        return None, None, None, None
    except socket.error as e:
        raise Exception(f"Socket error: {e}")
    except Exception as e:
        raise Exception(f"An error occurred: {e}")

    return conn, num_channels_64, fsample, bytes_in_sample


# Disconnect from Sessantaquattro by sending a stop command
def disconnect_from_sq(conn):
    if conn is not None:
        (stop_command,
         _,
         __,
         ___) = create_bin_command(start=0)
        conn.send(stop_command)
        conn.shutdown(2)
        conn.close()
    else:
        raise Exception(
            "Can't disconnect because the"
            "connection is not established")

