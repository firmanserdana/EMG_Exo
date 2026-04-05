#!/usr/bin/env python3
"""
Automatic Timestamp Detection from EMG Signal Activity

This script analyzes EMG data to automatically detect gesture/object boundaries
based on signal activity patterns. It can:
1. Detect activity peaks that correspond to object interactions
2. Compare detected timestamps with existing manual timestamps
3. Generate corrected timestamp files

The algorithm looks for:
- RMS envelope peaks across all channels
- Activity onset and offset detection
- Pattern matching for 6 objects with expected pause between each
"""

import numpy as np
import json
from pathlib import Path
from scipy import signal as sp_signal
from scipy.ndimage import gaussian_filter1d
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
from dataclasses import dataclass
import argparse


@dataclass
class DetectedGesture:
    """Container for a detected gesture/object timing"""
    gesture_id: int
    start_time: float
    end_time: float
    peak_time: float
    confidence: float
    activity_level: float


def load_emg_session(session_file: Path) -> np.ndarray:
    """Load EMG data from .npy file (handles multiple concatenated arrays)."""
    arrays = []
    with open(session_file, 'rb') as f:
        while True:
            try:
                arrays.append(np.load(f, allow_pickle=False))
            except (ValueError, EOFError):
                break
    return np.concatenate(arrays, axis=0) if arrays else np.array([])


def compute_activity_envelope(emg_data: np.ndarray, fs_hz: float = 1000.0, 
                               window_ms: float = 100.0) -> np.ndarray:
    """
    Compute the activity envelope from EMG data.
    
    Uses RMS across all channels with smoothing to get a 
    clean activity profile for timestamp detection.
    """
    num_channels = min(32, emg_data.shape[1])
    data = emg_data[:, :num_channels].astype(np.float64)
    
    # Remove DC offset per channel
    data = data - np.mean(data, axis=0, keepdims=True)
    
    # Compute RMS per sample across all channels
    rms_per_sample = np.sqrt(np.mean(data ** 2, axis=1))
    
    # Smooth with Gaussian filter
    sigma = (window_ms / 1000.0) * fs_hz / 2.0
    smoothed = gaussian_filter1d(rms_per_sample, sigma=sigma)
    
    return smoothed


def detect_activity_regions(envelope: np.ndarray, fs_hz: float = 1000.0,
                            threshold_percentile: float = 30,
                            min_duration_s: float = 1.0,
                            min_gap_s: float = 0.5) -> List[Tuple[int, int]]:
    """
    Detect regions of activity above threshold.
    
    Returns list of (start_idx, end_idx) tuples for active regions.
    """
    threshold = np.percentile(envelope, threshold_percentile)
    
    # Binary mask of activity
    active = envelope > threshold
    
    # Find transitions
    diff = np.diff(active.astype(int))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1
    
    # Handle edge cases
    if active[0]:
        starts = np.insert(starts, 0, 0)
    if active[-1]:
        ends = np.append(ends, len(envelope))
    
    # Pair starts and ends
    regions = list(zip(starts, ends))
    
    # Filter by minimum duration
    min_samples = int(min_duration_s * fs_hz)
    regions = [(s, e) for s, e in regions if (e - s) >= min_samples]
    
    # Merge nearby regions
    min_gap_samples = int(min_gap_s * fs_hz)
    merged = []
    for start, end in regions:
        if merged and (start - merged[-1][1]) < min_gap_samples:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    
    return merged


