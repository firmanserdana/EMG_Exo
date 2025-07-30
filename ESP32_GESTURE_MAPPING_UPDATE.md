# ESP32 Gesture Mapping Update

## Summary of Changes

The ESP32 gesture mapping has been updated to follow the Unity VR OpenLoopConfig.json gesture definitions, ensuring consistent gesture IDs across the entire EMG-Exo system.

## Updated Configuration (esp32_control.yaml)

### Task-Specific Gesture Mappings

The configuration now includes separate gesture mappings for each task type:

#### Open/Close Task
- **Unity IDs**: [0, 1] 
- **Labels**: ["HandOpen", "HandClose"]
- **ESP32 Mapping**:
  - 0 (HandOpen) → ESP32 Relax (0)
  - 1 (HandClose) → ESP32 All Flex (1)

#### Grasp Patterns Task  
- **Unity IDs**: [0, 2, 3, 4]
- **Labels**: ["HandOpen", "HookGrasp", "LateralGrasp", "IndexPointing"]
- **ESP32 Mapping**:
  - 0 (HandOpen) → ESP32 Relax (0)
  - 2 (HookGrasp) → ESP32 2-Finger Pinch (3)
  - 3 (LateralGrasp) → ESP32 3-Finger Pinch (4)
  - 4 (IndexPointing) → ESP32 Index (6)

#### Single Fingers Task
- **Unity IDs**: [0, 5, 6, 7]
- **Labels**: ["HandOpen", "ThumbFlexion", "IndexFlexion", "MRPFlexion"]
- **ESP32 Mapping**:
  - 0 (HandOpen) → ESP32 Relax (0)
  - 5 (ThumbFlexion) → ESP32 Thumb (5)
  - 6 (IndexFlexion) → ESP32 Index (6)
  - 7 (MRPFlexion) → ESP32 Middle (7)

## Code Changes

### 1. ESP32Controller Class (esp32_control.py)
- Added `update_gesture_mapping()` method
- Added task-specific mapping storage
- Updated default gesture mapping to match Unity definitions

### 2. ESP32ControlLoop Function
- Added `task` parameter to function signature
- Calls `update_gesture_mapping()` with task and configuration
- Automatically selects appropriate gesture mapping based on task

### 3. Main EMG Control Script (emg_control_64.py)
- Passes `task` parameter to ESP32ControlLoop
- ESP32 gesture mapping now adapts automatically based on `--task` argument

### 4. Integration Demo (integration_demo.py)
- Updated simulation examples to use Unity gesture labels
- Demonstrates task-specific gesture predictions

## Usage Examples

### Command Line Usage
```bash
# Open/Close task - uses gesture IDs [0, 1]
python emg_control_64.py --task open_close --decoding-active 1 --esp32-enabled 1

# Grasp Patterns task - uses gesture IDs [0, 2, 3, 4] 
python emg_control_64.py --task grasp_patterns --decoding-active 1 --esp32-enabled 1

# Single Fingers task - uses gesture IDs [0, 5, 6, 7]
python emg_control_64.py --task single_fingers --decoding-active 1 --esp32-enabled 1
```

### Configuration File Usage
```yaml
# In config/esp32_control.yaml
gesture_mapping_open_close:
  0: 0  # HandOpen -> ESP32 Relax
  1: 1  # HandClose -> ESP32 All Flex

gesture_mapping_grasp_patterns:
  0: 0  # HandOpen -> ESP32 Relax
  2: 3  # HookGrasp -> ESP32 2-Finger Pinch
  3: 4  # LateralGrasp -> ESP32 3-Finger Pinch
  4: 6  # IndexPointing -> ESP32 Index

gesture_mapping_single_fingers:
  0: 0  # HandOpen -> ESP32 Relax
  5: 5  # ThumbFlexion -> ESP32 Thumb
  6: 6  # IndexFlexion -> ESP32 Index
  7: 7  # MRPFlexion -> ESP32 Middle
```

## Benefits

1. **Consistency**: ESP32 gestures now match Unity VR gesture IDs exactly
2. **Task Awareness**: Different mappings for different experimental tasks
3. **Automatic Selection**: System automatically chooses correct mapping based on task
4. **Backward Compatibility**: Default mapping maintained for existing usage
5. **Flexibility**: Easy to modify mappings for new tasks or gesture sets

## Data Flow

```
EMG Signal → Decoding → Gesture ID (Unity format) → Task-specific mapping → ESP32 Command → Physical Glove
                                                  ↓
                                            Unity VR Hand (same gesture ID)
```

This ensures that both the Unity VR hand and the ESP32 physical glove respond to the same gesture predictions with consistent, task-appropriate movements.
