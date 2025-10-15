# Button Control Mode

This document describes the new Button Control Mode feature added to the ESP32 Exoskeleton Glove control system.

## Overview

Button Control Mode now runs as a two-board system: a lightweight "button bridge" board captures the physical button (or any trigger sensor) and forwards high-level commands to the ESP32 glove controller over WiFi or a dedicated UART link. The ESP32 responds to these remote commands by toggling between the selected gesture and the relax state, keeping the one-press workflow while removing the need to wire a button directly to the glove controller.

## Hardware Setup

### Components

- **Bridge board:** Any microcontroller that can read your button and speak UART or WiFi (ESP8266/ESP32, STM32, Arduino Nano + ESP-01, etc.).
- **ESP32 glove controller:** Runs `Bilateral_control_WIFI_V3.ino` and listens for remote button commands.
- **Trigger device:** Push button, foot switch, proximity sensor, or other digital/analog input handled by the bridge board.

### Communication Options

#### Option 1 – UART bridge (default)

- Bridge TX → ESP32 RX2 (GPIO 35)
- Bridge RX (optional for ACK) ← ESP32 TX2 (GPIO 4)
- Common ground between both boards
- Serial parameters: `115200 baud`, `8-N-1`
- Send newline-terminated ASCII commands such as `BTN:PRESS` or `BTN:ON`

> **Tip:** GPIO35 is input-only, so if your bridge does not need acknowledgements you can omit the RX connection entirely.

#### Option 2 – WiFi bridge (UDP)

- Connect the bridge board to the same WiFi network as the ESP32 (or join the ESP32 AP `ESP32_Glove`).
- Send UDP packets to the ESP32 IP on **port 4211** containing the same ASCII commands (`BTN:PRESS`, `BTN:OFF`, etc.).
- No handshake is required; each packet is processed as soon as it arrives.

Both transports can be enabled simultaneously. The firmware marks each command with its source (`SERIAL` or `UDP`) for diagnostics and exposes the latest bridge activity via the web dashboard.

## Software Configuration

### Firmware Settings

The bridge parameters live near the top of `Bilateral_control_WIFI_V3.ino`:

```cpp
const bool button_bridge_serial_enabled = true;
const int button_serial_rx_pin = 35;
const int button_serial_tx_pin = 4;
const bool button_bridge_wifi_enabled = true;
const unsigned int button_udp_port = 4211;
```

Tweak these values if you need to move the UART pins, disable one of the transports, or listen on a different UDP port. Any changes take effect after reflashing the ESP32.

The companion bridge firmware lives in `ESP32_Exo/v2/ButtonBridge/ButtonBridge.ino`. It reads the physical button, applies debounce logic, and forwards ASCII commands (`BTN:PRESS`, `BTN:ON`, `BTN:OFF`) over WiFi (UDP port 4211) and/or a UART link to the glove controller.

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

### Selecting Button Cycle Gestures

Button Control Mode now supports a configurable two- or three-press cycle. You can configure the primary (first press) and secondary (second press) gestures, then choose whether the cycle returns to rest after two presses (Primary → Rest) or after three presses (Primary → Secondary → Rest).

#### Via Web Interface:
1. In the Button Mode Configuration section, adjust the following dropdowns:
   - **Primary Gesture** (press 1)
   - **Secondary Gesture** (press 2 when three-press mode is enabled)
   - **Cycle Mode** – choose *2-press* or *3-press*
2. The controls update immediately; the secondary dropdown is disabled in 2-press mode.
3. Use the **Reset** button to return to the relax state manually and restart the cycle.

Available gestures:
- **HandClose** (Gesture 1) – All fingers flex
- **HandOpen** (Gesture 2) – All fingers extend
- **HookGrasp** (Gesture 3) – Hook/pinch grasp
- **LateralGrasp** (Gesture 4) – Lateral/key grasp
- **ThumbFlexion** (Gesture 5) – Thumb movement
- **IndexFlexion** (Gesture 6) – Index finger movement
- **MRPFlexion** (Gesture 7) – Middle, Ring, Pinky movement
- **IndexPointing** (Gesture 8) – Index pointing gesture

