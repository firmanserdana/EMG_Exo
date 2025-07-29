# ESP32 Glove Python Controller User Manual

## Overview

This Python script provides a simple command-line interface to control the ESP32 pneumatic glove system via WiFi. It allows you to send commands for gestures, pressure control, speed adjustment, and direct finger manipulation.

## Prerequisites

### 1. Hardware Setup
- ESP32 with pneumatic glove system running
- Computer with Python 3.6 or higher
- WiFi capability on your computer

### 2. Network Connection
1. Ensure the ESP32 is powered on and running the glove control firmware
2. Connect your computer to the ESP32's WiFi network:
   - **Network Name**: `ESP32_Glove`
   - **Password**: `12345678`

### 3. ESP32 Configuration
1. Open a web browser and navigate to `192.168.4.1`
2. Click on "WiFi Control" to set the ESP32 to WiFi control mode
3. Verify the ESP32 serial monitor shows "UDP server ready on port 4210"

## Installation

### Download the Script
Save the `simple_glove_controller.py` file to your computer.

### Run the Script
```bash
python simple_glove_controller.py
```

Or on some systems:
```bash
python3 simple_glove_controller.py
```

## Command Reference

### Basic Commands

| Command | Format | Description | Examples |
|---------|--------|-------------|----------|
| **g** | `g [0-8]` | Set gesture | `g 3` (2-finger pinch) |
| **p** | `p [flex] [ext]` | Set pressure (0-100) | `p 50 30` |
| **s** | `s [0-4]` | Set speed level | `s 2` |
| **f** | `f [states]` | Set finger states | `f 111100` |
| **m** | `m [0-3]` | Set control mode | `m 3` (WiFi mode) |
| **stop** | `stop` | Emergency stop | `stop` |
| **help** | `help` | Show help | `help` |
| **quit** | `quit` | Exit program | `quit` |

### Gesture Codes

| Code | Gesture | Description |
|------|---------|-------------|
| 0 | Relax | All fingers relaxed |
| 1 | All Flexion | All fingers bent inward |
| 2 | All Extension | All fingers extended outward |
| 3 | 2-Finger Pinch | Thumb and index finger pinch |
| 4 | 3-Finger Pinch | Thumb, index, and middle finger pinch |
| 5 | Thumb | Only thumb active |
| 6 | Index | Only index finger active |
| 7 | Middle | Only middle finger active |
| 8 | Peace Sign | Index and middle fingers extended |

### Pressure Control

- **Range**: 0-100 for both flexion and extension
- **Flexion**: Controls inward finger movement pressure
- **Extension**: Controls outward finger movement pressure
- **Example**: `p 60 40` sets flexion pressure to 60% and extension to 40%

### Speed Control

| Level | Description |
|-------|-------------|
| 0 | Stop/No movement |
| 1 | Slow speed |
| 2 | Medium-low speed |
| 3 | Medium-high speed |
| 4 | Maximum speed |

### Finger States (Advanced)

Direct finger control using 6-digit codes:
- **Positions**: `[Thumb][Index][Middle][Ring][Pinky][Abduction]`
- **Values**: 
  - `0` = Relax
  - `1` = Flexion (bend inward)
  - `2` = Extension (extend outward)
  - `3` = Pinch

**Examples**:
- `000000` = All fingers relaxed
- `111110` = All fingers flexed, no abduction
- `123400` = Thumb flex, Index extend, Middle pinch, others relax
- `222220` = All fingers extended, no abduction

### Control Modes

| Mode | Description |
|------|-------------|
| 0 | HTTP Mode - Control via web interface |
| 1 | Serial Mode - Control via serial commands |
| 2 | Data Glove Mode - Control via sensor glove |
| 3 | WiFi Mode - Control via this Python script |

## Usage Examples

### Quick Start
```
> m 3          # Set to WiFi mode
> g 0          # Set to relax position
> p 50 40      # Set moderate pressure
> s 2          # Set medium speed
> g 3          # Perform 2-finger pinch
> stop         # Emergency stop
```

