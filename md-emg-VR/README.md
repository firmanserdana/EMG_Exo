# EMG VR Hand Visualization

Unity-based real-time hand visualization for EMG-controlled exoskeleton.

## Overview

This Unity project renders a 3D hand model that mirrors the exoskeleton state received from the Python decoder via TCP.

## Requirements

- Unity 2020.3+ (LTS recommended)
- Linux build: Run `exo_virt.x86_64`
- Windows/Mac: Build from source

## Quick Start

### Option 1: Run Pre-built (Linux)

```bash
./exo_virt.x86_64
```

### Option 2: Build from Source

1. Open project in Unity Hub
2. Select `Assets/Scenes/SampleScene`
3. Build: File → Build Settings → Build

## TCP Connection

The Unity app runs a TCP server (default port 45001) that receives hand state from `md-emg-python`.

### Message Format

```
finger1,finger2,finger3,finger4,finger5\n
```

Values: `0` = extend, `1` = flex, `2` = rest

### Example Python Client

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 45001))
sock.send(b"1,1,1,1,0\n")  # All fingers flexed except pinky
```

## Key Scripts

| Script | Purpose |
|--------|---------|
| `TcpServerManager.cs` | TCP server for receiving predictions |
| `HandController.cs` | Maps received states to hand model |
| `SessionControl.cs` | Manages session start/stop |

## Integration with md-emg-python

1. Start Unity app
2. Run `streaming_predictions_gui.py` with Unity output enabled:
   ```python
   # In config/streaming_gui.yaml
   output:
     unity_enabled: true
     unity_host: "127.0.0.1"
     unity_port: 45001
   ```

The Python GUI sends decoded gestures to Unity for visualization.
