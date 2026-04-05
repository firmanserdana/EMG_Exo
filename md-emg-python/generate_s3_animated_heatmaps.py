"""
Generate animated EMG spatial heatmaps for each session of SCI/S3.

Each animation shows the 32-channel EMG heatmap evolving over time,
with a gesture label overlay (from events or predictions files when
available). Saved as MP4 (ffmpeg) with GIF fallback.

Usage:
    python generate_s3_animated_heatmaps.py              # all sessions
    python generate_s3_animated_heatmaps.py 1 5          # sessions 01 and 05
"""

import sys
import numpy as np
import pickle
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for rendering
import matplotlib.pyplot as plt
from matplotlib import cm, colors as mcolors
from matplotlib.animation import FuncAnimation
from pathlib import Path

from emg_comparative_analysis import (
    get_svg_heatmap_layout,
    draw_svg_heatmap,
    NUM_CHANNELS,
    DEFAULT_FS_HZ,
)

DATA_DIR = Path(__file__).parent / 'data' / 'SCI' / 'S3' / 'raw'
OUTPUT_DIR = Path(__file__).parent / 'results-analysis' / 'S3_animated_heatmaps'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GESTURE_NAMES = {0: 'Open', 1: 'Close', -1: 'Rest'}
PHASE_NAMES = {0: 'Rest', 1: 'Grasping', 2: 'Holding', 3: 'Releasing'}
# Phase encoding: 0=rest, 1=grasp_start→hold_start, 2=hold_start→hold_end, 3=hold_end→released

# Animation parameters
RMS_WINDOW_MS = 200       # RMS window size in ms
FRAME_STEP_MS = 500       # Time step between frames
FPS = 10                  # Output video frame rate


# ── Data loading ─────────────────────────────────────────────────────────────

def load_session(session_file: Path) -> np.ndarray:
    """Load a multi-array .npy session file (concatenated streaming buffers)."""
    arrays = []
    with open(session_file, 'rb') as f:
        while True:
            try:
                arrays.append(np.load(f, allow_pickle=False))
            except (ValueError, EOFError):
                break
    return np.concatenate(arrays, axis=0)


def load_events(session_idx: int):
    """Load events file if it exists. Returns list of event dicts or None."""
    events_file = DATA_DIR / f'session_{session_idx:02d}_events.pkl'
    if not events_file.exists():
        return None
    with open(events_file, 'rb') as f:
        events = pickle.load(f)
    return events if events else None


def load_predictions(session_idx: int):
    """Load all prediction chunks for a session.

    Prediction files are saved as multiple pickle chunks. Returns one
    concatenated ndarray, an empty ndarray if no predictions are stored,
    or None if the file is missing.
    """
    pred_file = DATA_DIR / f'session_{session_idx:02d}_predictions.pkl'
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
    """Extract class ids from either class-score rows or (label, confidence) rows."""
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


# ── Build per-sample gesture label array ─────────────────────────────────────

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
        etype = evt['event_type']
        ets = evt['timestamp']

        if etype.startswith('grasp_start_'):
            current_gesture = int(etype.split('_')[-1])
            grasp_start_ts = ets
        elif etype == 'grasp_hold_start' and grasp_start_ts is not None:
            # Phase 1: grasping (grasp_start → hold_start)
            mask = (timestamps_col >= grasp_start_ts) & (timestamps_col < ets)
            gesture_labels[mask] = current_gesture
            phase_labels[mask] = 1
            hold_start_ts = ets
        elif etype == 'grasp_hold_end' and hold_start_ts is not None:
            # Phase 2: holding (hold_start → hold_end)
            mask = (timestamps_col >= hold_start_ts) & (timestamps_col <= ets)
            gesture_labels[mask] = current_gesture
            phase_labels[mask] = 2
            hold_end_ts = ets
            hold_start_ts = None
        elif etype == 'grasp_released' and hold_end_ts is not None:
            # Phase 3: releasing (hold_end → released)
            mask = (timestamps_col > hold_end_ts) & (timestamps_col <= ets)
            gesture_labels[mask] = current_gesture
            phase_labels[mask] = 3
            grasp_start_ts = None
            hold_end_ts = None

    return gesture_labels, phase_labels


