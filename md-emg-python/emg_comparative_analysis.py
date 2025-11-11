"""
EMG Comparative Analysis for Multiple Conditions

This script generates figures comparing EMG data across different conditions:
- Figure B: Raw data comparison across 3 conditions for 6 objects/patterns
- Figure C: Heatmaps for 3 conditions 
- Figure C: PCA analysis
- Time consumption difference analysis

The script expects data in .npy format with timestamps.json for gesture identification.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import colors as mcolors
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
import json
import re
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy import signal as sp_signal
import warnings

warnings.filterwarnings('ignore')

# Configuration
DEFAULT_FS_HZ = 1000  # Default sampling rate in Hz; overwritten if inferred from data
NUM_CHANNELS = 32  # Number of EMG channels
NUM_GESTURES = 6  # Number of gestures/objects to analyze
CHANNEL_IDS = list(range(NUM_CHANNELS))  # Channel indices
CONDITIONS = ['Passive glove', 'Active glove', 'No glove']
CONDITION_COLORS = {
    'Passive glove': '#1f77b4',
    'Active glove': '#ff7f0e', 
    'No glove': '#2ca02c'
}

MATLAB_CONDITION_BASE_COLORS = {
    'No glove': (0.0, 0.3, 0.7),      # blue family
    'Passive glove': (0.0, 0.6, 0.3), # green family
    'Active glove': (0.9, 0.2, 0.5)   # pink/magenta family
}

# Spatial layout of electrodes on the sleeve (based on photo)
# The sleeve has electrodes arranged in rows - map to physical layout
# Channels 0-31 mapped to their spatial positions (row, col)
def get_channel_spatial_layout():
    """
    Returns channel positions based on physical electrode placement on sleeve.
    Based on the sleeve image: 2 rows of electrodes, multiple columns per finger/area
    """
    # Layout: Row 0 (top) and Row 1 (bottom), columns 0-15 for each row
    # This creates a 2x16 grid matching the physical sleeve
    layout = np.zeros((2, 16), dtype=int)
    
    # Top row: channels 0-15
    for col in range(16):
        layout[0, col] = col
    
    # Bottom row: channels 16-31
    for col in range(16):
        layout[1, col] = col + 16
    
    return layout

CONDITION_ALIASES = {
    'passive glove': 'Passive glove',
    'passive gloves': 'Passive glove',
    'passive': 'Passive glove',
    'active glove': 'Active glove',
    'active gloves': 'Active glove',
    'active': 'Active glove',
    'no glove': 'No glove',
    'no gloves': 'No glove',
    'no': 'No glove',
    'no extend': 'No glove',
    'redo': 'No glove'
}


def normalize_condition(condition_name: Optional[str]) -> Optional[str]:
    """Normalize condition labels to the canonical set used in plots."""
    if not condition_name:
        return None

    cleaned = condition_name.strip().lower()
    normalized = CONDITION_ALIASES.get(cleaned)

    if normalized:
        return normalized

    # Fallback to title case for unforeseen labels
    return condition_name.strip().title()

@dataclass
class SegmentRecord:
    """Container for segmented EMG data with provenance metadata."""

    samples: np.ndarray
    subject: str
    session: str
    start_time: float
    end_time: float


class EMGDataLoader:
    """Load and preprocess EMG data from .npy files"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        
    def load_session(self, session_file: Path) -> np.ndarray:
        """Load EMG data from .npy file and extract channels 0-31
        
        Note: The .npy files contain multiple arrays that need to be concatenated.
        Each array is a buffer from the streaming acquisition.
        """
        arrays = []
        with open(session_file, 'rb') as f:
            while True:
                try:
                    arrays.append(np.load(f, allow_pickle=False))
                except (ValueError, EOFError):
                    break
        
        # Concatenate all buffers into single array (time x channels)
        data = np.concatenate(arrays, axis=0)
        
        # If data has more than NUM_CHANNELS columns, assume last column is timestamp
        if data.shape[1] > NUM_CHANNELS:
            # Take only first NUM_CHANNELS channels
            data = data[:, :NUM_CHANNELS]
        
        return data
    
    def load_timestamps(self, timestamps_file: Path) -> Dict:
        """Load timestamps.json file with gesture timing information"""
        if not timestamps_file.exists():
            return {}
        
        with open(timestamps_file, 'r') as f:
            timestamps = json.load(f)
        
        return timestamps
    
    def infer_sampling_rate(self, emg_data: np.ndarray, timestamps: Dict,
                            fallback: float = DEFAULT_FS_HZ) -> float:
        """Infer sampling rate from metadata and data length."""
        session_info = timestamps.get('session_info', {}) if timestamps else {}
        total_duration = session_info.get('total_elapsed_time')

        if total_duration and total_duration > 0:
            inferred = emg_data.shape[0] / total_duration
            if inferred > 0:
                return inferred

        return fallback

    def segment_by_gesture(
        self,
        emg_data: np.ndarray,
        timestamps: Dict,
        gesture_id: int,
        fs_hz: Optional[float] = None,
        subject_id: Optional[str] = None,
        session_name: Optional[str] = None
    ) -> List[SegmentRecord]:
        """Extract EMG segments corresponding to a specific object (gesture pair).
        
        Each session has 12 timestamps that define 6 objects (pairs):
        - Object 0: between timestamp 1 and timestamp 2
        - Object 1: between timestamp 3 and timestamp 4
        - Object 2: between timestamp 5 and timestamp 6
        - Object 3: between timestamp 7 and timestamp 8
        - Object 4: between timestamp 9 and timestamp 10
        - Object 5: between timestamp 11 and timestamp 12
        
        With 3 sessions per condition, each condition gets 3 repetitions of each object.
        """
        segments: List[SegmentRecord] = []

        if emg_data is None or emg_data.size == 0:
            return segments

        fs = fs_hz or self.infer_sampling_rate(emg_data, timestamps)
        if fs <= 0:
            fs = DEFAULT_FS_HZ

        # Legacy format with explicit starts/ends
        if 'gesture_starts' in timestamps and 'gesture_ends' in timestamps:
            gesture_starts = timestamps.get('gesture_starts', {})
            gesture_ends = timestamps.get('gesture_ends', {})

            if str(gesture_id) in gesture_starts:
                starts = gesture_starts[str(gesture_id)]
                ends = gesture_ends.get(str(gesture_id), [])

                for start, end in zip(starts, ends):
                    start_idx = int(max(0, np.floor(start * fs)))
                    end_idx = int(min(emg_data.shape[0], np.ceil(end * fs)))
                    if end_idx > start_idx:
                        segment = emg_data[start_idx:end_idx, :NUM_CHANNELS].copy()
                        segments.append(
                            SegmentRecord(
                                samples=segment,
                                subject=(subject_id or 'UNKNOWN').upper(),
                                session=session_name or '',
                                start_time=start,
                                end_time=end
                            )
                        )

            return segments

        # Newer format: each object is the interval between two consecutive timestamps
        # The gesture timestamps are RELATIVE to data acquisition start
        # The data has an absolute timestamp column (column 32) that we need to use
        
        # Handle both 'gestures' field (S6-S10) and 'timestamps' field (S1-S5)
        events = []
        if 'gestures' in timestamps:
            events = timestamps.get('gestures', [])
        elif 'timestamps' in timestamps:
            # S1-S5 format: convert to same structure as 'gestures'
            ts_list = timestamps.get('timestamps', [])
            for ts_entry in ts_list:
                events.append({
                    'timestamp': ts_entry.get('start_time', 0.0),
                    'gesture_id': ts_entry.get('gesture_id', 0)
                })
        
        if events:
            # Sort events by timestamp
            sorted_events = sorted(events, key=lambda evt: float(evt.get('timestamp', 0.0)))
            
            # Handle special cases where first timestamp should be skipped
            skip_offset = 0
            subj = (subject_id or '').upper()
            sess_match = re.search(r'session_(\d+)', session_name.lower()) if session_name else None
            if sess_match:
                sess_num = int(sess_match.group(1))
                should_skip = ((subj == 'S8' and sess_num == 4) or 
                              (subj == 'S9' and sess_num == 8) or
                              (subj == 'S10' and sess_num == 4))
                if should_skip:
                    skip_offset = 1
                    if gesture_id == 0:  # Only print message once per session
                        print(f"  → Skipping first timestamp for {subj} {session_name} (per notes.txt)")
            
            # Calculate which timestamp pair corresponds to this gesture_id (object)
            # Object 0: timestamps 0-1, Object 1: timestamps 2-3, etc.
            # Apply skip_offset to adjust indices
            start_idx = gesture_id * 2 + skip_offset
            end_idx = start_idx + 1
            
            if end_idx < len(sorted_events):
                start_time = float(sorted_events[start_idx].get('timestamp', 0.0))
                end_time = float(sorted_events[end_idx].get('timestamp', 0.0))
                
                # The gesture timestamps are RELATIVE to the start of acquisition
                # Column 32 contains absolute timestamps, so we need to:
                # 1. Get the first data timestamp (data acquisition start)
                # 2. Add relative gesture times to it to get absolute gesture times
                # 3. Find samples where data timestamps fall within gesture interval
                
                if emg_data.shape[1] > NUM_CHANNELS:
                    # Column 32 is the timestamp column
                    data_timestamps = emg_data[:, NUM_CHANNELS]
                    data_start_time = data_timestamps[0]
                    
                    # Convert relative gesture times to absolute
                    abs_start_time = data_start_time + start_time
                    abs_end_time = data_start_time + end_time
                    
                    # Find samples within this time range
                    mask = (data_timestamps >= abs_start_time) & (data_timestamps <= abs_end_time)
                    indices = np.where(mask)[0]
                    
                    if len(indices) > 0:
                        start_sample = indices[0]
                        end_sample = indices[-1] + 1
                        
                        segment = emg_data[start_sample:end_sample, :NUM_CHANNELS].copy()
                        segments.append(
                            SegmentRecord(
                                samples=segment,
                                subject=(subject_id or 'UNKNOWN').upper(),
                                session=session_name or '',
                                start_time=start_time,
                                end_time=end_time
                            )
                        )
                else:
                    # Fallback: use sample-based calculation if no timestamp column
                    start_sample = int(np.floor(start_time * fs))
                    end_sample = int(np.ceil(end_time * fs))
                    
                    start_sample = max(0, start_sample)
                    end_sample = min(emg_data.shape[0], end_sample)
                    
                    if end_sample > start_sample:
                        segment = emg_data[start_sample:end_sample, :NUM_CHANNELS].copy()
                        segments.append(
                            SegmentRecord(
                                samples=segment,
                                subject=(subject_id or 'UNKNOWN').upper(),
                                session=session_name or '',
                                start_time=start_time,
                                end_time=end_time
                            )
                        )

        return segments


