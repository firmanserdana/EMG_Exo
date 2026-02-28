# Box and Block Test (BBT) Scene Setup Guide

## Overview
The BBT scene simulates a standard Box and Block Test where a virtual hand actively demonstrates **open/close** movements. The subject follows the hand to grasp a block, move it over a partition to the other side, and place it by opening the hand.

**Events are identical to the static open-close task** — the Python-side EMG pipeline receives the same `grasp_start`, `grasp_hold_start`, `grasp_hold_end`, `grasp_released`, `trial_start`, `trial_end`, `session_start`, `session_end` events with the same `event_id` values (0 = HandOpen, 1 = HandClose).

---

## Creating the Scene in Unity Editor

### Step 1: Create the Scene
1. **File → New Scene** (Basic Built-in)
2. **File → Save As** → save as `graspingBBT` in `Assets/Scenes/`
3. **Add to Build Settings**: File → Build Settings → Add Open Scenes

### Step 2: Add Core GameObjects

Create an empty **Manager** GameObject and attach these components:
- `ManagerBBT`
- `GUIManager`
- `TcpServerManager` (if not using DontDestroyOnLoad singleton from StartUI)

### Step 3: Set Up the Hands

1. Drag the hand prefabs from `Assets/Objects/Hand/` into the scene
2. Name them `LeftHand` and `RightHand`
3. Each hand must have the `HandController` component with fingers assigned
4. In **ManagerBBT** inspector:
   - Assign `Left Hand` → LeftHand GameObject
   - Assign `Right Hand` → RightHand GameObject

### Step 4: Set Up the BBT Box

1. Create an empty GameObject named **BBTBox**
2. Position it in front of the camera (e.g., position `(0, 0.8, 0.5)`)
3. Add the `BBTBoxSetup` component
4. Adjust dimensions in the inspector if needed:
   - Box Width: 0.5
   - Box Depth: 0.3
   - Box Height: 0.05
   - Partition Height: 0.15
5. The script auto-generates the box, walls, partition, source zone, and target zone at runtime

### Step 5: Set Up GUI

Create a **Canvas** (Screen Space - Overlay) with:

| Element | Type | Name | Wire to ManagerBBT |
|---------|------|------|---------------------|
| Play Button | Button | BtnPlay | `btnPlay` |
| Stop Button | Button | BtnStop | `btnStop` |
| Exit Button | Button | BtnExit | `btnExit` |
| Trials Label | TextMeshPro | LblTrials | `lblTrialsCount` |
| Block Count | TextMeshPro | LblBlocks | `lblBlockCount` |
| Timer | TextMeshPro | LblTimer | `lblTimer` |
| Instruction | TextMeshPro | LblInstruction | `lblInstruction` |

Wire button OnClick events:
- BtnPlay → `ManagerBBT.OnBtnPlayClick`
- BtnStop → `ManagerBBT.OnBtnStopClick`
- BtnExit → `ManagerBBT.OnBtnExitClick`

You can also reuse the same GUI instruction/state images from the open-close scene by adding a `GUIManager` component and assigning the sprites.

### Step 6: (Optional) FSM Display

To show FSM state + BBT scoring overlays:
1. Add `FSMDisplayAutoSetup` component to any GameObject
2. It will auto-create FSM state panel and BBT scoring panel at runtime
3. The `ManagerBBT` script automatically calls `FSMDisplayManager` to update scores

### Step 7: Camera Setup

Position camera to view the box and hand:
- Position: `(0, 1.2, -0.3)`
- Rotation: `(45, 0, 0)`
- Adjust field of view so both sides of the box are visible

---

## Configuration

Edit `Assets/Config/BBTConfig.json`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sessionDuration` | 60000 | Total session time limit (ms) |
| `trialsStartDelay` | 3000 | Delay before first trial (ms) |
| `graspCloseDuration` | 1500 | Not used directly — controlled by `AnimationConfig.speedHz` |
| `holdDuration` | 1000 | How long to hold block after grasping (ms) |
| `moveDuration` | 2000 | Hand movement duration across partition (ms) |
| `placePauseDuration` | 500 | Pause after placing block (ms) |
| `interTrialInterval` | 1500 | Interval between each block trial (ms) |
| `numberOfBlocks` | 15 | Number of blocks to transfer |
| `blockSize` | 0.025 | Block cube size in meters (2.5cm) |
| `handMoveHeight` | 0.15 | Arc height for hand trajectory over partition |

---

## Event Flow (Per Block)

Each block transfer produces events **identical** to a single open-close trial:

```
trial_start
  │
  ├── grasp_start (event_id=1)     ← Hand closes (same as HandClose)
  ├── [hand animation: close]
  ├── grasp_hold_start              ← Block is grasped
  ├── [hand moves block over partition]
  ├── grasp_hold_end                ← About to release
  ├── grasp_start (event_id=0)     ← Hand opens (same as HandOpen)
  ├── [hand animation: open]
  ├── grasp_released                ← Block placed
  ├── bbt_block_placed (event_id=N) ← BBT-specific scoring
  │
trial_end
```

Session-level events:
```
session_start  →  [block trials...]  →  session_end
```

---

## Selecting BBT from Start UI

In the **graspingStartUI** scene, the `AcquisitionType` dropdown now includes **BBT** (index 4).
When BBT is selected:
- Grasping type is automatically set to `HandOpenClose`
- The scene `graspingBBT` is loaded

---

## Files Created/Modified

| File | Action |
|------|--------|
| `Scripts/ManagerBBT.cs` | **New** — Main BBT manager |
| `Scripts/BBTBoxSetup.cs` | **New** — Auto-generates box environment |
| `Config/BBTConfig.json` | **New** — BBT timing & layout config |
| `Scripts/Configs.cs` | **Modified** — Added `BBTConfig` class |
| `Scripts/StartUI.cs` | **Modified** — Added `BBT` acquisition type |
