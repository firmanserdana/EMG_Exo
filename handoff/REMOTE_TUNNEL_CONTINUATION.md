# Continue On VS Code Remote Tunnel (WSL)

## What changes with VS Code Tunnel

The tunnel endpoint is editor transport, not a direct SSH host from this machine.
So automated scp or rsync from this local session to the tunnel target cannot be executed here.

## Fastest practical workflow

1. Open your tunnel workspace in VS Code (firman-neuroeng -> WSL).
2. In that remote terminal, clone the updated repository:
   git clone https://github.com/firmanserdana/EMG_Exo.git
   cd EMG_Exo
   git checkout main
   git pull
3. In remote WSL, create environment and install dependencies:
   cd md-emg-python
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt

## Copy datasets when using tunnel

Because this agent cannot directly access your tunnel file system, use one of these paths:

Option A (recommended): copy datasets from your local machine into the tunnel workspace using VS Code file operations.
- Source local folders:
  /home/fire/Documents/gitwork/EMG_Exo/md-emg-python/data/healthy
  /home/fire/Documents/gitwork/EMG_Exo/md-emg-python/data/SCI
- Destination remote folders:
  EMG_Exo/md-emg-python/data/healthy
  EMG_Exo/md-emg-python/data/SCI

Option B: temporary cloud/object storage bridge.
- Upload healthy and SCI folders to cloud storage from local.
- Download from remote WSL into md-emg-python/data.

## Agent instruction (copy-paste in remote instance)

Use the exact prompt below in the remote tunnel Copilot chat:

```text
Execute this workflow end-to-end in the current workspace:

1) Validate repository and branch
- Run: git rev-parse --is-inside-work-tree
- Run: git checkout main && git pull
- Confirm commit includes handoff docs under handoff/.

2) Validate dataset presence and counts
- Required folders:
  - md-emg-python/data/healthy
  - md-emg-python/data/SCI
- Run and report:
  - du -sh md-emg-python/data/healthy md-emg-python/data/SCI
  - find md-emg-python/data/healthy -type f | wc -l
  - find md-emg-python/data/SCI -type f | wc -l
- If folders are missing or empty, stop and print exactly what is missing.

3) Prepare Python environment
- From repo root run:
  - cd md-emg-python
  - python3 -m venv .venv
  - source .venv/bin/activate
  - pip install --upgrade pip
  - pip install -r requirements.txt

4) Start resumable full pipeline run
- From repo root run exactly:
  source md-emg-python/.venv/bin/activate
  python md-emg-python/scripts/train_transfer_pipeline_cli.py --run_all --healthy_subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --sci_subjects S3,S4 --models LSTM,CNNLSTM --n_trials 100 --hpo_epochs 25 --pretrain_epochs 80 --transfer_epochs 40 --transfer_lr 5e-4 --output_dir md-emg-python/results-optimization --run_tag remote_resume_20260315 --study_prefix healthy_open_close --hpo_storage_uri sqlite:////home/<REMOTE_USER>/EMG_Exo/md-emg-python/results-optimization/pipeline_remote_resume_20260315/hpo/optuna_studies.db --seed 18

5) Monitoring
- Create/append checkpoint log every 10 minutes into:
  md-emg-python/results-optimization/pipeline_remote_resume_20260315/progress_checkpoints.log
- Each checkpoint must include:
  - timestamp
  - current trial number
  - best value so far
  - process status

6) Resume behavior
- If run stops, rerun the exact same command in step 4.
- Do not change run_tag, study_prefix, or hpo_storage_uri.

7) Reporting format
- Return a concise report with:
  - dataset verification values
  - environment setup result
  - launch command used
  - first observed trials and current best
  - path to checkpoint log
```

## Start resumable full run on remote WSL

From repository root on remote:

source md-emg-python/.venv/bin/activate
python md-emg-python/scripts/train_transfer_pipeline_cli.py --run_all --healthy_subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --sci_subjects S3,S4 --models LSTM,CNNLSTM --n_trials 100 --hpo_epochs 25 --pretrain_epochs 80 --transfer_epochs 40 --transfer_lr 5e-4 --output_dir md-emg-python/results-optimization --run_tag remote_resume_20260315 --study_prefix healthy_open_close --hpo_storage_uri sqlite:////home/<REMOTE_USER>/EMG_Exo/md-emg-python/results-optimization/pipeline_remote_resume_20260315/hpo/optuna_studies.db --seed 18

## Resume rule

If interrupted, rerun the exact same command. The Optuna study is persistent and will continue from completed trials.

## Local status reference

- Latest pushed code commit: 7cfaa0a
- Paused local run artifacts:
  md-emg-python/results-optimization/pipeline_20260314_233541
- Handoff details:
  handoff/HANDOFF_PROGRESS_AND_PLAN_20260315.md
