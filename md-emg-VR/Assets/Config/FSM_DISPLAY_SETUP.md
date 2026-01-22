# FSM Display Setup for Unity

This guide explains how to set up the FSM state display and BBT scoring UI in Unity.

## Overview

The FSM Display system shows:
- **Current FSM State**: IDLE, CLOSING, LOCKED_GRASP, OPENING, or EMERGENCY_STOP
- **Grasp Lock Indicator**: Pulsing visual when grasp is locked during transport
- **BBT Scoring**: Block count, grasp count, and session timer

## Quick Setup (Automatic)

### Option 1: Use the Menu (Recommended)

1. Open Unity project (`md-emg-VR/`)
2. Go to menu: **EMG-Exo → Setup FSM Display UI**
3. Done! The UI is created automatically.

### Option 2: Auto-Setup Script

1. Create empty GameObject in your scene
2. Add Component → `FSMDisplayAutoSetup`
3. The UI will be created automatically on Play

## Manual Setup

### 1. Add the Script to Your Scene

1. In your Unity scene, create an empty GameObject: `GameObject → Create Empty`
2. Name it `FSMDisplayManager`
3. Add the script: `Add Component → FSMDisplayManager`

### 2. Create the UI Elements

Create the following UI hierarchy under a Canvas:

```
Canvas
└── FSMDisplayPanel
    ├── StateIndicator (Image)
    ├── StateText (TextMeshPro)
    ├── LockIndicator (Image)
    └── LockTimerText (TextMeshPro)
└── BBTScoringPanel
    ├── BlockCountLabel (TextMeshPro) "Blocks:"
    ├── BlockCountText (TextMeshPro) "0"
    ├── GraspCountLabel (TextMeshPro) "Grasps:"
    ├── GraspCountText (TextMeshPro) "0"
    └── SessionTimerText (TextMeshPro) "00:00"
```

### 3. Configure FSMDisplayManager

Drag the UI elements to the FSMDisplayManager component:

| Field | UI Element |
|-------|------------|
| Fsm Display Panel | FSMDisplayPanel |
| State Text | StateText |
| State Indicator | StateIndicator |
| Lock Indicator | LockIndicator |
| Lock Timer Text | LockTimerText |
| Bbt Scoring Panel | BBTScoringPanel |
| Block Count Text | BlockCountText |
| Session Timer Text | SessionTimerText |
| Grasp Count Text | GraspCountText |

### 4. Recommended UI Settings

#### State Indicator (Image)
- Width: 100, Height: 100
- Image Type: Simple
- Color: Will be set by script based on state

#### State Text
- Font Size: 36
- Alignment: Center
- Color: White

#### Lock Indicator (Image)
- Width: 50, Height: 50
- Use a lock icon sprite (or simple circle)
- Position next to state indicator

#### BBT Scoring Panel
- Position: Top-right corner
- Background: Semi-transparent black panel

## State Colors

The default colors are:
- **IDLE**: Green (0.3, 0.7, 0.3)
- **CLOSING**: Orange (0.9, 0.6, 0.2)
- **LOCKED_GRASP**: Blue (0.2, 0.5, 0.9)
- **OPENING**: Yellow (0.7, 0.7, 0.2)
- **EMERGENCY_STOP**: Red (0.9, 0.2, 0.2)

You can customize these in the Inspector.

## TCP Event Format

The Python FSM control sends these events:

### FSM State Update
```json
{
  "eventName": "fsm_state",
  "eventID": 2,
  "fsmState": "LOCKED_GRASP",
  "isLocked": true,
  "lockTime": 1.5,
  "handPosition": 1.0,
  "force": 0.7
}
```

### BBT Score Update
```json
{
  "eventName": "bbt_score",
  "eventID": 5,
  "blockCount": 5,
  "graspCount": 5,
  "sessionTime": 45.2
}
```

### Session Events
```json
{"eventName": "fsm_start", "eventID": 1}
{"eventName": "fsm_stop", "eventID": 0, "graspCount": 12, "sessionTime": 60.0}
```

## Testing

1. Run the Unity scene
2. Start the Python FSM control:
   ```bash
   python emg_control_64.py --control_mode fsm --functional_test box_and_block --decoding_active 1
   ```
3. The UI should show state changes and scoring updates

## Troubleshooting

### UI Not Updating
- Check that `TcpServerManager` is in the scene and connected
- Verify the `FSMDisplayManager.Instance` is not null
- Check Console for TCP connection errors

### Panels Not Visible
- The panels are hidden by default until `fsm_start` event is received
- You can manually call `FSMDisplayManager.Instance.StartFSMSession()` for testing

### Colors Not Changing
- Ensure `StateIndicator` is assigned in the Inspector
- Check that Image component is on the StateIndicator object
