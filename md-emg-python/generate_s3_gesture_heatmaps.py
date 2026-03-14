"""
Generate EMG heatmaps per gesture (Open / Close) for subject SCI/S3.

Uses the events files (sessions 01-05) to segment grasp hold periods,
and the predictions files (sessions 06, 09-13) to identify predicted
gesture windows. Computes RMS per channel, averages across all trials,
and renders spatial heatmaps using the existing SVG electrode layout.
"""

import numpy as np
import pickle
import matplotlib.pyplot as plt
from matplotlib import cm, colors as mcolors
from pathlib import Path

# Reuse existing heatmap rendering infrastructure
from emg_comparative_analysis import (
    get_svg_heatmap_layout,
    draw_svg_heatmap,
    NUM_CHANNELS,
    DEFAULT_FS_HZ,
)

DATA_DIR = Path(__file__).parent / 'data' / 'SCI' / 'S3' / 'raw'
OUTPUT_DIR = Path(__file__).parent / 'results-analysis'
OUTPUT_DIR.mkdir(exist_ok=True)

GESTURE_NAMES = {0: 'Open', 1: 'Close'}


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


def compute_rms_per_channel(data: np.ndarray, window_ms: int = 100,
                            fs_hz: float = DEFAULT_FS_HZ) -> np.ndarray:
    """Compute mean RMS per channel over the entire segment."""
    window_samples = max(1, int(round(window_ms * fs_hz / 1000)))
    n_samples, n_channels = data.shape
    pad = window_samples // 2
    padded = np.pad(data, ((pad, pad), (0, 0)), mode='edge')

    rms = np.zeros((n_samples, n_channels))
    for i in range(n_samples):
        window = padded[i:i + window_samples]
        rms[i] = np.sqrt(np.mean(window ** 2, axis=0))

    # Return mean RMS per channel across time
    return np.mean(rms, axis=0)


# ── Collect segments from events-based sessions (01-05) ──────────────────────

def extract_hold_segments_from_events(session_idx: int):
    """Extract EMG data during grasp hold periods, grouped by gesture id.

    Returns dict {gesture_id: [array(samples, 32), ...]}
    """
    events_file = DATA_DIR / f'session_{session_idx:02d}_events.pkl'
    npy_file = DATA_DIR / f'session_{session_idx:02d}.npy'

    if not events_file.exists() or not npy_file.exists():
        return {}

    with open(events_file, 'rb') as f:
        events = pickle.load(f)
    if not events:
        return {}

    data = load_session(npy_file)
    timestamps = data[:, NUM_CHANNELS]  # column 32

    segments = {}
    current_gesture = None
    hold_start_ts = None

    for evt in events:
        etype = evt['event_type']
        ets = evt['timestamp']

        if etype.startswith('grasp_start_'):
            current_gesture = int(etype.split('_')[-1])
        elif etype == 'grasp_hold_start':
            hold_start_ts = ets
        elif etype == 'grasp_hold_end' and hold_start_ts is not None and current_gesture is not None:
            # Find samples within [hold_start, hold_end]
            mask = (timestamps >= hold_start_ts) & (timestamps <= ets)
            indices = np.where(mask)[0]
            if len(indices) > 10:
                segment = data[indices[0]:indices[-1] + 1, :NUM_CHANNELS].copy()
                segments.setdefault(current_gesture, []).append(segment)
            hold_start_ts = None

    return segments


# ── Collect segments from prediction-based sessions (06, 09-13) ──────────────

def extract_segments_from_predictions(session_idx: int):
    """Extract EMG windows grouped by predicted gesture class.

    Returns dict {gesture_id: [array(samples, 32), ...]}
    """
    pred_file = DATA_DIR / f'session_{session_idx:02d}_predictions.pkl'
    npy_file = DATA_DIR / f'session_{session_idx:02d}.npy'

    if not pred_file.exists() or not npy_file.exists():
        return {}

    with open(pred_file, 'rb') as f:
        preds = pickle.load(f)

    data = load_session(npy_file)
    emg = data[:, :NUM_CHANNELS]

    n_preds = preds.shape[0]
    samples_per_pred = emg.shape[0] // n_preds
    pred_classes = np.argmax(preds, axis=1)

    segments = {}
    for i, cls in enumerate(pred_classes):
        start = i * samples_per_pred
        end = min(start + samples_per_pred, emg.shape[0])
        segment = emg[start:end].copy()
        if segment.shape[0] > 10:
            segments.setdefault(int(cls), []).append(segment)

    return segments


# ── Aggregate and render ─────────────────────────────────────────────────────

