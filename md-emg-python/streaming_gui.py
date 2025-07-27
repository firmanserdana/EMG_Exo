import socket
import threading
import time
import struct
import os
import yaml
import numpy as np
import dearpygui.dearpygui as dpg
import queue
import sys
from collections import deque

from utils.network_utils import *

# Shared data structures
data_queue = queue.Queue()
pred_queue = queue.Queue()
sample_counter = 0
pred_counter = 0

def server_thread(host, port, stop_event):
    server_sock = server_socket_open(host, port, timeout=1.0)
    print(f"Server listening at {host}:{port}")

    try:
        while not stop_event.is_set():
            try:
                conn, addr = server_sock.accept()
                print(f"Connection from {addr}")
                listen_to_sender(conn, stop_event)
                conn.close()
            except socket.timeout:
                continue
    finally:
        server_sock.close()

def listen_to_sender(conn, stop_event):
    header_size = struct.calcsize('!II8s')

    while not stop_event.is_set():
        try:
            header_bytes = recvall(conn, header_size)
            if header_bytes is None or len(header_bytes) != header_size:
                break

            rows, cols, dtype_bytes = struct.unpack('!II8s', header_bytes)
            dtype_str = dtype_bytes.decode('ascii').strip('\x00')
            dtype = np.dtype(dtype_str)
            n_bytes = rows * cols * dtype.itemsize

            data_bytes = recvall(conn, n_bytes)
            
            if len(data_bytes) != n_bytes:
                print(f"Data truncated: expected {n_bytes}, got {len(data_bytes)}")
                break

            arr = np.frombuffer(data_bytes, dtype=dtype).copy()

            # Distinguish EMG vs prediction_prob by shape
            if cols == n_channels:
                arr = arr.reshape(rows, cols)
                data_queue.put(arr)
            else:
                pred_queue.put(arr)

        except (OSError, struct.error) as e:
            print(f"Connection error: {str(e)}")
            break

def min_max_norm(arr):
    arr = np.array(arr)
    min_val, max_val = arr.min(), arr.max()
    return (arr - min_val) / (max_val - min_val) if (max_val - min_val) != 0 else arr

def update_data(stop_event):
    global sample_counter, pred_counter
    while not stop_event.is_set():
        updated = False
        # EMG data
        while not data_queue.empty():
            try:
                arr = data_queue.get_nowait()
                n_samples = arr.shape[0]
                for i in range(n_samples):
                    data_x.append(sample_counter)
                    for ch in range(n_channels):
                        data_y[ch].append(arr[i, ch])
                    sample_counter += 1
                updated = True
            except queue.Empty:
                break

        # Prediction probabilities
        while not pred_queue.empty():
            try:
                pred_prob = pred_queue.get_nowait()  # pred_prob is a 1D array of length N
                pred_x.append(pred_counter)
                for p in range(len(pred_prob)):
                    if p >= len(pred_y):
                        # Extend pred_y if needed
                        pred_y.append(deque(maxlen=n_samples_prob))
                    pred_y[p].append(pred_prob[p])
                pred_counter += 1
                updated = True
            except queue.Empty:
                break

        if updated:
            # EMG plot
            x_plot = list(data_x)
            for ch in range(n_channels):
                channel_data = np.array(data_y[ch])
                minimum = np.min(channel_data)
                maximum = np.max(channel_data)
                normed = (channel_data - minimum) / (maximum - minimum + 1e-9) + ch
                dpg.set_value(f'series_tag_{ch}', [x_plot, normed.tolist()])

            dpg.fit_axis_data('x_axis')
            dpg.fit_axis_data('y_axis')

            # Prediction probability plot
            try:
                px_plot = list(pred_x)
                for p in range(len(pred_y)):
                    py = list(pred_y[p])
                    min_len = min(len(px_plot), len(py))
                    if min_len == 0:
                        continue  # nothing to plot
                    dpg.set_value(f'pred_series_{p}', [px_plot[-min_len:], py[-min_len:]])
            except Exception as e:
                print(f"Error updating prediction series: {e}")

            dpg.fit_axis_data('pred_x_axis')
            dpg.fit_axis_data('pred_y_axis')

        time.sleep(0.01)

def create_red_button_theme():
    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (200, 0, 0), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 50, 50), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (150, 0, 0), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255), category=dpg.mvThemeCat_Core)
    return theme_id

def exit_callback(sender, app_data, user_data):
    stop_event = user_data["stop_event"]
    stop_event.set()
    dpg.destroy_context()
    sys.exit(0)

