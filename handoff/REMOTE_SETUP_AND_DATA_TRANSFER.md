# Remote Setup + Dataset Transfer (WSL, firman-neuroeng)

## 1) Clone latest code on remote WSL

Run this on the remote WSL terminal:

```bash
git clone https://github.com/firmanserdana/EMG_Exo.git
cd EMG_Exo
```

Current pushed commit:

- `7bc5aef`

## 2) Create Python env on remote WSL

```bash
cd md-emg-python
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3) Copy datasets (healthy S1-S10 + SCI) from local machine

This requires SSH access from local -> remote WSL host.

### 3A) Local machine: set remote target

```bash
export REMOTE_USER="<your_remote_user>"
export REMOTE_HOST="<your_remote_host_or_ip>"
export REMOTE_BASE="/home/<your_remote_user>/EMG_Exo/md-emg-python/data"
```

### 3B) Local machine: create destination and copy

```bash
ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p '$REMOTE_BASE'"

rsync -avh --progress \
  /home/fire/Documents/gitwork/EMG_Exo/md-emg-python/data/healthy/ \
  "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE/healthy/"

rsync -avh --progress \
  /home/fire/Documents/gitwork/EMG_Exo/md-emg-python/data/SCI/ \
  "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE/SCI/"
```

Dataset sizes (local):

- healthy: ~1.2G
- SCI: ~1.5G

## 4) Start resumable full training on remote WSL

Run this on remote WSL from repo root:

```bash
source md-emg-python/.venv/bin/activate

python md-emg-python/scripts/train_transfer_pipeline_cli.py \
  --run_all \
  --healthy_subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 \
  --sci_subjects S3,S4 \
  --models LSTM,CNNLSTM \
  --n_trials 100 \
  --hpo_epochs 25 \
  --pretrain_epochs 80 \
  --transfer_epochs 40 \
  --transfer_lr 5e-4 \
  --output_dir md-emg-python/results-optimization \
  --run_tag remote_resume_20260315 \
  --study_prefix healthy_open_close \
  --hpo_storage_uri sqlite:////home/<your_remote_user>/EMG_Exo/md-emg-python/results-optimization/pipeline_remote_resume_20260315/hpo/optuna_studies.db \
  --seed 18
```

## 5) Resume if interrupted

Re-run the exact same command in step 4.

Because `--hpo_storage_uri` is set and studies are loaded with `load_if_exists`, Optuna resumes from completed trials.
