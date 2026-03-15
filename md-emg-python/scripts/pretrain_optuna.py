#!/usr/bin/env python3
"""Optuna pretraining for healthy S1-S10 on open_close task.

Runs thorough HPO (default 100+ trials/model), then trains final models and saves
portable checkpoints for transfer learning.

Usage:
  python scripts/pretrain_optuna.py \
    --manifest manifests/healthy_pretrain_manifest.json \
    --models LSTM,CNNLSTM \
    --n-trials 120
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import yaml
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.pretrain_healthy import (  # noqa: E402
    EMGDataset,
    NUM_CHANNELS,
    SAMPLING_RATE,
    SessionRecord,
    build_cnn_lstm_model,
    build_lstm_model,
    load_session_data,
    load_timestamps,
    normalize_emg,
    prepare_open_close_data,
)


def import_optuna():
    try:
        import optuna

        return optuna
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Optuna is required. Install with: pip install optuna"
        ) from exc


def load_manifest(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "entries" not in data:
        raise ValueError("Invalid manifest: missing 'entries'")
    return data


def load_sessions_from_manifest(manifest: Dict) -> List[SessionRecord]:
    sessions: List[SessionRecord] = []
    for e in manifest["entries"]:
        npy_path = Path(e["npy_path"])
        ts_path = Path(e["timestamps_path"])
        if not npy_path.exists() or not ts_path.exists():
            continue

        emg_data = load_session_data(npy_path)
        timestamps = load_timestamps(ts_path)
        if emg_data.size == 0:
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
                subject=e["subject"],
                session=int(e["session"]),
                condition=e["condition"],
                fs_hz=fs_hz,
            )
        )

    return sessions


def build_model(model_type: str, params: Dict, seq_len: int, num_classes: int):
    if model_type == "LSTM":
        return build_lstm_model(
            input_size=NUM_CHANNELS,
            hidden_size=int(params["hidden_size"]),
            num_layers=int(params["num_layers"]),
            num_classes=num_classes,
            dropout=float(params["dropout"]),
        )

    if model_type == "CNNLSTM":
        return build_cnn_lstm_model(
            n_channels=NUM_CHANNELS,
            seq_len=seq_len,
            num_classes=num_classes,
            dropout=float(params["dropout"]),
        )

    raise ValueError(f"Unsupported model type: {model_type}")


def suggest_params(trial, model_type: str) -> Dict:
    params = {
        "lr": trial.suggest_float("lr", 1e-5, 5e-3, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [32, 64, 128]),
        "dropout": trial.suggest_float("dropout", 0.1, 0.5),
        "epochs": trial.suggest_int("epochs", 40, 120, step=20),
    }
    if model_type == "LSTM":
        params.update(
            {
                "hidden_size": trial.suggest_categorical("hidden_size", [64, 96, 128, 192, 256]),
                "num_layers": trial.suggest_int("num_layers", 1, 3),
            }
        )
    else:
        params.update({"hidden_size": 64, "num_layers": 2})

    return params


def train_one_trial(
    model: nn.Module,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    lr: float,
    batch_size: int,
    epochs: int,
    device: torch.device,
) -> Tuple[float, Dict]:
    train_ds = EMGDataset(X_train, y_train, augment=True, noise_factor=0.1, channel_dropout=0.1)
    val_ds = EMGDataset(X_val, y_val, augment=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)

    best_val_acc = 0.0
    best_state = None
    history = {"train_acc": [], "val_acc": [], "train_loss": [], "val_loss": []}

    for _ in range(epochs):
        model.train()
        tr_correct = 0
        tr_total = 0
        tr_loss = 0.0

        for xb, yb in train_loader:
            xb = xb.to(device).float()
            yb = yb.to(device).long()

            optimizer.zero_grad()
            out = model(xb)
            loss = criterion(out, yb)
            loss.backward()
            optimizer.step()

            tr_loss += float(loss.item())
            pred = out.argmax(dim=1)
            tr_correct += int((pred == yb).sum().item())
            tr_total += int(yb.size(0))

        train_acc = tr_correct / max(tr_total, 1)
        train_loss = tr_loss / max(len(train_loader), 1)

        model.eval()
        va_correct = 0
        va_total = 0
        va_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device).float()
                yb = yb.to(device).long()
                out = model(xb)
                loss = criterion(out, yb)
                va_loss += float(loss.item())
                pred = out.argmax(dim=1)
                va_correct += int((pred == yb).sum().item())
                va_total += int(yb.size(0))

        val_acc = va_correct / max(va_total, 1)
        val_loss = va_loss / max(len(val_loader), 1)

        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = copy.deepcopy(model.state_dict())

    if best_state is not None:
        model.load_state_dict(best_state)

    return best_val_acc, history


def main() -> None:
    parser = argparse.ArgumentParser(description="Optuna pretraining on healthy data")
    parser.add_argument("--manifest", type=str, default="manifests/healthy_pretrain_manifest.json")
    parser.add_argument("--models", type=str, default="LSTM,CNNLSTM")
    parser.add_argument("--n-trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=18)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--output-dir", type=str, default="models/pretrained")
    parser.add_argument("--study-dir", type=str, default="results-optimization/pretrain_optuna")
    parser.add_argument("--task", type=str, default="open_close")
    args = parser.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    optuna = import_optuna()

    manifest = load_manifest(Path(args.manifest))
    sessions = load_sessions_from_manifest(manifest)
    if not sessions:
        raise SystemExit("No valid sessions available from manifest.")

    X, y = prepare_open_close_data(sessions, balance_classes=True)
    if X.size == 0 or y.size == 0:
        raise SystemExit("Could not extract windows for open_close task from manifest sessions.")

    X, norm_params = normalize_emg(X, method="zscore")

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=y,
    )

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    output_dir = Path(args.output_dir)
    study_dir = Path(args.study_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    study_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seq_len = X.shape[1]
    num_classes = int(len(np.unique(y)))

    summary = {"task": args.task, "models": {}, "manifest": args.manifest}

    for model_type in models:
        print("=" * 70)
        print(f"Running Optuna for {model_type} with {args.n_trials} trials")
        print("=" * 70)

        def objective(trial):
            params = suggest_params(trial, model_type=model_type)
            model = build_model(model_type, params, seq_len=seq_len, num_classes=num_classes)
            best_val_acc, _ = train_one_trial(
                model=model,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                lr=float(params["lr"]),
                batch_size=int(params["batch_size"]),
                epochs=int(params["epochs"]),
                device=device,
            )
            return best_val_acc

        study = optuna.create_study(direction="maximize", study_name=f"{model_type}_healthy_{args.task}")
        study.optimize(objective, n_trials=args.n_trials)

        best_params = dict(study.best_params)
        best_model = build_model(model_type, best_params, seq_len=seq_len, num_classes=num_classes)
        best_val_acc, history = train_one_trial(
            model=best_model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            lr=float(best_params["lr"]),
            batch_size=int(best_params["batch_size"]),
            epochs=int(best_params["epochs"]),
            device=device,
        )

        checkpoint = {
            "model_state_dict": best_model.state_dict(),
            "model_type": model_type,
            "task": args.task,
            "num_classes": num_classes,
            "n_channels": NUM_CHANNELS,
            "window_ms": 200,
            "overlap_ms": 100,
            "norm_params": norm_params,
            "subjects": sorted({e["subject"] for e in manifest["entries"]}),
            "conditions": sorted({e["condition"] for e in manifest["entries"]}),
            "best_val_acc": float(best_val_acc),
            "best_params": best_params,
            "history": history,
            "manifest_path": args.manifest,
        }

        ckpt_name = f"pretrained_{model_type.lower()}_{args.task}_optuna.pth"
        ckpt_path = output_dir / ckpt_name
        torch.save(checkpoint, ckpt_path)

        trials_df = study.trials_dataframe()
        trials_csv = study_dir / f"{model_type.lower()}_{args.task}_trials.csv"
        trials_df.to_csv(trials_csv, index=False)

        best_yaml = study_dir / f"{model_type.lower()}_{args.task}_best_params.yaml"
        with best_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(best_params, f, sort_keys=False)

        summary["models"][model_type] = {
            "checkpoint": str(ckpt_path),
            "trials_csv": str(trials_csv),
            "best_params_yaml": str(best_yaml),
            "best_val_acc": float(best_val_acc),
            "n_trials": int(args.n_trials),
        }

    summary_path = study_dir / "pretrain_optuna_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