def reset_callback(sender, app_data, user_data):
    global data_x, data_y, n_channels, pred_x, pred_y, num_classes, n_samples_prob
    global sample_counter, pred_counter
    pred_x.clear()

    for p in range(len(pred_y)):
        pred_y[p].clear()
    # Reset the EMG data
    data_x.clear()
    data_y = [deque(maxlen=n_samples_prob) for _ in range(n_channels)]

    # Reset sample counters
    sample_counter = 0
    pred_counter = 0

    # Reset prediction probability lines
    for p in range(num_classes):
        dpg.set_value(f'pred_series_{p}', [[], []])

    # Reset All Channels plot lines
    for ch in range(n_channels):
        dpg.set_value(f'series_tag_{ch}', [[], []])

def resize_main_window():
    x, y = dpg.get_item_rect_size(main_window)
    # Reserve space for controls, adjust as needed
    controls_height = 60
    available_height = y - controls_height
    emg_height = int(available_height * 2 / 3)
    pred_height = available_height - emg_height

    dpg.set_item_width(plot_widget, x-20)
    dpg.set_item_height(plot_widget, emg_height)
    dpg.set_item_width(pred_plot_widget, x-20)
    dpg.set_item_height(pred_plot_widget, pred_height)

def main():
    global data_x, data_y, pred_x, pred_y, n_samples_prob, n_channels, num_classes

    config_folder = 'config'

    # Load configuration
    with open(os.path.join(config_folder, 'emg_signal_processing.yaml')) as f:
        emg_proc_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open(os.path.join(config_folder, 'streaming_gui.yaml')) as f:
        gui_cfg = yaml.load(f, Loader=yaml.FullLoader)

    # params setup
    num_classes = 4
    n_samples_raw = gui_cfg['raw_signal_length'] * emg_proc_cfg['fsample_emg']
    n_samples_prob = gui_cfg['pred_probs_num']
    n_channels = emg_proc_cfg['num_channels_emg']

    data_x = deque(maxlen=n_samples_raw)
    data_y = [deque(maxlen=n_samples_raw) for _ in range(n_channels)]
    pred_x = deque(maxlen=n_samples_prob)
    pred_y = [deque(maxlen=n_samples_prob) for _ in range(num_classes)]

    stop_event = threading.Event()
    server = threading.Thread(target=server_thread, args=(
        emg_proc_cfg['stream']['receiver']['host'],
        emg_proc_cfg['stream']['receiver']['port'],
        stop_event
    ))
    server.start()

    dpg.create_context()
    global main_window, plot_widget, pred_plot_widget

    with dpg.window() as main_window:
        with dpg.group():
            # Controls (buttons, text, etc.)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Exit",
                    callback=exit_callback,
                    user_data={"stop_event": stop_event},
                    width=100,
                    height=40,
                    tag="exit_button"
                )
                dpg.bind_item_theme("exit_button", create_red_button_theme())
                dpg.add_spacer(width=5)
                dpg.add_button(
                    label="Reset",
                    callback=reset_callback,
                    width=100,
                    height=40,
                    tag="reset_button"
                )
            dpg.add_spacer(height=5)

            # EMG plot (2/3 of 900px = 600px)
            with dpg.plot(label='All Channels', height=500, width=950) as plot_widget:
                dpg.add_plot_axis(dpg.mvXAxis, label='Samples', tag='x_axis')
                dpg.add_plot_axis(dpg.mvYAxis, label='Channels', tag='y_axis')
                for ch in range(n_channels):
                    dpg.add_line_series(
                        x=[], y=[],
                        label=f'Channel {ch}', parent='y_axis',
                        tag=f'series_tag_{ch}'
                    )

            # Prediction probability plot (1/3 of 900px = 300px)
            with dpg.plot(label='Prediction Probabilities', height=300, width=950) as pred_plot_widget:
                dpg.add_plot_axis(dpg.mvXAxis, label='Samples', tag='pred_x_axis')
                dpg.add_plot_axis(dpg.mvYAxis, label='Probability', tag='pred_y_axis')
                dpg.set_axis_limits('pred_y_axis', -0.05, 1.05)
                dpg.add_plot_legend(parent=pred_plot_widget, location=dpg.mvPlot_Location_SouthWest)
                for p in range(num_classes):
                    dpg.add_line_series(
                        x=[], y=[],
                        label=f'Class {p}', parent='pred_y_axis',
                        tag=f'pred_series_{p}'
                    )

    with dpg.item_handler_registry() as registry:
        dpg.add_item_resize_handler(callback=resize_main_window)
    dpg.bind_item_handler_registry(main_window, registry)

    dpg.set_primary_window(main_window, True)
    dpg.create_viewport(title='Real-time Data Plot', width=1000, height=900)  # <-- increased height
    dpg.setup_dearpygui()
    dpg.show_viewport()

    update_thread = threading.Thread(target=update_data, args=(stop_event,))
    update_thread.start()

    dpg.start_dearpygui()

    stop_event.set()
    server.join()
    update_thread.join()

if __name__ == "__main__":
    main()