import numpy
import h5py

# Replace 'path/to/your_file.h5' with the actual file path.
h5_file_path = 'path/to/your_file.h5'

with h5py.File(h5_file_path, 'r') as file:
    # Read the variables from the file
    time_vr = file['timestamp_vr_events'][:]
    time_emg = file['timestamp_HA-2015.08.05'][:]
    data_emg = file['HA-2015.08.05'][:]

print("VR Timestamps:", time_vr)
print("EMG Timestamps:", time_emg)
print("EMG Data:", data_emg)