# Rest State Implementation

## Overview

This document describes the implementation of automatic rest state return after live decoding stops in the EMG-Exo control system.

## Problem Statement

When live decoding stops (user presses Enter to stop the acquisition), the system needs to ensure that both Unity VR visualization and the ESP32 pneumatic glove return to a resting/relaxed state. Previously, the system would simply stop processing without explicitly commanding the devices to return to rest, potentially leaving the glove in an active state.

## Solution

The solution implements a clean shutdown sequence that sends explicit rest commands to both control outputs:

### 1. Control Loop Rest Command

**File**: `md-emg-python/realtime_components/control.py`

When the Control Loop receives `None` from the Decoding Loop (indicating decoding has stopped), it now:

1. Sends a relax command (gesture 0) to the ESP32 queue with full confidence
2. Logs the action for debugging
3. Provides information about Unity hand state (remains in last gesture, which is normal behavior)

```python
# When None is received (decoding stopped)
if pred_esp32_queue is not None:
    try:
        # Send relax gesture (0) to ESP32
        esp32_rest_data = (0, 1.0, time.perf_counter())  # gesture 0, full confidence, timestamp
        pred_esp32_queue.put(esp32_rest_data, timeout=1.0)
        print('✓ Sent relax command (gesture 0) to ESP32')
    except Exception as e:
        print(f'⚠️  Failed to send rest command to ESP32: {e}')
```

### 2. ESP32 Control Loop Cleanup

**File**: `md-emg-python/realtime_components/esp32_control.py`

The ESP32 Control Loop now has an enhanced cleanup phase that:

1. Processes any remaining commands in the queue (including the rest command from Control Loop)
2. Has a 2-second timeout to ensure commands are processed
3. Specifically detects and processes gesture 0 (rest state)
4. Sends a final emergency stop command to ensure the glove is in relax state
5. Waits 0.5 seconds for the ESP32 to process the stop command

```python
# Cleanup - process any remaining commands in queue before stopping
remaining_commands = 0
timeout_time = time.perf_counter() + 2.0  # 2 second timeout for cleanup
while time.perf_counter() < timeout_time:
    try:
        data = pred_esp32_queue.get_nowait()
        if data is not None:
            esp32_gesture = data[0]
            # Process this command
            if esp32_controller.connected:
                success = esp32_controller.set_gesture(esp32_gesture)
                if success:
                    remaining_commands += 1
            # If it's gesture 0 (relax), we're done
            if esp32_gesture == 0:
                print('✓ ESP32: Rest state command processed')
                break
    except Empty:
        break

# Final emergency stop to ensure relax state
esp32_controller.emergency_stop()
time.sleep(0.5)  # Give ESP32 time to process the stop command
```

## Control Flow

```
User stops acquisition
        ↓
Decoding Loop stops
        ↓
Sends None to Control Loop
        ↓
Control Loop receives None
        ↓
Sends gesture 0 (relax) to ESP32 queue
        ↓
Control Loop exits
        ↓
ESP32 Control Loop cleanup phase starts
        ↓
Processes remaining commands from queue
        ↓
Receives and executes gesture 0 (relax)
        ↓
Sends emergency stop (gesture 0)
        ↓
ESP32 Control Loop exits
        ↓
ESP32 glove is in rest state ✓
```

## ESP32 Gesture Mapping

The system uses gesture ID 0 for the rest/relax state:

- **Gesture 0**: Relax - all fingers relaxed, no actuation
- **Gesture 1**: All Flexion - all fingers flex
- **Gesture 2**: All Extension - all fingers extend
- **Gesture 3-8**: Various specific gestures (pinch, thumb, index, etc.)

## Unity Behavior

Unity VR hand visualization does not have a dedicated "rest" event. The hand will remain in its last displayed gesture when decoding stops. This is the expected and normal behavior for the Unity visualization system.

## Testing

A comprehensive test suite (`md-emg-python/test_rest_state.py`) validates the implementation:

### Test 1: Control Loop Rest State Behavior
- Simulates normal prediction flow
- Simulates decoding stop (None received)
- Verifies that gesture 0 is sent to ESP32 queue
- **Result**: ✓ PASSED

### Test 2: ESP32 Cleanup Behavior
- Simulates commands in ESP32 queue
- Simulates cleanup phase processing
- Verifies rest command is processed
- Verifies emergency stop is executed
- **Result**: ✓ PASSED

Run the test with:
```bash
cd md-emg-python
python3 test_rest_state.py
```

## Benefits

1. **Safety**: Ensures the pneumatic glove returns to a safe, relaxed state
2. **Consistency**: Both Unity and ESP32 receive appropriate rest commands
3. **Reliability**: Multiple layers (queue command + emergency stop) ensure rest state
4. **Debugging**: Clear logging shows rest state transitions
5. **Testing**: Comprehensive test coverage validates the implementation

## Future Enhancements

Possible future improvements:

1. Add a dedicated Unity "rest" event for explicit hand reset visualization
2. Make the cleanup timeout configurable
3. Add telemetry to track rest state command success rate
4. Implement rest state confirmation from ESP32