def build_gesture_timeline_from_predictions(preds: np.ndarray, n_samples: int):
    """Create per-sample gesture and phase labels from prediction windows.

    Returns:
        gesture_labels: array of int, 0=open, 1=close
        phase_labels:   array of int (all set to 2='holding' for predicted windows)
    """
    pred_classes = extract_prediction_classes(preds)
    n_preds = pred_classes.shape[0]
    if n_preds == 0:
        return np.full(n_samples, -1, dtype=int), np.zeros(n_samples, dtype=int)

    samples_per_pred = n_samples // n_preds

    gesture_labels = np.full(n_samples, -1, dtype=int)
    phase_labels = np.zeros(n_samples, dtype=int)
    for i, cls in enumerate(pred_classes):
        start = i * samples_per_pred
        end = min(start + samples_per_pred, n_samples)
        gesture_labels[start:end] = int(cls)
        phase_labels[start:end] = 2  # predicted = treated as hold

    return gesture_labels, phase_labels


# ── RMS computation ──────────────────────────────────────────────────────────

def compute_windowed_rms(emg_data: np.ndarray, center_idx: int,
                         half_window: int) -> np.ndarray:
    """Compute RMS per channel for a window centred at center_idx."""
    start = max(0, center_idx - half_window)
    end = min(emg_data.shape[0], center_idx + half_window)
    window = emg_data[start:end]
    if window.shape[0] == 0:
        return np.zeros(emg_data.shape[1])
    return np.sqrt(np.mean(window ** 2, axis=0))


# ── Precompute all frames ───────────────────────────────────────────────────

def precompute_frames(emg_data: np.ndarray, gesture_labels: np.ndarray,
                      phase_labels: np.ndarray, timestamps: np.ndarray):
    """Precompute RMS values and metadata for every frame.

    Returns list of dicts with keys: rms, time, gesture_label, gesture_name, phase, phase_name.
    """
    half_window = int(RMS_WINDOW_MS * DEFAULT_FS_HZ / 1000) // 2
    step_samples = int(FRAME_STEP_MS * DEFAULT_FS_HZ / 1000)
    n_samples = emg_data.shape[0]
    t0 = timestamps[0]

    frames = []
    for center in range(0, n_samples, step_samples):
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
        if len(ph_window) > 0:
            phase = int(np.bincount(ph_window).argmax())
        else:
            phase = 0

        frames.append({
            'rms': rms,
            'time': t,
            'gesture_label': gesture,
            'gesture_name': GESTURE_NAMES.get(gesture, 'Rest'),
            'phase': phase,
            'phase_name': PHASE_NAMES.get(phase, ''),
        })

    return frames


# ── Animation rendering ─────────────────────────────────────────────────────

GESTURE_COLORS = {-1: '#888888', 0: '#2196F3', 1: '#F44336'}
PHASE_COLORS = {
    0: '#888888',   # rest — gray
    1: '#FF9800',   # grasping — orange
    2: '#4CAF50',   # holding — green
    3: '#9C27B0',   # releasing — purple
}


