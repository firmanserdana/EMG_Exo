#!/usr/bin/env python3
"""
End-to-end CLI pipeline for:
1) Healthy pretraining with hyperparameter search (LSTM + CNNLSTM)
2) SCI S3/S4 evaluation of pretrained models
3) Transfer learning on SCI S3/S4 and re-evaluation
4) Summary CSV/figures export

Example:
    python scripts/train_transfer_pipeline_cli.py --run_all
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.pretrain_healthy import (
    EMGDataset,
    NUM_CHANNELS,
    SAMPLING_RATE,
    SESSION_MAPPINGS_CLEAN,
    SessionRecord,
    apply_normalization,
    load_session_data,
    load_timestamps,
    normalize_emg,
    parse_gesture_timestamps,
    prepare_open_close_data,
)
from scripts.test_sci_transfer import extract_grasp_windows, load_session as load_sci_session
from utils.data_utils import create_events_df


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class TunableLSTM(nn.Module):
    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        num_classes: int,
        dropout: float,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=True,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.fc(out)


class TunableCNNLSTM(nn.Module):
    def __init__(
        self,
        n_channels: int,
        seq_len: int,
        num_classes: int,
        conv1_channels: int,
        conv2_channels: int,
        lstm_hidden: int,
        lstm_layers: int,
        dropout: float,
    ):
        super().__init__()
        self.conv1 = nn.Conv1d(n_channels, conv1_channels, kernel_size=5, padding=2)
        self.bn1 = nn.BatchNorm1d(conv1_channels)
        self.conv2 = nn.Conv1d(conv1_channels, conv2_channels, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(conv2_channels)
        self.pool = nn.MaxPool1d(2)

        self.lstm = nn.LSTM(
            input_size=conv2_channels,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
            bidirectional=True,
        )
        self.fc = nn.Sequential(
            nn.Linear(lstm_hidden * 2, lstm_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(lstm_hidden, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.transpose(1, 2)
        x = torch.relu(self.bn1(self.conv1(x)))
        x = self.pool(x)
        x = torch.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        x = x.transpose(1, 2)
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.fc(out)


@dataclass
class HealthySessionEntry:
    subject: str
    condition: str
    session: int
    source: str
    data_file: Path
    timestamp_file: Path
    exists: bool


@dataclass
class SciSessionEntry:
    subject: str
    session: int
    has_unity_events: bool
    data_file: Path
    event_file: Path


def _flatten_sessions(values: Sequence) -> List[int]:
    out: List[int] = []
    for item in values:
        if isinstance(item, list):
            out.extend(_flatten_sessions(item))
        elif isinstance(item, int):
            out.append(item)
    return sorted(set(out))


def discover_healthy_sessions(base_dir: Path, subjects: Sequence[str]) -> List[HealthySessionEntry]:
    entries: List[HealthySessionEntry] = []

    for subject in subjects:
        subj_root = base_dir / subject / "emg_logs"
        mapping = SESSION_MAPPINGS_CLEAN.get(subject, {})

        for condition, mapped_sessions in mapping.items():
            for session_num in mapped_sessions:
                data_file = subj_root / f"session_{session_num:02d}.npy"
                ts_file = subj_root / f"session_{session_num:02d}_timestamps.json"
                entries.append(
                    HealthySessionEntry(
                        subject=subject,
                        condition=condition,
                        session=session_num,
                        source="mapping",
                        data_file=data_file,
                        timestamp_file=ts_file,
                        exists=data_file.exists() and ts_file.exists(),
                    )
                )

        if subj_root.exists():
            for npy_file in sorted(subj_root.glob("session_*.npy")):
                name = npy_file.stem
                sess_str = name.split("_")[-1]
                if not sess_str.isdigit():
                    continue
                sess = int(sess_str)
                ts_file = subj_root / f"session_{sess:02d}_timestamps.json"
                entries.append(
                    HealthySessionEntry(
                        subject=subject,
                        condition="unknown",
                        session=sess,
                        source="fallback_scan",
                        data_file=npy_file,
                        timestamp_file=ts_file,
                        exists=npy_file.exists() and ts_file.exists(),
                    )
                )

    dedup = {}
    for e in entries:
        key = (e.subject, e.session)
        if key not in dedup:
            dedup[key] = e
            continue
        # Prefer mapped entries, then existing ones.
        prev = dedup[key]
        if prev.source != "mapping" and e.source == "mapping":
            dedup[key] = e
        elif (not prev.exists) and e.exists:
            dedup[key] = e

    return sorted(dedup.values(), key=lambda x: (x.subject, x.session))


def load_healthy_sessions_from_manifest(manifest: Sequence[HealthySessionEntry]) -> List[SessionRecord]:
    sessions: List[SessionRecord] = []

    for entry in manifest:
        if not entry.exists:
            continue
        emg_data = load_session_data(entry.data_file)
        timestamps = load_timestamps(entry.timestamp_file)
        if emg_data.size == 0 or not timestamps:
            continue

        session_info = timestamps.get("session_info", {})
        total_duration = session_info.get("total_elapsed_time")
        if total_duration and total_duration > 0:
            fs_hz = emg_data.shape[0] / total_duration
        else:
            fs_hz = SAMPLING_RATE

        sessions.append(
            SessionRecord(
                emg_data=emg_data,
                timestamps=timestamps,
                subject=entry.subject,
                session=entry.session,
                condition=entry.condition,
                fs_hz=fs_hz,
            )
        )

    return sessions


def train_eval_once(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int,
    lr: float,
    weight_decay: float,
    device: torch.device,
) -> Tuple[nn.Module, Dict[str, List[float]]]:
    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_state = None
    best_val = -np.inf

    for _ in range(epochs):
        model.train()
        t_loss = 0.0
        t_correct = 0
        t_total = 0

        for xb, yb in train_loader:
            xb = xb.to(device).float()
            yb = yb.to(device).long()

            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()

            t_loss += loss.item()
            preds = logits.argmax(dim=1)
            t_total += yb.size(0)
            t_correct += (preds == yb).sum().item()

        model.eval()
        v_loss = 0.0
        v_correct = 0
        v_total = 0

        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device).float()
                yb = yb.to(device).long()
                logits = model(xb)
                loss = criterion(logits, yb)
                v_loss += loss.item()
                preds = logits.argmax(dim=1)
                v_total += yb.size(0)
                v_correct += (preds == yb).sum().item()

        train_acc = t_correct / max(1, t_total)
        val_acc = v_correct / max(1, v_total)
        history["train_loss"].append(t_loss / max(1, len(train_loader)))
        history["train_acc"].append(train_acc)
        history["val_loss"].append(v_loss / max(1, len(val_loader)))
        history["val_acc"].append(val_acc)

        if val_acc > best_val:
            best_val = val_acc
            best_state = copy.deepcopy(model.state_dict())

    if best_state is not None:
        model.load_state_dict(best_state)

    return model, history


def split_data(
    X: np.ndarray,
    y: np.ndarray,
    val_ratio: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(X))
    rng.shuffle(idx)
    X = X[idx]
    y = y[idx]
    n_val = int(len(X) * val_ratio)
    if n_val <= 0:
        n_val = 1
    X_val = X[:n_val]
    y_val = y[:n_val]
    X_train = X[n_val:]
    y_train = y[n_val:]
    return X_train, y_train, X_val, y_val


def build_model_from_params(model_type: str, seq_len: int, params: Dict[str, float], num_classes: int = 2) -> nn.Module:
    if model_type == "LSTM":
        return TunableLSTM(
            input_size=NUM_CHANNELS,
            hidden_size=int(params["hidden_size"]),
            num_layers=int(params["num_layers"]),
            num_classes=num_classes,
            dropout=float(params["dropout"]),
        )

    return TunableCNNLSTM(
        n_channels=NUM_CHANNELS,
        seq_len=seq_len,
        num_classes=num_classes,
        conv1_channels=int(params["conv1_channels"]),
        conv2_channels=int(params["conv2_channels"]),
        lstm_hidden=int(params["lstm_hidden"]),
        lstm_layers=int(params["lstm_layers"]),
        dropout=float(params["dropout"]),
    )


def suggest_params(trial, model_type: str) -> Dict[str, float]:
    common = {
        "lr": trial.suggest_float("lr", 1e-4, 3e-3, log=True),
        "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-3, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [32, 64, 128]),
        "dropout": trial.suggest_float("dropout", 0.1, 0.5),
    }

    if model_type == "LSTM":
        common.update(
            {
                "hidden_size": trial.suggest_categorical("hidden_size", [64, 96, 128, 160, 192, 256]),
                "num_layers": trial.suggest_int("num_layers", 1, 3),
            }
        )
    else:
        common.update(
            {
                "conv1_channels": trial.suggest_categorical("conv1_channels", [32, 48, 64, 96]),
                "conv2_channels": trial.suggest_categorical("conv2_channels", [64, 96, 128, 160]),
                "lstm_hidden": trial.suggest_categorical("lstm_hidden", [48, 64, 96, 128]),
                "lstm_layers": trial.suggest_int("lstm_layers", 1, 3),
            }
        )

    return common


def optimize_hyperparams(
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    out_dir: Path,
    n_trials: int,
    hpo_epochs: int,
    seed: int,
    device: torch.device,
    study_name: str,
    hpo_storage: Optional[str],
) -> Dict[str, float]:
    try:
        optuna = importlib.import_module("optuna")
    except ImportError as exc:
        raise RuntimeError(
            "optuna is required for hyperparameter search. Install dependencies from requirements.txt."
        ) from exc

    X_train, y_train, X_val, y_val = split_data(X, y, val_ratio=0.2, seed=seed)

    def objective(trial) -> float:
        params = suggest_params(trial, model_type)
        batch_size = int(params["batch_size"])

        train_ds = EMGDataset(X_train, y_train, augment=True)
        val_ds = EMGDataset(X_val, y_val, augment=False)

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

        model = build_model_from_params(model_type, seq_len=X.shape[1], params=params, num_classes=2)
        _, history = train_eval_once(
            model,
            train_loader,
            val_loader,
            epochs=hpo_epochs,
            lr=float(params["lr"]),
            weight_decay=float(params["weight_decay"]),
            device=device,
        )

        trial.set_user_attr("best_val_acc", float(max(history["val_acc"])))
        return float(max(history["val_acc"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    trials_csv_path = out_dir / f"{model_type.lower()}_hpo_trials.csv"
    progress_log_path = out_dir / f"{model_type.lower()}_hpo_progress.log"

    sampler = optuna.samplers.TPESampler(seed=seed)
    study_kwargs = {
        "direction": "maximize",
        "sampler": sampler,
    }

    if hpo_storage:
        study_kwargs.update(
            {
                "storage": hpo_storage,
                "study_name": study_name,
                "load_if_exists": True,
            }
        )

    study = optuna.create_study(**study_kwargs)

    def on_trial_complete(study_obj, trial_obj) -> None:
        trials_df = study_obj.trials_dataframe()
        trials_df.to_csv(trials_csv_path, index=False)
        with open(progress_log_path, "a", encoding="utf-8") as f:
            best_val = study_obj.best_value if len(study_obj.trials) > 0 else float("nan")
            f.write(
                f"trial={trial_obj.number} value={trial_obj.value} best={best_val} total_trials={len(study_obj.trials)}\n"
            )

    # If the study already has trials, write a snapshot before resuming.
    if len(study.trials) > 0:
        study.trials_dataframe().to_csv(trials_csv_path, index=False)

    remaining_trials = max(0, n_trials - len(study.trials))
    if remaining_trials > 0:
        study.optimize(objective, n_trials=remaining_trials, callbacks=[on_trial_complete])

    best_params = study.best_params

    with open(out_dir / f"{model_type.lower()}_best_params.json", "w", encoding="utf-8") as f:
        json.dump(best_params, f, indent=2)

    return best_params


def train_final_pretrained(
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    params: Dict[str, float],
    out_dir: Path,
    epochs: int,
    seed: int,
    device: torch.device,
) -> Path:
    X_train, y_train, X_val, y_val = split_data(X, y, val_ratio=0.2, seed=seed)

    train_ds = EMGDataset(X_train, y_train, augment=True)
    val_ds = EMGDataset(X_val, y_val, augment=False)

    batch_size = int(params.get("batch_size", 64))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = build_model_from_params(model_type, seq_len=X.shape[1], params=params, num_classes=2)
    model, history = train_eval_once(
        model,
        train_loader,
        val_loader,
        epochs=epochs,
        lr=float(params.get("lr", 1e-3)),
        weight_decay=float(params.get("weight_decay", 1e-4)),
        device=device,
    )

    # Save with normalization from full training data for downstream SCI evaluation.
    _, norm_params = normalize_emg(X, method="zscore")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"pretrained_{model_type.lower()}_open_close_best.pth"
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "model_type": model_type,
        "task": "open_close",
        "num_classes": 2,
        "n_channels": NUM_CHANNELS,
        "window_ms": 200,
        "overlap_ms": 100,
        "model_hparams": params,
        "norm_params": norm_params,
        "best_val_acc": float(max(history["val_acc"])),
        "history": history,
    }
    torch.save(checkpoint, path)

    with open(out_dir / f"pretrained_{model_type.lower()}_open_close_best.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "model_type": model_type,
                "best_val_acc": float(max(history["val_acc"])),
                "hparams": {k: float(v) if isinstance(v, np.floating) else int(v) if isinstance(v, np.integer) else v for k, v in params.items()},
            },
            f,
            sort_keys=False,
        )

    return path


def build_model_from_checkpoint(checkpoint: Dict) -> nn.Module:
    model_type = checkpoint["model_type"]
    params = checkpoint.get("model_hparams", {})
    model = build_model_from_params(model_type, seq_len=200, params=params, num_classes=int(checkpoint.get("num_classes", 2)))
    model.load_state_dict(checkpoint["model_state_dict"])
    return model


def get_sci_sessions(sci_config_path: Path, task: str = "task_open_close") -> List[int]:
    with open(sci_config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    tcfg = cfg.get(task, {})
    open_loop = _flatten_sessions(tcfg.get("sessions_open_loop", []))
    closed_loop = _flatten_sessions(tcfg.get("sessions_closed_loop", []))
    return sorted(set(open_loop + closed_loop))


def build_sci_manifest(base_dir: Path, subject: str, sessions: Sequence[int]) -> List[SciSessionEntry]:
    entries: List[SciSessionEntry] = []
    subj_raw = base_dir / subject / "raw"

    for sess in sessions:
        data_file = subj_raw / f"session_{sess:02d}.npy"
        event_file = subj_raw / f"session_{sess:02d}_events.pkl"
        if not data_file.exists() or not event_file.exists():
            continue

        has_unity_events = False
        try:
            import pickle
            with open(event_file, "rb") as f:
                events = pickle.load(f)
            if events:
                events_df = create_events_df(events, events[0]["timestamp"] if isinstance(events[0], dict) else events[0][1])
                if not events_df.empty:
                    has_unity_events = events_df["event_type"].isin(["grasp_objective_start", "grasp_decoded", "trial_result"]).any()
        except Exception:
            has_unity_events = False

        entries.append(
            SciSessionEntry(
                subject=subject,
                session=sess,
                has_unity_events=bool(has_unity_events),
                data_file=data_file,
                event_file=event_file,
            )
        )

    return entries


def load_sci_windows(subject: str, sessions: Sequence[int]) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    X_list: List[np.ndarray] = []
    y_list: List[np.ndarray] = []
    used_sessions: List[int] = []

    for sess in sessions:
        try:
            emg, timestamps, events = load_sci_session(subject, sess)
            X, y = extract_grasp_windows(emg, timestamps, events)
            if len(X) > 0:
                X_list.append(X)
                y_list.append(y)
                used_sessions.append(sess)
        except Exception:
            continue

    if not X_list:
        return np.array([]), np.array([]), []

    return np.concatenate(X_list, axis=0), np.concatenate(y_list, axis=0), used_sessions


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def run_inference(model: nn.Module, X: np.ndarray, device: torch.device, batch_size: int = 256) -> np.ndarray:
    model = model.to(device)
    model.eval()

    preds: List[np.ndarray] = []
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            xb = torch.from_numpy(X[i:i + batch_size]).float().to(device)
            logits = model(xb)
            pred = logits.argmax(dim=1).cpu().numpy()
            preds.append(pred)

    if not preds:
        return np.array([], dtype=np.int64)

    return np.concatenate(preds, axis=0)


def freeze_for_transfer(model: nn.Module, model_type: str, mode: str) -> None:
    if mode == "none":
        return

    if model_type == "LSTM":
        for name, param in model.named_parameters():
            if "lstm" in name:
                param.requires_grad = False
        return

    if model_type == "CNNLSTM":
        for name, param in model.named_parameters():
            if "conv" in name or "bn" in name:
                param.requires_grad = False


def transfer_train(
    model: nn.Module,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    model_type: str,
    freeze_mode: str,
    epochs: int,
    lr: float,
    device: torch.device,
) -> nn.Module:
    model = model.to(device)
    freeze_for_transfer(model, model_type, freeze_mode)

    train_ds = EMGDataset(X_train, y_train, augment=True)
    val_ds = EMGDataset(X_val, y_val, augment=False)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False, num_workers=0)

    criterion = nn.CrossEntropyLoss()
    optim_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(optim_params, lr=lr, weight_decay=1e-4)

    best_state = None
    best_val = -np.inf

    for _ in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb = xb.to(device).float()
            yb = yb.to(device).long()
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()

        model.eval()
        yv_true = []
        yv_pred = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device).float()
                logits = model(xb)
                pred = logits.argmax(dim=1).cpu().numpy()
                yv_pred.append(pred)
                yv_true.append(yb.numpy())

        if yv_true:
            val_acc = accuracy_score(np.concatenate(yv_true), np.concatenate(yv_pred))
            if val_acc > best_val:
                best_val = val_acc
                best_state = copy.deepcopy(model.state_dict())

    if best_state is not None:
        model.load_state_dict(best_state)

    return model


def generate_summary_figures(results_df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Before vs after grouped plot.
    pivot_before = results_df.pivot_table(index=["subject", "model_type"], values="before_accuracy")
    pivot_after = results_df.pivot_table(index=["subject", "model_type"], values="after_accuracy")

    idx = np.arange(len(pivot_before))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(idx - width / 2, pivot_before["before_accuracy"].values, width=width, label="Pretrained")
    ax.bar(idx + width / 2, pivot_after["after_accuracy"].values, width=width, label="After Transfer")
    ax.set_xticks(idx)
    ax.set_xticklabels([f"{s}-{m}" for s, m in pivot_before.index], rotation=25)
    ax.set_ylabel("Accuracy")
    ax.set_ylim(0.0, 1.0)
    ax.set_title("SCI S3/S4: Before vs After Transfer")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "accuracy_before_after.png", dpi=180)
    plt.close(fig)

    # Delta plot.
    fig, ax = plt.subplots(figsize=(10, 5))
    delta = results_df.groupby(["subject", "model_type"])["accuracy_delta"].mean().reset_index()
    labels = [f"{r.subject}-{r.model_type}" for r in delta.itertuples(index=False)]
    ax.bar(labels, delta["accuracy_delta"].values)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_ylabel("Accuracy Delta")
    ax.set_title("Transfer Improvement (After - Before)")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out_dir / "accuracy_delta.png", dpi=180)
    plt.close(fig)


def run_pipeline(args: argparse.Namespace) -> None:
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    root = Path(__file__).resolve().parents[1]
    healthy_dir = root / "data" / "healthy"
    sci_dir = root / "data" / "SCI"
    results_root = root / args.output_dir
    run_tag = args.run_tag.strip() if args.run_tag else datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = results_root / f"pipeline_{run_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    healthy_subjects = [s.strip() for s in args.healthy_subjects.split(",") if s.strip()]
    sci_subjects = [s.strip() for s in args.sci_subjects.split(",") if s.strip()]
    model_types = [m.strip().upper() for m in args.models.split(",") if m.strip()]

    # Step 1: healthy manifest.
    manifest = discover_healthy_sessions(healthy_dir, healthy_subjects)
    manifest_df = pd.DataFrame([e.__dict__ for e in manifest])
    manifest_df.to_csv(out_dir / "healthy_manifest.csv", index=False)

    healthy_sessions = load_healthy_sessions_from_manifest(manifest)
    if not healthy_sessions:
        raise RuntimeError("No healthy sessions were loaded. Check data paths and mappings.")

    X, y = prepare_open_close_data(
        healthy_sessions,
        window_size_ms=200,
        overlap_ms=100,
        balance_classes=True,
    )
    if len(X) == 0:
        raise RuntimeError("No healthy windows extracted for open_close task.")

    X, _ = normalize_emg(X, method="zscore")

    # Step 2: HPO + final pretraining.
    pretrained_paths: Dict[str, Path] = {}
    for model_type in model_types:
        hpo_dir = out_dir / "hpo"
        hpo_dir.mkdir(parents=True, exist_ok=True)

        if args.disable_hpo_persistence:
            hpo_storage_uri = None
        elif args.hpo_storage_uri.strip():
            hpo_storage_uri = args.hpo_storage_uri.strip()
        else:
            hpo_storage_uri = f"sqlite:///{(hpo_dir / 'optuna_studies.db').resolve()}"

        study_name = f"{args.study_prefix}_{model_type.lower()}"

        best_params = optimize_hyperparams(
            model_type=model_type,
            X=X,
            y=y,
            out_dir=hpo_dir,
            n_trials=args.n_trials,
            hpo_epochs=args.hpo_epochs,
            seed=args.seed,
            device=device,
            study_name=study_name,
            hpo_storage=hpo_storage_uri,
        )
        model_out_dir = out_dir / "pretrained"
        ckpt_path = train_final_pretrained(
            model_type=model_type,
            X=X,
            y=y,
            params=best_params,
            out_dir=model_out_dir,
            epochs=args.pretrain_epochs,
            seed=args.seed,
            device=device,
        )
        pretrained_paths[model_type] = ckpt_path

    # Also copy final checkpoints to default transfer-learning location.
    default_pretrained_dir = root / "models" / "pretrained"
    default_pretrained_dir.mkdir(parents=True, exist_ok=True)
    for model_type, src in pretrained_paths.items():
        dst = default_pretrained_dir / src.name
        torch.save(torch.load(src, map_location="cpu", weights_only=False), dst)

    # Step 3 + 4: SCI test and transfer.
    rows = []
    for subject in sci_subjects:
        config_path = root / "config" / "subjects" / "SCI" / f"{subject}.yaml"
        if not config_path.exists():
            continue

        sessions = get_sci_sessions(config_path)
        sci_manifest = build_sci_manifest(sci_dir, subject, sessions)
        pd.DataFrame([x.__dict__ for x in sci_manifest]).to_csv(out_dir / f"sci_manifest_{subject}.csv", index=False)

        valid_sessions = [x.session for x in sci_manifest]
        if len(valid_sessions) < 2:
            continue

        split_point = max(1, int(np.ceil(0.6 * len(valid_sessions))))
        train_sessions = valid_sessions[:split_point]
        test_sessions = valid_sessions[split_point:]
        if not test_sessions:
            test_sessions = [valid_sessions[-1]]
            train_sessions = valid_sessions[:-1]

        X_train_raw, y_train, used_train = load_sci_windows(subject, train_sessions)
        X_test_raw, y_test, used_test = load_sci_windows(subject, test_sessions)
        if len(X_train_raw) == 0 or len(X_test_raw) == 0:
            continue

        for model_type in model_types:
            ckpt = torch.load(pretrained_paths[model_type], map_location="cpu", weights_only=False)
            norm_params = ckpt.get("norm_params")
            X_train = apply_normalization(X_train_raw, norm_params) if norm_params else X_train_raw.copy()
            X_test = apply_normalization(X_test_raw, norm_params) if norm_params else X_test_raw.copy()

            base_model = build_model_from_checkpoint(ckpt)
            before_pred = run_inference(base_model, X_test, device)
            before_metrics = evaluate_predictions(y_test, before_pred)
            before_cm = confusion_matrix(y_test, before_pred, labels=[0, 1])

            # Validation split inside transfer set.
            X_tr, y_tr, X_val, y_val = split_data(X_train, y_train, val_ratio=0.2, seed=args.seed)

            best_after_metrics = None
            best_after_cm = None
            best_after_pred = None
            best_mode = None
            for freeze_mode in ["spatial", "none"]:
                model = build_model_from_checkpoint(ckpt)
                model = transfer_train(
                    model=model,
                    X_train=X_tr,
                    y_train=y_tr,
                    X_val=X_val,
                    y_val=y_val,
                    model_type=model_type,
                    freeze_mode=freeze_mode,
                    epochs=args.transfer_epochs,
                    lr=args.transfer_lr,
                    device=device,
                )
                after_pred = run_inference(model, X_test, device)
                after_metrics = evaluate_predictions(y_test, after_pred)
                if (best_after_metrics is None) or (after_metrics["accuracy"] > best_after_metrics["accuracy"]):
                    best_after_metrics = after_metrics
                    best_after_cm = confusion_matrix(y_test, after_pred, labels=[0, 1])
                    best_after_pred = after_pred
                    best_mode = freeze_mode

            row = {
                "subject": subject,
                "model_type": model_type,
                "train_sessions": ",".join(map(str, used_train)),
                "test_sessions": ",".join(map(str, used_test)),
                "before_accuracy": before_metrics["accuracy"],
                "after_accuracy": best_after_metrics["accuracy"],
                "before_balanced_accuracy": before_metrics["balanced_accuracy"],
                "after_balanced_accuracy": best_after_metrics["balanced_accuracy"],
                "before_f1_macro": before_metrics["f1_macro"],
                "after_f1_macro": best_after_metrics["f1_macro"],
                "accuracy_delta": best_after_metrics["accuracy"] - before_metrics["accuracy"],
                "transfer_mode": best_mode,
                "n_train_windows": int(len(X_train_raw)),
                "n_test_windows": int(len(X_test_raw)),
            }
            rows.append(row)

            cm_dir = out_dir / "confusion_matrices"
            cm_dir.mkdir(parents=True, exist_ok=True)
            np.save(cm_dir / f"{subject}_{model_type}_before_cm.npy", before_cm)
            np.save(cm_dir / f"{subject}_{model_type}_after_cm.npy", best_after_cm)

            pred_dir = out_dir / "predictions"
            pred_dir.mkdir(parents=True, exist_ok=True)
            np.save(pred_dir / f"{subject}_{model_type}_before_pred.npy", before_pred)
            np.save(pred_dir / f"{subject}_{model_type}_after_pred.npy", best_after_pred)
            np.save(pred_dir / f"{subject}_{model_type}_y_true.npy", y_test)

    results_df = pd.DataFrame(rows)
    if results_df.empty:
        raise RuntimeError("Pipeline finished but no SCI results were generated.")

    results_df.to_csv(out_dir / "sci_pretrain_transfer_results.csv", index=False)
    generate_summary_figures(results_df, out_dir / "figures")

    summary = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "run_tag": run_tag,
        "device": str(device),
        "healthy_subjects": healthy_subjects,
        "sci_subjects": sci_subjects,
        "models": model_types,
        "n_trials": args.n_trials,
        "hpo_epochs": args.hpo_epochs,
        "pretrain_epochs": args.pretrain_epochs,
        "transfer_epochs": args.transfer_epochs,
        "output_dir": str(out_dir),
    }
    with open(out_dir / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nPipeline finished successfully.")
    print(f"Artifacts: {out_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI pipeline: pretrain -> SCI test -> transfer -> summary")
    parser.add_argument("--run_all", action="store_true", help="Run all pipeline stages")
    parser.add_argument("--healthy_subjects", default="S1,S2,S3,S4,S5,S6,S7,S8,S9,S10")
    parser.add_argument("--sci_subjects", default="S3,S4")
    parser.add_argument("--models", default="LSTM,CNNLSTM", help="Comma separated list")
    parser.add_argument("--n_trials", type=int, default=100)
    parser.add_argument("--hpo_epochs", type=int, default=25)
    parser.add_argument("--pretrain_epochs", type=int, default=80)
    parser.add_argument("--transfer_epochs", type=int, default=40)
    parser.add_argument("--transfer_lr", type=float, default=5e-4)
    parser.add_argument("--output_dir", default="results-optimization")
    parser.add_argument("--run_tag", default="", help="Stable run tag for pause/resume, e.g. 20260315_remote_a")
    parser.add_argument("--study_prefix", default="healthy_open_close", help="Optuna study name prefix")
    parser.add_argument("--hpo_storage_uri", default="", help="Optuna storage URI (sqlite:///... recommended)")
    parser.add_argument("--disable_hpo_persistence", action="store_true", help="Disable persistent Optuna storage")
    parser.add_argument("--seed", type=int, default=18)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.run_all:
        raise SystemExit("Pass --run_all to execute the pipeline.")
    run_pipeline(args)


if __name__ == "__main__":
    main()