class EMGAnalyzer:
    """Analyze and visualize EMG data across conditions"""
    
    def __init__(
        self,
        data_loader: EMGDataLoader,
        fs_hz: float = DEFAULT_FS_HZ
    ):
        self.data_loader = data_loader
        self.fs_hz = fs_hz
        self.results_dir = Path('results-analysis')
        self.results_dir.mkdir(exist_ok=True)

        # Signal cleaning configuration
        # Note: Bandpass filtering requires fs > 100 Hz (Nyquist > 50 Hz)
        # For EMG: typical bandpass is 20-450 Hz
        self.bandpass_low_hz = 20.0
        self.bandpass_high_hz = 450.0
        self.bandpass_order = 4
        self.bandpass_effective_bounds = None
        
        # Only enable bandpass if sampling rate is adequate (Nyquist > 50 Hz)
        if fs_hz >= 100:
            self._bandpass_sos = self._design_bandpass_filter(fs_hz)
        else:
            print(f"Warning: Sampling rate {fs_hz:.1f} Hz too low for EMG bandpass filtering (need >100 Hz)")
            print("  Bandpass filtering disabled. Using outlier removal only.")
            self._bandpass_sos = None

        self.outlier_threshold = 6.0
        self.outlier_noise_scale = 0.1
        self._outlier_counter = 0
        self._rng = np.random.default_rng(1337)

    def _normalize_segment(self, segment: np.ndarray, subject_id: Optional[str]) -> np.ndarray:
        """Clean segment using bandpass filtering and outlier attenuation."""

        data = segment.astype(np.float64, copy=True)
        data = self._apply_bandpass(data)
        data = self._attenuate_outliers(data)
        return data

    def _design_bandpass_filter(self, fs_hz: float) -> Optional[np.ndarray]:
        """Design bandpass filter; return SOS coefficients or None if invalid."""

        self.bandpass_effective_bounds = None
        if fs_hz is None or fs_hz <= 0:
            print("Warning: invalid sampling rate; bandpass filtering disabled.")
            return None

        nyquist = fs_hz / 2.0
        if nyquist <= 0:
            print("Warning: non-positive Nyquist frequency; bandpass filtering disabled.")
            return None

        low = max(self.bandpass_low_hz / nyquist, 1e-4)
        high = self.bandpass_high_hz / nyquist

        if high >= 1.0:
            adjusted_high = min(0.99, 0.95 * (nyquist - 1e-6) / nyquist)
            print(
                f"Warning: requested highcut {self.bandpass_high_hz} Hz exceeds Nyquist; "
                f"using {adjusted_high * nyquist:.2f} Hz instead."
            )
            high = adjusted_high

        if low >= high:
            low = max(high * 0.5, 1e-4)
            if low >= high:
                print("Warning: unable to design bandpass filter with given limits; disabling filter.")
                return None

        try:
            sos = sp_signal.butter(self.bandpass_order, [low, high], btype='band', output='sos')
        except ValueError as exc:
            print(f"Warning: bandpass design failed ({exc}); filtering disabled.")
            return None

        self.bandpass_effective_bounds = (low * nyquist, high * nyquist)
        return sos

    def _apply_bandpass(self, data: np.ndarray) -> np.ndarray:
        """Apply the configured bandpass filter if available."""

        if self._bandpass_sos is None or data.shape[0] <= 1:
            return data

        try:
            return sp_signal.sosfiltfilt(self._bandpass_sos, data, axis=0)
        except ValueError:
            return sp_signal.sosfilt(self._bandpass_sos, data, axis=0)

    def _attenuate_outliers(self, data: np.ndarray) -> np.ndarray:
        """Replace extreme samples with low-level white noise."""

        if data.size == 0:
            return data

        median = np.median(data, axis=0)
        deviation = np.abs(data - median)
        mad = np.median(deviation, axis=0)
        robust_scale = 1.4826 * np.where(mad > 0.0, mad, np.std(data, axis=0) + 1e-9)
        robust_scale = np.where(robust_scale == 0.0, 1.0, robust_scale)

        robust_z = deviation / robust_scale
        mask = robust_z > self.outlier_threshold
        if not np.any(mask):
            return data

        cleaned = data.copy()
        noise_scale = self.outlier_noise_scale * robust_scale
        noise = self._rng.normal(loc=0.0, scale=noise_scale, size=data.shape)
        cleaned[mask] = noise[mask]
        self._outlier_counter += int(mask.sum())
        return cleaned

    @property
    def outlier_samples_replaced(self) -> int:
        return self._outlier_counter

    def _condition_palette(self, condition: str, count: int) -> List[Tuple[float, float, float]]:
        """Generate MATLAB-inspired color variants for repeated samples."""

        base = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
        if isinstance(base, str):
            base_rgb = np.array(mcolors.to_rgb(base))
        else:
            base_rgb = np.array(base, dtype=float)

        if count <= 1:
            return [tuple(np.clip(base_rgb, 0.0, 1.0))]

        mix_levels = np.linspace(0.45, 1.0, count)
        variants = []
        for level in mix_levels:
            color = base_rgb * level + (1.0 - level)
            variants.append(tuple(np.clip(color, 0.0, 1.0)))

        return variants

    def _collect_segments_by_condition(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_id: int
    ) -> Dict[str, List[SegmentRecord]]:
        """Return available segments grouped by condition for an object."""

        grouped: Dict[str, List[SegmentRecord]] = {}
        for condition in CONDITIONS:
            segments = data_dict.get(condition, {}).get(object_id, [])
            if segments:
                grouped[condition] = segments
        return grouped

    def _global_channel_min_max(
        self,
        grouped_segments: Dict[str, List[SegmentRecord]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute global per-channel min/max across conditions."""

        channel_min = np.full(NUM_CHANNELS, np.inf, dtype=np.float64)
        channel_max = np.full(NUM_CHANNELS, -np.inf, dtype=np.float64)

        for records in grouped_segments.values():
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                channel_min = np.minimum(channel_min, segment.min(axis=0))
                channel_max = np.maximum(channel_max, segment.max(axis=0))

        channel_min = np.where(np.isfinite(channel_min), channel_min, 0.0)
        channel_max = np.where(np.isfinite(channel_max), channel_max, 1.0)

        # Avoid zero range
        mask = channel_max - channel_min
        channel_max = np.where(mask == 0.0, channel_min + 1.0, channel_max)

        return channel_min, channel_max

    def compute_global_channel_scale(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_id: int
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Public helper returning global min/max for stacked plotting."""

        grouped = self._collect_segments_by_condition(data_dict, object_id)
        if not grouped:
            return None
        return self._global_channel_min_max(grouped)

    @staticmethod
    def _resample_to_length(data: np.ndarray, target_len: int) -> np.ndarray:
        """Resample a 2D array along axis 0 to a fixed length using linear interpolation."""

        if data.shape[0] == target_len:
            return data

        old_idx = np.linspace(0.0, 1.0, data.shape[0])
        new_idx = np.linspace(0.0, 1.0, target_len)
        resampled = np.empty((target_len, data.shape[1]), dtype=np.float64)
        for ch in range(data.shape[1]):
            resampled[:, ch] = np.interp(new_idx, old_idx, data[:, ch])
        return resampled

    def _aggregate_condition_envelope(
        self,
        records: List[SegmentRecord],
        target_len: int = 200,
        window_ms: int = 50
    ) -> Optional[np.ndarray]:
        """Average RMS envelope across segments, resampled to a fixed length."""

        if not records:
            return None

        envelopes = []
        for record in records:
            segment = self._normalize_segment(record.samples, record.subject)
            rms = self.compute_rms(segment, window_ms=window_ms)
            resampled = self._resample_to_length(rms, target_len)
            envelopes.append(resampled)

        if not envelopes:
            return None

        stacked = np.stack(envelopes, axis=0)  # (segments, time, channels)
        return stacked.mean(axis=0)

    def figure_a_stacked_view(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        condition: str,
        object_id: int = 0,
        save_prefix: str = 'figureA_stacked',
        channel_min: Optional[np.ndarray] = None,
        channel_max: Optional[np.ndarray] = None
    ) -> Optional[plt.Figure]:
        """Figure A: Stacked view using optional global channel scaling."""

        if condition not in data_dict or object_id not in data_dict[condition]:
            print(f"No data found for condition '{condition}' and object {object_id}")
            return None

        records = data_dict[condition][object_id]
        if not records:
            print(f"No segments available for condition '{condition}' and object {object_id}")
            return None

        record = records[0]
        segment = self._normalize_segment(record.samples, record.subject)

        if segment.size == 0:
            print(f"Empty segment for condition '{condition}' and object {object_id}")
            return None

        x_axis = np.arange(segment.shape[0])
        fig, ax = plt.subplots(figsize=(16, 8))

        cmap = plt.cm.get_cmap('tab20', NUM_CHANNELS)
        for ch in range(NUM_CHANNELS):
            channel_data = segment[:, ch]
            if channel_min is not None and channel_max is not None:
                ch_min = channel_min[ch]
                ch_max = channel_max[ch]
            else:
                ch_min = np.min(channel_data)
                ch_max = np.max(channel_data)

            scale = ch_max - ch_min
            if scale <= 0:
                scale = 1.0
            normalized = (channel_data - ch_min) / scale + ch
            ax.plot(x_axis, normalized, color=cmap(ch), linewidth=0.6, alpha=0.85)

        ax.set_title(
            f"32 EMG Channels - Stacked View\nCondition: {condition} | Object {object_id} | Subject {record.subject}",
            fontsize=16,
            fontweight='bold'
        )
        ax.set_xlabel('Sample', fontsize=12)
        ax.set_ylabel('Channel (stacked & normalized)', fontsize=12)
        ax.set_yticks(range(NUM_CHANNELS))
        ax.set_yticklabels([f'Ch {i}' for i in range(NUM_CHANNELS)])
        ax.grid(True, axis='x', alpha=0.25)
        ax.margins(x=0)
        plt.tight_layout()

        condition_slug = condition.lower().replace(' ', '_')
        save_path = self.results_dir / f"{save_prefix}_{condition_slug}_object_{object_id}.svg"
        plt.savefig(save_path, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path}")

        return fig

    def figure_a_channel_overlay(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_id: int = 0,
        save_prefix: str = 'figureA_overlay',
        target_len: int = 200
    ) -> Optional[plt.Figure]:
        """Overlay averaged RMS envelopes per condition for each channel."""

        grouped = self._collect_segments_by_condition(data_dict, object_id)
        if not grouped:
            print(f"No data available to overlay for object {object_id}")
            return None

        aggregated: Dict[str, np.ndarray] = {}
        for condition, records in grouped.items():
            envelope = self._aggregate_condition_envelope(records, target_len=target_len)
            if envelope is not None:
                aggregated[condition] = envelope

        if not aggregated:
            print(f"Unable to compute overlays for object {object_id}")
            return None

        fig, axes = plt.subplots(8, 4, figsize=(20, 16), sharex=True)
        axes = axes.flatten()
        time_axis = np.linspace(0, 1, target_len)

        for ch in range(NUM_CHANNELS):
            ax = axes[ch]
            for condition in CONDITIONS:
                if condition not in aggregated:
                    continue
                color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
                if isinstance(color, str):
                    color = mcolors.to_rgb(color)
                ax.plot(time_axis, aggregated[condition][:, ch], label=condition, color=color, linewidth=1.0)

            ax.set_title(f'Ch {ch}', fontsize=9)
            ax.grid(True, alpha=0.2)
            if ch % 4 == 0:
                ax.set_ylabel('RMS (a.u.)', fontsize=9)
            if ch >= 28:
                ax.set_xlabel('Normalized Time', fontsize=9)

        # Remove unused axes if any
        for idx in range(NUM_CHANNELS, len(axes)):
            axes[idx].axis('off')

        handles, labels = axes[0].get_legend_handles_labels()
        if handles:
            fig.legend(handles, labels, loc='upper center', ncol=3, frameon=True)

        fig.suptitle(f'Averaged RMS Overlay per Channel - Object {object_id}', fontsize=16, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.97])

        save_path = self.results_dir / f"{save_prefix}_object_{object_id}.svg"
        plt.savefig(save_path, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path}")

        return fig

    def channel_statistics_summary(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_id: int = 0,
        save_prefix: str = 'figureD'
    ) -> Optional[pd.DataFrame]:
        """Compute per-channel RMS statistics and generate summary visualisations."""

        grouped = self._collect_segments_by_condition(data_dict, object_id)
        if not grouped:
            print(f"No data available for statistics of object {object_id}")
            return None

        per_condition_channel_values: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))

        for condition, records in grouped.items():
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                rms = self.compute_rms(segment, window_ms=50)
                mean_rms = rms.mean(axis=0)
                for ch in range(NUM_CHANNELS):
                    per_condition_channel_values[condition][ch].append(float(mean_rms[ch]))

        stats_rows = []
        condition_means: Dict[str, np.ndarray] = {}
        condition_stds: Dict[str, np.ndarray] = {}
        condition_counts: Dict[str, np.ndarray] = {}

        for condition in CONDITIONS:
            channel_lists = per_condition_channel_values.get(condition)
            if not channel_lists:
                continue
            mean_vec = np.zeros(NUM_CHANNELS, dtype=np.float64)
            std_vec = np.zeros(NUM_CHANNELS, dtype=np.float64)
            count_vec = np.zeros(NUM_CHANNELS, dtype=int)
            for ch in range(NUM_CHANNELS):
                values = channel_lists.get(ch, [])
                if values:
                    arr = np.asarray(values, dtype=np.float64)
                    mean_vec[ch] = arr.mean()
                    std_vec[ch] = arr.std(ddof=1) if arr.size > 1 else 0.0
                    count_vec[ch] = arr.size
                    stats_rows.append({
                        'Channel': ch,
                        'Condition': condition,
                        'Mean_RMS': mean_vec[ch],
                        'Std_RMS': std_vec[ch],
                        'Samples': arr.size
                    })
            condition_means[condition] = mean_vec
            condition_stds[condition] = std_vec
            condition_counts[condition] = count_vec

        if not stats_rows:
            print(f"Unable to derive statistics for object {object_id}")
            return None

        stats_df = pd.DataFrame(stats_rows)

        # Grouped bar chart with error bars
        present_conditions = list(condition_means.keys())
        means_matrix = np.vstack([condition_means[c] for c in present_conditions]).T
        std_matrix = np.vstack([condition_stds[c] for c in present_conditions]).T

        fig, ax = plt.subplots(figsize=(18, 6))
        x = np.arange(NUM_CHANNELS)
        num_conditions = len(present_conditions)
        width = min(0.2, 0.8 / max(num_conditions, 1))

        for idx, condition in enumerate(present_conditions):
            offsets = x + (idx - (num_conditions - 1) / 2) * width
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            if isinstance(color, str):
                color = mcolors.to_rgb(color)
            ax.bar(
                offsets,
                means_matrix[:, idx],
                yerr=std_matrix[:, idx],
                width=width,
                color=color,
                edgecolor='black',
                linewidth=0.6,
                label=condition,
                alpha=0.85,
                error_kw={'elinewidth': 1.0, 'capsize': 3}
            )

        ax.set_title(f'Channel RMS Summary - Object {object_id}', fontsize=16, fontweight='bold')
        ax.set_xlabel('Channel', fontsize=12)
        ax.set_ylabel('Mean RMS (a.u.)', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels([f'{ch}' for ch in range(NUM_CHANNELS)], rotation=45)
        ax.legend()
        ax.grid(True, axis='y', alpha=0.3)
        plt.tight_layout()

        save_path_bar = self.results_dir / f"{save_prefix}_channels_bar_object_{object_id}.svg"
        plt.savefig(save_path_bar, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path_bar}")
        plt.close(fig)

        # Difference heatmap between conditions
        comparisons = [
            ('Active glove', 'Passive glove'),
            ('Active glove', 'No glove'),
            ('Passive glove', 'No glove')
        ]
        diff_matrix = []
        diff_labels = []
        for cond_a, cond_b in comparisons:
            if cond_a in condition_means and cond_b in condition_means:
                diff = condition_means[cond_a] - condition_means[cond_b]
                diff_matrix.append(diff)
                diff_labels.append(f'{cond_a} - {cond_b}')

        if diff_matrix:
            diff_array = np.vstack(diff_matrix)
            fig, ax = plt.subplots(figsize=(18, 4))
            sns.heatmap(
                diff_array,
                cmap='coolwarm',
                center=0.0,
                annot=False,
                xticklabels=[f'{ch}' for ch in range(NUM_CHANNELS)],
                yticklabels=diff_labels,
                ax=ax
            )
            ax.set_title(f'Channel Mean RMS Differences - Object {object_id}', fontsize=14, fontweight='bold')
            ax.set_xlabel('Channel', fontsize=12)
            ax.set_ylabel('Comparison', fontsize=12)
            plt.tight_layout()

            save_path_heatmap = self.results_dir / f"{save_prefix}_channels_diff_object_{object_id}.svg"
            plt.savefig(save_path_heatmap, bbox_inches='tight', format='svg')
            print(f"Saved: {save_path_heatmap}")
            plt.close(fig)

            max_diff_idx = np.unravel_index(np.argmax(np.abs(diff_array)), diff_array.shape)
            max_comp = diff_labels[max_diff_idx[0]]
            max_channel = max_diff_idx[1]
            max_value = diff_array[max_diff_idx]
            print(f"Largest mean RMS difference: {max_comp} at Channel {max_channel} ({max_value:+.3f})")

        # Export statistics to CSV
        stats_csv_path = self.results_dir / f"channel_rms_stats_object_{object_id}.csv"
        stats_df.to_csv(stats_csv_path, index=False)
        print(f"Saved statistics table: {stats_csv_path}")

        return stats_df

    def _segment_duration(self, record: SegmentRecord) -> float:
        return max(record.end_time - record.start_time, record.samples.shape[0] / max(self.fs_hz, 1e-9))
        
    def compute_rms(self, data: np.ndarray, window_ms: int = 100) -> np.ndarray:
        """Compute RMS envelope with sliding window"""
        window_samples = max(1, int(round(window_ms * self.fs_hz / 1000)))
        n_samples, n_channels = data.shape
        
        # Pad data
        pad_size = window_samples // 2
        data_padded = np.pad(data, ((pad_size, pad_size), (0, 0)), mode='edge')
        
        # Compute RMS
        rms = np.zeros((n_samples, n_channels))
        for i in range(n_samples):
            window = data_padded[i:i+window_samples]
            rms[i] = np.sqrt(np.mean(window**2, axis=0))
        
        return rms

    def _extract_rms_features(self, segment: np.ndarray, window_size: int, step_size: int) -> np.ndarray:
        """Extract RMS features for PCA using sliding windows."""

        n_samples = segment.shape[0]
        if n_samples <= 0:
            return np.empty((0, segment.shape[1]))

        if n_samples < window_size:
            rms = np.sqrt(np.mean(segment**2, axis=0, keepdims=True))
            return rms

        windows = []
        for start in range(0, n_samples - window_size + 1, step_size):
            window = segment[start:start + window_size]
            windows.append(np.sqrt(np.mean(window**2, axis=0)))

        if not windows:
            return np.sqrt(np.mean(segment**2, axis=0, keepdims=True))

        return np.asarray(windows)
    
    def figure_b_raw_comparison(self, data_dict: Dict[str, Dict[int, List[SegmentRecord]]], 
                               object_id: int = 0, save_prefix: str = 'figureB') -> plt.Figure:
        """
        Figure B: Compare raw EMG data across 3 conditions for one object
        Shows side-by-side heatmaps and direct overlay to emphasize differences
        
        Args:
            data_dict: {condition: {object_id: [segments]}}
            object_id: Which object/pattern to plot
            save_prefix: Prefix for saved figure
        """
        valid_conditions = []
        condition_data = {}
        
        # Collect and prepare data
        for condition in CONDITIONS:
            if condition not in data_dict or object_id not in data_dict[condition]:
                continue
            records = data_dict[condition][object_id]
            if not records:
                continue
            valid_conditions.append(condition)
            
            # Average all segments for this condition
            all_segments = []
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                rms = self.compute_rms(segment, window_ms=100)
                all_segments.append(rms)
            
            # Find common length and average
            min_len = min(seg.shape[0] for seg in all_segments)
            trimmed = [seg[:min_len, :] for seg in all_segments]
            avg_rms = np.mean(trimmed, axis=0)
            condition_data[condition] = avg_rms
        
        if not valid_conditions:
            print(f"No valid data for object {object_id}")
            return None
        
        # Create comprehensive comparison figure
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # Row 1: Side-by-side heatmaps for each condition
        vmin = min(data.min() for data in condition_data.values())
        vmax = max(data.max() for data in condition_data.values())
        
        for idx, condition in enumerate(valid_conditions):
            ax = fig.add_subplot(gs[0, idx])
            data = condition_data[condition]
            
            im = ax.imshow(data.T, aspect='auto', cmap='hot', interpolation='bilinear',
                          vmin=vmin, vmax=vmax, origin='lower')
            ax.set_title(f'{condition}\nMean RMS: {data.mean():.1f} a.u.', 
                        fontsize=14, fontweight='bold')
            ax.set_xlabel('Time (samples)', fontsize=11)
            ax.set_ylabel('Channel', fontsize=11)
            ax.set_yticks(np.arange(0, NUM_CHANNELS, 4))
            
            # Add colorbar
            plt.colorbar(im, ax=ax, label='RMS Amplitude (a.u.)')
        
        # Row 2: Channel-wise mean amplitude comparison (bar plot)
        ax_bar = fig.add_subplot(gs[1, :])
        
        channel_means = {}
        for condition in valid_conditions:
            channel_means[condition] = condition_data[condition].mean(axis=0)
        
        x = np.arange(NUM_CHANNELS)
        width = 0.25
        
        for idx, condition in enumerate(valid_conditions):
            offset = (idx - 1) * width
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            ax_bar.bar(x + offset, channel_means[condition], width, 
                      label=condition, alpha=0.8, color=color, edgecolor='black', linewidth=0.5)
        
        ax_bar.set_xlabel('Channel', fontsize=12, fontweight='bold')
        ax_bar.set_ylabel('Mean RMS Amplitude (a.u.)', fontsize=12, fontweight='bold')
        ax_bar.set_title('Channel-wise Amplitude Comparison', fontsize=14, fontweight='bold')
        ax_bar.set_xticks(x[::2])
        ax_bar.set_xticklabels([f'{ch}' for ch in range(NUM_CHANNELS)][::2])
        ax_bar.legend(fontsize=11)
        ax_bar.grid(True, alpha=0.3, axis='y')
        
        # Row 3: Overall amplitude distribution (violin plot) + Time-series overlay
        ax_violin = fig.add_subplot(gs[2, 0:2])
        
        violin_data = []
        violin_labels = []
        for condition in valid_conditions:
            violin_data.append(condition_data[condition].flatten())
            violin_labels.append(condition)
        
        parts = ax_violin.violinplot(violin_data, positions=range(len(valid_conditions)),
                                     showmeans=True, showmedians=True, widths=0.7)
        
        # Color the violin plots
        for idx, (pc, condition) in enumerate(zip(parts['bodies'], valid_conditions)):
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            pc.set_facecolor(color)
            pc.set_alpha(0.7)
        
        ax_violin.set_xticks(range(len(valid_conditions)))
        ax_violin.set_xticklabels(violin_labels, fontsize=12, fontweight='bold')
        ax_violin.set_ylabel('RMS Amplitude (a.u.)', fontsize=12, fontweight='bold')
        ax_violin.set_title('Amplitude Distribution Comparison', fontsize=14, fontweight='bold')
        ax_violin.grid(True, alpha=0.3, axis='y')
        
        # Time-series overlay of mean across all channels
        ax_overlay = fig.add_subplot(gs[2, 2])
        
        # Find max length for proper x-axis and pad shorter signals
        max_len = max(condition_data[c].shape[0] for c in valid_conditions)
        
        for condition in valid_conditions:
            data = condition_data[condition]
            mean_over_channels = data.mean(axis=1)
            
            # Pad with last value if shorter than max
            if len(mean_over_channels) < max_len:
                pad_length = max_len - len(mean_over_channels)
                mean_over_channels = np.pad(mean_over_channels, (0, pad_length), 
                                           mode='edge')  # Repeat last value
            
            time = np.arange(len(mean_over_channels))
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            ax_overlay.plot(time, mean_over_channels, label=f'{condition} ({data.shape[0]} samples)', 
                          linewidth=2.5, alpha=0.8, color=color)
        
        ax_overlay.set_xlabel('Time (samples)', fontsize=11, fontweight='bold')
        ax_overlay.set_ylabel('Mean RMS (all channels)', fontsize=11, fontweight='bold')
        ax_overlay.set_title('Temporal Comparison (padded to same length)', fontsize=13, fontweight='bold')
        ax_overlay.legend(fontsize=9)
        ax_overlay.grid(True, alpha=0.3)
        ax_overlay.set_xlim(0, max_len)  # Set proper x-axis limit
        
        # Overall figure title
        fig.suptitle(f'Comprehensive EMG Comparison Across Conditions - Object {object_id}', 
                    fontsize=18, fontweight='bold', y=0.98)
        
        # Save figure as SVG for publication
        save_path = self.results_dir / f'{save_prefix}_object_{object_id}.svg'
        plt.savefig(save_path, dpi=300, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path}")
        plt.close(fig)
        
        return fig
    
    def figure_b_amplitude_summary(self, data_dict: Dict[str, Dict[int, List[SegmentRecord]]], 
                                   object_id: int = 0, save_prefix: str = 'figureB_summary') -> Optional[plt.Figure]:
        """
        Statistical comparison of amplitude across conditions.
        Shows box plots and mean differences with significance indicators.
        """
        # Collect all RMS values per condition
        condition_rms_values = {}
        condition_mean_per_segment = {}
        
        for condition in CONDITIONS:
            if condition not in data_dict or object_id not in data_dict[condition]:
                continue
            
            records = data_dict[condition][object_id]
            if not records:
                continue
            
            all_rms = []
            segment_means = []
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                rms = self.compute_rms(segment, window_ms=100)
                all_rms.append(rms.flatten())  # All values
                segment_means.append(rms.mean())  # Mean per segment
            
            if all_rms:
                condition_rms_values[condition] = np.concatenate(all_rms)
                condition_mean_per_segment[condition] = np.array(segment_means)
        
        if not condition_rms_values:
            print(f"No valid data for amplitude summary of object {object_id}")
            return None
        
        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Subplot 1: Box plot of all RMS values
        positions = list(range(len(condition_rms_values)))
        box_data = [condition_rms_values[c] for c in CONDITIONS if c in condition_rms_values]
        labels = [c for c in CONDITIONS if c in condition_rms_values]
        colors = [MATLAB_CONDITION_BASE_COLORS.get(c, '#1f77b4') for c in labels]
        
        bp = ax1.boxplot(box_data, positions=positions, widths=0.6, patch_artist=True,
                         showfliers=False, notch=True,
                         boxprops=dict(linewidth=1.5),
                         medianprops=dict(linewidth=2, color='red'),
                         whiskerprops=dict(linewidth=1.5),
                         capprops=dict(linewidth=1.5))
        
        # Color the boxes
        for patch, color in zip(bp['boxes'], colors):
            if isinstance(color, str):
                color = mcolors.to_rgb(color)
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        # Add mean markers
        for idx, condition in enumerate(labels):
            mean_val = condition_rms_values[condition].mean()
            ax1.plot(idx, mean_val, 'D', color='black', markersize=10, 
                    markeredgewidth=1.5, markeredgecolor='white', zorder=10,
                    label='Mean' if idx == 0 else '')
        
        ax1.set_xticks(positions)
        ax1.set_xticklabels(labels, fontsize=12, fontweight='bold')
        ax1.set_ylabel('RMS Amplitude (a.u.)', fontsize=13, fontweight='bold')
        ax1.set_title('Overall Amplitude Distribution', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.legend(fontsize=10)
        
        # Add mean values as text
        for idx, condition in enumerate(labels):
            mean_val = condition_rms_values[condition].mean()
            ax1.text(idx, ax1.get_ylim()[1] * 0.95, f'{mean_val:.1f}',
                    ha='center', fontsize=11, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Subplot 2: Mean per segment with statistical comparison
        positions2 = list(range(len(condition_mean_per_segment)))
        labels2 = [c for c in CONDITIONS if c in condition_mean_per_segment]
        
        # Violin plot
        parts = ax2.violinplot([condition_mean_per_segment[c] for c in labels2],
                              positions=positions2, widths=0.7, showmeans=True, showmedians=True)
        
        # Color the violins
        for idx, (pc, condition) in enumerate(zip(parts['bodies'], labels2)):
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, '#1f77b4')
            if isinstance(color, str):
                color = mcolors.to_rgb(color)
            pc.set_facecolor(color)
            pc.set_alpha(0.7)
        
        # Overlay individual points
        for idx, condition in enumerate(labels2):
            values = condition_mean_per_segment[condition]
            x = np.random.normal(idx, 0.04, size=len(values))
            ax2.scatter(x, values, alpha=0.6, s=50, edgecolors='black', linewidths=0.5,
                       color=MATLAB_CONDITION_BASE_COLORS.get(condition, '#1f77b4'))
        
        ax2.set_xticks(positions2)
        ax2.set_xticklabels(labels2, fontsize=12, fontweight='bold')
        ax2.set_ylabel('Mean RMS per Segment (a.u.)', fontsize=13, fontweight='bold')
        ax2.set_title(f'Segment-wise Comparison (n={[len(condition_mean_per_segment[c]) for c in labels2]})', 
                     fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Statistical tests moved to separate summary files
        # See: results-analysis/statistical_summary_amplitude.md
        
        fig.suptitle(f'Statistical Amplitude Comparison - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save as SVG
        save_path_svg = self.results_dir / f'{save_prefix}_object_{object_id}.svg'
        plt.savefig(save_path_svg, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path_svg}")
        plt.close(fig)

        return fig
    
    def figure_c_heatmap(self, data_dict: Dict[str, Dict[int, List[SegmentRecord]]], 
                        object_id: int = 0, save_prefix: str = 'figureC_heatmap') -> plt.Figure:
        """
        Figure C: Heatmap visualization across 3 conditions + difference maps
        Uses GLOBAL color scale to show amplitude differences clearly
        
        Shows channel activity (RMS) over time for each condition + pairwise differences
        """
        # First pass: compute global RMS range across all conditions
        global_vmin = np.inf
        global_vmax = -np.inf
        
        condition_rms = {}
        for condition in CONDITIONS:
            if condition not in data_dict or object_id not in data_dict[condition]:
                continue
            
            records = data_dict[condition][object_id]
            if not records or len(records) == 0:
                continue
            
            # Average all segments for this condition
            all_rms = []
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                rms = self.compute_rms(segment, window_ms=50)
                all_rms.append(rms)
            
            # Find common length and average
            min_len = min(r.shape[0] for r in all_rms)
            trimmed = [r[:min_len, :] for r in all_rms]
            avg_rms = np.mean(trimmed, axis=0)
            
            # Downsample for visualization
            downsample_factor = max(1, int(self.fs_hz / 10))  # Target ~10 Hz
            rms_downsampled = avg_rms[::downsample_factor]
            condition_rms[condition] = rms_downsampled
            
            global_vmin = min(global_vmin, rms_downsampled.min())
            global_vmax = max(global_vmax, rms_downsampled.max())
        
        if not condition_rms:
            print(f"No data available for heatmap of object {object_id}")
            return None
        
        # Add 5% margin to color scale
        vrange = global_vmax - global_vmin
        global_vmin = max(0, global_vmin - 0.05 * vrange)
        global_vmax = global_vmax + 0.05 * vrange
        
        # Create figure with 2 rows: conditions and differences
        fig = plt.figure(figsize=(18, 10))
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.35, height_ratios=[1, 0.9])
        
        # Row 1: Individual condition heatmaps
        for idx, condition in enumerate(CONDITIONS):
            if condition not in condition_rms:
                continue
            
            ax = fig.add_subplot(gs[0, idx])
            rms_downsampled = condition_rms[condition]
            
            downsample_factor = max(1, int(self.fs_hz / 10))
            duration = (rms_downsampled.shape[0] - 1) * downsample_factor / max(self.fs_hz, 1e-9) if rms_downsampled.shape[0] > 1 else 0.0
            
            # Transpose for heatmap (channels on y-axis, time on x-axis)
            extent = [0, duration, 0, NUM_CHANNELS]
            im = ax.imshow(
                rms_downsampled.T,
                aspect='auto',
                cmap='hot',
                interpolation='bilinear',
                origin='lower',
                extent=extent,
                vmin=global_vmin,
                vmax=global_vmax
            )
            
            # Add condition color border
            color_border = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            if isinstance(color_border, str):
                color_border = mcolors.to_rgb(color_border)
            for spine in ax.spines.values():
                spine.set_edgecolor(color_border)
                spine.set_linewidth(4)
            
            # Add mean amplitude annotation
            mean_amp = rms_downsampled.mean()
            ax.set_title(f'{condition}\nMean: {mean_amp:.1f} a.u.', 
                        fontsize=13, fontweight='bold')
            ax.set_xlabel('Time (s)', fontsize=11)
            ax.set_ylabel('Channel', fontsize=11)
            ax.set_yticks(np.arange(0, NUM_CHANNELS, 4))
            ax.set_yticklabels(np.arange(0, NUM_CHANNELS, 4))
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('RMS (a.u.)', fontsize=10)
        
        # Row 2: Difference heatmaps
        comparisons = [
            ('Active glove', 'No glove'),
            ('Active glove', 'Passive glove'),
            ('No glove', 'Passive glove')
        ]
        
        # Calculate max difference for symmetric color scale
        max_diff = 0
        diff_maps = {}
        for cond_a, cond_b in comparisons:
            if cond_a in condition_rms and cond_b in condition_rms:
                # Match lengths
                len_a = condition_rms[cond_a].shape[0]
                len_b = condition_rms[cond_b].shape[0]
                min_len = min(len_a, len_b)
                diff = condition_rms[cond_a][:min_len] - condition_rms[cond_b][:min_len]
                diff_maps[f'{cond_a} - {cond_b}'] = diff
                max_diff = max(max_diff, np.abs(diff).max())
        
        for idx, (label, diff_data) in enumerate(diff_maps.items()):
            ax = fig.add_subplot(gs[1, idx])
            
            downsample_factor = max(1, int(self.fs_hz / 10))
            duration = (diff_data.shape[0] - 1) * downsample_factor / max(self.fs_hz, 1e-9) if diff_data.shape[0] > 1 else 0.0
            extent = [0, duration, 0, NUM_CHANNELS]
            
            im = ax.imshow(
                diff_data.T,
                aspect='auto',
                cmap='coolwarm',
                interpolation='bilinear',
                origin='lower',
                extent=extent,
                vmin=-max_diff,
                vmax=max_diff
            )
            
            mean_diff = diff_data.mean()
            ax.set_title(f'Difference: {label}\nMean Δ: {mean_diff:+.1f} a.u.', 
                        fontsize=12, fontweight='bold')
            ax.set_xlabel('Time (s)', fontsize=11)
            ax.set_ylabel('Channel', fontsize=11)
            ax.set_yticks(np.arange(0, NUM_CHANNELS, 4))
            ax.set_yticklabels(np.arange(0, NUM_CHANNELS, 4))
            
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Δ RMS (a.u.)', fontsize=10)
        
        fig.suptitle(f'EMG Activity Heatmap Comparison - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        
        # Save as SVG for publication
        save_path_svg = self.results_dir / f'{save_prefix}_object_{object_id}.svg'
        plt.savefig(save_path_svg, dpi=300, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path_svg}")
        plt.close(fig)
        
        return fig
    
    def figure_c_spatial_heatmap(self, data_dict: Dict[str, Dict[int, List[SegmentRecord]]], 
                                object_id: int = 0, save_prefix: str = 'figureC_spatial') -> plt.Figure:
        """
        Spatial heatmap showing mean RMS per electrode in physical sleeve layout.
        Shows both mean across all segments and example from one subject.
        """
        channel_layout = get_channel_spatial_layout()
        
        # Collect data for each condition
        condition_means = {}
        condition_examples = {}
        
        for condition in CONDITIONS:
            if condition not in data_dict or object_id not in data_dict[condition]:
                continue
            
            records = data_dict[condition][object_id]
            if not records:
                continue
            
            # Compute mean RMS across all segments (all subjects)
            all_ch_rms = []
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                ch_mean_rms = np.sqrt(np.mean(segment**2, axis=0))  # RMS per channel
                all_ch_rms.append(ch_mean_rms)
            
            if all_ch_rms:
                condition_means[condition] = np.mean(all_ch_rms, axis=0)
                # Use first segment as example
                first_seg = self._normalize_segment(records[0].samples, records[0].subject)
                condition_examples[condition] = np.sqrt(np.mean(first_seg**2, axis=0))
        
        if not condition_means:
            print(f"No data for spatial heatmap of object {object_id}")
            return None
        
        # Create figure with 2 rows: Mean and Example
        fig, axes = plt.subplots(2, len(condition_means), figsize=(5 * len(condition_means), 8))
        if len(condition_means) == 1:
            axes = axes.reshape(-1, 1)
        
        # Global color scale
        all_values = np.concatenate([v for v in condition_means.values()])
        vmin, vmax = all_values.min(), all_values.max()
        
        # Row 1: Mean RMS across all segments
        for idx, condition in enumerate(CONDITIONS):
            if condition not in condition_means:
                continue
            
            ax = axes[0, idx]
            
            # Map channels to spatial layout
            spatial_map = np.zeros_like(channel_layout, dtype=float)
            for row in range(channel_layout.shape[0]):
                for col in range(channel_layout.shape[1]):
                    ch = channel_layout[row, col]
                    spatial_map[row, col] = condition_means[condition][ch]
            
            im = ax.imshow(spatial_map, cmap='hot', vmin=vmin, vmax=vmax, 
                          interpolation='bilinear', aspect='auto')
            
            # Add channel labels
            for row in range(channel_layout.shape[0]):
                for col in range(channel_layout.shape[1]):
                    ch = channel_layout[row, col]
                    ax.text(col, row, f'{ch}', ha='center', va='center', 
                           fontsize=7, color='white' if spatial_map[row, col] > (vmin + vmax)/2 else 'black')
            
            ax.set_title(f'{condition}\nMean: {condition_means[condition].mean():.1f} a.u.', 
                        fontsize=13, fontweight='bold')
            ax.set_xlabel('Electrode Column', fontsize=10)
            ax.set_ylabel('Row', fontsize=10)
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Top', 'Bottom'])
            
            plt.colorbar(im, ax=ax, label='Mean RMS (a.u.)')
        
        # Row 2: Example from one subject
        for idx, condition in enumerate(CONDITIONS):
            if condition not in condition_examples:
                continue
            
            ax = axes[1, idx]
            
            # Map channels to spatial layout
            spatial_map = np.zeros_like(channel_layout, dtype=float)
            for row in range(channel_layout.shape[0]):
                for col in range(channel_layout.shape[1]):
                    ch = channel_layout[row, col]
                    spatial_map[row, col] = condition_examples[condition][ch]
            
            im = ax.imshow(spatial_map, cmap='hot', vmin=vmin, vmax=vmax, 
                          interpolation='bilinear', aspect='auto')
            
            # Add channel labels
            for row in range(channel_layout.shape[0]):
                for col in range(channel_layout.shape[1]):
                    ch = channel_layout[row, col]
                    ax.text(col, row, f'{ch}', ha='center', va='center', 
                           fontsize=7, color='white' if spatial_map[row, col] > (vmin + vmax)/2 else 'black')
            
            ax.set_title(f'Example Subject\nMean: {condition_examples[condition].mean():.1f} a.u.', 
                        fontsize=12, fontweight='bold')
            ax.set_xlabel('Electrode Column', fontsize=10)
            ax.set_ylabel('Row', fontsize=10)
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Top', 'Bottom'])
            
            plt.colorbar(im, ax=ax, label='RMS (a.u.)')
        
        axes[0, 0].set_ylabel('MEAN\n(All Subjects)\n\nRow', fontsize=11, fontweight='bold')
        axes[1, 0].set_ylabel('EXAMPLE\n(1 Subject)\n\nRow', fontsize=11, fontweight='bold')
        
        fig.suptitle(f'Spatial EMG Activity Map - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save as SVG
        save_path_svg = self.results_dir / f'{save_prefix}_object_{object_id}.svg'
        plt.savefig(save_path_svg, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path_svg}")
        plt.close(fig)
        
        return fig
    
    def figure_c_pca(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_ids: List[int] = None,
        save_prefix: str = 'figC_pca'
    ) -> Optional[plt.Figure]:
        """Figure C: MATLAB-inspired PCA overview with component subplots per object."""

        if object_ids is None:
            object_ids = [0]

        n_objects = len(object_ids)
        if n_objects == 0:
            print("No objects provided for PCA analysis")
            return None

        fig, axes = plt.subplots(3, n_objects, figsize=(5 * n_objects, 9), squeeze=False, sharey='row')

        window_size = max(1, int(round(0.25 * self.fs_hz)))
        step_size = max(1, int(round(0.125 * self.fs_hz)))

        for col, obj_id in enumerate(object_ids):
            all_features = []
            segment_meta: List[Tuple[str, str, int]] = []

            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue

                for record in data_dict[condition][obj_id]:
                    normalized = self._normalize_segment(record.samples, record.subject)
                    features = self._extract_rms_features(normalized, window_size, step_size)
                    if features.size == 0:
                        continue
                    all_features.append(features)
                    segment_meta.append((condition, record.subject, features.shape[0]))

            if not all_features:
                for row_idx in range(3):
                    ax = axes[row_idx, col]
                    ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center', transform=ax.transAxes)
                    ax.axis('off')
                continue

            X = np.vstack(all_features)
            if X.shape[0] < 3:
                for row_idx in range(3):
                    ax = axes[row_idx, col]
                    ax.text(0.5, 0.5, 'Not enough samples for PCA', ha='center', va='center', transform=ax.transAxes)
                    ax.axis('off')
                continue

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            pca = PCA(n_components=3)
            scores = pca.fit_transform(X_scaled)
            
            # Use absolute values to avoid negative components
            scores = np.abs(scores)

            subject_condition_scores: Dict[Tuple[str, str], List[np.ndarray]] = defaultdict(list)
            offset = 0
            for condition, subject, length in segment_meta:
                segment_scores = scores[offset:offset + length]
                offset += length
                if segment_scores.size == 0:
                    continue
                subject_condition_scores[(condition, subject)].append(segment_scores.mean(axis=0))

            condition_subject_vectors: Dict[str, List[np.ndarray]] = defaultdict(list)
            for (condition, subject), vectors in subject_condition_scores.items():
                if not vectors:
                    continue
                subject_mean = np.mean(vectors, axis=0)
                condition_subject_vectors[condition].append(subject_mean)

            present_conditions = [cond for cond in CONDITIONS if cond in condition_subject_vectors]
            if not present_conditions:
                for row_idx in range(3):
                    ax = axes[row_idx, col]
                    ax.text(0.5, 0.5, 'No condition data', ha='center', va='center', transform=ax.transAxes)
                    ax.axis('off')
                continue

            condition_arrays: Dict[str, np.ndarray] = {}
            for condition in present_conditions:
                condition_arrays[condition] = np.vstack(condition_subject_vectors[condition])

            variance_text = [f'PC{i+1}: {var:.1%}' for i, var in enumerate(pca.explained_variance_ratio_[:3])]

            for row_idx in range(3):
                component_name = f'PC{row_idx + 1}'
                ax = axes[row_idx, col]
                ax.grid(True, axis='y', alpha=0.25)

                bars_positions = np.arange(len(present_conditions))
                means = []
                stds = []
                bar_colors = []

                for condition in present_conditions:
                    component_values = condition_arrays[condition][:, row_idx]
                    means.append(np.mean(component_values))
                    stds.append(np.std(component_values, ddof=1) if component_values.size > 1 else 0.0)
                    base_color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
                    if isinstance(base_color, str):
                        bar_colors.append(mcolors.to_rgb(base_color))
                    else:
                        bar_colors.append(base_color)

                bars = ax.bar(
                    bars_positions,
                    means,
                    yerr=stds,
                    color=bar_colors,
                    alpha=0.85,
                    width=0.55,
                    edgecolor='black',
                    linewidth=0.8,
                    error_kw={'elinewidth': 1.0, 'capsize': 4, 'capthick': 1.0}
                )

                for idx, condition in enumerate(present_conditions):
                    component_values = condition_arrays[condition][:, row_idx]
                    if component_values.size == 0:
                        continue
                    palette = self._condition_palette(condition, component_values.size)
                    offsets = np.linspace(-0.15, 0.15, component_values.size)
                    for value, offset_val, color in zip(component_values, offsets, palette):
                        ax.scatter(
                            bars_positions[idx] + offset_val,
                            value,
                            color=color,
                            edgecolors='black',
                            linewidth=0.4,
                            s=35,
                            zorder=3
                        )

                ax.set_xticks(bars_positions)
                ax.set_xticklabels([cond for cond in present_conditions], rotation=15, ha='right')
                ax.set_ylabel(f'{component_name} Score (a.u.)', fontsize=11)

                if row_idx == 0:
                    ax.set_title(f'Object {obj_id}\n{variance_text[row_idx]}', fontsize=13, fontweight='bold')
                else:
                    ax.set_title(variance_text[row_idx], fontsize=11, fontweight='bold')

                if row_idx == 2:
                    ax.set_xlabel('Condition', fontsize=11)

            # Create legend once per column using proxy artists
            proxy_patches = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=bar_colors[i],
                                        markeredgecolor='black', markersize=8)
                             for i in range(len(present_conditions))]
            axes[0, col].legend(
                proxy_patches,
                [f'{cond} (n={condition_arrays[cond].shape[0]})' for cond in present_conditions],
                loc='upper right',
                fontsize=9,
                frameon=True
            )
            
            # Add magnitude comparison annotation with statistical test
            # Calculate overall magnitude (L2 norm across all PCs)
            from scipy import stats
            
            condition_magnitudes = {}
            condition_magnitude_values = {}
            for condition in present_conditions:
                # Magnitude for each subject
                mags = np.linalg.norm(condition_arrays[condition], axis=1)
                condition_magnitude_values[condition] = mags
                condition_magnitudes[condition] = np.mean(mags)
            
            # Statistical tests moved to separate summary files
            # See: results-analysis/statistical_summary_pca.md

        plt.tight_layout()

        # Save as SVG
        save_path_svg = self.results_dir / f'{save_prefix}_objects_{"_".join(map(str, object_ids))}.svg'
        plt.savefig(save_path_svg, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path_svg}")
        plt.close(fig)

        return fig
    
    def analyze_time_consumption(self, data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
                                object_ids: List[int] = None) -> pd.DataFrame:
        """
        Analyze time consumption differences across conditions
        
        Returns DataFrame with timing statistics
        """
        if object_ids is None:
            object_ids = list(range(NUM_GESTURES))
        
        results = []
        
        for condition in CONDITIONS:
            if condition not in data_dict:
                continue
            
            for obj_id in object_ids:
                if obj_id not in data_dict[condition]:
                    continue
                
                records = data_dict[condition][obj_id]
                
                for seg_idx, record in enumerate(records):
                    duration_sec = self._segment_duration(record)
                    
                    results.append({
                        'Condition': condition,
                        'Object': obj_id,
                        'Segment': seg_idx,
                        'Duration (s)': duration_sec
                    })
        
        df = pd.DataFrame(results)
        
        if len(df) > 0:
            # Create summary statistics
            summary = df.groupby(['Condition', 'Object'])['Duration (s)'].agg([
                'count', 'mean', 'std', 'min', 'max'
            ]).reset_index()
            
            print("\n=== Time Consumption Analysis ===")
            print(summary.to_string())
            
            # Save to CSV
            save_path = self.results_dir / 'time_consumption_analysis.csv'
            summary.to_csv(save_path, index=False)
            print(f"\nSaved: {save_path}")
            
            # Create visualization
            self._plot_time_consumption(df)
        
        return df
    
    def _plot_time_consumption(self, df: pd.DataFrame):
        """Plot time consumption comparison"""
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        # Box plot
        ax = axes[0]
        df_plot = df.copy()
        sns.boxplot(data=df_plot, x='Condition', y='Duration (s)', 
                   palette=CONDITION_COLORS, ax=ax)
        ax.set_title('Task Duration by Condition', fontsize=14, fontweight='bold')
        ax.set_ylabel('Duration (seconds)', fontsize=12)
        ax.set_xlabel('Condition', fontsize=12)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Violin plot by object
        ax = axes[1]
        sns.violinplot(data=df_plot, x='Object', y='Duration (s)', 
                      hue='Condition', palette=CONDITION_COLORS, ax=ax)
        ax.set_title('Task Duration by Object and Condition', fontsize=14, fontweight='bold')
        ax.set_ylabel('Duration (seconds)', fontsize=12)
        ax.set_xlabel('Object ID', fontsize=12)
        ax.legend(title='Condition', bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        save_path = self.results_dir / 'time_consumption_comparison.svg'
        plt.savefig(save_path, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path}")
        plt.close()


def generate_example_data(fs_hz: float = DEFAULT_FS_HZ) -> Dict[str, Dict[int, List[SegmentRecord]]]:
    """
    Generate example data for demonstration
    
    This creates synthetic EMG-like data to demonstrate the analysis pipeline
    when real data is not available.
    """
    print("\n=== Generating example data ===")
    print("Note: Using synthetic data for demonstration.")
    print("Replace with actual .npy files from md-emg-python/data/healthy/\n")
    
    data_dict: Dict[str, Dict[int, List[SegmentRecord]]] = {}
    
    # Different activation patterns for each condition
    condition_params = {
        'Passive glove': {'amplitude': 30, 'noise': 5, 'duration': 3},
        'Active glove': {'amplitude': 50, 'noise': 8, 'duration': 4},
        'No glove': {'amplitude': 40, 'noise': 6, 'duration': 3.5}
    }
    
    for condition, params in condition_params.items():
        data_dict[condition] = {}
        
        # Generate data for NUM_GESTURES objects
        for obj_id in range(NUM_GESTURES):
            segments = []
            
            # Generate 2-3 segments per object
            n_segments = np.random.randint(2, 4)
            for _ in range(n_segments):
                duration = params['duration'] + np.random.randn() * 0.5
                n_samples = int(max(1, duration * fs_hz))
                
                # Create synthetic EMG with different patterns per channel
                emg = np.zeros((n_samples, NUM_CHANNELS))
                
                for ch in range(NUM_CHANNELS):
                    # Base signal with some temporal structure
                    t = np.linspace(0, duration, n_samples, endpoint=False)
                    freq = 20 + ch * 2  # Different frequency per channel
                    
                    # Muscle activation pattern (burst-like)
                    activation = np.exp(-((t - duration/2)**2) / (duration/4)**2)
                    signal = params['amplitude'] * activation * np.sin(2 * np.pi * freq * t)
                    
                    # Add noise
                    noise = np.random.randn(n_samples) * params['noise']
                    
                    emg[:, ch] = signal + noise
                
                segments.append(
                    SegmentRecord(
                        samples=emg.astype(np.float64),
                        subject='SYNTHETIC',
                        session=f'synthetic_{condition}_{obj_id}',
                        start_time=0.0,
                        end_time=n_samples / (fs_hz if fs_hz and fs_hz > 0 else DEFAULT_FS_HZ)
                    )
                )
            
            data_dict[condition][obj_id] = segments
    
    return data_dict


def load_real_data(data_dir: Path) -> Tuple[Optional[Dict[str, Dict[int, List[SegmentRecord]]]], Optional[float]]:
    """Load EMG data from S1-S5 and S6-S10 (excluding S0).
    Uses notes.txt for conditions and handles special cases."""

    # Exclude S0, include S1-S5 (iPhone stopwatch) and S6-S10 (proper 12-timestamp protocol)
    SKIP_SUBJECTS = {'S0'}  # S0 excluded per user request
    SKIP_SESSIONS = {
        'S1': {0, 1, 2},  # bad (0), mvc (1), bad (2)
        'S2': {0},  # mvc
        'S3': {0, 1},  # mvc, bad
        'S4': {0, 4},  # mvc, fall
        'S5': {0},  # mvc
        'S6': {0, 10},  # rearranged, mvc
        'S7': {0, 1, 2, 3, 8},  # mvc, disconnected, bad
        'S8': {0},  # mvc (session 4 processed with first timestamp skipped)
        'S9': {1},  # mvc (session 8 now has manual timestamps from notes.txt)
        'S10': {0, 6},  # mvc, bad (session 4 processed with first timestamp skipped)
    }
    
    # Fallback conditions from notes.txt for sessions missing metadata
    FALLBACK_CONDITIONS = {
        'S1': {3: 'no', 4: 'no', 5: 'passive', 6: 'passive', 7: 'passive', 8: 'active', 9: 'active', 10: 'active', 11: 'no'},
        'S2': {1: 'passive', 2: 'passive', 3: 'passive', 4: 'no', 5: 'no', 6: 'no', 7: 'active', 8: 'active', 9: 'active'},
        'S3': {2: 'active', 3: 'active', 4: 'active', 5: 'no', 6: 'no', 7: 'no', 8: 'passive', 9: 'passive', 10: 'passive'},
        'S4': {1: 'no', 2: 'no', 3: 'no', 5: 'redo', 6: 'active', 7: 'active', 8: 'active', 9: 'no extend', 10: 'passive', 11: 'passive', 12: 'passive'},
        'S5': {1: 'active', 2: 'active', 3: 'active', 4: 'passive', 5: 'passive', 6: 'passive', 7: 'no', 8: 'no', 9: 'no'},
        'S6': {1: 'passive', 2: 'passive', 3: 'passive', 4: 'active', 5: 'active', 6: 'active', 7: 'no', 8: 'no', 9: 'no'},
        'S7': {4: 'no', 5: 'no', 6: 'no', 7: 'passive', 9: 'passive', 10: 'passive', 11: 'active', 12: 'active', 13: 'active'},
        'S8': {1: 'passive', 2: 'passive', 3: 'passive', 4: 'no', 6: 'no', 7: 'passive', 8: 'active', 9: 'active', 10: 'active'},
        'S9': {2: 'passive', 3: 'passive', 4: 'passive', 5: 'no', 6: 'no', 7: 'no', 8: 'active', 10: 'active', 13: 'active'},
        'S10': {1: 'no', 2: 'no', 3: 'no', 4: 'active', 5: 'active', 7: 'active', 8: 'passive', 9: 'passive', 10: 'passive'},
    }

    data_dir = Path(data_dir)

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return None, None

    loader = EMGDataLoader(data_dir)
    data_dict: Dict[str, Dict[int, List[SegmentRecord]]] = {}
    fs_estimates: List[float] = []

    subject_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    if not subject_dirs:
        print(f"No subject subdirectories found in {data_dir}")
        return None, None

    skipped_count = 0
    loaded_count = 0

    for subject_dir in subject_dirs:
        subject_id = subject_dir.name.upper()
        
        # Skip S0 entirely
        if subject_id in SKIP_SUBJECTS:
            print(f"Skipping {subject_id} (excluded per notes.txt)")
            continue
        
        logs_dir = subject_dir / 'emg_logs'
        if not logs_dir.exists():
            print(f"Skipping {subject_id} (missing emg_logs folder)")
            continue

        print(f"Scanning: {logs_dir}")
        
        # Special case: S9 session 8 has no timestamps JSON but has manual log in notes.txt
        if subject_id == 'S9':
            session_08_path = logs_dir / 'session_08.npy'
            if session_08_path.exists():
                # Check if we have timestamps for it
                ts_08_path = logs_dir / 'session_08_timestamps.json'
                if not ts_08_path.exists():
                    print(f"  Session 08: found .npy but no timestamps JSON - creating manual timestamps from notes.txt")
                    manual_times = [14.398, 20.726, 27.053, 35.189, 41.269, 51.110, 58.237, 64.615, 70.138, 75.865, 81.690, 89.474]
                    manual_timestamps = {
                        'gestures': [{'gesture_id': i, 'timestamp': t} for i, t in enumerate(manual_times)],
                        'session_info': {
                            'session_number': 8,
                            'total_elapsed_time': 90.0,
                            'condition': 'active'
                        }
                    }
                    # Save it so we can process it normally
                    with open(ts_08_path, 'w') as f:
                        json.dump(manual_timestamps, f, indent=2)
                    print(f"  Created {ts_08_path.name} with 12 gesture timestamps from notes.txt log")
        
        timestamp_files = sorted(logs_dir.glob('*_timestamps.json'))
        if not timestamp_files:
            print(f"  No timestamp files found in {logs_dir}")
            continue

        for ts_file in timestamp_files:
            timestamps = loader.load_timestamps(ts_file)
            if not timestamps:
                print(f"  Skipping {ts_file.name}: could not parse timestamps")
                skipped_count += 1
                continue
            
            session_info = timestamps.get('session_info', {})
            session_num = session_info.get('session_number')
            
            # If session number not in JSON, extract from filename
            if session_num is None:
                match = re.search(r'session_(\d+)', ts_file.name)
                if match:
                    session_num = int(match.group(1))
                else:
                    print(f"  Skipping {ts_file.name}: cannot determine session number")
                    skipped_count += 1
                    continue
            
            # Check if this session should be skipped per notes.txt
            if subject_id in SKIP_SESSIONS and session_num in SKIP_SESSIONS[subject_id]:
                print(f"  Skipping session {session_num:02d}: bad data per notes.txt")
                skipped_count += 1
                continue
            
            # Get condition from JSON or fallback to notes.txt
            condition_raw = session_info.get('condition')
            if not condition_raw and subject_id in FALLBACK_CONDITIONS:
                condition_raw = FALLBACK_CONDITIONS[subject_id].get(session_num)
                if condition_raw:
                    print(f"  Session {session_num:02d}: using condition '{condition_raw}' from notes.txt")
            
            condition = normalize_condition(condition_raw)
            if not condition:
                print(f"  Skipping session {session_num:02d}: unknown condition (JSON={condition_raw}, no fallback)")
                skipped_count += 1
                continue

            candidates: List[Path] = []
            session_file = session_info.get('session_file')
            if session_file:
                candidates.append(data_dir / session_file)

            base_name = ts_file.stem.replace('_timestamps', '')
            candidates.append(ts_file.with_name(f"{base_name}.npy"))

            if 'session_' in base_name:
                suffix = base_name.split('session_')[-1]
                candidates.append(ts_file.parent / f"session_{suffix}.npy")

            seen: Set[Path] = set()
            unique_candidates = []
            for path in candidates:
                if path not in seen:
                    unique_candidates.append(path)
                    seen.add(path)

            session_path = next((path for path in unique_candidates if path.exists()), None)
            if not session_path:
                print(f"  Warning: session file not found for {ts_file.name}")
                continue

            try:
                emg_data = loader.load_session(session_path)
            except Exception as exc:
                print(f"  Warning: failed to load {session_path.name}: {exc}")
                continue

            fs_est = loader.infer_sampling_rate(emg_data, timestamps)
            if fs_est > 0:
                fs_estimates.append(fs_est)

            segments_found = False
            # Handle both 'gestures' (S6-S10) and 'timestamps' (S1-S5) fields
            gesture_entries = []
            if 'gestures' in timestamps:
                gesture_entries = timestamps.get('gestures', []) or []
            elif 'timestamps' in timestamps:
                gesture_entries = timestamps.get('timestamps', []) or []
            
            if gesture_entries:
                # Count total timestamps to determine number of objects
                num_timestamps = len(gesture_entries)
                num_objects = num_timestamps // 2  # Each object defined by 2 timestamps
                
                # Generate object IDs (0 to num_objects-1)
                for obj_id in range(num_objects):
                    segments = loader.segment_by_gesture(
                        emg_data,
                        timestamps,
                        obj_id,  # Use object ID (0-5), not gesture_id from JSON
                        fs_est,
                        subject_id=subject_id,
                        session_name=session_path.name
                    )
                    if segments:
                        data_dict.setdefault(condition, {}).setdefault(obj_id, []).extend(segments)
                        segments_found = True
            else:
                for gid in range(NUM_GESTURES):
                    segments = loader.segment_by_gesture(
                        emg_data,
                        timestamps,
                        gid,
                        fs_est,
                        subject_id=subject_id,
                        session_name=session_path.name
                    )
                    if segments:
                        data_dict.setdefault(condition, {}).setdefault(gid, []).extend(segments)
                        segments_found = True

            if not segments_found:
                fallback_obj = session_info.get('session_number', 0)
                print(f"  Warning: no gesture segments extracted from {session_path.name}; using fallback object {fallback_obj}")
                duration = emg_data.shape[0] / (fs_est if fs_est and fs_est > 0 else 1.0)
                data_dict.setdefault(condition, {}).setdefault(fallback_obj, []).append(
                    SegmentRecord(
                        samples=emg_data[:, :NUM_CHANNELS].copy(),
                        subject=subject_id,
                        session=session_path.name,
                        start_time=0.0,
                        end_time=duration
                    )
                )

            if segments_found:
                loaded_count += 1

    if not data_dict:
        return None, None

    print(f"\n{'='*70}")
    print(f"Data Loading Summary:")
    print(f"  Sessions loaded: {loaded_count}")
    print(f"  Sessions skipped: {skipped_count}")
    print(f"  S0 excluded (S1-S5 and S6-S10 included)")
    print(f"{'='*70}\n")

    inferred_fs = float(np.median(fs_estimates)) if fs_estimates else None
    return data_dict, inferred_fs


def main():
    """Main analysis pipeline"""
    print("=" * 70)
    print("EMG Comparative Analysis")
    print("=" * 70)
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    data_dict, inferred_fs = load_real_data(data_dir)
    
    if data_dict is None:
        data_dict = generate_example_data(fs_hz=DEFAULT_FS_HZ)
        inferred_fs = DEFAULT_FS_HZ
        object_ids = list(range(NUM_GESTURES))
    else:
        if inferred_fs:
            print(f"Inferred sampling rate: {inferred_fs:.2f} Hz")
        else:
            inferred_fs = DEFAULT_FS_HZ
            print(f"Sampling rate inference failed; defaulting to {DEFAULT_FS_HZ} Hz")

        object_ids = sorted({obj_id for condition_data in data_dict.values() for obj_id in condition_data.keys()})
        if not object_ids:
            object_ids = list(range(NUM_GESTURES))
        else:
            if len(object_ids) > NUM_GESTURES:
                print(f"Detected {len(object_ids)} unique gestures; limiting analysis to first {NUM_GESTURES} IDs: {object_ids[:NUM_GESTURES]}")
                object_ids = object_ids[:NUM_GESTURES]
    
    # Find primary_object that exists in all conditions (for Figure A stacked views)
    # Object 0 is often a fallback/MVC, so prefer objects 1-6
    common_objects = set(object_ids)
    for condition in CONDITIONS:
        if condition in data_dict:
            common_objects &= set(data_dict[condition].keys())
    
    if common_objects:
        # Prefer object 1 if available, otherwise take the smallest common object
        if 1 in common_objects:
            primary_object = 1
        else:
            primary_object = min(common_objects)
        print(f"Using object {primary_object} for stacked views (exists in all conditions)")
    else:
        primary_object = object_ids[0] if object_ids else 0
        print(f"Warning: no object exists in all conditions; using object {primary_object}")

    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs or DEFAULT_FS_HZ)

    if analyzer.bandpass_effective_bounds:
        low_eff, high_eff = analyzer.bandpass_effective_bounds
        print(
            f"\nBandpass filter applied: {low_eff:.1f}-{high_eff:.1f} Hz (order {analyzer.bandpass_order})"
        )
    else:
        print("\nBandpass filter disabled or unavailable for current sampling rate.")
    
    print("\n" + "=" * 70)
    print("Generating Figures")
    print("=" * 70)

    # Note: Figure A stacked views removed (not readable/pointless)
    
    # Generate Figure B for all NUM_GESTURES objects
    print("\n--- Figure B: Raw Data Comparison ---")
    for obj_id in object_ids:
        print(f"\nGenerating Figure B for Object {obj_id}...")
        try:
            analyzer.figure_b_raw_comparison(data_dict, object_id=obj_id, 
                                           save_prefix=f'figureB')
            plt.close('all')
        except Exception as e:
            print(f"  Error generating Figure B for object {obj_id}: {e}")
    
    # Generate amplitude summary for ALL objects (not just primary)
    print("\n--- Figure B: Amplitude Summary (All Objects) ---")
    for obj_id in object_ids:
        print(f"\nGenerating amplitude summary for Object {obj_id}...")
        try:
            analyzer.figure_b_amplitude_summary(data_dict, object_id=obj_id, save_prefix='figureB_summary')
            plt.close('all')
        except Exception as e:
            print(f"  Error generating amplitude summary for object {obj_id}: {e}")
    
    # Skip heatmap generation (focus on summary figures only)
    # # Generate Figure C heatmaps for all NUM_GESTURES objects
    # print("\n--- Figure C: Heatmaps ---")
    # for obj_id in object_ids:
    #     print(f"\nGenerating heatmap for Object {obj_id}...")
    #     try:
    #         analyzer.figure_c_heatmap(data_dict, object_id=obj_id, 
    #                                 save_prefix='figureC_heatmap')
    #         plt.close('all')
    #     except Exception as e:
    #         print(f"  Error generating heatmap for object {obj_id}: {e}")
    
    # Skip spatial heatmap (focus on summary figures only)
    # # Generate spatial heatmap
    # print(f"\nGenerating spatial electrode heatmap for Object {primary_object}...")
    # try:
    #     analyzer.figure_c_spatial_heatmap(data_dict, object_id=primary_object, 
    #                                      save_prefix='figureC_spatial')
    #     plt.close('all')
    # except Exception as e:
    #     print(f"  Error generating spatial heatmap: {e}")
    
    # Generate Figure C PCA
    print("\n--- Figure C: PCA Analysis ---")
    
    # Option 1: PCA for single best object
    print(f"\nGenerating PCA for Object {primary_object} (primary object)...")
    try:
        analyzer.figure_c_pca(data_dict, object_ids=[primary_object], 
                            save_prefix='figureC_pca_single')
        plt.close('all')
    except Exception as e:
        print(f"  Error generating PCA for single object: {e}")
    
    # Option 2: PCA for all NUM_GESTURES objects
    print(f"\nGenerating PCA for objects {object_ids}...")
    try:
        analyzer.figure_c_pca(data_dict, object_ids=object_ids, 
                            save_prefix='figureC_pca_all')
        plt.close('all')
    except Exception as e:
        print(f"  Error generating PCA for all objects: {e}")
    
    print(f"\nGenerating channel statistics for Object {primary_object}...")
    try:
        analyzer.channel_statistics_summary(data_dict, object_id=primary_object, save_prefix='figureD')
        plt.close('all')
    except Exception as e:
        print(f"  Error generating channel statistics summary: {e}")

    # Time consumption analysis
    print("\n--- Time Consumption Analysis ---")
    try:
        analyzer.analyze_time_consumption(data_dict, object_ids=object_ids)
    except Exception as e:
        print(f"  Error in time consumption analysis: {e}")
    
    object_id_list_str = "_".join(str(obj) for obj in object_ids) if object_ids else ""

    print("\n" + "=" * 70)
    print("Analysis Complete!")
    print("=" * 70)
    print(f"\nAll figures saved in: {analyzer.results_dir}")
    print("\nGenerated files:")
    print("  - figureB_object_<id>.svg (temporal comparison, one per analyzed object)")
    print("  - figureB_summary_object_<id>.svg (amplitude summary for ALL objects)")
    if object_ids:
        print(f"  - figureC_pca_single_objects_{primary_object}.svg (primary object)")
        print(f"  - figureC_pca_all_objects_{object_id_list_str}.svg (all analyzed objects)")
    print("  - time_consumption_comparison.png")
    print("  - time_consumption_analysis.csv")
    print("  - figureD_channels_bar_object_{primary}.svg (channel RMS summary)".replace('{primary}', str(primary_object)))
    print("  - figureD_channels_diff_object_{primary}.svg (condition difference heatmap)".replace('{primary}', str(primary_object)))
    print("  - channel_rms_stats_object_{primary}.csv (exported RMS statistics)".replace('{primary}', str(primary_object)))
    print("\nNote: Statistical tests available in results-analysis/statistical_summary_*.md")

    if analyzer.outlier_samples_replaced:
        print(f"\nOutlier handling: replaced {analyzer.outlier_samples_replaced} samples with synthetic noise.")


if __name__ == '__main__':
    main()
