# Button Control Mode

This document describes the new Button Control Mode feature added to the ESP32 Exoskeleton Glove control system.

## Overview

Button Control Mode allows you to control the exoskeleton glove using a simple push button. Each button press toggles between a selected gesture and the relax state, making it easy to operate the glove with minimal input.

## Hardware Setup

### Pin Configuration

**Version 2 (Bilateral_control_WIFI_V3):**
- Button Pin: GPIO 33
- Configure the button with a pull-up resistor or use the internal pull-up (active LOW)

**Version 1 (Bilateral_control_WIFI):**
- Button Pin: GPIO 32
- Configure the button with a pull-up resistor or use the internal pull-up (active LOW)

### Wiring

Connect a momentary push button between the button pin and GND:
```
Button Pin (33 or 32) ----[Button]---- GND
```

The internal pull-up resistor is enabled, so the pin reads HIGH when the button is not pressed and LOW when pressed.

## Software Configuration

### Activating Button Control Mode

#### Method 1: Via Web Interface

1. Connect to the ESP32's WiFi network:
   - **SSID:** ESP32_Glove (v2) or TP-Link_8541 (v1)
   - **Password:** 12345678 (v2) or 90872709 (v1)

2. Open a web browser and navigate to:
   - `http://192.168.4.1`

3. In the **Control Mode** section, click the **"Force BUTTON Mode"** button (v2) or **"Button Control"** button (v1)

4. The Button Mode Configuration panel will appear, allowing you to select which gesture to activate

#### Method 2: Via HTTP API (v1 only)

Send a GET request to set the mode:
```
GET http://192.168.4.1/setMode?mode=4
```

### Selecting the Active Gesture

When Button Control Mode is active, you can select which gesture will be triggered by the button press:

#### Via Web Interface:
1. In the Button Mode Configuration section, use the dropdown menu to select a gesture:
   - **HandClose** (Gesture 1) - All fingers flex
   - **HandOpen** (Gesture 2) - All fingers extend
   - **HookGrasp** (Gesture 3) - Hook/pinch grasp
   - **LateralGrasp** (Gesture 4) - Lateral/key grasp
   - **ThumbFlexion** (Gesture 5) - Thumb movement
   - **IndexFlexion** (Gesture 6) - Index finger movement
   - **MRPFlexion** (Gesture 7) - Middle, Ring, Pinky movement
   - **IndexPointing** (Gesture 8) - Index pointing gesture

2. The selection is saved immediately

#### Via HTTP API (v2):
```
GET http://192.168.4.1/button-gesture?value=1
```

#### Via HTTP API (v1):
```
GET http://192.168.4.1/setButtonGesture?gesture=1
```

Where the value is the gesture number (1-8).

## Usage

### Operating the Button

1. **Activate Button Control Mode** using one of the methods above
2. **Select your desired gesture** from the dropdown menu
3. **Press the button once** - The selected gesture will activate
4. **Press the button again** - The glove will return to the relax state (Gesture 0)
5. Repeat steps 3-4 to toggle between the gesture and relax state

### Button Behavior

- **Debouncing:** The button has a 200ms debounce delay to prevent accidental multiple triggers
- **Toggle Mode:** Each press alternates between the active gesture and relax state
- **State Indication:** Monitor the Serial output for button press feedback:
  - `[BUTTON] Gesture ON - Gesture X` - Gesture activated
  - `[BUTTON] Gesture OFF - Relax state` - Returned to relax

## Features

### Button Control Advantages

1. **Simple Operation:** Single button control is easy to use and understand
2. **Safety:** Always returns to relax state between activations
3. **Customizable:** Select from 8 different gestures
4. **Real-time:** Instant response with minimal latency
5. **Independent:** Works alongside other control modes

### Control Mode Switching

Button Control Mode can coexist with other control modes:
- **Web Control Mode:** Manual control via web interface
- **TCP Control Mode:** Automated control from computer via TCP/IP
- **WiFi Control Mode (v1):** UDP-based control
- **Data Glove Mode (v1):** Sensor-based control

Switch between modes at any time using the web interface or API.

## Technical Details

### Implementation

