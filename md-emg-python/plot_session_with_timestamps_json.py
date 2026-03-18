"""
Generate Stacked EMG Plots with Timestamp Lines
Creates 32-channel stacked plots for all sessions (S1-S10) with timestamp markers
Uses the same data loading infrastructure as emg_comparative_analysis.py
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

# Import from main analysis script
sys.path.insert(0, str(Path(__file__).parent))

try:
    from emg_comparative_analysis import load_real_data, SegmentRecord  # type: ignore[import-not-found]
except ImportError:
    # Workspace fallback with equivalent structures.
    from scripts.pretrain_healthy import load_all_healthy_data, SegmentRecord

    def load_real_data(data_dir: Path):
        conditions = ["No Glove", "Passive Glove", "Active Glove"]
        subjects = [f"S{i}" for i in range(1, 11)]
        data = load_all_healthy_data(data_dir=data_dir, subjects=subjects, conditions=conditions)
        return data, 1000.0, {}


# Configuration
NUM_CHANNELS = 32


def normalize_session_name(session: str) -> str:
    """Normalize session labels to an emg_logs file name."""
    s = str(session)
    if s.endswith(".npy"):
        return s
    if s.startswith("session_"):
        tail = s.replace("session_", "")
        if tail.isdigit():
            return f"session_{int(tail):02d}.npy"
        return f"{s}.npy"
    if s.isdigit():
        return f"session_{int(s):02d}.npy"
    return f"{s}.npy"


def load_session_with_timestamps(subject_dir: Path, session: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Load full session data including timestamp column.

    Returns:
        emg_data: (n_samples, 32) - EMG channels only
        timestamps: (n_samples,) - Timestamp column
    """
    session_file = subject_dir / "emg_logs" / normalize_session_name(session)

    try:
        arrays = []
        with open(session_file, "rb") as f:
            while True:
                try:
                    arrays.append(np.load(f, allow_pickle=False))
                except (ValueError, EOFError):
                    break

        if not arrays:
            return None, None

        data = np.concatenate(arrays, axis=0)

        # Extract EMG data (first 32 channels) and timestamps (last column)
        if data.shape[1] >= 33:
            emg_data = data[:, :NUM_CHANNELS]
            timestamps = data[:, -1]
        else:
            emg_data = data[:, :NUM_CHANNELS]
            timestamps = None

        return emg_data, timestamps
    except Exception as e:
        print(f"    Error loading {session}: {e}")
        return None, None


