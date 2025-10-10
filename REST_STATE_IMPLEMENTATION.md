# Rest State Implementation

## Overview

This document describes the implementation of automatic rest state return after live decoding stops in the EMG-Exo control system.

## Problem Statement


## Solution

The solution implements a clean shutdown sequence that sends explicit rest commands to both control outputs:

### 1. Control Loop Rest Command

**File**: `md-emg-python/realtime_components/control.py`

When the Control Loop receives `None` from the Decoding Loop (indicating decoding has stopped), it now:

2. Logs the action for debugging
3. Provides information about Unity hand state (remains in last gesture, which is normal behavior)

```python
# When None is received (decoding stopped)
    try:
    except Exception as e:
```




1. Processes any remaining commands in the queue (including the rest command from Control Loop)
2. Has a 2-second timeout to ensure commands are processed
3. Specifically detects and processes gesture 0 (rest state)
4. Sends a final emergency stop command to ensure the glove is in relax state

```python
# Cleanup - process any remaining commands in queue before stopping
remaining_commands = 0
timeout_time = time.perf_counter() + 2.0  # 2 second timeout for cleanup
while time.perf_counter() < timeout_time:
    try:
        if data is not None:
            # Process this command
                if success:
                    remaining_commands += 1
            # If it's gesture 0 (relax), we're done
                break
    except Empty:
        break

# Final emergency stop to ensure relax state
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
        ↓
Control Loop exits
        ↓
        ↓
Processes remaining commands from queue
        ↓
Receives and executes gesture 0 (relax)
        ↓
Sends emergency stop (gesture 0)
        ↓
        ↓
```


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
- **Result**: ✓ PASSED

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
3. **Reliability**: Multiple layers (queue command + emergency stop) ensure rest state
4. **Debugging**: Clear logging shows rest state transitions
5. **Testing**: Comprehensive test coverage validates the implementation

## Future Enhancements

Possible future improvements:

1. Add a dedicated Unity "rest" event for explicit hand reset visualization
2. Make the cleanup timeout configurable
3. Add telemetry to track rest state command success rate