The button control is implemented with:
- **Interrupt-free polling:** Button state checked in main loop
- **Software debouncing:** 200ms delay between accepted presses
- **State machine:** Tracks whether gesture is active or inactive
- **Non-blocking:** Does not interfere with other operations

### Default Settings

- **Default Gesture:** Gesture 1 (HandClose/All Flex)
- **Initial State:** Relax (Gesture 0)
- **Debounce Time:** 200ms

### Pin Assignment Rationale

- **V2 uses GPIO 33:** Available GPIO with INPUT_PULLUP capability
- **V1 uses GPIO 32:** GPIO 33 is used for emergency switch in v1

## Troubleshooting

### Button Not Responding

1. **Check wiring:** Ensure button is connected between the button pin and GND
2. **Verify mode:** Confirm Button Control Mode is active in web interface
3. **Check Serial output:** Look for "[BUTTON]" messages when pressing
4. **Test button:** Use multimeter to verify button makes connection

### Unexpected Behavior

1. **Multiple triggers:** If gestures trigger multiple times per press:
   - This may indicate contact bouncing
   - Increase `button_debounce_delay` if needed (default 200ms)

2. **No gesture change:** 
   - Verify a valid gesture (1-8) is selected
   - Check Serial monitor for error messages

3. **Mode switching:**
   - Ensure FORCE_BUTTON_MODE is active (not AUTO mode)
   - TCP connection can override AUTO mode

## Serial Monitor Output

When using Button Control Mode, you'll see these messages:

```
[HTTP] Mode set to Button Control
[HTTP] Button will toggle gesture 1
[BUTTON] Gesture ON - Gesture 1
[BUTTON] Gesture OFF - Relax state
```

## Example Use Cases

### 1. Basic Hand Opening/Closing
- Select Gesture 1 (HandClose)
- Press button to close hand
- Press button to open hand (relax)

### 2. Grasp Pattern Switching
- Select Gesture 3 (HookGrasp)
- Press button to form hook grasp
- Press button to release

### 3. Single Finger Control
- Select Gesture 6 (IndexFlexion)
- Press button to move index finger
- Press button to return to relax

## API Reference

### V2 Endpoints

#### Status
```
GET /status
Response: JSON with current mode, gesture, pressure, speed, etc.
```

#### Set Control Mode
```
GET /mode?value=BUTTON
```

#### Set Button Gesture
```
GET /button-gesture?value=1
```

### V1 Endpoints

#### Set Control Mode
```
GET /setMode?mode=4
```

#### Set Button Gesture
```
GET /setButtonGesture?gesture=1
```

## Integration Examples

### Python Example (V2)
```python
import requests

# Set to Button Control Mode
requests.get('http://192.168.4.1/mode?value=BUTTON')

# Select HandClose gesture
requests.get('http://192.168.4.1/button-gesture?value=1')

# Check status
status = requests.get('http://192.168.4.1/status').json()
print(f"Current mode: {status['mode']}")
print(f"Current gesture: {status['gesture']}")
```

### Python Example (V1)
```python
import requests

# Set to Button Control Mode
requests.get('http://192.168.4.1/setMode?mode=4')

# Select All Flex gesture
requests.get('http://192.168.4.1/setButtonGesture?gesture=1')
```

## Safety Considerations

1. **Emergency Stop:** Emergency stop button (GPIO 33 in v1, GPIO 15 in v2) takes priority over button control
2. **Initial State:** System always starts in relax state when entering Button Control Mode
3. **Mode Switching:** Can switch to other modes at any time for safety

## Future Enhancements

Potential improvements for future versions:
- Multiple button support for different gestures
- Long-press vs short-press gestures
- Button combination support
- Configurable debounce timing via web interface
- Button state LED indicator

## Support

For issues or questions:
1. Check Serial monitor output for diagnostic messages
2. Verify hardware connections
3. Test with web interface first
4. Review this documentation

## Version History

- **v1.0 (2025-01-15):** Initial implementation of Button Control Mode
  - Added to both v1 and v2 firmware
  - Web interface integration
  - Configurable gesture selection
  - 200ms debounce implementation