### Custom Finger Patterns
```
> f 100000     # Only thumb flexed
> f 110000     # Thumb and index flexed
> f 123000     # Thumb flex, index extend, middle pinch
> f 222220     # All fingers extended
```

### Pressure and Speed Adjustment
```
> p 80 60      # High pressure for strong grip
> s 4          # Maximum speed
> g 1          # All fingers flex with high pressure/speed
> p 20 20      # Reduce to low pressure
> s 1          # Reduce to slow speed
```

## Program Modes

### 1. Interactive Mode
- Enter commands one by one
- Real-time control
- Best for manual testing and operation

### 2. Quick Test Mode
- Runs a predefined sequence of commands
- Tests all basic functions
- Good for verifying system operation

## Troubleshooting

### Connection Issues

**Problem**: "Connection failed" message
**Solutions**:
1. Verify you're connected to `ESP32_Glove` WiFi
2. Check ESP32 is powered and running
3. Ensure ESP32 is set to WiFi Control mode via web interface
4. Try restarting the ESP32

**Problem**: "No response received"
**Solutions**:
1. Check ESP32 serial monitor for error messages
2. Verify UDP port 4210 is not blocked by firewall
3. Try sending commands more slowly
4. Restart both Python script and ESP32

### Command Issues

**Problem**: Commands not working
**Solutions**:
1. Ensure ESP32 is in WiFi mode (`m 3`)
2. Check command format (see examples above)
3. Verify parameter ranges (gestures 0-8, pressure 0-100, etc.)
4. Use `stop` command to reset system

**Problem**: Hardware not responding
**Solutions**:
1. Check if I2C devices (DAC, sensors) are connected
2. ESP32 will show "DAC not available" if hardware missing
3. Basic finger control should work even without I2C devices
4. Check ESP32 serial output for hardware status

### Performance Issues

**Problem**: Slow response
**Solutions**:
1. Reduce command frequency
2. Use direct finger states (`f` command) for faster updates
3. Check WiFi signal strength
4. Ensure ESP32 has adequate power supply

## Safety Notes

1. **Emergency Stop**: Always use `stop` command if something goes wrong
2. **Pressure Limits**: Don't exceed safe pressure levels for your application
3. **Hardware Check**: Verify all connections before operation
4. **Power Supply**: Ensure stable power to ESP32 and pneumatic system

## Programming Interface

### For Custom Applications

```python
from simple_glove_controller import SimpleGloveController

# Initialize controller
glove = SimpleGloveController()

# Set to WiFi mode
glove.set_mode(3)

# Send commands
glove.set_pressure(50, 30)
glove.set_speed(2)
glove.set_gesture(3)

# Real-time control loop
import time
finger_patterns = ["111100", "000000", "222200", "000000"]
for pattern in finger_patterns:
    glove.set_finger_states(pattern)
    time.sleep(1)

# Cleanup
glove.stop_all()
glove.close()
```

## Advanced Usage

### Real-time Control
For applications requiring high-frequency updates (like mimicking sensor input):

```python
import time

glove = SimpleGloveController()
glove.set_mode(3)

try:
    while True:
        # Get sensor data or user input
        finger_data = get_sensor_data()  # Your function
        
        # Convert to finger states
        states = convert_to_states(finger_data)  # Your function
        
        # Send to glove
        glove.set_finger_states(states)
        
        # Update at 20Hz
        time.sleep(0.05)
        
except KeyboardInterrupt:
    glove.stop_all()
    glove.close()
```

### Batch Commands
```python
commands = [
    ("m:3", "Set WiFi mode"),
    ("p:60:40", "Set pressure"),
    ("s:3", "Set speed"),
    ("g:3", "Perform pinch")
]

for cmd, desc in commands:
    print(f"Executing: {desc}")
    glove.send_command(cmd)
    time.sleep(0.5)
```

## Support

For technical issues:
1. Check ESP32 serial monitor output
2. Verify network connectivity
3. Test with basic commands first
4. Ensure all prerequisites are met

For hardware-related issues, refer to the ESP32 glove system documentation.
