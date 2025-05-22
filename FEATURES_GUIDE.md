# EMG Exo Advanced Features Guide

This guide explains the advanced features that have been added to the EMG Exo project, including data recording/export capabilities and improved visualization options.

## Table of Contents
- [Data Recording and Export](#data-recording-and-export)
- [Enhanced Visualization](#enhanced-visualization)
- [Using the New Features](#using-the-new-features)
- [Command-Line Options](#command-line-options)
- [File Formats](#file-formats)

## Data Recording and Export

The EMG Exo system now includes a comprehensive data recording system that allows you to:

- Record raw EMG signals during demo sessions
- Save extracted features alongside raw data
- Track gesture labels and timestamps
- Export data in multiple formats for analysis

### Features

- **Session Management**: Each recording creates a new session folder with timestamp
- **Multiple Data Formats**: 
  - Raw data saved as compressed NumPy (.npz) files
  - Features extracted as CSV
  - Gesture labels with timestamps
  - Session metadata in JSON format
- **Export Options**:
  - MATLAB (.mat) export for scientific analysis
  - CSV exports for spreadsheet analysis
- **Automatic Directory Structure**: Organized directory structure for easy data management

## Enhanced Visualization

The new visualization system provides more detailed views of EMG data:

### Features

- **Multiple View Modes**:
  - Time-domain signal display
  - RMS envelope visualization
  - Spectrogram visualization for frequency analysis
- **Channel Control**:
  - Selectively show/hide channels
  - Focus on channels of interest
- **Interactive Elements**:
  - Button controls for view modes
  - Real-time gesture display
  - Status messages
- **Performance Optimizations**:
  - Efficient rendering for smoother display
  - Memory-optimized data buffers

## Using the New Features

### Data Recording

To record data during a demo session:

1. Run simple_demo.py with recording enabled (default)
2. Click the "Start Recording" button when ready
3. Perform gestures that you want to record
4. Click the same button (now labeled "Stop Recording") when finished
5. Use "Export Data" to convert to MATLAB format if needed

Recording creates a directory structure:
```
emg_recordings/
  ├── session_YYYYMMDD_HHMMSS/
  │   ├── session_info.json     # Session metadata
  │   ├── raw_data.npz          # Raw EMG signals
  │   ├── features.csv          # Extracted features
  │   ├── gestures.csv          # Gesture labels with timestamps
  │   └── emg_data.mat          # MATLAB export (if selected)
```

### Enhanced Visualization

To use the enhanced visualization:

1. Run simple_demo.py with the `--enhanced-viz` flag
2. The visualization window offers multiple display options:
   - Use the "Time" button for standard signal display
   - Use the "Envelope" button for RMS envelope display
3. Check/uncheck boxes to show or hide individual channels
4. Status messages appear at the bottom of the window

## Command-Line Options

The simple_demo.py script now accepts the following command-line arguments:

```
python simple_demo.py [options]

Options:
  --channels N         Number of EMG channels to simulate (default: 8)
  --no-train           Disable automatic model training
  --no-record          Disable data recording
  --enhanced-viz       Use enhanced visualization
  -h, --help           Show help message
```

Examples:
```
# Run with default settings
python simple_demo.py

# Run with enhanced visualization and 4 channels
python simple_demo.py --channels 4 --enhanced-viz

# Run without data recording or auto-training
python simple_demo.py --no-train --no-record
```

## File Formats

### Raw Data (raw_data.npz)

The raw data is stored in NumPy's compressed format:
- `emg_data`: Array of EMG signals, shape varies based on recording
- `timestamps`: Array of timestamps corresponding to each data sample

### Features (features.csv)

CSV file with columns:
- `timestamp`: Time in seconds from start of recording
- Feature columns for each channel (e.g., `rms_1`, `rms_2`, ...)

### Gestures (gestures.csv)

CSV file with columns:
- `timestamp`: Time in seconds from start of recording
- `gesture`: Detected gesture label

### MATLAB Export (emg_data.mat)

MATLAB file containing:
- `raw_data`: Matrix of EMG signals
- `timestamps`: Vector of timestamps
- `sampling_rate`: Sampling frequency in Hz
- `gestures`: Cell array of gesture labels
- `session_info`: Session metadata

## Troubleshooting

If you encounter issues with data recording:

1. Check that you have write permissions to the `emg_recordings` directory
2. Ensure you have sufficient disk space
3. Check the logs for any error messages

If visualization performance is slow:

1. Reduce the number of channels displayed
2. Switch to standard visualization mode
3. Ensure you have the latest matplotlib version installed