#### Via HTTP API (v2):
```
GET http://192.168.4.1/button-gesture?value=1          # Set primary gesture
GET http://192.168.4.1/button-secondary-gesture?value=2 # Set secondary gesture
GET http://192.168.4.1/button-cycle-mode?value=3        # Use three-press cycle (2 for two-press)
GET http://192.168.4.1/button-cycle-reset               # Force cycle back to rest
```

Values for `value` must be integers between 1 and 8 (inclusive) for the gesture endpoints, and either `2` or `3` for the cycle mode.

#### Via HTTP API (v1):
```
GET http://192.168.4.1/setButtonGesture?gesture=1
```

*Note:* v1 firmware still exposes the single-gesture selector only.

## Usage

### Operating the Button

1. **Activate Button Control Mode** using one of the methods above.
2. **Select your desired primary/secondary gestures and cycle length** from the configuration dropdowns.
3. **Trigger the bridge board** – send `BTN:PRESS` (toggle), `BTN:ON`, or `BTN:OFF` from the bridge firmware whenever the physical button changes state.
4. In three-press mode the cycle advances *Primary → Secondary → Rest*; in two-press mode it toggles *Primary ↔ Rest*.
5. The ESP32 mirrors the command immediately and enforces the configured cycle. Use `BTN:RESET` (or the web reset button) to jump back to relax at any time.
6. Repeat as needed; debounce logic (200 ms) still applies on the ESP32 side so spurious duplicates are ignored.

### Button Behavior

- **Debouncing:** The ESP32 still enforces a 200 ms debounce window, so send a single command per physical event.
- **Press Cycle:** Configure 2-press (Primary ↔ Rest) or 3-press (Primary → Secondary → Rest) cycles.
- **Toggle Mode:** `BTN:PRESS` advances the cycle; `BTN:ON` forces the primary state; `BTN:OFF` returns to rest.
- **State Indication:** Monitor the main serial console for tagged messages, e.g.:
   - `[BUTTON][SERIAL] Gesture ON - Gesture 3`
   - `[BUTTON][UDP] Gesture OFF - Relax state`
- **Bridge telemetry:** The web dashboard now shows whether the most recent command arrived via Serial or WiFi and how long ago it was seen.

## Features

### Button Control Advantages

1. **Simple Operation:** Single button control is easy to use and understand
2. **Safety:** Always returns to relax state between activations
3. **Customizable:** Select from 8 gestures with configurable 2- or 3-press cycles
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

The remote button bridge is implemented with:
- **Dual-transport parsing:** Both Serial2 and UDP ports are polled without blocking the main control loop.
- **ASCII protocol:** Commands are plain text (`BTN:PRESS`, `BTN:ON`, `BTN:OFF`, `BTN:PRIMARY:<id>`, `BTN:SECONDARY:<id>`, `BTN:CYCLE:<length>`, `BTN:RESET`), terminated by `\n` or `\r\n`.
- **Software debouncing:** 200 ms guard window on the ESP32 ensures duplicate packets or switch bounce do not re-trigger the gesture.
- **State machine:** Tracks whether the gesture is currently latched (`button_gesture_active`) and enforces relax/gesture transitions.
- **Telemetry hooks:** Last activity timestamps and transport source are exposed via `/status` for diagnostics and the web UI.

### Default Settings

- **Default Primary Gesture:** Gesture 1 (HandClose/All Flex)
- **Default Secondary Gesture:** Gesture 2 (HandOpen)
- **Default Cycle:** Two-press (Primary ↔ Rest)
- **Initial State:** Relax (Gesture 0)
- **Debounce Time:** 200ms
- **Serial Port:** RX2 = GPIO 35, TX2 = GPIO 4, 115200 baud (disable via `button_bridge_serial_enabled`)
- **UDP Port:** 4211 (disable via `button_bridge_wifi_enabled`)

### Pin Assignment Rationale

- **Serial RX2 (GPIO35):** Input-only pin dedicated to receiving commands from the bridge.
- **Serial TX2 (GPIO4):** Optional acknowledgement channel if the bridge expects responses.
- **Legacy GPIO 33/32:** Previously wired button inputs; keep them free for other peripherals now that the bridge handles button events.