def detect_gesture_boundaries(emg_data: np.ndarray, fs_hz: float = 1000.0,
                              num_gestures: int = 6,
                              expected_gesture_duration_s: float = 3.0,
                              search_window_s: float = 2.0) -> List[DetectedGesture]:
    """
    Detect gesture boundaries from EMG activity.
    
    Uses a peak detection approach combined with activity region analysis.
    Expects 6 distinct activity bursts corresponding to 6 objects.
    """
    envelope = compute_activity_envelope(emg_data, fs_hz)
    
    # Normalize envelope to 0-1
    envelope_min = np.min(envelope)
    envelope_max = np.max(envelope)
    if envelope_max > envelope_min:
        envelope_norm = (envelope - envelope_min) / (envelope_max - envelope_min)
    else:
        envelope_norm = envelope
    
    # Find prominent peaks in the envelope
    # These correspond to gesture activity centers
    min_distance = int(expected_gesture_duration_s * fs_hz * 0.8)
    prominence = 0.1  # Minimum peak prominence (relative to normalized range)
    
    peaks, properties = sp_signal.find_peaks(
        envelope_norm, 
        distance=min_distance,
        prominence=prominence,
        height=0.15  # Minimum height threshold
    )
    
    # If we found more peaks than expected, keep the most prominent ones
    if len(peaks) > num_gestures:
        prominences = properties['prominences']
        top_indices = np.argsort(prominences)[-num_gestures:]
        peaks = np.sort(peaks[top_indices])
        # Update properties
        properties = {k: v[top_indices] for k, v in properties.items()}
    
    # For each peak, find the activity boundaries
    gestures = []
    search_samples = int(search_window_s * fs_hz)
    
    for i, peak_idx in enumerate(peaks):
        peak_time = peak_idx / fs_hz
        
        # Search for activity start (before peak)
        start_region = envelope_norm[max(0, peak_idx - search_samples):peak_idx]
        if len(start_region) > 0:
            # Find where activity drops below threshold going backwards
            threshold = np.percentile(start_region, 20)
            below_thresh = start_region < threshold
            if np.any(below_thresh):
                offset = len(start_region) - 1 - np.argmax(below_thresh[::-1])
                start_idx = max(0, peak_idx - search_samples) + offset
            else:
                start_idx = max(0, peak_idx - search_samples)
        else:
            start_idx = max(0, peak_idx - search_samples // 2)
        
        # Search for activity end (after peak)
        end_region = envelope_norm[peak_idx:min(len(envelope_norm), peak_idx + search_samples)]
        if len(end_region) > 0:
            threshold = np.percentile(end_region, 20)
            below_thresh = end_region < threshold
            if np.any(below_thresh):
                offset = np.argmax(below_thresh)
                end_idx = peak_idx + offset
            else:
                end_idx = min(len(envelope_norm), peak_idx + search_samples)
        else:
            end_idx = min(len(envelope_norm), peak_idx + search_samples // 2)
        
        start_time = start_idx / fs_hz
        end_time = end_idx / fs_hz
        
        # Compute confidence based on peak prominence
        if 'prominences' in properties and i < len(properties['prominences']):
            confidence = min(1.0, properties['prominences'][i] / 0.5)
        else:
            confidence = 0.5
        
        # Activity level is the peak height
        activity_level = envelope_norm[peak_idx]
        
        gestures.append(DetectedGesture(
            gesture_id=i + 1,
            start_time=start_time,
            end_time=end_time,
            peak_time=peak_time,
            confidence=confidence,
            activity_level=activity_level
        ))
    
    return gestures


def convert_to_timestamp_format(gestures: List[DetectedGesture], 
                                 session_file: str) -> Dict:
    """
    Convert detected gestures to the JSON timestamp format.
    
    Creates timestamps for each gesture boundary (12 timestamps for 6 objects).
    """
    # Create gesture list with both start and end as separate timestamps
    gesture_list = []
    for g in gestures:
        # Start timestamp
        gesture_list.append({
            "gesture_id": len(gesture_list) + 1,
            "timestamp": round(g.start_time, 2),
            "absolute_time": "",
            "description": f"Object {g.gesture_id} start",
            "detected_confidence": round(g.confidence, 2)
        })
        # End timestamp
        gesture_list.append({
            "gesture_id": len(gesture_list) + 1,
            "timestamp": round(g.end_time, 2),
            "absolute_time": "",
            "description": f"Object {g.gesture_id} end",
            "detected_confidence": round(g.confidence, 2)
        })
    
    return {
        "session_info": {
            "total_gestures": len(gesture_list),
            "session_file": session_file,
            "created_at": "",
            "auto_detected": True
        },
        "gestures": gesture_list
    }


def visualize_detection(emg_data: np.ndarray, gestures: List[DetectedGesture],
                        existing_timestamps: Optional[List[float]] = None,
                        fs_hz: float = 1000.0, 
                        title: str = "EMG Activity Detection",
                        save_path: Optional[Path] = None):
    """
    Visualize detected gestures overlaid on EMG activity envelope.
    """
    envelope = compute_activity_envelope(emg_data, fs_hz)
    time = np.arange(len(envelope)) / fs_hz
    
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    
    # Panel 1: Raw EMG (mean across channels)
    ax1 = axes[0]
    num_channels = min(32, emg_data.shape[1])
    mean_emg = np.mean(emg_data[:, :num_channels], axis=1)
    ax1.plot(time, mean_emg, 'b-', alpha=0.5, linewidth=0.5)
    ax1.set_ylabel('Mean EMG (raw)')
    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Activity envelope with detected boundaries
    ax2 = axes[1]
    ax2.plot(time, envelope, 'b-', linewidth=1, label='Activity envelope')
    ax2.set_ylabel('RMS Activity')
    ax2.grid(True, alpha=0.3)
    
    colors = plt.cm.Set1(np.linspace(0, 1, len(gestures)))
    for i, g in enumerate(gestures):
        # Shade the detected gesture region
        ax2.axvspan(g.start_time, g.end_time, alpha=0.3, color=colors[i],
                   label=f'Object {g.gesture_id}')
        # Mark peak
        ax2.axvline(g.peak_time, color=colors[i], linestyle='--', alpha=0.8)
    
    ax2.legend(loc='upper right', fontsize=8, ncol=3)
    
    # Panel 3: Comparison with existing timestamps if provided
    ax3 = axes[2]
    ax3.plot(time, envelope, 'b-', linewidth=1, label='Activity envelope')
    ax3.set_ylabel('RMS Activity')
    ax3.set_xlabel('Time (s)')
    ax3.grid(True, alpha=0.3)
    
    # Show detected timestamps (pairs for each object)
    for i, g in enumerate(gestures):
        ax3.axvline(g.start_time, color='green', linestyle='-', alpha=0.8, linewidth=2)
        ax3.axvline(g.end_time, color='green', linestyle='-', alpha=0.8, linewidth=2)
    
    # Show existing timestamps if provided
    if existing_timestamps:
        for ts in existing_timestamps:
            ax3.axvline(ts, color='red', linestyle='--', alpha=0.6, linewidth=1.5)
        ax3.plot([], [], 'g-', linewidth=2, label='Auto-detected')
        ax3.plot([], [], 'r--', linewidth=1.5, label='Existing timestamps')
        ax3.legend(loc='upper right')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved visualization to: {save_path}")
    
    return fig


def load_existing_timestamps(timestamps_file: Path) -> List[float]:
    """Load existing timestamps from JSON file."""
    if not timestamps_file.exists():
        return []
    
    with open(timestamps_file, 'r') as f:
        data = json.load(f)
    
    timestamps = []
    if 'gestures' in data:
        for g in data['gestures']:
            timestamps.append(float(g.get('timestamp', 0)))
    
    return sorted(timestamps)


def process_session(session_file: Path, timestamps_file: Optional[Path] = None,
                    fs_hz: float = 1000.0, num_gestures: int = 6,
                    output_dir: Optional[Path] = None,
                    visualize: bool = True) -> Dict:
    """
    Process a single session file to detect and optionally update timestamps.
    """
    print(f"\n{'='*60}")
    print(f"Processing: {session_file.name}")
    print(f"{'='*60}")
    
    # Load EMG data
    emg_data = load_emg_session(session_file)
    if emg_data.size == 0:
        print("  ERROR: Could not load EMG data")
        return {}
    
    print(f"  Loaded EMG data: {emg_data.shape}")
    duration = emg_data.shape[0] / fs_hz
    print(f"  Duration: {duration:.1f}s")
    
    # Detect gestures
    gestures = detect_gesture_boundaries(emg_data, fs_hz, num_gestures)
    print(f"  Detected {len(gestures)} gesture regions:")
    
    for g in gestures:
        print(f"    Object {g.gesture_id}: {g.start_time:.2f}s - {g.end_time:.2f}s "
              f"(peak: {g.peak_time:.2f}s, confidence: {g.confidence:.2f})")
    
    # Load existing timestamps for comparison
    existing_timestamps = []
    if timestamps_file and timestamps_file.exists():
        existing_timestamps = load_existing_timestamps(timestamps_file)
        print(f"\n  Existing timestamps ({len(existing_timestamps)}):")
        for i, ts in enumerate(existing_timestamps):
            print(f"    [{i+1}] {ts:.2f}s")
    
    # Convert to output format
    session_name = session_file.stem.replace('session_', '')
    result = convert_to_timestamp_format(gestures, session_file.name)
    
    # Visualize if requested
    if visualize and output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        vis_path = output_dir / f"{session_file.stem}_detection.png"
        visualize_detection(emg_data, gestures, existing_timestamps, fs_hz,
                          title=f"Detection: {session_file.name}", save_path=vis_path)
        plt.close()
    
    return result


def process_subject_folder(subject_dir: Path, times_dir: Path,
                           output_dir: Path, fs_hz: float = 1000.0,
                           sessions: Optional[List[int]] = None):
    """
    Process all sessions for a subject.
    """
    emg_logs_dir = subject_dir / "emg_logs"
    if not emg_logs_dir.exists():
        print(f"No emg_logs directory found in {subject_dir}")
        return
    
    subject_name = subject_dir.name.lower()
    times_subject_dir = times_dir / subject_name
    
    session_files = sorted(emg_logs_dir.glob("session_*.npy"))
    
    for session_file in session_files:
        # Extract session number
        try:
            session_num = int(session_file.stem.split('_')[1])
        except (IndexError, ValueError):
            continue
        
        # Filter by session if specified
        if sessions and session_num not in sessions:
            continue
        
        # Find corresponding timestamp file
        timestamps_file = times_subject_dir / f"session_{session_num:02d}_timestamps.json"
        
        # Process session
        subject_output_dir = output_dir / subject_dir.name
        result = process_session(
            session_file, 
            timestamps_file if timestamps_file.exists() else None,
            fs_hz=fs_hz,
            output_dir=subject_output_dir,
            visualize=True
        )
        
        # Save detected timestamps
        if result:
            out_file = subject_output_dir / f"session_{session_num:02d}_detected.json"
            subject_output_dir.mkdir(parents=True, exist_ok=True)
            with open(out_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"  Saved: {out_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Automatic EMG timestamp detection based on signal activity"
    )
    parser.add_argument(
        "--data-dir", type=Path, 
        default=Path("data/healthy"),
        help="Root directory containing subject folders"
    )
    parser.add_argument(
        "--times-dir", type=Path,
        default=Path("data/healthy/times"),
        help="Directory containing timestamp JSON files"
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("results-analysis/timestamp_detection"),
        help="Output directory for detected timestamps and visualizations"
    )
    parser.add_argument(
        "--subject", type=str, default=None,
        help="Process only this subject (e.g., 'S1')"
    )
    parser.add_argument(
        "--session", type=int, default=None,
        help="Process only this session number"
    )
    parser.add_argument(
        "--fs", type=float, default=1000.0,
        help="Sampling frequency in Hz"
    )
    
    args = parser.parse_args()
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find subject directories
    subject_dirs = sorted(args.data_dir.glob("S*"))
    
    if args.subject:
        subject_dirs = [d for d in subject_dirs if d.name.upper() == args.subject.upper()]
    
    sessions_filter = [args.session] if args.session else None
    
    for subject_dir in subject_dirs:
        if not subject_dir.is_dir():
            continue
        print(f"\n{'#'*60}")
        print(f"# Subject: {subject_dir.name}")
        print(f"{'#'*60}")
        
        process_subject_folder(
            subject_dir, 
            args.times_dir, 
            args.output_dir,
            fs_hz=args.fs,
            sessions=sessions_filter
        )
    
    print(f"\n{'='*60}")
    print("Detection complete!")
    print(f"Results saved in: {args.output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