def create_session_animation(session_idx: int):
    """Build and save an animated heatmap for a single session."""
    npy_file = DATA_DIR / f'session_{session_idx:02d}.npy'
    if not npy_file.exists():
        print(f"  Session {session_idx:02d}: npy file not found, skipping.")
        return

    print(f"  Session {session_idx:02d}: loading data …")
    data = load_session(npy_file)
    emg = data[:, :NUM_CHANNELS]
    timestamps = data[:, NUM_CHANNELS]
    duration = timestamps[-1] - timestamps[0]
    print(f"    {emg.shape[0]} samples, {duration:.1f}s")

    # Build gesture timeline
    events = load_events(session_idx)
    preds = load_predictions(session_idx)

    if events is not None:
        gesture_labels, phase_labels = build_gesture_timeline_from_events(events, timestamps)
        label_source = 'events'
    elif preds is not None:
        gesture_labels, phase_labels = build_gesture_timeline_from_predictions(preds, emg.shape[0])
        label_source = 'predictions'
    else:
        gesture_labels = np.full(emg.shape[0], -1, dtype=int)
        phase_labels = np.zeros(emg.shape[0], dtype=int)
        label_source = 'none'

    # Report event counts
    n_open = np.sum(gesture_labels == 0)
    n_close = np.sum(gesture_labels == 1)
    print(f"    Label source: {label_source} — Open: {n_open} samples, Close: {n_close} samples")

    # Precompute all frames
    print(f"    Precomputing frames …")
    frames = precompute_frames(emg, gesture_labels, phase_labels, timestamps)
    n_frames = len(frames)
    print(f"    {n_frames} frames ({FRAME_STEP_MS}ms step, {RMS_WINDOW_MS}ms window)")

    if n_frames == 0:
        print(f"    No frames to render, skipping.")
        return

    # Global color range across all frames for consistent scaling
    all_rms = np.array([f['rms'] for f in frames])
    global_vmin = float(np.percentile(all_rms[all_rms > 0], 2)) if np.any(all_rms > 0) else 0.0
    global_vmax = float(np.percentile(all_rms, 98))
    if global_vmax <= global_vmin:
        global_vmax = global_vmin + 1.0

    layout = get_svg_heatmap_layout()

    # Set up figure
    fig, ax = plt.subplots(1, 1, figsize=(8, 6.5))
    fig.patch.set_facecolor('white')

    # Title and info text objects
    title_text = fig.suptitle('', fontsize=13, fontweight='bold', y=0.97)
    time_text = ax.text(0.02, 0.02, '', transform=ax.transAxes,
                        fontsize=11, fontfamily='monospace',
                        verticalalignment='bottom',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                  edgecolor='gray', alpha=0.85),
                        zorder=10)
    gesture_text = ax.text(0.98, 0.02, '', transform=ax.transAxes,
                           fontsize=12, fontweight='bold',
                           verticalalignment='bottom',
                           horizontalalignment='right',
                           zorder=10)

    # Colorbar (created once)
    sm = cm.ScalarMappable(
        norm=mcolors.Normalize(vmin=global_vmin, vmax=global_vmax),
        cmap='emg_spatial',
    )
    cbar = fig.colorbar(sm, ax=ax, orientation='vertical',
                        fraction=0.04, pad=0.02)
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

        title_text.set_text(f'SCI S3 — Session {session_idx:02d}  ({label_source})')

        # Re-add text objects after ax.clear()
        ax.text(0.02, 0.02, f't = {t:6.1f}s / {duration:.0f}s',
                transform=ax.transAxes, fontsize=11, fontfamily='monospace',
                verticalalignment='bottom',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor='gray', alpha=0.85),
                zorder=10)

        # Gesture type badge (top-right)
        ax.text(0.98, 0.98, gesture,
                transform=ax.transAxes, fontsize=14, fontweight='bold',
                verticalalignment='top', horizontalalignment='right',
                color='white',
                bbox=dict(boxstyle='round,pad=0.4', facecolor=gesture_color,
                          edgecolor='none', alpha=0.9),
                zorder=10)

        # Phase badge (below gesture badge)
        if phase > 0:
            ax.text(0.98, 0.88, phase_name,
                    transform=ax.transAxes, fontsize=11, fontweight='bold',
                    verticalalignment='top', horizontalalignment='right',
                    color='white',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=phase_color,
                              edgecolor='none', alpha=0.85),
                    zorder=10)

        return []

    print(f"    Rendering animation …")
    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000 // FPS, blit=False)

    # Save as MP4 (ffmpeg), fallback to GIF
    out_base = OUTPUT_DIR / f'session_{session_idx:02d}'
    try:
        out_path = out_base.with_suffix('.mp4')
        anim.save(str(out_path), writer='ffmpeg', fps=FPS,
                  dpi=120, codec='libx264',
                  extra_args=['-pix_fmt', 'yuv420p'])
        print(f"    Saved: {out_path}")
    except Exception as e:
        print(f"    MP4 failed ({e}), trying GIF …")
        out_path = out_base.with_suffix('.gif')
        anim.save(str(out_path), writer='pillow', fps=FPS, dpi=100)
        print(f"    Saved: {out_path}")

    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        sessions = [int(s) for s in sys.argv[1:]]
    else:
        sessions = list(range(14))

    print(f"Generating animated heatmaps for SCI/S3 — sessions: {sessions}")
    print(f"  Window: {RMS_WINDOW_MS}ms | Step: {FRAME_STEP_MS}ms | FPS: {FPS}")
    print(f"  Output: {OUTPUT_DIR}\n")

    for s in sessions:
        create_session_animation(s)
        print()

    print("Done.")


if __name__ == '__main__':
    main()
