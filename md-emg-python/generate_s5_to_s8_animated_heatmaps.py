"""
Generate animated EMG spatial heatmaps for SCI subjects S5 to S8.

Each animation shows the 32-channel EMG heatmap evolving over time,
with a gesture label overlay (from events or predictions files when
available). Saved as MP4 (ffmpeg) with GIF fallback.

When prediction files are present, this script also checks prediction
accuracy against events-derived labels (if events exist for that session).

Usage:
    python generate_s5_to_s8_animated_heatmaps.py
    python generate_s5_to_s8_animated_heatmaps.py S6
    python generate_s5_to_s8_animated_heatmaps.py S5,S7 1 4
"""

import sys
import pickle
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use('Agg')  # Non-interactive backend for rendering

import matplotlib.pyplot as plt
from matplotlib import cm, colors as mcolors
from matplotlib.animation import FuncAnimation

from emg_comparative_analysis import (
    DEFAULT_FS_HZ,
    NUM_CHANNELS,
    draw_svg_heatmap,
    get_svg_heatmap_layout,
)

DATA_ROOT = Path(__file__).parent / 'data' / 'SCI'
OUTPUT_ROOT = Path(__file__).parent / 'results-analysis'

DEFAULT_SUBJECTS = ['S5', 'S6', 'S7', 'S8']

GESTURE_NAMES = {0: 'Open', 1: 'Close', -1: 'Rest'}
PHASE_NAMES = {0: 'Rest', 1: 'Grasping', 2: 'Holding', 3: 'Releasing'}
# Phase encoding: 0=rest, 1=grasp_start->hold_start, 2=hold_start->hold_end, 3=hold_end->released

# Animation parameters
RMS_WINDOW_MS = 200            # RMS window size in ms
ACTIVE_FRAME_STEP_MS = 250     # Smaller step -> slower playback in active grasp phases
REST_FRAME_STEP_MS = 1000      # Larger step -> fast-forward playback in rest phases
FPS = 10                       # Output video frame rate


# Data loading ----------------------------------------------------------------

def load_session(session_file: Path) -> np.ndarray:
    """Load a multi-array .npy session file (concatenated streaming buffers)."""
    arrays = []
    with open(session_file, 'rb') as f:
        while True:
            try:
                arrays.append(np.load(f, allow_pickle=False))
            except (ValueError, EOFError):
                break
    if not arrays:
        return np.empty((0, NUM_CHANNELS + 1), dtype=float)
    return np.concatenate(arrays, axis=0)


def load_events(data_dir: Path, session_idx: int):
    """Load events file if it exists. Returns list of event dicts or None."""
    events_file = data_dir / f'session_{session_idx:02d}_events.pkl'
    if not events_file.exists():
        return None
    with open(events_file, 'rb') as f:
        events = pickle.load(f)
    return events if events else None


def load_predictions(data_dir: Path, session_idx: int):
    """Load all prediction chunks for a session.

    Prediction files are stored as a pickle stream with multiple chunks.
    Returns a single concatenated ndarray, an empty ndarray if file exists
    but has no predictions, or None if file is missing.
    """
    pred_file = data_dir / f'session_{session_idx:02d}_predictions.pkl'
    if not pred_file.exists():
        return None

    chunks = []
    with open(pred_file, 'rb') as f:
        while True:
            try:
                chunk = np.asarray(pickle.load(f))
            except EOFError:
                break

            if chunk.size == 0:
                continue
            if chunk.ndim == 1:
                chunk = np.atleast_2d(chunk)
            chunks.append(chunk)

    if not chunks:
        return np.empty((0, 2), dtype=float)

    return np.concatenate(chunks, axis=0)


def extract_prediction_classes(preds) -> np.ndarray:
    """Extract predicted class ids from either class-scores or (label, confidence) rows."""
    preds_arr = np.asarray(preds)
    if preds_arr.size == 0:
        return np.array([], dtype=int)

    if preds_arr.ndim == 1:
        return preds_arr.astype(int)

    if preds_arr.shape[1] >= 2:
        pred_labels = preds_arr[:, 0]
        pred_conf = preds_arr[:, 1]
        labels_integer_like = np.all(np.abs(pred_labels - np.round(pred_labels)) < 1e-6)
        conf_probability_like = np.all((pred_conf >= 0.0) & (pred_conf <= 1.0))
        if labels_integer_like and conf_probability_like:
            return np.round(pred_labels).astype(int)

    return np.argmax(preds_arr, axis=1).astype(int)


