import dearpygui.dearpygui as dpg
import numpy as np
import time
import threading
import argparse

def min_max_norm(arr):
    arr = np.array(arr)
    min_val = arr.min()
    max_val = arr.max()
    if max_val - min_val == 0:
        return np.zeros_like(arr)
    return (arr - min_val) / (max_val - min_val)

def parse_args():
    parser = argparse.ArgumentParser(description="Simple multi-channel live plot using DearPyGui")
    parser.add_argument("--channels", type=int, default=32, help="Number of channels to plot")
    parser.add_argument("--nsamples", type=int, default=1000, help="Window length (samples)")
    parser.add_argument("--interval", type=float, default=0.01, help="Update sleep interval (s)")
    parser.add_argument("--width", type=int, default=850, help="Viewport width")
    parser.add_argument("--height", type=int, default=640, help="Viewport height")
    return parser.parse_args()


def main():
    args = parse_args()
    n_channels = args.channels
    nsamples = args.nsamples
    interval = args.interval

    # Initialize data: each channel is a list of nsamples
    data_x = [0.0] * nsamples
    data_y = [[0.0] * nsamples for _ in range(n_channels)]

    def update_data():
        t0 = time.time()
        while True:
            t = time.time() - t0
            data_x.append(t)
            # Simulate new random data for each channel
            new_vals = np.random.randn(n_channels)
            for ch in range(n_channels):
                data_y[ch].append(new_vals[ch])

            # Prepare and update each channel's line series
            for ch in range(n_channels):
                # Min-max normalize and offset by channel index
                normed = min_max_norm(data_y[ch][-nsamples:]) + ch
                dpg.set_value(f"series_tag_{ch}", [list(data_x[-nsamples:]), list(normed)])

            dpg.fit_axis_data("x_axis")
            dpg.fit_axis_data("y_axis")
            time.sleep(interval)

    dpg.create_context()
    with dpg.window(label="Multi-channel Plot", tag="win", width=800, height=600):
        with dpg.plot(label="All Channels", height=-1, width=-1):
            dpg.add_plot_axis(dpg.mvXAxis, label="x", tag="x_axis")
            dpg.add_plot_axis(dpg.mvYAxis, label="Channels", tag="y_axis")
            # Add a line series for each channel
            for ch in range(n_channels):
                dpg.add_line_series(
                    x=list(data_x),
                    y=list(data_y[ch]),
                    label=f"Channel {ch}",
                    parent="y_axis",
                    tag=f"series_tag_{ch}",
                )

    dpg.create_viewport(title="Multi-channel Live Plot", width=args.width, height=args.height)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    thread = threading.Thread(target=update_data, daemon=True)
    thread.start()
    try:
        dpg.start_dearpygui()
    finally:
        dpg.destroy_context()


if __name__ == "__main__":
    main()