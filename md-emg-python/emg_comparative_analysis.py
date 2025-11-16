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
from matplotlib import cm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Circle
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Iterable
import json
import re
import xml.etree.ElementTree as ET
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy import signal as sp_signal
from scipy import stats
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from scipy.spatial import QhullError
import warnings

warnings.filterwarnings('ignore')

# Configuration
DEFAULT_FS_HZ = 1000  # Default sampling rate in Hz; overwritten if inferred from data
NUM_CHANNELS = 32  # Number of EMG channels
NUM_GESTURES = 6  # Number of gestures/objects to analyze
CHANNEL_IDS = list(range(NUM_CHANNELS))  # Channel indices
CONDITIONS = ['No glove', 'Passive glove', 'Active glove']
BASE_CONDITION = 'No glove'
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

EMG_SPATIAL_COLOR_STOPS = [
    (0.0, '#050A30'),   # deep navy lows
    (0.18, '#0B3B8C'),  # cobalt transition
    (0.38, '#1E91D6'),  # cyan/teal mids
    (0.62, '#5BCB53'),  # lime for active bands
    (0.82, '#F6C443'),  # golden high activity
    (1.0, '#F2542D')    # saturated hot spots
]
EMG_SPATIAL_CMAP = LinearSegmentedColormap.from_list('emg_spatial', EMG_SPATIAL_COLOR_STOPS, N=512)
# Register colormap if not already present
if 'emg_spatial' not in plt.colormaps():
    plt.colormaps.register(EMG_SPATIAL_CMAP)

# Spatial layout of electrodes on the sleeve (based on photo)
# The sleeve has electrodes arranged in rows - map to physical layout
# Channels 0-31 mapped to their spatial positions (row, col)
def get_channel_spatial_layout():
    """
    Returns channel positions based on physical electrode placement on sleeve.
    
    Layout from user specification:
    First band (3 rows x 6 columns):
    Row 0: [1, 2, 3, 4, 5, 6]
    Row 1: [7, 8, 9, 10, 11, 12]
    Row 2: [13, 14, 15, 16, 17, 18]
    
    Second band (2 rows x 7 columns):
    Row 3: [19, 20, 21, 22, 23, 24, 25]
    Row 4: [26, 27, 28, 29, 30, 31, 32]
    
    Note: Channel numbers in layout are 1-indexed (1-32), 
    but EMG data uses 0-indexed (0-31)
    """
    # Create 5x7 layout (padded with -1 for empty spaces)
    layout = np.full((5, 7), -1, dtype=int)
    
    # First band - 3 rows x 6 columns (channels 0-17, which are 1-18 in 1-indexed)
    # Row 0: channels 0-5 (displayed as 1-6)
    layout[0, :6] = [0, 1, 2, 3, 4, 5]
    # Row 1: channels 6-11 (displayed as 7-12)
    layout[1, :6] = [6, 7, 8, 9, 10, 11]
    # Row 2: channels 12-17 (displayed as 13-18)
    layout[2, :6] = [12, 13, 14, 15, 16, 17]
    
    # Second band - 2 rows x 7 columns (channels 18-31, which are 19-32 in 1-indexed)
    # Row 3: channels 18-24 (displayed as 19-25)
    layout[3, :] = [18, 19, 20, 21, 22, 23, 24]
    # Row 4: channels 25-31 (displayed as 26-32)
    layout[4, :] = [25, 26, 27, 28, 29, 30, 31]
    
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


def ordered_conditions(source_conditions: Iterable[str]) -> List[str]:
    """Return available conditions in the configured display order."""

    return [cond for cond in CONDITIONS if cond in source_conditions]