def available_sessions(data_dir: Path):
    """Return sorted list of session indices found in a subject raw directory."""
    sessions = []
    for npy_file in data_dir.glob('session_*.npy'):
        try:
            sessions.append(int(npy_file.stem.split('_')[-1]))
        except ValueError:
            continue
    return sorted(set(sessions))


# Build per-sample gesture label arrays ---------------------------------------

def build_gesture_timeline_from_events(events, timestamps_col: np.ndarray):
    """Create per-sample gesture and phase labels from events.

    Returns:
        gesture_labels: array of int, -1=rest, 0=open, 1=close
        phase_labels:   array of int, 0=rest, 1=grasping, 2=holding, 3=releasing
    """
    n = len(timestamps_col)
    gesture_labels = np.full(n, -1, dtype=int)
    phase_labels = np.zeros(n, dtype=int)  # 0 = rest

    current_gesture = -1
    grasp_start_ts = None
    hold_start_ts = None
    hold_end_ts = None

    for evt in events:
        etype = evt.get('event_type', '')
        ets = evt.get('timestamp')
        if ets is None:
            continue

        if etype.startswith('grasp_start_'):
            try:
                current_gesture = int(etype.split('_')[-1])
            except ValueError:
                current_gesture = -1
            grasp_start_ts = ets
        elif etype == 'grasp_hold_start' and grasp_start_ts is not None and current_gesture >= 0:
            # Phase 1: grasping (grasp_start -> hold_start)
            mask = (timestamps_col >= grasp_start_ts) & (timestamps_col < ets)
            gesture_labels[mask] = current_gesture
            phase_labels[mask] = 1
            hold_start_ts = ets
        elif etype == 'grasp_hold_end' and hold_start_ts is not None and current_gesture >= 0:
            # Phase 2: holding (hold_start -> hold_end)
            mask = (timestamps_col >= hold_start_ts) & (timestamps_col <= ets)
            gesture_labels[mask] = current_gesture
            phase_labels[mask] = 2
            hold_end_ts = ets
            hold_start_ts = None
        elif etype == 'grasp_released' and hold_end_ts is not None and current_gesture >= 0:
            # Phase 3: releasing (hold_end -> released)
            mask = (timestamps_col > hold_end_ts) & (timestamps_col <= ets)
            gesture_labels[mask] = current_gesture
            phase_labels[mask] = 3
            grasp_start_ts = None
            hold_end_ts = None

    return gesture_labels, phase_labels


