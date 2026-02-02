# ESP32 Exoskeleton Controller

Arduino firmware for ESP32-based pneumatic glove control.

## Versions

| Version | Description | Protocol |
|---------|-------------|----------|
| `v1/` | Basic sketches, UDP communication | UDP port 4210 |
| `v2/` | Production firmware, TCP server | TCP port 4210 |

## Quick Start (v2)

### 1. Configure WiFi

Copy and edit config:
```bash
cd v2/Bilateral_control_WIFI_V3
cp config.h.example config.h
```

Edit `config.h`:
```cpp
#define WIFI_STA_SSID "Arlen"
#define WIFI_STA_PASSWORD "12345678"
```

### 2. Upload Firmware

1. Open `v2/Bilateral_control_WIFI_V3/Bilateral_control_WIFI_V3.ino` in Arduino IDE
2. Select board: **ESP32 Dev Module**
3. Upload

### 3. Connect

The ESP32 starts a TCP server on port 4210. Connect from Python:
```python
from v2.Glove_wifi_controller import ESP32GloveTCPController

glove = ESP32GloveTCPController(esp32_ip="192.168.50.11")
glove.connect()
glove.set_gesture(1)  # Close hand
```

## Command Protocol

Commands are sent as text over TCP, terminated with newline.

| Command | Format | Description |
|---------|--------|-------------|
| Gesture | `g:N` | Set gesture (0-8) |
| Pressure | `p:FLEX,EXT` | Set pressure (0-100) |
| Speed | `s:N` | Set speed (0-4) |
| Finger | `f:STATES` | Set finger states (6 digits: 0/1/2) |

### Gesture Mapping

| ID | Gesture | Finger States |
|----|---------|---------------|
| 0 | Relax | `000000` |
| 1 | All Flex | `111110` |
| 2 | All Extend | `222222` |
| 3 | 4-Finger Pinch | `011110` |
| 4 | 3-Finger Pinch | `111110` |
| 5 | Thumb | `100000` |
| 6 | Index | `010000` |
| 7 | MRP Flex | `001110` |
| 8 | Index Point | `121110` |

## Hardware Pins

```
Flexion:   [13, 14, 12, 27, 15]  (Thumb, Index, Middle, Ring, Pinky)
Extension: [17,  5, 18, 19, 15]
I2C DAC:   SDA=21, SCL=22
```

## Web Interface

When in AP mode, connect to `ESP32_Glove` (password: `12345678`) and open `http://192.168.4.1` for manual control.
