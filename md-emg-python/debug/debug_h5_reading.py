import numpy as np
import h5py
import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser(description="Quick HDF5 reader for EMG datasets")
    parser.add_argument("--path", required=True, help="Path to .h5 file")
    parser.add_argument("--vr-key", default="timestamp_vr_events", help="H5 dataset key for VR timestamps")
    parser.add_argument("--emg-ts-key", default="timestamp_HA-2015.08.05", help="H5 key for EMG timestamps")
    parser.add_argument("--emg-data-key", default="HA-2015.08.05", help="H5 key for EMG data")
    return parser.parse_args()


def main():
    args = parse_args()
    h5_file_path = args.path
    if not os.path.isfile(h5_file_path):
        raise FileNotFoundError(f"File not found: {h5_file_path}")

    with h5py.File(h5_file_path, 'r') as file:
        # Read the variables from the file
        time_vr = file[args.vr_key][:] if args.vr_key in file else None
        time_emg = file[args.emg_ts_key][:] if args.emg_ts_key in file else None
        data_emg = file[args.emg_data_key][:] if args.emg_data_key in file else None

    print("VR Timestamps:", None if time_vr is None else time_vr.shape)
    print("EMG Timestamps:", None if time_emg is None else time_emg.shape)
    print("EMG Data:", None if data_emg is None else data_emg.shape)


if __name__ == "__main__":
    main()