## Troubleshooting

### Button Not Responding

1. **Check bridge wiring:** Confirm the bridge board sees the physical button and, for UART, that TX → RX2 (GPIO35) is connected with common ground.
2. **Verify mode:** Confirm Button Control Mode is active in the web interface.
3. **Check telemetry:** On the dashboard, the Button Bridge indicator should turn green shortly after activity.
4. **Monitor serial logs:** Look for `[BUTTON][SERIAL]` or `[BUTTON][UDP]` messages when the bridge fires.
5. **Manual packet test:** From a computer, send `BTN:PRESS` via UDP to port 4211 or inject the same string into Serial2 to isolate the bridge firmware.

### Unexpected Behavior

1. **Multiple triggers:** If gestures trigger multiple times per press:
   - The bridge may be emitting repeated commands – ensure it sends only one packet per physical press.
   - Increase `button_debounce_delay` if you need additional filtering (default 200 ms).

2. **No gesture change:** 
   - Verify a valid gesture (1-8) is selected.
   - Check Serial monitor for parsing errors (e.g. malformed command strings).

3. **Mode switching:**
   - Ensure FORCE_BUTTON_MODE is active (not AUTO mode).
   - A live TCP client will still override AUTO mode.

## Serial Monitor Output

When using Button Control Mode, you'll see these messages:

```
[HTTP] Mode set to Button Control
[HTTP] Button will toggle gesture 1
[BUTTON][SERIAL] Gesture ON - Gesture 1
[BUTTON][SERIAL] Gesture OFF - Relax state
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

### Remote Command Protocol (Bridge → ESP32)

Send ASCII strings terminated by `\n` via Serial2 or UDP (port 4211).

| Command              | Effect                                                   |
|----------------------|----------------------------------------------------------|
| `BTN:PRESS` / `PRESS`| Advance the press cycle (Primary ↔ Rest or Primary → Secondary → Rest) |
| `BTN:ON`             | Force the cycle into the primary gesture state (idempotent)             |
| `BTN:OFF`            | Force relax (gesture 0)                                                  |
| `BTN:GESTURE:X`      | Set the primary gesture to `X` (1-8)                                     |
| `BTN:PRIMARY:X`      | Alias for `BTN:GESTURE:X`                                                |
| `BTN:SECONDARY:X`    | Set the secondary gesture (used in three-press mode)                     |
| `BTN:CYCLE:Y`        | Set cycle length to `2` (two-press) or `3` (three-press)                 |
| `BTN:RESET`          | Immediately reset cycle to relax (state 0)                               |
| `BTN:RELEASE`        | Alias for `BTN:OFF`                                                      |

Unknown commands are ignored and reported in the serial log.

### V2 Endpoints

#### Status
```
GET /status
Response: JSON with current mode, gesture, pressure, speed, etc.
Includes button-specific telemetry:
{
   "button_config": {
      "primary": 1,
      "secondary": 2,
      "use_three_press": true,
      "cycle_state": 0,
      "active": false
   }
}
```

#### Set Control Mode
```
GET /mode?value=BUTTON
```

#### Configure Button Cycle
```
GET /button-gesture?value=1
GET /button-secondary-gesture?value=2
GET /button-cycle-mode?value=3
GET /button-cycle-reset
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

# Optional: configure three-press cycle with HandOpen as secondary
requests.get('http://192.168.4.1/button-secondary-gesture?value=2')
requests.get('http://192.168.4.1/button-cycle-mode?value=3')

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

- **v1.1 (2025-10-15):** Multi-press cycle upgrade
   - Added primary/secondary gesture configuration with optional three-press cycle
   - Expanded web UI and `/status` payload with button cycle telemetry
   - Bridge protocol now supports `BTN:PRIMARY`, `BTN:SECONDARY`, `BTN:CYCLE`, and `BTN:RESET`

- **v1.0 (2025-01-15):** Initial implementation of Button Control Mode
  - Added to both v1 and v2 firmware
  - Web interface integration
  - Configurable gesture selection
  - 200ms debounce implementation
