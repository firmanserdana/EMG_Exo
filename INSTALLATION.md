# Installation and Setup Guide

## System Requirements

- Python 3.8 or higher
- pip package manager
- Windows, macOS, or Linux operating system

## Installation Steps

1. Clone the repository:
```bash
git clone https://github.com/yourusername/EMG_Exo.git
cd EMG_Exo
```

2. Create a virtual environment (optional but recommended):
```bash
# Using venv
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Demo

To run the simple demo without hardware:

```bash
python simple_demo.py
```

This demo will:
- Simulate EMG signals for various hand gestures
- Visualize the raw EMG signals in real-time
- Train a gesture recognition model
- Classify gestures from the signals

### Command-line Options

The demo supports the following command-line arguments:

```bash
python simple_demo.py --channels 8 --disable-training
```

- `--channels`: Number of EMG channels to simulate (default: 8)
- `--disable-training`: Disable automatic model training

## Hardware Setup (Optional)

### EMG Hardware Requirements

If you have a Sessantaquatro EMG board:

1. Connect the board to your computer via USB
2. Identify the COM port assigned to the board:
   - Windows: Check Device Manager under "Ports (COM & LPT)"
   - macOS: Run `ls /dev/tty.*` in Terminal
   - Linux: Run `ls /dev/ttyUSB*` or `ls /dev/ttyACM*` in Terminal

3. Run the application with the correct port:
```bash
python main.py --port COM3  # Replace COM3 with your port
```

### Electrode Placement

For optimal results with real hardware:

1. Clean the skin with alcohol wipes
2. Place electrodes on the following muscles:
   - Channel 1-2: Flexor Digitorum Superficialis (inner forearm)
   - Channel 3-4: Extensor Digitorum (outer forearm)
   - Channel 5-6: Thenar/Hypothenar muscles (palm)
   - Channel 7-8: Flexor/Extensor Carpi (wrist)

3. Place reference electrode on a bony area (e.g., elbow or wrist)

## Troubleshooting

### Common Issues

1. **ImportError**: Ensure all dependencies are installed correctly.
   ```bash
   pip install -r requirements.txt
   ```

2. **Serial Port Access Denied**:
   - Windows: Run as administrator
   - macOS/Linux: Use `chmod` to set permissions
     ```bash
     sudo chmod 666 /dev/ttyUSB0  # Replace with your port
     ```

3. **No EMG Signal**:
   - Check electrode connections
   - Verify port configuration
   - Ensure board is powered on

4. **Visualization Issues**:
   - Update matplotlib: `pip install matplotlib --upgrade`
   - Try a different backend: `export MPLBACKEND="TkAgg"`

### Getting Help

If you encounter issues not covered in this guide:

1. Check the logs in the `logs` directory
2. Refer to the API documentation
3. Create an issue on GitHub with:
   - Detailed description of the problem
   - Steps to reproduce
   - Error messages and logs
   - Your system information