def collect_all_segments():
    """Gather all segments from all available sessions for S3."""
    all_segments = {0: [], 1: []}

    # Events sessions (01-05)
    for s in range(6):
        segs = extract_hold_segments_from_events(s)
        for gid in [0, 1]:
            all_segments[gid].extend(segs.get(gid, []))

    # Prediction sessions
    for s in [6, 9, 10, 11, 12, 13]:
        segs = extract_segments_from_predictions(s)
        for gid in [0, 1]:
            all_segments[gid].extend(segs.get(gid, []))

    return all_segments


def render_heatmaps():
    """Generate and save heatmap figures for Open and Close gestures."""
    all_segments = collect_all_segments()

    # Compute per-channel RMS for each segment, then average across trials
    gesture_channel_rms = {}
    for gid in [0, 1]:
        segments = all_segments[gid]
        if not segments:
            print(f"No segments found for gesture {GESTURE_NAMES[gid]}")
            continue
        rms_values = np.array([compute_rms_per_channel(seg) for seg in segments])
        gesture_channel_rms[gid] = np.mean(rms_values, axis=0)
        print(f"Gesture {GESTURE_NAMES[gid]}: {len(segments)} segments, "
              f"mean RMS range [{gesture_channel_rms[gid].min():.1f}, {gesture_channel_rms[gid].max():.1f}]")

    if not gesture_channel_rms:
        print("ERROR: No segments found for any gesture.")
        return

    # Use a shared color scale across both gestures for comparability
    global_vmin = min(v.min() for v in gesture_channel_rms.values())
    global_vmax = max(v.max() for v in gesture_channel_rms.values())

    layout = get_svg_heatmap_layout()

    # ── Side-by-side figure ──────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('SCI Subject S3 — EMG Spatial Heatmaps per Gesture\n(Mean RMS across all trials)',
                 fontsize=14, fontweight='bold', y=0.98)

    for ax_idx, gid in enumerate([0, 1]):
        ax = axes[ax_idx]
        if gid not in gesture_channel_rms:
            ax.set_title(f'{GESTURE_NAMES[gid]} (no data)')
            ax.axis('off')
            continue

        sm = draw_svg_heatmap(
            ax,
            channel_values=gesture_channel_rms[gid],
            layout=layout,
            cmap='emg_spatial',
            vmin=global_vmin,
            vmax=global_vmax,
            annotate=True,
            spacing_scale=0.7,
            blur_sigma=7.0,
        )
        n_segs = len(all_segments[gid])
        ax.set_title(f'{GESTURE_NAMES[gid]} (n={n_segs} trials)', fontsize=13, pad=10)

    # Shared colorbar
    cbar = fig.colorbar(
        cm.ScalarMappable(
            norm=mcolors.Normalize(vmin=global_vmin, vmax=global_vmax),
            cmap='emg_spatial',
        ),
        ax=axes,
        orientation='horizontal',
        fraction=0.05,
        pad=0.08,
        aspect=40,
    )
    cbar.set_label('Mean RMS Amplitude', fontsize=11)

    fig.tight_layout(rect=[0, 0.06, 1, 0.93])
    out_path = OUTPUT_DIR / 'S3_gesture_heatmaps_open_close.png'
    fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"Saved combined figure: {out_path}")

    # ── Individual per-gesture figures ───────────────────────────────────
    for gid in [0, 1]:
        if gid not in gesture_channel_rms:
            continue

        fig_single, ax_single = plt.subplots(1, 1, figsize=(8, 6))
        sm = draw_svg_heatmap(
            ax_single,
            channel_values=gesture_channel_rms[gid],
            layout=layout,
            cmap='emg_spatial',
            vmin=global_vmin,
            vmax=global_vmax,
            annotate=True,
            spacing_scale=0.7,
            blur_sigma=7.0,
        )
        n_segs = len(all_segments[gid])
        ax_single.set_title(
            f'SCI S3 — {GESTURE_NAMES[gid]} Gesture\n(Mean RMS, n={n_segs} trials)',
            fontsize=13, fontweight='bold', pad=12,
        )

        cbar_single = fig_single.colorbar(
            cm.ScalarMappable(
                norm=mcolors.Normalize(vmin=global_vmin, vmax=global_vmax),
                cmap='emg_spatial',
            ),
            ax=ax_single,
            orientation='vertical',
            fraction=0.04,
            pad=0.02,
        )
        cbar_single.set_label('Mean RMS Amplitude', fontsize=10)

        fig_single.tight_layout()
        out_single = OUTPUT_DIR / f'S3_heatmap_{GESTURE_NAMES[gid].lower()}.png'
        fig_single.savefig(out_single, dpi=200, bbox_inches='tight', facecolor='white')
        plt.close(fig_single)
        print(f"Saved individual figure: {out_single}")


if __name__ == '__main__':
    render_heatmaps()
