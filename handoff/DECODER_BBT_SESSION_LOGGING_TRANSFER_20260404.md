# Decoder-BBT Session Logging Transfer Notes

Date: 2026-04-04

## Goal

Persist the online Decoder-BBT task outputs beside the EMG session files so the run can be analyzed or resumed on another PC without relying on Unity's generic persistent-data folder.

## What Was Implemented

### 1) Python sends session save context to Unity

File:

- `md-emg-python/emg_control_64.py`

Behavior:

- Before the acquisition starts, Python now sends a `session_context` TCP payload to Unity.
- That payload includes:
  - `outputDirectory`
  - `sessionLabel`
  - `sessionIndex`
  - `subjectID`
  - `taskName`
  - `acquisitionType`
- This lets Unity know the exact folder where the current EMG session is being written.

### 2) Unity stores that session context

Files:

- `md-emg-VR/Assets/Scripts/TcpServerManager.cs`
- `md-emg-VR/Assets/Scripts/Events.cs`

Behavior:

- `TcpServerManager` now caches:
  - `CurrentOutputDirectory`
  - `CurrentSessionLabel`
  - `CurrentSessionIndex`
- `TCPEvent` and the raw TCP parser were extended so Unity can also receive decoder metadata fields.

### 3) Python sends richer decoder events to Unity

File:

- `md-emg-python/realtime_components/control.py`

Behavior:

- `grasp_decoded` events sent from Python to Unity now include:
  - `eventID`: Unity-facing decoded class id
  - `predictionRawID`: raw model label before Unity remapping
  - `predictionProb`: confidence of the decoded class
  - `predictionTimestamp`: timestamp generated on the Python side

This makes the Unity-side decoder log useful for later offline inspection.

### 4) Unity Decoder-BBT now writes session-side logs

File:

- `md-emg-VR/Assets/Scripts/ManagerDecoderBBT.cs`

Behavior:

- On each Decoder-BBT session start, Unity now resolves the active EMG session folder from `TcpServerManager.CurrentOutputDirectory`.
- Unity no longer writes Decoder-BBT output only to its generic `Application.persistentDataPath` fallback when session context is available.
- Each session creates two artifacts inside the active EMG session output folder:

1. Summary JSON

   - Filename pattern:
     - `<sessionLabel>_decoder_bbt_<runtimeSessionId>_summary.json`

2. Detailed JSONL log

   - Filename pattern:
     - `<sessionLabel>_decoder_bbt_<runtimeSessionId>_decoder_results.jsonl`

## Metrics Now Captured

The Decoder-BBT summary/log now includes:

- `blocksMovedSuccessfully`
- `blocksSucceeded`
- `blocksDropped`
- `blocksDroppedDuringMove`
- `blocksTimedOut`
- `totalAttempts`
- `decoderEventsLogged`
- `decoderResultsLogFile`

Note:

- `blocksMovedSuccessfully` and `blocksSucceeded` currently track the same successful placements.
- `blocksDropped` and `blocksDroppedDuringMove` currently track the same dropped-during-move count.
- Both names were kept so downstream scripts can use either the more descriptive label or the legacy-style field.

## JSONL Entry Types

The detailed Decoder-BBT log writes one JSON object per line. Current entry types are:

- `session_start`
- `decoder_result`
- `attempt_outcome`
- `session_end`

Useful fields inside those lines include:

- `phase`
- `detail`
- `predictedUnityEventId`
- `predictedRawId`
- `predictionProb`
- `predictionTimestamp`
- running counts for success, drops, timeouts, attempts

## Output Location Example

If Python is saving the EMG run into:

- `md-emg-python/data/<subj_type>/S<id>/raw/session_07.npy`

then Unity Decoder-BBT outputs should land in the same raw session directory, for example:

- `md-emg-python/data/<subj_type>/S<id>/raw/session_07_decoder_bbt_<runtimeSessionId>_summary.json`
- `md-emg-python/data/<subj_type>/S<id>/raw/session_07_decoder_bbt_<runtimeSessionId>_decoder_results.jsonl`

The existing EMG artifacts remain unchanged:

- `session_07.npy`
- `session_07_events.pkl`
- `session_07_predictions.pkl`

## Files That Must Be Transferred To Another PC

Code files:

- `md-emg-python/emg_control_64.py`
- `md-emg-python/realtime_components/control.py`
- `md-emg-VR/Assets/Scripts/Events.cs`
- `md-emg-VR/Assets/Scripts/TcpServerManager.cs`
- `md-emg-VR/Assets/Scripts/ManagerDecoderBBT.cs`

Handoff documentation:

- `handoff/DECODER_BBT_SESSION_LOGGING_TRANSFER_20260404.md`
- `handoff/HANDOFF_PROGRESS_AND_PLAN_20260315.md`

## Recommended Transfer Method

Preferred:

1. Commit the code and handoff docs in git.
2. Pull the branch on the other PC.

Manual fallback:

1. Copy the five code files listed above.
2. Copy this handoff markdown file.
3. Reopen the Unity project and let Unity recompile scripts.
4. Run one Decoder-BBT test session to confirm logs land in the EMG session folder.

## Validation Status

Static validation completed:

- No editor errors were reported in the modified Python and Unity files.

Not yet completed:

- Full live end-to-end run with Python acquisition + Unity Decoder-BBT on the current machine.

## What To Check First On The Other PC

1. Start Python acquisition with decoding enabled.
2. Confirm the `session_context` message is received by Unity.
3. Start the Decoder-BBT task.
4. End the session.
5. Check the EMG session output folder for the new summary JSON and JSONL files.
6. Confirm the JSONL contains `decoder_result` lines with raw id and confidence values.