def create_stacked_plot_with_timestamps(
    records: List[SegmentRecord],
    subject: str,
    session: str,
    condition: str,
    output_path: Path,
    fs_hz: float = 1000.0,
):
    """Create stacked EMG plot with timestamp lines from SegmentRecords."""

    # Load the full session data with actual timestamps from the .npy file
    data_dir = Path(__file__).parent / "data" / "healthy"
    subject_dir = data_dir / subject

    emg_data, time_axis = load_session_with_timestamps(subject_dir, session)

    if emg_data is None:
        print(f"  Could not load session data for {subject} {session}")
        return

    # Load timestamps directly from JSON file instead of using filtered records
    # This ensures we show ALL objects, not just those within filtered ranges
    session_name = normalize_session_name(session)
    timestamp_json = subject_dir / "emg_logs" / f"{session_name.replace('.npy', '')}_timestamps.json"

    object_timestamps = []
    if timestamp_json.exists():
        with open(timestamp_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        gestures = data.get("gestures", [])

        # Extract timestamps (might be dict or float)
        timestamps = []
        for g in gestures:
            if isinstance(g, dict):
                timestamps.append(float(g.get("time", g.get("timestamp", 0))))
            else:
                timestamps.append(float(g))

        # Create object pairs from timestamps
        for i in range(0, len(timestamps) - 1, 2):
            start = timestamps[i]
            end = timestamps[i + 1]
            object_timestamps.append((start, end))
    else:
        # Fallback: use records if JSON not found
        for rec in records:
            object_timestamps.append((rec.start_time, rec.end_time))

    n_samples = emg_data.shape[0]
    n_channels = min(emg_data.shape[1], NUM_CHANNELS)

    # Normalize time axis to start from 0 if timestamps are available
    if time_axis is not None:
        session_start_time = time_axis[0]
        time_axis = time_axis - session_start_time
    else:
        time_axis = np.arange(n_samples) / fs_hz

    fig, ax = plt.subplots(figsize=(20, 10))

    # Plot each channel (normalized and stacked)
    for ch in range(n_channels):
        channel_data = emg_data[:, ch]

        # Normalize to [0, 1] for better visualization
        minimum = np.min(channel_data)
        maximum = np.max(channel_data)

        if maximum - minimum > 1e-9:
            normed = (channel_data - minimum) / (maximum - minimum) + ch
        else:
            normed = np.ones_like(channel_data) * ch

        ax.plot(time_axis, normed, linewidth=0.4, alpha=0.7, color="black")

    # Add colored regions for each object manipulation period
    colors = plt.cm.Set3(np.linspace(0, 1, len(object_timestamps)))

    for i, (start, end) in enumerate(object_timestamps):
        ax.axvspan(start, end, alpha=0.25, color=colors[i], zorder=0)
        ax.axvline(start, color="green", linestyle="--", linewidth=1.5, alpha=0.7, zorder=1)
        ax.axvline(end, color="red", linestyle="--", linewidth=1.5, alpha=0.7, zorder=1)

        mid_point = (start + end) / 2
        duration = end - start
        ax.text(
            mid_point,
            n_channels + 0.5,
            f"Object {i + 1}\n({duration:.1f}s)",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=colors[i], edgecolor="black", linewidth=1.5, alpha=0.8),
        )

    if len(object_timestamps) > 0:
        from matplotlib.lines import Line2D

        legend_elements = [
            Line2D([0], [0], color="green", linestyle="--", linewidth=1.5, label="Object Start"),
            Line2D([0], [0], color="red", linestyle="--", linewidth=1.5, label="Object End"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=10, framealpha=0.9)

    # Formatting
    ax.set_xlabel("Time (seconds)", fontsize=14, fontweight="bold")
    ax.set_ylabel("Channel (stacked & normalized)", fontsize=14, fontweight="bold")
    ax.set_title(
        f"{subject} - Session {session} - {condition}\n"
        f"32 EMG Channels - RAW DATA - {len(object_timestamps)} Objects",
        fontsize=16,
        fontweight="bold",
    )
    ax.set_yticks(range(0, n_channels, 2))
    ax.set_yticklabels([f"Ch {i}" for i in range(0, n_channels, 2)], fontsize=9)
    ax.grid(True, alpha=0.3, axis="x", linewidth=0.5)
    ax.set_ylim(-0.5, n_channels + 1.5)
    ax.set_xlim(0, time_axis[-1])

    legend_elements = [
        plt.Line2D([0], [0], color="green", linestyle="--", linewidth=2, label="Object Start"),
        plt.Line2D([0], [0], color="red", linestyle="--", linewidth=2, label="Object End"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=11, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_path, format="svg", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"  Saved: {output_path.name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a stacked EMG plot for one session.")
    parser.add_argument("--subject", default="S10", help="Subject ID, e.g. S10")
    parser.add_argument("--session", default="session_16", help="Session name/number, e.g. session_16 or 16")
    parser.add_argument("--condition", default="single_session", help="Condition label used in plot title/output name")
    return parser.parse_args()


def main():
    print("=" * 70)
    print("Generating Raw Stacked EMG Plots with Timestamps")
    print("=" * 70)

    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / "data" / "healthy"
    output_dir = script_dir / "results-analysis" / "raw_plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    args = parse_args()
    target_subject = args.subject
    target_session = args.session
    target_condition = args.condition

    # Load all data using the same infrastructure as main analysis
    print("\nLoading data using main analysis infrastructure...")
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)

    if data_dict is None:
        print("Failed to load data")
        return

    print(f"Loaded {sum(len(data_dict[cond]) for cond in data_dict)} objects across conditions")
    print(f"Sampling rate: {inferred_fs:.2f} Hz\n")

    # Keep compatibility with previous logic by collecting matching records only.
    target_records: List[SegmentRecord] = []
    for condition in data_dict:
        for obj_id in data_dict[condition]:
            records = data_dict[condition][obj_id]
            for rec in records:
                rec_session = rec.session
                if isinstance(rec_session, int):
                    rec_session = f"session_{rec_session:02d}"
                if rec.subject == target_subject and str(rec_session) == str(target_session):
                    target_records.append(rec)

    print(f"Processing {target_subject} - {target_session} - {target_condition}...")

    output_filename = f"{target_subject}_{target_session}_{target_condition.replace(' ', '_')}.svg"
    output_path = output_dir / output_filename

    total_plots = 0
    try:
        create_stacked_plot_with_timestamps(
            records=target_records,
            subject=target_subject,
            session=target_session,
            condition=target_condition,
            output_path=output_path,
            fs_hz=inferred_fs,
        )
        total_plots = 1
    except Exception as e:
        print(f"  Error creating plot: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"Complete! Generated {total_plots} stacked EMG plots")
    print(f"Output directory: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
