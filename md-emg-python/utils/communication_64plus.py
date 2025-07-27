#!python3
# -------------------------------------------------------
# Module to connect to Sessantaquattro+ signal data logger
#
import socket  

CONVERSION_FACTOR = 0.000286  # conversion factor needed to get values in mV

def create_bin_command(start=1):
    rec = 0
    trig = 0
    ext = 0
    hpf = 1
    hres = 0
    mode = 1 # changed
    nch = 1
    fsamp = 2
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

    number_of_channels = None
    sample_frequency = None
    bytes_in_sample = None

    if nch == 0:
        if mode == 1:
            number_of_channels = 12
        else:
            number_of_channels = 16
    elif nch == 1:
        if mode == 1:
            number_of_channels = 16
        else:
            number_of_channels = 24
    elif nch == 2:
        if mode == 1:
            number_of_channels = 24
        else:
            number_of_channels = 40
    elif nch == 3:
        if mode == 1:
            number_of_channels = 40
        else:
            number_of_channels = 72
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
        raise Exception('wrong value for fsamp. Got: {fsamp}', fsamp)

    if hres == 1:
        bytes_in_sample = 3
    else:
        bytes_in_sample = 2

    if (
            not number_of_channels or
            not sample_frequency or
            not bytes_in_sample):
        raise Exception(
            "Could not set number_of_channels "
            "and/or and/or bytes_in_sample")

    command_in_bytes = int(command).to_bytes(2, byteorder="big")
    # print("number_of_channels", number_of_channels)

    return (command_in_bytes,
            number_of_channels,
            sample_frequency,
            bytes_in_sample)

def connect_to_sq(serverIP,port):
    """
    Initialize connection
    """
    # create TCP server socket (listens to a client, waits for data)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # set some other socket options
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # setsockopt --> per settare le opzioni della socket
    server_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)

    server_socket.bind((serverIP, port))
    server_socket.listen(1) 
    conn, addr = server_socket.accept()
    print('Connection from address: {0}'.format((addr)))

    start_command, nb_channels, sample_freq, bytes_per_ch = create_bin_command(start=1)

    conn.send(start_command)
    
    return conn, nb_channels,sample_freq,bytes_per_ch


def read_raw_bytes(conn,nb_channels,bytes_per_ch):
    buffer_size = nb_channels * bytes_per_ch
    new_bytes = conn.recv(buffer_size)
    return new_bytes


# Convert channels from bytes to integers
def bytes_to_integers(sample_from_channels_as_bytes, nb_channels, bytes_per_ch, output_milli_volts):
    channel_values = []
    # Separate channels from byte-string. One channel has
    # "bytes_in_sample" many bytes in it.
    for channel_index in range(nb_channels):
        channel_start = channel_index * bytes_per_ch
        channel_end = (channel_index + 1) * bytes_per_ch
        channel = sample_from_channels_as_bytes[channel_start:channel_end]

        # Convert channel's byte value to integer
        value = convert_bytes_to_int(channel, bytes_per_ch)

        # Convert bio measurement channels to milli volts if needed
        # The 4 last channels (Auxiliary and Accessory-channels)
        # are not to be converted to milli volts
        if output_milli_volts and channel_index < (nb_channels - 8):
            value *= CONVERSION_FACTOR
        channel_values.append(value)
    return channel_values




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


def disconnect_from_sq(conn):
    """
    Disconnect from Sessantaquattro by sending a stop command
    """
    if conn is not None:
        start = 0
        stop_cmd, _,_,_ = create_bin_command(start)
        conn.send(stop_cmd)
        conn.shutdown(2)
        conn.close()
    else:
        raise Exception(
            "Can't disconnect because the"
            "connection is not established")