def build_gesture_timeline_from_predictions(preds, n_samples: int):
    """Create per-sample gesture and phase labels from prediction windows.

    Returns:
        gesture_labels: array of int, 0=open, 1=close
        phase_labels:   array of int (all set to 2='holding' for predicted windows)
    """
    pred_classes = extract_prediction_classes(preds)
    if pred_classes.size == 0:
        return np.full(n_samples, -1, dtype=int), np.zeros(n_samples, dtype=int)

    n_preds = len(pred_classes)
    if n_preds == 0:
        return np.full(n_samples, -1, dtype=int), np.zeros(n_samples, dtype=int)

    samples_per_pred = max(1, n_samples // n_preds)

    gesture_labels = np.full(n_samples, -1, dtype=int)
    phase_labels = np.zeros(n_samples, dtype=int)
    for i, cls in enumerate(pred_classes):
        start = i * samples_per_pred
        end = min(start + samples_per_pred, n_samples)
        gesture_labels[start:end] = int(cls)
        phase_labels[start:end] = 2  # predicted = treated as hold

    return gesture_labels, phase_labels


def compute_prediction_accuracy(pred_labels: np.ndarray, event_labels: np.ndarray):
    """Compute prediction accuracy against events-derived labels.

    Returns None if there is no overlap of valid labels.
    """
    valid = np.isin(pred_labels, [0, 1]) & np.isin(event_labels, [0, 1])
    n_valid = int(np.sum(valid))
    if n_valid == 0:
        return None

    pred_valid = pred_labels[valid]
    event_valid = event_labels[valid]
    overall = float(np.mean(pred_valid == event_valid))

    per_class = {}
    for gid in [0, 1]:
        class_mask = event_valid == gid
        class_count = int(np.sum(class_mask))
        class_acc = float(np.mean(pred_valid[class_mask] == gid)) if class_count > 0 else np.nan
        per_class[gid] = {'count': class_count, 'accuracy': class_acc}

    confusion = np.zeros((2, 2), dtype=int)
    for gt in [0, 1]:
        for pd in [0, 1]:
            confusion[gt, pd] = int(np.sum((event_valid == gt) & (pred_valid == pd)))

    return {
        'n_valid': n_valid,
        'overall': overall,
        'per_class': per_class,
        'confusion': confusion,
    }


# RMS computation --------------------------------------------------------------

def compute_windowed_rms(emg_data: np.ndarray, center_idx: int, half_window: int) -> np.ndarray:
    """Compute RMS per channel for a window centered at center_idx."""
    start = max(0, center_idx - half_window)
    end = min(emg_data.shape[0], center_idx + half_window)
    window = emg_data[start:end]
    if window.shape[0] == 0:
        return np.zeros(emg_data.shape[1])
    return np.sqrt(np.mean(window ** 2, axis=0))


# Precompute all frames --------------------------------------------------------

def precompute_frames(emg_data: np.ndarray, gesture_labels: np.ndarray,
                      phase_labels: np.ndarray, timestamps: np.ndarray):
    """Precompute RMS values and metadata for every frame."""
    half_window = max(1, int(RMS_WINDOW_MS * DEFAULT_FS_HZ / 1000) // 2)
    active_step_samples = max(1, int(ACTIVE_FRAME_STEP_MS * DEFAULT_FS_HZ / 1000))
    rest_step_samples = max(1, int(REST_FRAME_STEP_MS * DEFAULT_FS_HZ / 1000))
    n_samples = emg_data.shape[0]
    t0 = timestamps[0]

    frames = []
    center = 0
    while center < n_samples:
        rms = compute_windowed_rms(emg_data, center, half_window)
        t = timestamps[min(center, n_samples - 1)] - t0
        win_start = max(0, center - half_window)
        win_end = min(n_samples, center + half_window)

        # Majority vote for gesture label
        lbl_window = gesture_labels[win_start:win_end]
        active = lbl_window[lbl_window >= 0]
        if len(active) > len(lbl_window) * 0.3:
            gesture = int(np.bincount(active).argmax())
        else:
            gesture = -1

        # Majority vote for phase
        ph_window = phase_labels[win_start:win_end]
        phase = int(np.bincount(ph_window).argmax()) if len(ph_window) > 0 else 0

        frames.append({
            'rms': rms,
            'time': t,
            'gesture_label': gesture,
            'gesture_name': GESTURE_NAMES.get(gesture, 'Rest'),
            'phase': phase,
            'phase_name': PHASE_NAMES.get(phase, ''),
        })

        step_samples = active_step_samples if phase > 0 else rest_step_samples
        center += step_samples

    return frames


# Animation rendering ----------------------------------------------------------

GESTURE_COLORS = {-1: '#888888', 0: '#2196F3', 1: '#F44336'}
PHASE_COLORS = {
    0: '#888888',   # rest - gray
    1: '#FF9800',   # grasping - orange
    2: '#4CAF50',   # holding - green
    3: '#9C27B0',   # releasing - purple
}


def create_session_animation(subject: str, session_idx: int, data_dir: Path, output_dir: Path):
    """Build and save an animated heatmap for a single session."""
    npy_file = data_dir / f'session_{session_idx:02d}.npy'
    if not npy_file.exists():
        print(f'  Session {session_idx:02d}: npy file not found, skipping.')
        return

    print(f'  Session {session_idx:02d}: loading data ...')
    data = load_session(npy_file)
    if data.size == 0 or data.shape[1] <= NUM_CHANNELS:
        print(f'    Session {session_idx:02d}: invalid/empty data, skipping.')
        return

    emg = data[:, :NUM_CHANNELS]
    timestamps = data[:, NUM_CHANNELS]
    duration = timestamps[-1] - timestamps[0]
    print(f'    {emg.shape[0]} samples, {duration:.1f}s')

    # Build labels from events and/or predictions
    events = load_events(data_dir, session_idx)
    preds = load_predictions(data_dir, session_idx)

    event_labels = None
    event_phases = None
    pred_labels = None
    pred_phases = None

    if events is not None:
        event_labels, event_phases = build_gesture_timeline_from_events(events, timestamps)

    if preds is not None:
        pred_labels, pred_phases = build_gesture_timeline_from_predictions(preds, emg.shape[0])

    if event_labels is not None:
        gesture_labels, phase_labels = event_labels, event_phases
        label_source = 'events'
    elif pred_labels is not None:
        gesture_labels, phase_labels = pred_labels, pred_phases
        label_source = 'predictions'
    else:
        gesture_labels = np.full(emg.shape[0], -1, dtype=int)
        phase_labels = np.zeros(emg.shape[0], dtype=int)
        label_source = 'none'

    n_open = int(np.sum(gesture_labels == 0))
    n_close = int(np.sum(gesture_labels == 1))
    print(f'    Label source: {label_source} - Open: {n_open} samples, Close: {n_close} samples')

    pred_acc_info = None
    if pred_labels is not None and event_labels is not None:
        pred_acc_info = compute_prediction_accuracy(pred_labels, event_labels)
        if pred_acc_info is None:
            print('    Prediction accuracy: unavailable (no overlapping labeled samples).')
        else:
            conf = pred_acc_info['confusion']
            print(
                f"    Prediction accuracy vs events: {pred_acc_info['overall'] * 100:.2f}% "
                f"(n={pred_acc_info['n_valid']} samples)"
            )
            print(
                '      Confusion [gt rows: Open, Close | pred cols: Open, Close]: '
                f'[[{conf[0, 0]}, {conf[0, 1]}], [{conf[1, 0]}, {conf[1, 1]}]]'
            )
    elif pred_labels is not None:
        print('    Prediction accuracy: unavailable (events file missing).')

    print('    Precomputing frames ...')
    frames = precompute_frames(emg, gesture_labels, phase_labels, timestamps)
    n_frames = len(frames)
    print(
        f'    {n_frames} frames '
        f'({ACTIVE_FRAME_STEP_MS}ms active / {REST_FRAME_STEP_MS}ms rest step, {RMS_WINDOW_MS}ms window)'
    )

    if n_frames == 0:
        print('    No frames to render, skipping.')
        return

    all_rms = np.array([f['rms'] for f in frames])
    global_vmin = float(np.percentile(all_rms[all_rms > 0], 2)) if np.any(all_rms > 0) else 0.0
    global_vmax = float(np.percentile(all_rms, 98))
    if global_vmax <= global_vmin:
        global_vmax = global_vmin + 1.0

    layout = get_svg_heatmap_layout()

    fig, ax = plt.subplots(1, 1, figsize=(8, 6.5))
    fig.patch.set_facecolor('white')

    title_text = fig.suptitle('', fontsize=13, fontweight='bold', y=0.97)

    sm = cm.ScalarMappable(
        norm=mcolors.Normalize(vmin=global_vmin, vmax=global_vmax),
        cmap='emg_spatial',
    )
    cbar = fig.colorbar(sm, ax=ax, orientation='vertical', fraction=0.04, pad=0.02)
    cbar.set_label('RMS Amplitude', fontsize=10)

    def update(frame_idx):
        ax.clear()
        frame = frames[frame_idx]

        draw_svg_heatmap(
            ax,
            channel_values=frame['rms'],
            layout=layout,
            cmap='emg_spatial',
            vmin=global_vmin,
            vmax=global_vmax,
            annotate=True,
            spacing_scale=0.7,
            blur_sigma=7.0,
        )

        t = frame['time']
        gesture = frame['gesture_name']
        gesture_id = frame['gesture_label']
        phase = frame['phase']
        phase_name = frame['phase_name']
        gesture_color = GESTURE_COLORS.get(gesture_id, '#888888')
        phase_color = PHASE_COLORS.get(phase, '#888888')

        title_text.set_text(f'SCI {subject} - Session {session_idx:02d} ({label_source})')

        ax.text(
            0.02,
            0.02,
            f't = {t:6.1f}s / {duration:.0f}s',
            transform=ax.transAxes,
            fontsize=11,
            fontfamily='monospace',
            verticalalignment='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.85),
            zorder=10,
        )

        ax.text(
            0.98,
            0.98,
            gesture,
            transform=ax.transAxes,
            fontsize=14,
            fontweight='bold',
            verticalalignment='top',
            horizontalalignment='right',
            color='white',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=gesture_color, edgecolor='none', alpha=0.9),
            zorder=10,
        )

        if phase > 0:
            ax.text(
                0.98,
                0.88,
                phase_name,
                transform=ax.transAxes,
                fontsize=11,
                fontweight='bold',
                verticalalignment='top',
                horizontalalignment='right',
                color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=phase_color, edgecolor='none', alpha=0.85),
                zorder=10,
            )

        return []

    print('    Rendering animation ...')
    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000 // FPS, blit=False)

    out_base = output_dir / f'session_{session_idx:02d}'
    try:
        out_path = out_base.with_suffix('.mp4')
        anim.save(
            str(out_path),
            writer='ffmpeg',
            fps=FPS,
            dpi=120,
            codec='libx264',
            extra_args=['-pix_fmt', 'yuv420p'],
        )
        print(f'    Saved: {out_path}')
    except Exception as exc:
        print(f'    MP4 failed ({exc}), trying GIF ...')
        out_path = out_base.with_suffix('.gif')
        anim.save(str(out_path), writer='pillow', fps=FPS, dpi=100)
        print(f'    Saved: {out_path}')

    plt.close(fig)