def summarize_condition_values(
    values_by_condition: Dict[str, List[float]]
) -> Tuple[List[str], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """Compute mean/median stats and baseline comparisons for each condition."""

    summary: Dict[str, Dict[str, float]] = {}
    available: List[str] = []

    for condition in CONDITIONS:
        raw_values = values_by_condition.get(condition)
        if raw_values is None or len(raw_values) == 0:
            continue

        arr = np.asarray(raw_values, dtype=float)
        stats_entry = {
            '_values': arr,
            'mean': float(np.mean(arr)),
            'median': float(np.median(arr)),
            'std': float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
            'n': int(arr.size)
        }

        summary[condition] = stats_entry
        available.append(condition)

    comparisons: Dict[str, Dict[str, float]] = {}
    base_stats = summary.get(BASE_CONDITION)

    if base_stats and base_stats['n'] > 1:
        base_values = base_stats['_values']
        for condition in available:
            if condition == BASE_CONDITION:
                continue

            cond_stats = summary.get(condition)
            if not cond_stats or cond_stats['n'] < 2:
                continue

            base_mean = base_stats['mean'] if base_stats['mean'] != 0 else np.nan
            ratio = cond_stats['mean'] / base_mean if base_mean and not np.isnan(base_mean) else np.nan
            p_val = stats.ttest_ind(cond_stats['_values'], base_values, equal_var=False).pvalue
            comparisons[condition] = {
                'ratio': float(ratio) if ratio == ratio else np.nan,  # NaN-safe
                'p_value': float(p_val)
            }

    # Drop raw arrays from summary before returning to keep structure light
    for stats_entry in summary.values():
        stats_entry.pop('_values', None)

    return available, summary, comparisons


def format_stats_text(
    condition_order: List[str],
    summary: Dict[str, Dict[str, float]],
    comparisons: Dict[str, Dict[str, float]]
) -> str:
    """Return multiline string describing per-condition stats and comparisons."""

    lines: List[str] = []
    for condition in condition_order:
        stats_entry = summary.get(condition)
        if not stats_entry:
            continue

        lines.append(
            f"{condition}: mean={stats_entry['mean']:.2f}, median={stats_entry['median']:.2f}, n={stats_entry['n']}"
        )

        if condition in comparisons:
            comp = comparisons[condition]
            ratio_text = f"{comp['ratio']:.2f}x" if comp['ratio'] == comp['ratio'] else 'n/a'
            lines.append(
                f"  vs {BASE_CONDITION}: ratio={ratio_text}, p={comp['p_value']:.3e}"
            )

    return "\n".join(lines)


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


@dataclass(frozen=True)
class ChannelNode:
    """Geometry for a single electrode node in the SVG layout."""

    index: int
    x: float
    y: float
    band: str
    row: str


@dataclass(frozen=True)
class SvgHeatmapLayout:
    """Pre-parsed SVG layout that maps channels onto 2D coordinates."""

    nodes: List[ChannelNode]
    rows: List[List[int]]
    width: float
    height: float
    radius: float


SVG_LAYOUT_PATH = Path(__file__).with_name('emg_heatmap.svg')
_SVG_LAYOUT_CACHE: Optional[SvgHeatmapLayout] = None


def _parse_svg_layout(svg_path: Path) -> SvgHeatmapLayout:
    """Load channel coordinates from the shared emg_heatmap.svg layout."""

    if not svg_path.exists():
        raise FileNotFoundError(f"Missing SVG layout: {svg_path}")

    tree = ET.parse(str(svg_path))
    root = tree.getroot()

    def _parse_float(value: Optional[str], default: float = 0.0) -> float:
        if value is None:
            return default
        value = value.strip()
        if value.endswith('pt'):
            value = value[:-2]
        return float(value)

    width = _parse_float(root.attrib.get('width'), 600.0)
    height = _parse_float(root.attrib.get('height'), 400.0)

    # Attempt to read default radius from first circle element
    circle_elements = root.findall('.//{*}circle')
    default_radius = _parse_float(circle_elements[0].attrib.get('r'), 24.0) if circle_elements else 24.0

    metadata = root.find('.//{*}metadata')
    mapping = metadata.find('.//{*}emg-mapping') if metadata is not None else None

    nodes: List[ChannelNode] = []
    rows: List[List[int]] = []
    channel_idx = 0

    if mapping is not None:
        for band in mapping.findall('.//{*}band'):
            band_id = band.get('id', 'band')
            for row in band.findall('.//{*}row'):
                row_id = row.get('id', '')
                channels_count = int(row.get('channels', '0'))
                start_x = _parse_float(row.get('start_x'))
                start_y = _parse_float(row.get('start_y'))
                spacing_x = _parse_float(row.get('spacing_x'))
                spacing_y = _parse_float(row.get('spacing_y'))

                row_indices: List[int] = []
                for offset in range(channels_count):
                    x = start_x + offset * spacing_x
                    y = start_y + offset * spacing_y
                    nodes.append(
                        ChannelNode(
                            index=channel_idx,
                            x=x,
                            y=y,
                            band=band_id,
                            row=f"{band_id}_{row_id}"
                        )
                    )
                    row_indices.append(channel_idx)
                    channel_idx += 1
                rows.append(row_indices)

    if not nodes:
        raise ValueError('SVG layout did not define any electrode nodes.')

    return SvgHeatmapLayout(nodes=nodes, rows=rows, width=width, height=height, radius=default_radius * 0.8)


def get_svg_heatmap_layout() -> SvgHeatmapLayout:
    """Return the cached SVG layout for electrode rendering."""

    global _SVG_LAYOUT_CACHE
    if _SVG_LAYOUT_CACHE is None:
        _SVG_LAYOUT_CACHE = _parse_svg_layout(SVG_LAYOUT_PATH)
    return _SVG_LAYOUT_CACHE


def draw_svg_heatmap(
    ax: plt.Axes,
    channel_values: np.ndarray,
    layout: Optional[SvgHeatmapLayout] = None,
    cmap: str = 'emg_spatial',
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    annotate: bool = True,
    spacing_scale: float = 0.7,
    blur_sigma: float = 7.0
) -> cm.ScalarMappable:
    """Render channel amplitudes using the shared SVG layout with a blurred field."""

    layout = layout or get_svg_heatmap_layout()
    values = np.asarray(channel_values, dtype=float)
    if values.ndim != 1:
        values = values.flatten()

    node_indices = [node.index for node in layout.nodes if node.index < values.size]
    if not node_indices:
        raise ValueError('No channel data available for spatial heatmap rendering.')

    coords = np.array([[layout.nodes[idx].x, layout.nodes[idx].y] for idx in node_indices])
    center = coords.mean(axis=0)
    scaled_coords = center + (coords - center) * spacing_scale

    data_vmin = float(np.nanmin(values[node_indices]))
    data_vmax = float(np.nanmax(values[node_indices]))
    norm = mcolors.Normalize(
        vmin if vmin is not None else data_vmin,
        vmax if vmax is not None else data_vmax
    )
    cmap_obj = cm.get_cmap(cmap)
    sm = cm.ScalarMappable(norm=norm, cmap=cmap_obj)

    # Interpolate blurred background
    pad_extent = layout.radius * 2.0
    grid_x = np.linspace(scaled_coords[:, 0].min() - pad_extent, scaled_coords[:, 0].max() + pad_extent, 520)
    grid_y = np.linspace(scaled_coords[:, 1].min() - pad_extent, scaled_coords[:, 1].max() + pad_extent, 320)
    grid_xx, grid_yy = np.meshgrid(grid_x, grid_y)

    points = scaled_coords
    values_subset = values[node_indices]

    def _griddata(method: str):
        return griddata(points, values_subset, (grid_xx, grid_yy), method=method)

    try:
        heat = _griddata('cubic')
    except QhullError:
        heat = None

    if heat is None or np.isnan(heat).all():
        heat = _griddata('linear')

    if heat is None or np.isnan(heat).all():
        heat = _griddata('nearest')

    nearest = _griddata('nearest')
    if nearest is not None:
        mask = np.isnan(heat)
        heat[mask] = nearest[mask]

    if blur_sigma and blur_sigma > 0:
        heat = gaussian_filter(heat, sigma=blur_sigma, mode='nearest')

    extent = [grid_x.min(), grid_x.max(), grid_y.max(), grid_y.min()]
    heat_norm = norm(heat)
    heat_norm = np.clip(heat_norm, 0.0, 1.0)
    heat_rgba = cmap_obj(heat_norm)
    alpha_map = np.clip(np.power(heat_norm, 0.85), 0.12, 0.98)
    heat_rgba[..., -1] = alpha_map
    ax.imshow(heat_rgba, extent=extent, origin='upper')

    # Draw filled circles per channel (no connector lines)
    scatter = ax.scatter(
        scaled_coords[:, 0],
        scaled_coords[:, 1],
        c=values_subset,
        cmap=cmap_obj,
        norm=norm,
        s=layout.radius**2 * 14,
        edgecolors='none',
        linewidths=0.0,
        alpha=0.8,
        zorder=3
    )

    if annotate:
        for (x, y), idx in zip(scaled_coords, node_indices):
            val = float(values[idx])
            text_color = 'black' if norm(val) < 0.55 else 'white'
            ax.text(
                x,
                y,
                f'{idx + 1}',
                ha='center',
                va='center',
                fontsize=7,
                color=text_color,
                fontweight='bold',
                zorder=4
            )

    pad_x = (scaled_coords[:, 0].max() - scaled_coords[:, 0].min()) * 0.08
    pad_y = (scaled_coords[:, 1].max() - scaled_coords[:, 1].min()) * 0.08
    ax.set_xlim(scaled_coords[:, 0].min() - pad_x, scaled_coords[:, 0].max() + pad_x)
    ax.set_ylim(scaled_coords[:, 1].max() + pad_y, scaled_coords[:, 1].min() - pad_y)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_facecolor('none')

    return sm


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
        fs_hz: float = DEFAULT_FS_HZ,
        mvc_dict: Optional[Dict[str, np.ndarray]] = None
    ):
        self.data_loader = data_loader
        self.fs_hz = fs_hz
        self.mvc_dict = mvc_dict or {}  # Subject MVC normalization values
        self.results_dir = Path('results-analysis')
        self.results_dir.mkdir(exist_ok=True)

        # Signal cleaning configuration
        # Note: Bandpass filtering requires fs > 100 Hz (Nyquist > 50 Hz)
        # For EMG: typical bandpass is 20-450 Hz
        self.bandpass_low_hz = 20.0
        self.bandpass_high_hz = 450.0
        self.bandpass_order = 4
        self.bandpass_effective_bounds = None
        
        # DISABLED: No bandpass filtering - using raw unfiltered data
        print("INFO: Bandpass filtering DISABLED - using raw unfiltered data")
        self._bandpass_sos = None

        # Outlier handling disabled - data preserved as-is
        self._outlier_counter = 0
        self._rng = np.random.default_rng(1337)

    def _normalize_segment(self, segment: np.ndarray, subject_id: Optional[str]) -> np.ndarray:
        """Apply MVC normalization but NO filtering. Returns data in %MVC units."""

        data = segment.astype(np.float64, copy=True)
        
        # Clip extreme values before normalization (likely artifacts/saturation)
        # Values > 50000 are typically electrode saturation or disconnection
        data = np.clip(data, -50000, 50000)
        
        # No bandpass filtering - raw data
        # No outlier attenuation - data preserved as-is
        
        # Apply MVC normalization if available
        if subject_id and subject_id in self.mvc_dict:
            mvc_rms = self.mvc_dict[subject_id]
            # Normalize to %MVC (percentage of maximum voluntary contraction)
            # Each channel divided by its MVC value, then multiply by 100
            data = (data / mvc_rms[np.newaxis, :]) * 100.0
        
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
        """Keep outliers as-is (no replacement) - preserves original data integrity."""

        # Simply return the data unchanged - no outlier replacement
        # This preserves the original signal including extreme values
        return data

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
    
    def compute_peak_amplitude(self, data: np.ndarray, window_ms: int = 100) -> float:
        """
        Compute peak amplitude (maximum RMS) - duration-independent metric.
        
        Reference: Hodges & Bui (1996) - standard method for peak muscle activation
        
        Args:
            data: EMG signal (samples, channels)
            window_ms: RMS window size in milliseconds
            
        Returns:
            Peak amplitude averaged across channels (%MVC if normalized)
        """
        rms = self.compute_rms(data, window_ms=window_ms)
        peak_per_channel = np.max(rms, axis=0)
        return float(np.mean(peak_per_channel))
    
    def compute_percentile_amplitude(self, data: np.ndarray, percentile: float = 90.0, 
                                     window_ms: int = 100) -> float:
        """
        Compute percentile amplitude - robust high-amplitude metric.
        
        90th percentile captures high-effort periods while being robust to outliers.
        Duration-independent metric suitable for comparing tasks of different lengths.
        
        Reference: Hermens et al. (2000) - SENIAM recommendations for EMG analysis
        
        Args:
            data: EMG signal (samples, channels)
            percentile: Percentile to compute (default 90th)
            window_ms: RMS window size in milliseconds
            
        Returns:
            Percentile amplitude averaged across channels (%MVC if normalized)
        """
        rms = self.compute_rms(data, window_ms=window_ms)
        percentile_per_channel = np.percentile(rms, percentile, axis=0)
        return float(np.mean(percentile_per_channel))
    
    def compute_active_amplitude(self, data: np.ndarray, threshold_percentile: float = 10.0,
                                window_ms: int = 100) -> float:
        """
        Compute mean amplitude during active periods only (above threshold).
        
        Excludes rest/low-activity periods by thresholding. Duration-independent
        as it only considers time points when muscle is actually active.
        
        Args:
            data: EMG signal (samples, channels)
            threshold_percentile: Percentile for baseline threshold (default 10th)
            window_ms: RMS window size in milliseconds
            
        Returns:
            Mean amplitude during active periods, averaged across channels (%MVC)
        """
        rms = self.compute_rms(data, window_ms=window_ms)
        
        # Calculate threshold per channel
        threshold_per_channel = np.percentile(rms, threshold_percentile, axis=0)
        
        # Find active periods (above threshold for any channel)
        active_mask = np.any(rms > threshold_per_channel, axis=1)
        
        if not np.any(active_mask):
            return 0.0
        
        active_rms = rms[active_mask]
        return float(np.mean(active_rms))
    
    def compute_activation_duration(self, data: np.ndarray, threshold_percentile: float = 10.0,
                                    window_ms: int = 100) -> float:
        """
        Compute proportion of time with muscle activation above baseline.
        
        Temporal metric indicating how much of the task duration involves active
        muscle contraction. Range: [0, 1] where 1 = continuous activation.
        
        Reference: Tenan et al. (2017) - muscle onset detection methods
        
        Args:
            data: EMG signal (samples, channels)
            threshold_percentile: Percentile for baseline threshold
            window_ms: RMS window size in milliseconds
            
        Returns:
            Proportion of time active (0-1)
        """
        rms = self.compute_rms(data, window_ms=window_ms)
        
        # Calculate threshold per channel
        threshold_per_channel = np.percentile(rms, threshold_percentile, axis=0)
        
        # Active when above threshold in any channel
        active_mask = np.any(rms > threshold_per_channel, axis=1)
        
        return float(np.sum(active_mask) / len(active_mask))
    
    def compute_burst_frequency(self, data: np.ndarray, threshold_percentile: float = 10.0,
                                window_ms: int = 100, min_burst_duration_ms: float = 50.0) -> float:
        """
        Compute muscle burst frequency (activations per second).
        
        Counts discrete activation events (bursts) where muscle activity exceeds
        baseline for at least min_burst_duration_ms. More physiologically meaningful
        than amplitude/duration ratio.
        
        Reference: Tenan et al. (2017) - burst detection in EMG
        
        Args:
            data: EMG signal (samples, channels)
            threshold_percentile: Percentile for baseline threshold
            window_ms: RMS window size in milliseconds
            min_burst_duration_ms: Minimum burst duration to count (ms)
            
        Returns:
            Burst frequency in Hz (bursts per second)
        """
        rms = self.compute_rms(data, window_ms=window_ms)
        
        # Calculate threshold per channel
        threshold_per_channel = np.percentile(rms, threshold_percentile, axis=0)
        
        # Active when above threshold in any channel
        active_mask = np.any(rms > threshold_per_channel, axis=1)
        
        # Find burst onsets (transitions from inactive to active)
        active_int = active_mask.astype(int)
        transitions = np.diff(active_int)
        burst_onsets = np.where(transitions == 1)[0]
        burst_offsets = np.where(transitions == -1)[0]
        
        # Filter bursts by minimum duration
        min_burst_samples = max(1, int(min_burst_duration_ms * self.fs_hz / 1000))
        valid_bursts = 0
        
        for onset in burst_onsets:
            # Find corresponding offset
            offsets_after = burst_offsets[burst_offsets > onset]
            if len(offsets_after) > 0:
                offset = offsets_after[0]
                duration_samples = offset - onset
                if duration_samples >= min_burst_samples:
                    valid_bursts += 1
            else:
                # Burst extends to end of signal
                duration_samples = len(active_mask) - onset
                if duration_samples >= min_burst_samples:
                    valid_bursts += 1
        
        # Convert to frequency (bursts per second)
        duration_seconds = len(data) / self.fs_hz
        return float(valid_bursts / duration_seconds) if duration_seconds > 0 else 0.0
    
    def extract_temporal_features(self, data: np.ndarray, window_ms: int = 100) -> np.ndarray:
        """
        Extract comprehensive temporal features for PCA - duration-independent.
        
        Returns a fixed-size feature vector per segment, ensuring equal contribution
        to PCA regardless of task duration. Each segment contributes one row.
        
        Reference: Phinyomark et al. (2012) - feature extraction for EMG classification
        
        Args:
            data: EMG signal (samples, channels)
            window_ms: RMS window size in milliseconds
            
        Returns:
            Feature vector of shape (n_features,) containing:
            - Per-channel statistics (mean, std, peak, percentiles)
            - Temporal features (activation duration, burst frequency)
            - Global statistics across channels
        """
        rms = self.compute_rms(data, window_ms=window_ms)
        n_channels = rms.shape[1]
        
        features = []
        
        # Per-channel amplitude features
        for ch in range(n_channels):
            ch_rms = rms[:, ch]
            features.extend([
                np.mean(ch_rms),          # Mean amplitude
                np.std(ch_rms),           # Amplitude variability
                np.percentile(ch_rms, 90), # High-amplitude (90th percentile)
                np.max(ch_rms),           # Peak amplitude
            ])
        
        # Global features (across all channels)
        mean_across_channels = np.mean(rms, axis=1)
        features.extend([
            np.mean(mean_across_channels),
            np.std(mean_across_channels),
            np.percentile(mean_across_channels, 90),
            np.max(mean_across_channels),
        ])
        
        # Temporal features (duration-independent)
        features.append(self.compute_activation_duration(data, window_ms=window_ms))
        features.append(self.compute_burst_frequency(data, window_ms=window_ms))
        
        # Cross-channel coordination (correlation between channels)
        if n_channels > 1:
            # Mean absolute correlation between adjacent channels
            correlations = []
            for ch in range(n_channels - 1):
                if np.std(rms[:, ch]) > 0 and np.std(rms[:, ch+1]) > 0:
                    corr = np.corrcoef(rms[:, ch], rms[:, ch+1])[0, 1]
                    correlations.append(abs(corr))
            features.append(np.mean(correlations) if correlations else 0.0)
        else:
            features.append(0.0)
        
        return np.array(features, dtype=np.float64)

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
        condition_data: Dict[str, np.ndarray] = {}
        condition_segment_means: Dict[str, List[float]] = defaultdict(list)
        
        # Collect and prepare data
        for condition in CONDITIONS:
            if condition not in data_dict or object_id not in data_dict[condition]:
                continue
            records = data_dict[condition][object_id]
            if not records:
                continue
            
            # Average all segments for this condition
            all_segments = []
            for record in records:
                segment = self._normalize_segment(record.samples, record.subject)
                rms = self.compute_rms(segment, window_ms=100)
                all_segments.append(rms)
                condition_segment_means[condition].append(float(np.mean(rms)))
            
            # Find common length and average
            min_len = min(seg.shape[0] for seg in all_segments)
            trimmed = [seg[:min_len, :] for seg in all_segments]
            avg_rms = np.mean(trimmed, axis=0)
            condition_data[condition] = avg_rms
        
        if not condition_data:
            print(f"No valid data for object {object_id}")
            return None

        plot_conditions, condition_stats, condition_comparisons = summarize_condition_values(
            condition_segment_means
        )

        if not plot_conditions:
            plot_conditions = ordered_conditions(condition_data.keys())
        
        # Create comprehensive comparison figure
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # Row 1: Side-by-side heatmaps for each condition
        vmin = min(data.min() for data in condition_data.values())
        vmax = max(data.max() for data in condition_data.values())
        
        for idx, condition in enumerate(plot_conditions):
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
        for condition in plot_conditions:
            channel_means[condition] = condition_data[condition].mean(axis=0)
        
        x = np.arange(NUM_CHANNELS)
        width = 0.25
        
        for idx, condition in enumerate(plot_conditions):
            offset = (idx - 1) * width
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            ax_bar.bar(x + offset, channel_means[condition], width, 
                      label=condition, alpha=0.8, color=color, edgecolor='black', linewidth=0.5)
        if channel_means:
            bar_max = max(values.max() for values in channel_means.values())
            ax_bar.set_ylim(0, bar_max * 1.1 if bar_max > 0 else 1)
        
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
        for condition in plot_conditions:
            violin_data.append(condition_data[condition].flatten())
            violin_labels.append(condition)
        
        parts = ax_violin.violinplot(violin_data, positions=range(len(valid_conditions)),
                                     showmeans=True, showmedians=True, widths=0.7)
        
        # Color the violin plots
        for idx, (pc, condition) in enumerate(zip(parts['bodies'], valid_conditions)):
            color = MATLAB_CONDITION_BASE_COLORS.get(condition, CONDITION_COLORS.get(condition, '#1f77b4'))
            pc.set_facecolor(color)
            pc.set_alpha(0.7)
        
        ax_violin.set_xticks(range(len(plot_conditions)))
        ax_violin.set_xticklabels(violin_labels, fontsize=12, fontweight='bold')
        ax_violin.set_ylabel('RMS Amplitude (a.u.)', fontsize=12, fontweight='bold')
        ax_violin.set_title('Amplitude Distribution Comparison', fontsize=14, fontweight='bold')
        ax_violin.grid(True, alpha=0.3, axis='y')
        if violin_data:
            violin_max = max(np.max(values) for values in violin_data)
            ax_violin.set_ylim(0, violin_max * 1.1 if violin_max > 0 else 1)
        for idx, condition in enumerate(plot_conditions):
            stats_entry = condition_stats.get(condition)
            if not stats_entry:
                continue
            ax_violin.text(
                idx,
                stats_entry['median'],
                f"μ={stats_entry['mean']:.1f}\nmed={stats_entry['median']:.1f}",
                ha='center',
                va='center',
                fontsize=9,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
            )
        
        # Time-series overlay of mean across all channels
        ax_overlay = fig.add_subplot(gs[2, 2])
        
        # Find max length for proper x-axis and pad shorter signals
        max_len = max(condition_data[c].shape[0] for c in valid_conditions)
        
        for condition in plot_conditions:
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
        ax_overlay.set_ylim(bottom=0)
        
        # Overall figure title
        fig.suptitle(f'Comprehensive EMG Comparison Across Conditions - Object {object_id}', 
                    fontsize=18, fontweight='bold', y=0.98)

        stats_text = format_stats_text(plot_conditions, condition_stats, condition_comparisons)
        if stats_text:
            fig.text(
                0.01,
                0.01,
                stats_text,
                ha='left',
                va='bottom',
                fontsize=10,
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9)
            )
        
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

        plot_conditions, summary_stats, comparisons = summarize_condition_values(
            condition_mean_per_segment
        )
        if not plot_conditions:
            plot_conditions = ordered_conditions(condition_rms_values.keys())
        
        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Subplot 1: Box plot of all RMS values
        labels = [c for c in plot_conditions if c in condition_rms_values]
        positions = list(range(len(labels)))
        box_data = [condition_rms_values[c] for c in labels]
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
        ax1.set_ylim(bottom=0)
        
        # Add mean values as text
        for idx, condition in enumerate(labels):
            stats_entry = summary_stats.get(condition)
            if not stats_entry:
                continue
            ax1.text(
                idx,
                ax1.get_ylim()[1] * 0.9,
                f"μ={stats_entry['mean']:.1f}\nmed={stats_entry['median']:.1f}",
                ha='center',
                fontsize=10,
                fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
            )
        
        # Subplot 2: Mean per segment with statistical comparison
        labels2 = [c for c in plot_conditions if c in condition_mean_per_segment]
        positions2 = list(range(len(labels2)))
        
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
        ax2.set_ylim(bottom=0)
        
        # Statistical tests moved to separate summary files
        # See: results-analysis/statistical_summary_amplitude.md
        
        fig.suptitle(f'Statistical Amplitude Comparison - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        stats_text = format_stats_text(plot_conditions, summary_stats, comparisons)
        if stats_text:
            fig.text(
                0.5,
                0.01,
                stats_text,
                ha='center',
                va='bottom',
                fontsize=10,
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9)
            )
        plt.tight_layout(rect=(0, 0.04, 1, 1))
        
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
        fig.patch.set_alpha(0.0)
        if len(condition_means) == 1:
            axes = axes.reshape(-1, 1)
        
        # Global color scale
        all_values = np.concatenate([v for v in condition_means.values()])
        vmin, vmax = all_values.min(), all_values.max()
        layout = get_svg_heatmap_layout()
        
        # Row 1: Mean RMS across all segments
        for idx, condition in enumerate(CONDITIONS):
            if condition not in condition_means:
                continue
            
            ax = axes[0, idx]
            sm = draw_svg_heatmap(
                ax,
                condition_means[condition],
                layout=layout,
                vmin=vmin,
                vmax=vmax,
                cmap='magma'
            )
            
            ax.set_title(f'{condition}\nMean: {condition_means[condition].mean():.1f} a.u.', 
                        fontsize=13, fontweight='bold')
            plt.colorbar(sm, ax=ax, label='Mean RMS (a.u.)')
        
        # Row 2: Example from one subject
        for idx, condition in enumerate(CONDITIONS):
            if condition not in condition_examples:
                continue
            
            ax = axes[1, idx]
            sm = draw_svg_heatmap(
                ax,
                condition_examples[condition],
                layout=layout,
                vmin=vmin,
                vmax=vmax,
                cmap='magma'
            )
            
            ax.set_title(f'Example Subject\nMean: {condition_examples[condition].mean():.1f} a.u.', 
                        fontsize=12, fontweight='bold')
            plt.colorbar(sm, ax=ax, label='RMS (a.u.)')

        fig.text(0.02, 0.74, 'MEAN\n(All Subjects)', fontsize=11, fontweight='bold', va='center')
        fig.text(0.02, 0.32, 'EXAMPLE\n(1 Subject)', fontsize=11, fontweight='bold', va='center')
        
        fig.suptitle(f'Spatial EMG Activity Map - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save as SVG
        save_path_svg = self.results_dir / f'{save_prefix}_object_{object_id}.svg'
        plt.savefig(save_path_svg, bbox_inches='tight', format='svg')
        print(f"Saved: {save_path_svg}")
        plt.close(fig)
        
        return fig
    
    def generate_spatial_heatmaps_per_subject(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_ids: List[int] = None
    ) -> None:
        """
        Generate spatial heatmaps for each subject and object across all conditions.
        
        Creates individual heatmap files showing EMG activity patterns in the physical
        electrode layout for each subject-object combination.
        
        Output: One figure per subject-object combination showing 3 conditions side-by-side
        Saved to: results-analysis/emg_heatmap/
        """
        # Create output directory
        heatmap_dir = self.results_dir / 'emg_heatmap'
        heatmap_dir.mkdir(parents=True, exist_ok=True)
        
        layout = get_svg_heatmap_layout()
        
        if object_ids is None:
            # Get all available object IDs
            object_ids = sorted({obj_id for condition_data in data_dict.values() 
                                for obj_id in condition_data.keys()})
        
        if not object_ids:
            print("No objects found for spatial heatmap generation")
            return
        
        # Collect all subjects
        all_subjects = set()
        for condition in CONDITIONS:
            if condition not in data_dict:
                continue
            for obj_id in object_ids:
                if obj_id not in data_dict[condition]:
                    continue
                for record in data_dict[condition][obj_id]:
                    all_subjects.add(record.subject)
        
        subjects = sorted(all_subjects)
        print(f"\nGenerating spatial heatmaps for {len(subjects)} subjects x {len(object_ids)} objects...")
        
        # Generate one figure per subject-object combination
        for subject in subjects:
            for obj_id in object_ids:
                # Collect data for this subject-object across conditions
                subject_data = {}
                
                for condition in CONDITIONS:
                    if condition not in data_dict or obj_id not in data_dict[condition]:
                        continue
                    
                    # Find records for this subject
                    subject_records = [rec for rec in data_dict[condition][obj_id] 
                                      if rec.subject == subject]
                    
                    if not subject_records:
                        continue
                    
                    # Compute mean RMS across all sessions for this subject
                    all_ch_rms = []
                    for record in subject_records:
                        segment = self._normalize_segment(record.samples, record.subject)
                        # Compute RMS per channel
                        ch_mean_rms = np.sqrt(np.mean(segment**2, axis=0))
                        all_ch_rms.append(ch_mean_rms)
                    
                    if all_ch_rms:
                        # Average across sessions
                        subject_data[condition] = np.mean(all_ch_rms, axis=0)
                
                if not subject_data:
                    # No data for this subject-object combination
                    continue
                
                # Create figure with 3 subplots (one per condition)
                present_conditions = [c for c in CONDITIONS if c in subject_data]
                n_conditions = len(present_conditions)
                
                if n_conditions == 0:
                    continue
                
                fig, axes = plt.subplots(1, n_conditions, figsize=(6 * n_conditions, 6))
                fig.patch.set_alpha(0.0)
                if n_conditions == 1:
                    axes = [axes]
                
                # Global color scale across all conditions for this subject-object
                all_values = np.concatenate([v for v in subject_data.values()])
                vmin, vmax = all_values.min(), all_values.max()
                
                for idx, condition in enumerate(present_conditions):
                    ax = axes[idx]
                    sm = draw_svg_heatmap(
                        ax,
                        subject_data[condition],
                        layout=layout,
                        vmin=vmin,
                        vmax=vmax,
                        cmap='magma'
                    )
                    
                    mean_val = subject_data[condition].mean()
                    ax.set_title(f'{condition}\nMean: {mean_val:.1f} %MVC', 
                                fontsize=13, fontweight='bold')
                    cbar = plt.colorbar(sm, ax=ax, label='%MVC')
                
                fig.suptitle(f'Spatial EMG Activity Map: {subject} - Object {obj_id}', 
                            fontsize=16, fontweight='bold')
                plt.tight_layout()
                
                # Save figure
                filename = f'spatial_{subject}_object_{obj_id}.svg'
                save_path = heatmap_dir / filename
                plt.savefig(save_path, bbox_inches='tight', format='svg')
                print(f"  Saved: {filename}")
                plt.close(fig)
        
        print(f"\n✓ All spatial heatmaps saved to: {heatmap_dir}")
    
    def figure_c_pca(
        self,
        data_dict: Dict[str, Dict[int, List[SegmentRecord]]],
        object_ids: List[int] = None,
        save_prefix: str = 'figC_pca'
    ) -> Optional[plt.Figure]:
        """
        Figure C: MATLAB-inspired PCA overview with component subplots per object.
        
        Uses feature-based approach where each segment contributes equally (one row)
        regardless of duration, ensuring fair comparison across conditions.
        
        Reference: Phinyomark et al. (2012) - EMG feature extraction
        """

        if object_ids is None:
            object_ids = [0]

        n_objects = len(object_ids)
        if n_objects == 0:
            print("No objects provided for PCA analysis")
            return None

        fig, axes = plt.subplots(3, n_objects, figsize=(5 * n_objects, 9), squeeze=False, sharey='row')

        for col, obj_id in enumerate(object_ids):
            all_features = []
            segment_meta: List[Tuple[str, str]] = []  # (condition, subject)

            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue

                for record in data_dict[condition][obj_id]:
                    normalized = self._normalize_segment(record.samples, record.subject)
                    # Extract temporal features: each segment → 1 row (duration-independent)
                    features = self.extract_temporal_features(normalized, window_ms=100)
                    if features.size == 0:
                        continue
                    all_features.append(features)
                    segment_meta.append((condition, record.subject))

            if not all_features:
                for row_idx in range(3):
                    ax = axes[row_idx, col]
                    ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center', transform=ax.transAxes)
                    ax.axis('off')
                continue

            # Each segment contributes exactly 1 row (equal contribution)
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

            # Map scores back to segments (each segment has exactly 1 score)
            subject_condition_scores: Dict[Tuple[str, str], List[np.ndarray]] = defaultdict(list)
            for idx, (condition, subject) in enumerate(segment_meta):
                segment_score = scores[idx]
                subject_condition_scores[(condition, subject)].append(segment_score)

            # Average scores per subject per condition
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


def load_mvc_references(data_dir: Path, subjects: List[str]) -> Dict[str, np.ndarray]:
    """Load MVC (Maximum Voluntary Contraction) data for each subject.
    
    Uses the 99th percentile of RMS values across ALL sessions to get robust MVC estimate.
    This approach is more robust than relying on a single MVC session which may have
    recording issues or insufficient contractions.
    
    Returns a dictionary mapping subject_id to MVC RMS values (per channel).
    """
    mvc_dict = {}
    loader = EMGDataLoader(data_dir)
    
    for subject_id in subjects:
        subject_id_upper = subject_id.upper()
        
        subject_dir = data_dir / subject_id / 'emg_logs'
        if not subject_dir.exists():
            print(f"  Warning: No emg_logs directory for {subject_id}")
            continue
        
        # Load ALL sessions for this subject and find maximum activation
        all_session_files = sorted(subject_dir.glob('session_*.npy'))
        
        if not all_session_files:
            print(f"  Warning: No session files found for {subject_id}")
            continue
        
        try:
            # Collect RMS values from all sessions
            all_rms_values = [[] for _ in range(NUM_CHANNELS)]
            
            for session_file in all_session_files:
                try:
                    session_data = loader.load_session(session_file)
                    if session_data is None or session_data.size == 0:
                        continue
                    
                    emg_channels = session_data[:, :NUM_CHANNELS]
                    
                    # Skip sessions with excessive saturation (>1% of values saturated)
                    # Occasional spikes are OK, but widespread saturation indicates bad recording
                    saturation_percent = (np.abs(emg_channels) > 100000).sum() / emg_channels.size * 100
                    if saturation_percent > 1.0:
                        print(f"    Skipping {session_file.name} for {subject_id}: {saturation_percent:.1f}% saturated values")
                        continue
                    
                    # Compute RMS for this session using 500ms windows
                    window_samples = int(0.5 * 1000)  # 500ms at ~1000Hz
                    n_samples = emg_channels.shape[0]
                    
                    if n_samples < window_samples:
                        continue  # Skip very short sessions
                    
                    for ch in range(NUM_CHANNELS):
                        channel_data = emg_channels[:, ch]
                        
                        # Slide window and collect RMS values
                        for start_idx in range(0, n_samples - window_samples + 1, window_samples // 2):
                            end_idx = start_idx + window_samples
                            window = channel_data[start_idx:end_idx]
                            rms_val = np.sqrt(np.mean(window**2))
                            
                            # Only include reasonable RMS values (< 50000)
                            if rms_val < 50000:
                                all_rms_values[ch].append(rms_val)
                
                except Exception as e:
                    print(f"  Warning: Failed to load {session_file.name} for {subject_id}: {e}")
                    continue
            
            # Use 99th percentile across ALL windows from ALL sessions
            # But first remove extreme outliers (>99.9th percentile) to avoid artifacts
            mvc_rms = np.zeros(NUM_CHANNELS)
            for ch in range(NUM_CHANNELS):
                if all_rms_values[ch]:
                    # Remove extreme outliers first (likely artifacts)
                    channel_rms = np.array(all_rms_values[ch])
                    outlier_threshold = np.percentile(channel_rms, 99.9)
                    filtered_rms = channel_rms[channel_rms <= outlier_threshold]
                    
                    if len(filtered_rms) > 0:
                        # Now take 99th percentile of filtered data
                        mvc_rms[ch] = np.percentile(filtered_rms, 99)
                    else:
                        mvc_rms[ch] = np.percentile(channel_rms, 99)
                else:
                    mvc_rms[ch] = 1.0  # Fallback
            
            # Ensure no zero values (would cause division by zero)
            mvc_rms = np.where(mvc_rms > 1e-6, mvc_rms, 1.0)
            
            mvc_dict[subject_id_upper] = mvc_rms
            print(f"  Loaded MVC for {subject_id} from {len(all_session_files)} sessions: mean={mvc_rms.mean():.2f}, std={mvc_rms.std():.2f}")
            
        except Exception as e:
            print(f"  Warning: Failed to compute MVC for {subject_id}: {e}")
            continue
    
    return mvc_dict


def load_real_data(data_dir: Path) -> Tuple[Optional[Dict[str, Dict[int, List[SegmentRecord]]]], Optional[float], Optional[Dict[str, np.ndarray]]]:
    """Load EMG data from S1, S2, S5-S10 (excluding S0, S3, S4).
    Uses notes.txt for conditions and handles special cases.
    
    Returns:
        data_dict: {condition: {object_id: [SegmentRecord]}}
        inferred_fs: Sampling rate in Hz
        mvc_dict: {subject_id: mvc_rms_per_channel} for MVC normalization
    """

    # Skip S0 (system test), S3 (only 5 sessions), S4 (only 8 sessions, irregular conditions)
    # Include: S1, S2, S5-S10 (all with 9 sessions, 3 per condition)
    SKIP_SUBJECTS = {'S0', 'S3', 'S4'}
    SKIP_SESSIONS = {
        'S1': {0, 1, 2},  # bad (0), mvc (1), bad (2)
        'S2': {0},  # mvc
        'S3': {0, 1},  # mvc, bad
        'S4': {0, 4},  # mvc, fall
        'S5': {0},  # mvc
        'S6': {0, 10},  # rearranged, mvc
        'S7': {0, 1, 2, 3, 8},  # mvc, disconnected (1-3), bad (8) - sessions 4-7, 9-13 available
        'S8': {0, 5},  # mvc, skip session 5 (sessions 1-4, 6-10 = 9 sessions)
        'S9': {1},  # mvc (sessions 2-8, 10, 13 = 9 sessions already)
        'S10': {0, 6},  # mvc, bad (sessions 1-5, 7-10 = 9 sessions)
    }
    
    # Fallback conditions from notes.txt for sessions missing metadata
    FALLBACK_CONDITIONS = {
        'S1': {3: 'no', 4: 'no', 5: 'no', 6: 'passive', 7: 'passive', 8: 'passive', 9: 'active', 10: 'active', 11: 'active'},  # 9 sessions: 3 per condition
        'S2': {1: 'passive', 2: 'passive', 3: 'passive', 4: 'no', 5: 'no', 6: 'no', 7: 'active', 8: 'active', 9: 'active'},
        'S3': {2: 'active', 3: 'active', 4: 'active', 5: 'no', 6: 'no', 7: 'no', 8: 'passive', 9: 'passive', 10: 'passive'},
        'S4': {1: 'no', 2: 'no', 3: 'no', 5: 'redo', 6: 'active', 7: 'active', 8: 'active', 9: 'no extend', 10: 'passive', 11: 'passive', 12: 'passive'},
        'S5': {1: 'active', 2: 'active', 3: 'active', 4: 'passive', 5: 'passive', 6: 'passive', 7: 'no', 8: 'no', 9: 'no'},
        'S6': {1: 'passive', 2: 'passive', 3: 'passive', 4: 'active', 5: 'active', 6: 'active', 7: 'no', 8: 'no', 9: 'no'},
        'S7': {4: 'no', 5: 'no', 6: 'no', 7: 'passive', 9: 'passive', 10: 'passive', 11: 'active', 12: 'active', 13: 'active'},  # 9 sessions: 3 no, 3 passive, 3 active
        'S8': {1: 'passive', 2: 'passive', 3: 'passive', 4: 'no', 6: 'no', 7: 'no', 8: 'active', 9: 'active', 10: 'active'},
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
        
        # Skip S0 only (include S1-S10)
        if subject_id in SKIP_SUBJECTS:
            print(f"Skipping {subject_id} (excluded - insufficient sessions for balanced design)")
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
        return None, None, None

    print(f"\n{'='*70}")
    print(f"Data Loading Summary:")
    print(f"  Sessions loaded: {loaded_count}")
    print(f"  Sessions skipped: {skipped_count}")
    print(f"  S0, S3, S4 excluded (S1, S2, S5-S10 included, balanced 3 sessions per condition)")
    print(f"  Note: S7 has 8 sessions (3 no, 2 passive, 3 active)")
    print(f"{'='*70}\n")

    # Load MVC references for all included subjects
    print("Loading MVC references for normalization...")
    included_subjects = sorted({seg.subject for cond_data in data_dict.values() 
                               for obj_segs in cond_data.values() 
                               for seg in obj_segs})
    mvc_dict = load_mvc_references(data_dir, included_subjects)
    print(f"MVC loaded for {len(mvc_dict)} subjects: {sorted(mvc_dict.keys())}\n")

    inferred_fs = float(np.median(fs_estimates)) if fs_estimates else None
    return data_dict, inferred_fs, mvc_dict


def main():
    """Main analysis pipeline"""
    print("=" * 70)
    print("EMG Comparative Analysis with MVC Normalization")
    print("=" * 70)
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    
    if data_dict is None:
        data_dict = generate_example_data(fs_hz=DEFAULT_FS_HZ)
        inferred_fs = DEFAULT_FS_HZ
        mvc_dict = {}
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
            print(f"Available object IDs: {object_ids}")
        
        # Report MVC normalization status
        if mvc_dict:
            print(f"\nMVC normalization enabled for {len(mvc_dict)} subjects")
            print("  All EMG values will be expressed as %MVC (percentage of maximum voluntary contraction)")
        else:
            print("\nWarning: No MVC data loaded - results will be in raw units")
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
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs or DEFAULT_FS_HZ, mvc_dict=mvc_dict)

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

    # Spatial heatmaps per subject
    print("\n--- Spatial Heatmaps per Subject ---")
    try:
        analyzer.generate_spatial_heatmaps_per_subject(data_dict, object_ids=object_ids)
        plt.close('all')
    except Exception as e:
        print(f"  Error generating spatial heatmaps: {e}")

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
    print("  - emg_heatmap/ (spatial heatmaps per subject and object)")
    print("\nNote: Statistical tests available in results-analysis/statistical_summary_*.md")

    # MVC normalization enabled, no filtering, outliers kept as-is
    print(f"\nData processing: MVC NORMALIZED - No bandpass filtering, MVC normalization enabled ({len(analyzer.mvc_dict)} subjects), Outliers kept as-is")



if __name__ == '__main__':
    main()
