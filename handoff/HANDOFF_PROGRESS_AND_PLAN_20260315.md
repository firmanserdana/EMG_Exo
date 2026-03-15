# EMG_Exo Training Handoff (Saved Before Pause)

Date: 2026-03-15

## User Goal Summary

1. Pretrain CNNLSTM and LSTM on healthy S1-S10 with best hyperparameters.
2. Test pretrained models on SCI S3/S4 sessions (including Unity-event sessions).
3. Transfer learn with SCI S3/S4 and retest.
4. Generate summary (accuracy, figures, confusion matrices).
5. Add Unity Decoder-BBT benchmark mode/scene for closed-loop performance scoring.

## Completed Engineering Work

### Python pipeline and helper CLIs

- Added orchestration CLI:
  - `md-emg-python/scripts/train_transfer_pipeline_cli.py`
- Added helper scripts:
  - `md-emg-python/scripts/build_pretrain_manifest.py`
  - `md-emg-python/scripts/pretrain_optuna.py`
  - `md-emg-python/scripts/evaluate_transfer_sci_s3_s4.py`
  - `md-emg-python/scripts/summarize_transfer_results.py`

### Unity Decoder-BBT integration

- Decoder-BBT mode and routing in `StartUI.cs`.
- Robust TCP event parser in `TcpServerManager.cs` for both `event/event_id` and `eventName/eventID` payloads.
- Added decoder manager and config support.
- Added scene and build settings entry for `graspingDecoderBBT.unity`.

## Full Run Invocation Used

Executed from repository root:

`/home/fire/.conda/envs/md-emg/bin/python md-emg-python/scripts/train_transfer_pipeline_cli.py --run_all --healthy_subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --sci_subjects S3,S4 --models LSTM,CNNLSTM --n_trials 100 --hpo_epochs 25 --pretrain_epochs 80 --transfer_epochs 40 --transfer_lr 5e-4 --output_dir results-optimization --seed 18`

## Runtime Progress Captured Before Pause

Active process before pause:

- PID: `730103`
- Runtime observed: > 1 day wall-clock with heavy CPU utilization

Observed Optuna trial completions in terminal output:

- Trial 0: value=0.6089253187613843, params={lr=0.0009134433449113726, weight_decay=3.2836746574684305e-05, batch_size=32, dropout=0.40005451444240425, hidden_size=96, num_layers=3}
- Trial 1: value=0.5788706739526411, params={lr=0.0001073333358777688, weight_decay=2.161769533972357e-06, batch_size=128, dropout=0.17945374367351238, hidden_size=192, num_layers=3}
- Trial 2: value=0.592896174863388, params={lr=0.0005058206556069419, weight_decay=9.995419916707376e-05, batch_size=64, dropout=0.2175743898807154, hidden_size=96, num_layers=2}
- Trial 3: value=0.6413479052823315, params={lr=0.0007009598610565682, weight_decay=1.0889241069132648e-06, batch_size=32, dropout=0.1054550006976589, hidden_size=96, num_layers=3}
- Trial 4: value=0.5409836065573771, params={lr=0.00020941483022206213, weight_decay=0.0006365241763382525, batch_size=32, dropout=0.3741454475249645, hidden_size=256, num_layers=2}
- Trial 5: value=0.6103825136612022, params={lr=0.000981566095262634, weight_decay=1.9533400025627024e-05, batch_size=64, dropout=0.3638621582448286, hidden_size=96, num_layers=1}

Best observed so far: Trial 3 (0.6413479052823315)

## Important Note About Resume Capability

The current long run used an in-memory Optuna study (no persistent DB configured), so exact native resume of that same process state is not guaranteed after pause/stop.

Workaround used here:

- Saved all visible trial results and runtime evidence in this handoff file.
- Next run should use persistent Optuna storage (`sqlite`) to support true pause/resume and remote continuation.

## Discussion/Planning Snapshot

- Selected full-thorough search budget: 100+ trials per model.
- Healthy data policy: hybrid mapped sessions with fallback scan.
- SCI evaluation policy: include open-loop + closed-loop sessions for S3/S4.
- Unity scope: dedicated Decoder-BBT mode/scene with moved/dropped block metrics and phase checks.
- Main risk recognized: full HPO wall-clock on local hardware is very long; remote better GPU recommended.