# Main ------------------------------------------------------------------------

def normalize_subject(subject_token: str):
    """Normalize subject token to format S<number>, e.g. S5."""
    s = subject_token.strip().upper()
    if not s:
        return None
    if s.startswith('S') and s[1:].isdigit():
        return f'S{int(s[1:])}'
    return None


def parse_args(argv):
    """Parse CLI args into subjects and sessions."""
    subjects = []
    sessions = []

    for token in argv[1:]:
        parts = [p for p in token.split(',') if p.strip()]
        for part in parts:
            subj = normalize_subject(part)
            if subj is not None:
                subjects.append(subj)
            else:
                try:
                    sessions.append(int(part))
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid argument '{part}'. Use subject tokens like S5 and session indices like 0 1 2."
                    ) from exc

    if not subjects:
        subjects = list(DEFAULT_SUBJECTS)

    # Preserve order but remove duplicates
    subjects = list(dict.fromkeys(subjects))
    sessions = sorted(set(sessions)) if sessions else None
    return subjects, sessions


def main():
    try:
        subjects, sessions_filter = parse_args(sys.argv)
    except ValueError as exc:
        print(f'ERROR: {exc}')
        sys.exit(1)

    print(f'Generating animated heatmaps for subjects: {subjects}')
    print(
        f'  Window: {RMS_WINDOW_MS}ms | '
        f'Active step: {ACTIVE_FRAME_STEP_MS}ms | Rest step: {REST_FRAME_STEP_MS}ms | FPS: {FPS}'
    )

    for subject in subjects:
        data_dir = DATA_ROOT / subject / 'raw'
        output_dir = OUTPUT_ROOT / f'{subject}_animated_heatmaps'
        output_dir.mkdir(parents=True, exist_ok=True)

        if not data_dir.exists():
            print(f'\nSubject {subject}: raw directory not found at {data_dir}, skipping.')
            continue

        if sessions_filter is None:
            sessions = available_sessions(data_dir)
        else:
            sessions = sessions_filter

        print(f'\nSubject {subject}')
        print(f'  Sessions: {sessions}')
        print(f'  Output: {output_dir}\n')

        if not sessions:
            print('  No sessions found, skipping.')
            continue

        for session_idx in sessions:
            create_session_animation(subject, session_idx, data_dir, output_dir)
            print()

    print('Done.')


if __name__ == '__main__':
    main()