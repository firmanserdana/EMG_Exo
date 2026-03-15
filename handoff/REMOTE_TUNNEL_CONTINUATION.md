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

## Start resumable full run on remote WSL

From repository root on remote:

source md-emg-python/.venv/bin/activate
python md-emg-python/scripts/train_transfer_pipeline_cli.py --run_all --healthy_subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 --sci_subjects S3,S4 --models LSTM,CNNLSTM --n_trials 100 --hpo_epochs 25 --pretrain_epochs 80 --transfer_epochs 40 --transfer_lr 5e-4 --output_dir md-emg-python/results-optimization --run_tag remote_resume_20260315 --study_prefix healthy_open_close --hpo_storage_uri sqlite:////home/<REMOTE_USER>/EMG_Exo/md-emg-python/results-optimization/pipeline_remote_resume_20260315/hpo/optuna_studies.db --seed 18

## Resume rule

If interrupted, rerun the exact same command. The Optuna study is persistent and will continue from completed trials.

## Local status reference

- Latest pushed code commit: 7bc5aef
- Paused local run artifacts:
  md-emg-python/results-optimization/pipeline_20260314_233541
- Handoff details:
  handoff/HANDOFF_PROGRESS_AND_PLAN_20260315.md
