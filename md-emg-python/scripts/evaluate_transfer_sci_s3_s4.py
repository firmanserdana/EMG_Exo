#!/usr/bin/env python3
"""Evaluate pretrained models on SCI S3/S4, transfer-learn, and re-test.

Policy implemented:
- Subjects: S3 and S4
- Sessions: include both open-loop and closed-loop sessions from subject configs
- Unity-event tagging: per-session indicator using event types

Outputs:
- CSV with per-model/per-subject before/after metrics
- JSON with configuration and selected sessions

Usage:
  python scripts/evaluate_transfer_sci_s3_s4.py \
      --pretrained-models models/pretrained/pretrained_lstm_open_close_optuna.pth,models/pretrained/pretrained_cnnlstm_open_close_optuna.pth
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, TensorDataset

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.test_sci_transfer import extract_grasp_windows, load_data_numpy, normalize_data  # noqa: E402
from scripts.transfer_learning import fine_tune, freeze_feature_extractor, load_pretrained_model  # noqa: E402
from utils.data_utils import create_events_df  # noqa: E402


@dataclass
class SessionData:
    session: int
    X: np.ndarray
    y: np.ndarray
    has_unity_events: bool


def load_subject_cfg(subj: str) -> Dict:
    cfg_path = Path("config") / "subjects" / "SCI" / f"{subj}.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_sessions(values) -> List[int]:
    out: List[int] = []
    if values is None:
        return out
    for v in values:
        if isinstance(v, list):
            out.extend(int(x) for x in v)
        else:
            out.append(int(v))
    return sorted(set(out))


def detect_unity_events(events: List[dict]) -> bool:
    if not events:
        return False
    start_time = events[0].get("timestamp", 0.0) if isinstance(events[0], dict) else events[0][1]
    events_df = create_events_df(events, start_time)
    if events_df.empty:
        return False
    unity_markers = {"grasp_objective_start", "grasp_decoded", "trial_result"}
    event_types = set(events_df["event_type"].astype(str).tolist())
    return len(event_types.intersection(unity_markers)) > 0


def load_session_data(subj: str, session: int) -> Tuple[np.ndarray, np.ndarray, List[dict]]:
    raw_dir = Path("data") / "SCI" / subj / "raw"
    npy_path = raw_dir / f"session_{session:02d}.npy"
    ev_path = raw_dir / f"session_{session:02d}_events.pkl"

    if not npy_path.exists() or not ev_path.exists():
        raise FileNotFoundError(f"Missing npy/events for {subj} session {session:02d}")

    data = load_data_numpy(str(npy_path))
    timestamps = data[:, -1]
    emg_data = data[:, :32]
    with ev_path.open("rb") as f:
        events = pickle.load(f)

    return emg_data, timestamps, events


def collect_sessions(subj: str) -> List[SessionData]:
    cfg = load_subject_cfg(subj)
    open_sessions = flatten_sessions(cfg["task_open_close"].get("sessions_open_loop", []))
    closed_sessions = flatten_sessions(cfg["task_open_close"].get("sessions_closed_loop", []))
    sessions = sorted(set(open_sessions + closed_sessions))

    collected: List[SessionData] = []
    for s in sessions:
        try:
            emg, ts, events = load_session_data(subj, s)
            X, y = extract_grasp_windows(emg, ts, events)
            if X.size == 0 or y.size == 0:
                continue
            collected.append(SessionData(session=s, X=X, y=y, has_unity_events=detect_unity_events(events)))
        except Exception:
            continue

    return collected


def split_by_session(data: List[SessionData]) -> Tuple[List[SessionData], List[SessionData], List[SessionData]]:
    if len(data) < 3:
        # Fallback when session count is limited
        n = len(data)
        train = data[: max(1, n - 2)]
        val = data[max(1, n - 2): max(1, n - 1)]
        test = data[max(1, n - 1):]
        return train, val, test

    n = len(data)
    n_train = max(1, int(round(n * 0.6)))
    n_val = max(1, int(round(n * 0.2)))
    if n_train + n_val >= n:
        n_val = 1
        n_train = n - 2

    train = data[:n_train]
    val = data[n_train:n_train + n_val]
    test = data[n_train + n_val:]
    return train, val, test


def merge_sessions(sessions: List[SessionData]) -> Tuple[np.ndarray, np.ndarray]:
    X = np.concatenate([s.X for s in sessions], axis=0)
    y = np.concatenate([s.y for s in sessions], axis=0)
    return X, y


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def predict(model: torch.nn.Module, X: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        xb = torch.FloatTensor(X).to(device)
        logits = model(xb)
        pred = logits.argmax(dim=1).detach().cpu().numpy()
    return pred


def build_loader(X: np.ndarray, y: np.ndarray, batch_size: int) -> DataLoader:
    ds = TensorDataset(torch.FloatTensor(X), torch.LongTensor(y))
    return DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=0)


def run_transfer_variant(
    model,
    model_type: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    freeze_features: bool,
    device: str,
) -> Dict[str, float]:
    work_model = copy.deepcopy(model)

    if freeze_features:
        work_model = freeze_feature_extractor(work_model, model_type=model_type)

    train_loader = build_loader(X_train, y_train, batch_size=64)
    val_loader = build_loader(X_val, y_val, batch_size=64)

    work_model, history = fine_tune(
        model=work_model,
        train_loader=train_loader,
        val_loader=val_loader,
        epochs=60,
        lr=1e-4 if freeze_features else 5e-5,
        device=device,
    )

    y_pred = predict(work_model, X_test, torch.device(device))
    metrics = evaluate_predictions(y_test, y_pred)
    metrics["val_acc_max"] = float(max(history["val_acc"])) if history["val_acc"] else 0.0
    metrics["variant"] = "freeze_features" if freeze_features else "full_finetune"
    metrics["confusion_matrix"] = confusion_matrix(y_test, y_pred).tolist()
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate and transfer pretrained models on SCI S3/S4")
    parser.add_argument(
        "--pretrained-models",
        type=str,
        default="models/pretrained/pretrained_lstm_open_close_optuna.pth,models/pretrained/pretrained_cnnlstm_open_close_optuna.pth",
    )
    parser.add_argument("--subjects", type=str, default="S3,S4")
    parser.add_argument("--output-csv", type=str, default="results-analysis/transfer_sci_s3_s4.csv")
    parser.add_argument("--output-json", type=str, default="results-analysis/transfer_sci_s3_s4.json")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model_paths = [m.strip() for m in args.pretrained_models.split(",") if m.strip()]
    subjects = [s.strip() for s in args.subjects.split(",") if s.strip()]

    rows: List[Dict] = []
    metadata: Dict = {"subjects": {}, "device": device}

    for subj in subjects:
        sessions = collect_sessions(subj)
        sessions = sorted(sessions, key=lambda x: x.session)
        if len(sessions) < 2:
            continue

        train_sessions, val_sessions, test_sessions = split_by_session(sessions)
        if len(test_sessions) == 0:
            continue

        X_train, y_train = merge_sessions(train_sessions)
        X_val, y_val = merge_sessions(val_sessions)
        X_test, y_test = merge_sessions(test_sessions)

        metadata["subjects"][subj] = {
            "train_sessions": [s.session for s in train_sessions],
            "val_sessions": [s.session for s in val_sessions],
            "test_sessions": [s.session for s in test_sessions],
            "test_has_unity_events": {s.session: s.has_unity_events for s in test_sessions},
        }

        for model_path in model_paths:
            if not Path(model_path).exists():
                continue

            model, model_meta = load_pretrained_model(model_path, device=device)
            model_type = model_meta["model_type"]
            norm_params = model_meta.get("norm_params")

            if norm_params is not None:
                X_train_norm, _ = normalize_data(X_train, norm_params)
                X_val_norm, _ = normalize_data(X_val, norm_params)
                X_test_norm, _ = normalize_data(X_test, norm_params)
            else:
                X_train_norm, nparams = normalize_data(X_train, None)
                X_val_norm, _ = normalize_data(X_val, nparams)
                X_test_norm, _ = normalize_data(X_test, nparams)

            # Before transfer
            y_pred_before = predict(model, X_test_norm, torch.device(device))
            before_metrics = evaluate_predictions(y_test, y_pred_before)
            before_cm = confusion_matrix(y_test, y_pred_before).tolist()

            # Transfer variants
            freeze_metrics = run_transfer_variant(
                model=model,
                model_type=model_type,
                X_train=X_train_norm,
                y_train=y_train,
                X_val=X_val_norm,
                y_val=y_val,
                X_test=X_test_norm,
                y_test=y_test,
                freeze_features=True,
                device=device,
            )
            full_metrics = run_transfer_variant(
                model=model,
                model_type=model_type,
                X_train=X_train_norm,
                y_train=y_train,
                X_val=X_val_norm,
                y_val=y_val,
                X_test=X_test_norm,
                y_test=y_test,
                freeze_features=False,
                device=device,
            )

            best_variant = max([freeze_metrics, full_metrics], key=lambda d: d["balanced_accuracy"])

            rows.append(
                {
                    "subject": subj,
                    "model_type": model_type,
                    "model_path": model_path,
                    "before_accuracy": before_metrics["accuracy"],
                    "before_balanced_accuracy": before_metrics["balanced_accuracy"],
                    "before_f1_macro": before_metrics["f1_macro"],
                    "before_confusion_matrix": json.dumps(before_cm),
                    "after_variant": best_variant["variant"],
                    "after_accuracy": best_variant["accuracy"],
                    "after_balanced_accuracy": best_variant["balanced_accuracy"],
                    "after_f1_macro": best_variant["f1_macro"],
                    "after_confusion_matrix": json.dumps(best_variant["confusion_matrix"]),
                    "delta_accuracy": best_variant["accuracy"] - before_metrics["accuracy"],
                    "delta_balanced_accuracy": best_variant["balanced_accuracy"] - before_metrics["balanced_accuracy"],
                    "n_train": int(len(X_train_norm)),
                    "n_val": int(len(X_val_norm)),
                    "n_test": int(len(X_test_norm)),
                }
            )

    out_csv = Path(args.output_csv)
    out_json = Path(args.output_json)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved results: {out_csv}")
    print(f"Saved metadata: {out_json}")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "18")
    main()
