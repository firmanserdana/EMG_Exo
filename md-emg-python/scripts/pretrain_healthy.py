"""
Pre-train EMG model on healthy subjects S1-S10 for open_close task.

The healthy subject data was recorded under 3 conditions:
- No glove: EMG recording without exoskeleton
- Passive glove: Wearing exoskeleton but not activated
- Active glove: Exoskeleton activated (no EMG control)

Each session involves grabbing 6 different objects, with 12 timestamps marking:
- Object 0: timestamps 1-2 (grasp start, grasp end)
- Object 1: timestamps 3-4
- Object 2: timestamps 5-6
- Object 3: timestamps 7-8
- Object 4: timestamps 9-10
- Object 5: timestamps 11-12

For open_close task (2 classes):
- Class 0 (OPEN): Not grasping - hand is open (before grasp, between objects, after grasp)
- Class 1 (CLOSE): During grasp - hand is closed (from grasp_start to grasp_end)

Usage:
    python scripts/pretrain_healthy.py --task open_close --model_type CNNLSTM --epochs 100
    python scripts/pretrain_healthy.py --subjects S1,S2,S3 --task open_close
"""

import argparse
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, Dataset
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import yaml
import sys
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
NUM_CHANNELS = 32
SAMPLING_RATE = 1000  # Hz
WINDOW_SIZE_MS = 200  # ms
OVERLAP_MS = 100  # ms


# =============================================================================
# Data Augmentation and Normalization
# =============================================================================

class EMGDataset(Dataset):
    """PyTorch Dataset with data augmentation for EMG signals."""
    
    def __init__(self, X: np.ndarray, y: np.ndarray, augment: bool = False,
                 noise_factor: float = 0.1, channel_dropout: float = 0.1,
                 time_shift_max: int = 20):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)
        self.augment = augment
        self.noise_factor = noise_factor
        self.channel_dropout = channel_dropout
        self.time_shift_max = time_shift_max
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        x = self.X[idx].clone()
        y = self.y[idx]
        
        if self.augment:
            x = self._augment(x)
        
        return x, y
    
    def _augment(self, x):
        """Apply random augmentations to EMG window."""
        # 1. Add Gaussian noise
        if np.random.random() < 0.5:
            noise = torch.randn_like(x) * self.noise_factor * x.std()
            x = x + noise
        
        # 2. Channel dropout (simulate electrode failure)
        if np.random.random() < 0.3:
            n_drop = int(x.shape[1] * self.channel_dropout)
            drop_channels = np.random.choice(x.shape[1], n_drop, replace=False)
            x[:, drop_channels] = 0
        
        # 3. Time shift
        if np.random.random() < 0.3:
            shift = np.random.randint(-self.time_shift_max, self.time_shift_max)
            x = torch.roll(x, shifts=shift, dims=0)
        
        # 4. Amplitude scaling
        if np.random.random() < 0.5:
            scale = np.random.uniform(0.8, 1.2)
            x = x * scale
        
        return x


def normalize_emg(X: np.ndarray, method: str = 'zscore') -> Tuple[np.ndarray, Dict]:
    """Normalize EMG data.
    
    Args:
        X: EMG data (n_windows, n_samples, n_channels)
        method: 'zscore', 'minmax', or 'robust'
    
    Returns:
        X_norm: Normalized data
        norm_params: Parameters for applying same normalization to new data
    """
    norm_params = {'method': method}
    
    if method == 'zscore':
        # Z-score normalization per channel across all windows
        mean = X.mean(axis=(0, 1), keepdims=True)  # (1, 1, n_channels)
        std = X.std(axis=(0, 1), keepdims=True) + 1e-8
        X_norm = (X - mean) / std
        norm_params['mean'] = mean.squeeze()
        norm_params['std'] = std.squeeze()
        
    elif method == 'minmax':
        min_val = X.min(axis=(0, 1), keepdims=True)
        max_val = X.max(axis=(0, 1), keepdims=True)
        X_norm = (X - min_val) / (max_val - min_val + 1e-8)
        norm_params['min'] = min_val.squeeze()
        norm_params['max'] = max_val.squeeze()
        
    elif method == 'robust':
        # Robust scaling using median and IQR
        median = np.median(X, axis=(0, 1), keepdims=True)
        q75 = np.percentile(X, 75, axis=(0, 1), keepdims=True)
        q25 = np.percentile(X, 25, axis=(0, 1), keepdims=True)
        iqr = q75 - q25 + 1e-8
        X_norm = (X - median) / iqr
        norm_params['median'] = median.squeeze()
        norm_params['iqr'] = iqr.squeeze()
    else:
        X_norm = X
    
    return X_norm, norm_params


def apply_normalization(X: np.ndarray, norm_params: Dict) -> np.ndarray:
    """Apply saved normalization parameters to new data."""
    method = norm_params['method']
    
    if method == 'zscore':
        mean = norm_params['mean'].reshape(1, 1, -1)
        std = norm_params['std'].reshape(1, 1, -1)
        return (X - mean) / std
    elif method == 'minmax':
        min_val = norm_params['min'].reshape(1, 1, -1)
        max_val = norm_params['max'].reshape(1, 1, -1)
        return (X - min_val) / (max_val - min_val + 1e-8)
    elif method == 'robust':
        median = norm_params['median'].reshape(1, 1, -1)
        iqr = norm_params['iqr'].reshape(1, 1, -1)
        return (X - median) / iqr
    return X

# Session mappings from notes.txt
# Format: subject_id -> condition -> list of valid session numbers
SESSION_MAPPINGS = {
    'S1': {
        'no_glove': [2, 3, 4],      # sessions 2-4 (session 2 noted as bad in some versions)
        'passive_glove': [5, 6, 7],  # sessions 5-7 (or 4-6 in cleaner version)
        'active_glove': [8, 9, 10],  # sessions 8-10 (or 7-9 in cleaner version)
    },
    'S2': {
        'no_glove': [4, 5, 6],
        'passive_glove': [1, 2, 3],
        'active_glove': [7, 8, 9],
    },
    'S3': {
        'no_glove': [5, 6, 7],       # or 4-6 in cleaner version
        'passive_glove': [8, 9, 10], # or 7-9 in cleaner version
        'active_glove': [2, 3, 4],   # or 1-3 in cleaner version
    },
    'S4': {
        'no_glove': [1, 2, 3],
        'passive_glove': [10, 11, 12],  # or 7-9 in cleaner version
        'active_glove': [6, 7, 8],      # or 4-6 in cleaner version
    },
    'S5': {
        'no_glove': [7, 8, 9],
        'passive_glove': [4, 5, 6],
        'active_glove': [1, 2, 3],
    },
    'S6': {
        'no_glove': [7, 8, 9],
        'passive_glove': [1, 2, 3],
        'active_glove': [4, 5, 6],
    },
    'S7': {
        'no_glove': [5, 6],          # 4-6 (4 has 13 markers, ditch 1)
        'passive_glove': [9, 10],     # 7 look below, 8 bad
        'active_glove': [11, 12, 13],
    },
    'S8': {
        'no_glove': [4, 6, 7],       # session 5 missing
        'passive_glove': [1, 2, 3],
        'active_glove': [8, 9, 10],
    },
    'S9': {
        'no_glove': [5, 6, 7],
        'passive_glove': [2, 3, 4],
        'active_glove': [10, 13],    # sessions 8, 10, 13 (some missing)
    },
    'S10': {
        'no_glove': [1, 2, 3],
        'passive_glove': [8, 9, 10],
        'active_glove': [5, 7],      # 4 has misclick, 6 missing
    },
}

# Clean session mappings from the branch (preferred)
SESSION_MAPPINGS_CLEAN = {
    'S1': {
        'no_glove': [1, 2, 3],
        'passive_glove': [4, 5, 6],
        'active_glove': [7, 8, 9],
    },
    'S2': {
        'no_glove': [4, 5, 6],
        'passive_glove': [1, 2, 3],
        'active_glove': [7, 8, 9],
    },
    'S3': {
        'no_glove': [4, 5, 6],
        'passive_glove': [7, 8, 9],
        'active_glove': [1, 2, 3],
    },
    'S4': {
        'no_glove': [1, 2, 3],
        'passive_glove': [7, 8, 9],
        'active_glove': [4, 5, 6],
    },
    'S5': {
        'no_glove': [7, 8, 9],
        'passive_glove': [4, 5, 6],
        'active_glove': [1, 2, 3],
    },
    'S6': {
        'no_glove': [7, 8, 9],
        'passive_glove': [1, 2, 3],
        'active_glove': [4, 5, 6],
    },
    'S7': {
        'no_glove': [5, 6],
        'passive_glove': [9, 10],
        'active_glove': [11, 12, 13],
    },
    'S8': {
        'no_glove': [4, 6, 7],
        'passive_glove': [1, 2, 3],
        'active_glove': [8, 9, 10],
    },
    'S9': {
        'no_glove': [5, 6, 7],
        'passive_glove': [2, 3, 4],
        'active_glove': [10, 13],
    },
    'S10': {
        'no_glove': [1, 2, 3],
        'passive_glove': [8, 9, 10],
        'active_glove': [5, 7],
    },
}


@dataclass
class SegmentRecord:
    """Container for segmented EMG data."""
    samples: np.ndarray
    subject: str
    session: int
    condition: str
    object_id: int
    start_time: float
    end_time: float


def load_session_data(session_file: Path) -> np.ndarray:
    """Load EMG data from .npy file.
    
    The .npy files contain multiple arrays that were saved during streaming.
    Each array is a buffer from the acquisition.
    """
    arrays = []
    with open(session_file, 'rb') as f:
        while True:
            try:
                arrays.append(np.load(f, allow_pickle=False))
            except (ValueError, EOFError):
                break
    
    if not arrays:
        return np.array([])
    
    # Concatenate all buffers into single array (time x channels)
    data = np.concatenate(arrays, axis=0)
    return data


def load_timestamps(timestamps_file: Path) -> Dict:
    """Load timestamps.json file with gesture timing information."""
    if not timestamps_file.exists():
        return {}
    
    with open(timestamps_file, 'r') as f:
        timestamps = json.load(f)
    
    return timestamps


def segment_by_object(
    emg_data: np.ndarray,
    timestamps: Dict,
    object_id: int,
    fs_hz: float = SAMPLING_RATE
) -> Tuple[Optional[np.ndarray], float, float]:
    """Extract EMG segment for a specific object.
    
    Each session has 12 gesture timestamps that define 6 objects:
    - Object 0: between gesture 1 and gesture 2
    - Object 1: between gesture 3 and gesture 4
    - etc.
    
    Returns:
        segment: EMG data array or None
        start_time: Start timestamp
        end_time: End timestamp
    """
    gestures = timestamps.get('gestures', [])
    
    # Calculate gesture indices for this object
    # Object 0 uses gestures 1,2; Object 1 uses gestures 3,4; etc.
    start_gesture_idx = object_id * 2  # 0-indexed: 0, 2, 4, 6, 8, 10
    end_gesture_idx = start_gesture_idx + 1  # 1, 3, 5, 7, 9, 11
    
    # Find the corresponding timestamps
    start_time = None
    end_time = None
    
    for gesture in gestures:
        gid = gesture.get('gesture_id', 0)
        ts = gesture.get('timestamp', 0)
        
        if gid == start_gesture_idx + 1:  # gesture_id is 1-indexed
            start_time = ts
        elif gid == end_gesture_idx + 1:
            end_time = ts
    
    if start_time is None or end_time is None:
        return None, 0.0, 0.0
    
    # Convert to sample indices
    start_idx = int(max(0, np.floor(start_time * fs_hz)))
    end_idx = int(min(emg_data.shape[0], np.ceil(end_time * fs_hz)))
    
    if end_idx <= start_idx:
        return None, start_time, end_time
    
    # Extract segment (only EMG channels, not timestamp column)
    segment = emg_data[start_idx:end_idx, :NUM_CHANNELS].copy()
    
    return segment, start_time, end_time


@dataclass
class SessionRecord:
    """Container for full session EMG data with timestamps."""
    emg_data: np.ndarray
    timestamps: Dict
    subject: str
    session: int
    condition: str
    fs_hz: float


def parse_gesture_timestamps(timestamps: Dict) -> List[Tuple[float, float]]:
    """Parse gesture timestamps to get (start_time, end_time) for each object.
    
    Returns:
        List of (grasp_start, grasp_end) tuples for each object (6 objects per session)
    """
    gestures = timestamps.get('gestures', [])
    
    # Build mapping of gesture_id -> timestamp
    gesture_times = {}
    for gesture in gestures:
        gid = gesture.get('gesture_id', 0)
        ts = gesture.get('timestamp', 0)
        gesture_times[gid] = ts
    
    # Extract pairs for each object
    # Object 0: gestures 1,2; Object 1: gestures 3,4; etc.
    object_pairs = []
    for obj_id in range(6):
        start_gid = obj_id * 2 + 1  # 1, 3, 5, 7, 9, 11
        end_gid = obj_id * 2 + 2    # 2, 4, 6, 8, 10, 12
        
        start_time = gesture_times.get(start_gid)
        end_time = gesture_times.get(end_gid)
        
        if start_time is not None and end_time is not None:
            object_pairs.append((start_time, end_time))
    
    return object_pairs


def load_sessions_for_open_close(
    data_dir: Path,
    subjects: List[str],
    conditions: List[str],
    use_clean_mappings: bool = True
) -> List[SessionRecord]:
    """Load full session data for open_close task.
    
    Returns:
        List of SessionRecord with full EMG data and timestamps
    """
    mappings = SESSION_MAPPINGS_CLEAN if use_clean_mappings else SESSION_MAPPINGS
    sessions = []
    
    for subject in subjects:
        subject_dir = data_dir / subject / 'emg_logs'
        
        if not subject_dir.exists():
            print(f"  ⚠️  Subject directory not found: {subject_dir}")
            continue
        
        if subject not in mappings:
            print(f"  ⚠️  No session mappings for {subject}")
            continue
        
        subject_mappings = mappings[subject]
        
        for condition in conditions:
            condition_key = condition.lower().replace(' ', '_')
            
            if condition_key not in subject_mappings:
                continue
            
            session_nums = subject_mappings[condition_key]
            
            for session_num in session_nums:
                session_file = subject_dir / f'session_{session_num:02d}.npy'
                timestamps_file = subject_dir / f'session_{session_num:02d}_timestamps.json'
                
                if not session_file.exists() or not timestamps_file.exists():
                    continue
                
                # Load data
                emg_data = load_session_data(session_file)
                timestamps = load_timestamps(timestamps_file)
                
                if emg_data.size == 0:
                    continue
                
                # Infer sampling rate
                session_info = timestamps.get('session_info', {})
                total_duration = session_info.get('total_elapsed_time')
                if total_duration and total_duration > 0:
                    fs_hz = emg_data.shape[0] / total_duration
                else:
                    fs_hz = SAMPLING_RATE
                
                record = SessionRecord(
                    emg_data=emg_data,
                    timestamps=timestamps,
                    subject=subject,
                    session=session_num,
                    condition=condition,
                    fs_hz=fs_hz
                )
                sessions.append(record)
    
    return sessions


def prepare_open_close_data(
    sessions: List[SessionRecord],
    window_size_ms: int = WINDOW_SIZE_MS,
    overlap_ms: int = OVERLAP_MS,
    balance_classes: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """Prepare training data for open_close task (2 classes).
    
    Labels:
    - 0: OPEN - not grasping (before grasp, between objects, after grasp)
    - 1: CLOSE - during grasp (from grasp_start to grasp_end - hand closing/holding)
    
    Args:
        sessions: List of SessionRecord
        window_size_ms: Window size in ms
        overlap_ms: Overlap between windows in ms
        balance_classes: If True, undersample majority class
    
    Returns:
        X: Windows array (n_windows, window_samples, n_channels)
        y: Labels array (n_windows,) with values 0 or 1
    """
    windows_by_class = {0: [], 1: []}  # OPEN, CLOSE
    
    for session in sessions:
        emg_data = session.emg_data
        fs_hz = session.fs_hz
        n_samples = emg_data.shape[0]
        
        window_samples = int(window_size_ms * fs_hz / 1000)
        step_samples = int((window_size_ms - overlap_ms) * fs_hz / 1000)
        
        # Parse gesture timestamps
        object_pairs = parse_gesture_timestamps(session.timestamps)
        
        if not object_pairs:
            continue
        
        # Create label array for full session
        # Default to OPEN (0), mark CLOSE (1) during grasp periods
        labels = np.zeros(n_samples, dtype=np.int64)
        
        for grasp_start, grasp_end in object_pairs:
            start_idx = int(max(0, grasp_start * fs_hz))
            end_idx = int(min(n_samples, grasp_end * fs_hz))
            
            # Label CLOSE period (during grasp)
            labels[start_idx:end_idx] = 1
        
        # Extract windows
        for start in range(0, n_samples - window_samples + 1, step_samples):
            end = start + window_samples
            
            # Use majority label for window
            window_labels = labels[start:end]
            label = int(np.bincount(window_labels).argmax())
            
            # Only include if clear majority (>80% same label)
            majority_ratio = np.sum(window_labels == label) / len(window_labels)
            if majority_ratio < 0.8:
                continue
            
            window = emg_data[start:end, :NUM_CHANNELS].copy()
            
            # Skip windows with NaN or extreme values
            if np.isnan(window).any() or np.abs(window).max() > 1e6:
                continue
            
            windows_by_class[label].append(window)
    
    print(f"  Before balancing:")
    print(f"    OPEN (0) windows: {len(windows_by_class[0])}")
    print(f"    CLOSE (1) windows: {len(windows_by_class[1])}")
    
    # Balance classes by undersampling majority class
    if balance_classes:
        min_count = min(len(windows_by_class[0]), len(windows_by_class[1]))
        for label in [0, 1]:
            if len(windows_by_class[label]) > min_count:
                indices = np.random.choice(len(windows_by_class[label]), min_count, replace=False)
                windows_by_class[label] = [windows_by_class[label][i] for i in indices]
    
    print(f"  After balancing:")
    print(f"    OPEN (0): {len(windows_by_class[0])} windows")
    print(f"    CLOSE (1): {len(windows_by_class[1])} windows")
    
    # Combine all windows
    all_windows = []
    all_labels = []
    for label in [0, 1]:
        for window in windows_by_class[label]:
            all_windows.append(window)
            all_labels.append(label)
    
    X = np.array(all_windows)
    y = np.array(all_labels)
    
    return X, y


def load_all_healthy_data(
    data_dir: Path,
    subjects: List[str],
    conditions: List[str],
    use_clean_mappings: bool = True
) -> Dict[str, Dict[int, List[SegmentRecord]]]:
    """Load all healthy subject data organized by condition and object.
    
    Returns:
        Dict mapping condition -> object_id -> list of SegmentRecord
    """
    mappings = SESSION_MAPPINGS_CLEAN if use_clean_mappings else SESSION_MAPPINGS
    
    data_by_condition = defaultdict(lambda: defaultdict(list))
    
    for subject in subjects:
        subject_dir = data_dir / subject / 'emg_logs'
        
        if not subject_dir.exists():
            print(f"  ⚠️  Subject directory not found: {subject_dir}")
            continue
        
        if subject not in mappings:
            print(f"  ⚠️  No session mappings for {subject}")
            continue
        
        subject_mappings = mappings[subject]
        
        for condition in conditions:
            condition_key = condition.lower().replace(' ', '_')
            
            if condition_key not in subject_mappings:
                continue
            
            sessions = subject_mappings[condition_key]
            
            for session_num in sessions:
                session_file = subject_dir / f'session_{session_num:02d}.npy'
                timestamps_file = subject_dir / f'session_{session_num:02d}_timestamps.json'
                
                if not session_file.exists():
                    print(f"    ⚠️  Session file not found: {session_file}")
                    continue
                
                if not timestamps_file.exists():
                    print(f"    ⚠️  Timestamps file not found: {timestamps_file}")
                    continue
                
                # Load data
                emg_data = load_session_data(session_file)
                timestamps = load_timestamps(timestamps_file)
                
                if emg_data.size == 0:
                    print(f"    ⚠️  Empty EMG data: {session_file}")
                    continue
                
                # Infer sampling rate from data if possible
                session_info = timestamps.get('session_info', {})
                total_duration = session_info.get('total_elapsed_time')
                if total_duration and total_duration > 0:
                    fs_hz = emg_data.shape[0] / total_duration
                else:
                    fs_hz = SAMPLING_RATE
                
                # Extract segments for each object
                for obj_id in range(6):
                    segment, start_time, end_time = segment_by_object(
                        emg_data, timestamps, obj_id, fs_hz
                    )
                    
                    if segment is not None and segment.shape[0] > 100:  # Min 100 samples
                        record = SegmentRecord(
                            samples=segment,
                            subject=subject,
                            session=session_num,
                            condition=condition,
                            object_id=obj_id,
                            start_time=start_time,
                            end_time=end_time
                        )
                        data_by_condition[condition][obj_id].append(record)
    
    return data_by_condition


def compute_features(segment: np.ndarray, fs_hz: float = SAMPLING_RATE) -> np.ndarray:
    """Compute time-domain features from EMG segment.
    
    Features per channel:
    - Mean Absolute Value (MAV)
    - Root Mean Square (RMS)
    - Waveform Length (WL)
    - Zero Crossings (ZC)
    - Slope Sign Changes (SSC)
    - Variance (VAR)
    """
    n_channels = segment.shape[1]
    features = []
    
    for ch in range(n_channels):
        channel_data = segment[:, ch]
        
        # Mean Absolute Value
        mav = np.mean(np.abs(channel_data))
        
        # Root Mean Square
        rms = np.sqrt(np.mean(channel_data ** 2))
        
        # Waveform Length
        wl = np.sum(np.abs(np.diff(channel_data)))
        
        # Zero Crossings
        zc = np.sum(np.abs(np.diff(np.sign(channel_data)))) / 2
        
        # Slope Sign Changes
        diff_data = np.diff(channel_data)
        ssc = np.sum(np.abs(np.diff(np.sign(diff_data)))) / 2
        
        # Variance
        var = np.var(channel_data)
        
        features.extend([mav, rms, wl, zc, ssc, var])
    
    return np.array(features)


def prepare_training_data(
    data_by_condition: Dict,
    window_size_ms: int = WINDOW_SIZE_MS,
    overlap_ms: int = OVERLAP_MS,
    fs_hz: float = SAMPLING_RATE,
    task_type: str = 'grasp_vs_rest'
) -> Tuple[np.ndarray, np.ndarray]:
    """Prepare training data with windowing and labeling.
    
    Args:
        data_by_condition: Data organized by condition and object
        window_size_ms: Window size in milliseconds
        overlap_ms: Overlap between windows in milliseconds
        fs_hz: Sampling rate
        task_type: 'grasp_vs_rest' or 'object_classification'
    
    Returns:
        X: Features array (n_windows, n_features) or (n_windows, window_samples, n_channels)
        y: Labels array
    """
    window_samples = int(window_size_ms * fs_hz / 1000)
    step_samples = int((window_size_ms - overlap_ms) * fs_hz / 1000)
    
    all_windows = []
    all_labels = []
    
    for condition, objects_data in data_by_condition.items():
        for obj_id, records in objects_data.items():
            for record in records:
                segment = record.samples
                n_samples = segment.shape[0]
                
                # Sliding window
                for start in range(0, n_samples - window_samples + 1, step_samples):
                    window = segment[start:start + window_samples, :]
                    all_windows.append(window)
                    
                    if task_type == 'grasp_vs_rest':
                        # Label 1 for grasp activity
                        all_labels.append(1)
                    else:
                        # Object classification
                        all_labels.append(obj_id)
    
    X = np.array(all_windows)
    y = np.array(all_labels)
    
    return X, y


def create_rest_data(
    data_by_condition: Dict,
    n_rest_windows: int,
    window_size_ms: int = WINDOW_SIZE_MS,
    fs_hz: float = SAMPLING_RATE
) -> Tuple[np.ndarray, np.ndarray]:
    """Create rest/baseline data from inter-gesture periods.
    
    Uses the beginning of each session (before first gesture) as rest.
    """
    window_samples = int(window_size_ms * fs_hz / 1000)
    
    rest_windows = []
    
    # Collect segments before first gesture from each session
    # This is a simplification - ideally would have explicit rest periods
    for condition, objects_data in data_by_condition.items():
        if 0 in objects_data:  # Object 0 is the first grasp
            for record in objects_data[0]:
                # Create synthetic rest by using low-amplitude noise
                # In practice, you'd want actual rest recordings
                n_samples = window_samples * 2
                rest_segment = np.random.randn(n_samples, NUM_CHANNELS) * 0.01
                
                for start in range(0, n_samples - window_samples + 1, window_samples):
                    window = rest_segment[start:start + window_samples, :]
                    rest_windows.append(window)
                    
                    if len(rest_windows) >= n_rest_windows:
                        break
            
            if len(rest_windows) >= n_rest_windows:
                break
    
    X_rest = np.array(rest_windows[:n_rest_windows])
    y_rest = np.zeros(len(X_rest), dtype=np.int64)
    
    return X_rest, y_rest


def build_lstm_model(
    input_size: int,
    hidden_size: int = 128,
    num_layers: int = 2,
    num_classes: int = 2,
    dropout: float = 0.3
) -> nn.Module:
    """Build LSTM model for EMG classification."""
    
    class LSTMClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
                bidirectional=True
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden_size * 2, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size, num_classes)
            )
        
        def forward(self, x):
            # x: (batch, seq_len, input_size)
            lstm_out, _ = self.lstm(x)
            # Use last timestep
            out = lstm_out[:, -1, :]
            out = self.fc(out)
            return out
    
    return LSTMClassifier()


def build_cnn_lstm_model(
    n_channels: int,
    seq_len: int,
    num_classes: int = 2,
    dropout: float = 0.3
) -> nn.Module:
    """Build CNN-LSTM model for EMG classification."""
    
    class CNNLSTMClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            
            # CNN for spatial features
            self.conv1 = nn.Conv1d(n_channels, 64, kernel_size=5, padding=2)
            self.bn1 = nn.BatchNorm1d(64)
            self.conv2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
            self.bn2 = nn.BatchNorm1d(128)
            self.pool = nn.MaxPool1d(2)
            
            # Calculate LSTM input size
            lstm_seq_len = seq_len // 4  # After 2 pooling layers
            
            # LSTM for temporal features
            self.lstm = nn.LSTM(
                input_size=128,
                hidden_size=64,
                num_layers=2,
                batch_first=True,
                dropout=dropout,
                bidirectional=True
            )
            
            # Classifier
            self.fc = nn.Sequential(
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, num_classes)
            )
        
        def forward(self, x):
            # x: (batch, seq_len, n_channels)
            x = x.transpose(1, 2)  # (batch, n_channels, seq_len)
            
            # CNN
            x = torch.relu(self.bn1(self.conv1(x)))
            x = self.pool(x)
            x = torch.relu(self.bn2(self.conv2(x)))
            x = self.pool(x)
            
            # Prepare for LSTM: (batch, seq_len, features)
            x = x.transpose(1, 2)
            
            # LSTM
            lstm_out, _ = self.lstm(x)
            out = lstm_out[:, -1, :]
            
            # Classifier
            out = self.fc(out)
            return out
    
    return CNNLSTMClassifier()


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 100,
    lr: float = 0.001,
    device: str = 'cuda'
) -> Tuple[nn.Module, Dict]:
    """Train the model.
    
    Returns:
        model: Trained model
        history: Training history
    """
    device = torch.device(device if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=10
    )
    
    history = {
        'train_loss': [],
        'val_loss': [],
        'train_acc': [],
        'val_acc': []
    }
    
    best_val_loss = float('inf')
    best_model_state = None
    patience_counter = 0
    patience = 20
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0
        
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(device).float()
            y_batch = y_batch.to(device).long()
            
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = outputs.max(1)
            train_total += y_batch.size(0)
            train_correct += predicted.eq(y_batch).sum().item()
        
        train_loss /= len(train_loader)
        train_acc = train_correct / train_total
        
        # Validation
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch = X_batch.to(device).float()
                y_batch = y_batch.to(device).long()
                
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                
                val_loss += loss.item()
                _, predicted = outputs.max(1)
                val_total += y_batch.size(0)
                val_correct += predicted.eq(y_batch).sum().item()
        
        val_loss /= len(val_loader)
        val_acc = val_correct / val_total
        
        scheduler.step(val_loss)
        
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_acc'].append(train_acc)
        history['val_acc'].append(val_acc)
        
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1}/{epochs} - "
                  f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f} - "
                  f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Early stopping at epoch {epoch+1}")
                break
    
    # Load best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    
    return model, history


def main():
    parser = argparse.ArgumentParser(description='Pre-train EMG model on healthy subjects')
    parser.add_argument('--subjects', type=str, default='S1,S2,S3,S4,S5,S6,S7,S8,S9,S10',
                        help='Comma-separated list of subjects to include')
    parser.add_argument('--conditions', type=str, default='all',
                        choices=['all', 'no_glove', 'passive_glove', 'active_glove'],
                        help='Which conditions to include')
    parser.add_argument('--model_type', type=str, default='LSTM',
                        choices=['LSTM', 'CNNLSTM'],
                        help='Model architecture')
    parser.add_argument('--task', type=str, default='open_close',
                        choices=['open_close', 'grasp_vs_rest', 'object_classification'],
                        help='Training task (open_close aligns with online decoder)')
    parser.add_argument('--epochs', type=int, default=100,
                        help='Number of training epochs')
    parser.add_argument('--batch_size', type=int, default=64,
                        help='Batch size')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='Learning rate')
    parser.add_argument('--window_ms', type=int, default=200,
                        help='Window size in milliseconds')
    parser.add_argument('--overlap_ms', type=int, default=100,
                        help='Overlap in milliseconds')
    parser.add_argument('--output_dir', type=str, default='models/pretrained',
                        help='Output directory for pretrained model')
    parser.add_argument('--val_split', type=float, default=0.2,
                        help='Validation split ratio')
    
    args = parser.parse_args()
    
    # Setup paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / 'data' / 'healthy'
    output_dir = script_dir.parent / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse subjects
    subjects = [s.strip() for s in args.subjects.split(',')]
    
    # Parse conditions
    if args.conditions == 'all':
        conditions = ['no_glove', 'passive_glove', 'active_glove']
    else:
        conditions = [args.conditions]
    
    print("\n" + "="*60)
    print("🧠 Pre-training EMG Model on Healthy Subjects")
    print("="*60)
    print(f"  Subjects: {', '.join(subjects)}")
    print(f"  Conditions: {', '.join(conditions)}")
    print(f"  Model: {args.model_type}")
    print(f"  Task: {args.task}")
    print(f"  Window: {args.window_ms}ms, Overlap: {args.overlap_ms}ms")
    print("="*60 + "\n")
    
    # Handle different task types
    if args.task == 'open_close':
        # Use open_close data preparation (2 classes: OPEN=0, CLOSE=1)
        print("📂 Loading healthy subject sessions for open_close task...")
        sessions = load_sessions_for_open_close(
            data_dir, subjects, conditions, use_clean_mappings=True
        )
        
        print(f"  Loaded {len(sessions)} sessions")
        
        if not sessions:
            print("❌ No sessions loaded! Check data directory and session mappings.")
            return
        
        # Prepare training data
        print("\n📊 Preparing open_close training data...")
        print("  Labels: 0=OPEN (not grasping), 1=CLOSE (grasping)")
        X, y = prepare_open_close_data(
            sessions,
            window_size_ms=args.window_ms,
            overlap_ms=args.overlap_ms,
            balance_classes=True
        )
        
        num_classes = 2  # OPEN, CLOSE
        total_segments = len(sessions)
        
    else:
        # Use original grasp_vs_rest or object_classification
        print("📂 Loading healthy subject data...")
        data_by_condition = load_all_healthy_data(
            data_dir, subjects, conditions, use_clean_mappings=True
        )
        
        # Count loaded data
        total_segments = 0
        for condition, objects_data in data_by_condition.items():
            for obj_id, records in objects_data.items():
                total_segments += len(records)
                print(f"  {condition} - Object {obj_id}: {len(records)} segments")
        
        print(f"\n  Total segments loaded: {total_segments}")
        
        if total_segments == 0:
            print("❌ No data loaded! Check data directory and session mappings.")
            return
        
        # Prepare training data
        print("\n📊 Preparing training data...")
        X_grasp, y_grasp = prepare_training_data(
            data_by_condition,
            window_size_ms=args.window_ms,
            overlap_ms=args.overlap_ms,
            task_type=args.task
        )
        
        print(f"  Grasp windows: {X_grasp.shape[0]}")
        
        # Create rest data (synthetic for now)
        n_rest = min(X_grasp.shape[0], 1000)  # Balance classes
        X_rest, y_rest = create_rest_data(
            data_by_condition, n_rest,
            window_size_ms=args.window_ms
        )
        print(f"  Rest windows: {X_rest.shape[0]}")
        
        # Combine data
        X = np.concatenate([X_grasp, X_rest], axis=0)
        y = np.concatenate([y_grasp, y_rest], axis=0)
        
        num_classes = 2 if args.task == 'grasp_vs_rest' else 6
    
    print(f"\n  Total windows: {X.shape[0]}")
    print(f"  Window shape: {X.shape[1:]} (samples x channels)")
    print(f"  Number of classes: {num_classes}")
    
    # Normalize data
    print("\n📈 Normalizing data (z-score)...")
    X, norm_params = normalize_emg(X, method='zscore')
    print(f"  Mean range: [{norm_params['mean'].min():.4f}, {norm_params['mean'].max():.4f}]")
    print(f"  Std range: [{norm_params['std'].min():.4f}, {norm_params['std'].max():.4f}]")
    
    # Shuffle and split
    indices = np.random.permutation(len(X))
    X = X[indices]
    y = y[indices]
    
    split_idx = int(len(X) * (1 - args.val_split))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    print(f"  Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Create data loaders with augmentation for training
    print("\n🔄 Creating data loaders with augmentation...")
    train_dataset = EMGDataset(X_train, y_train, augment=True, 
                               noise_factor=0.1, channel_dropout=0.1)
    val_dataset = EMGDataset(X_val, y_val, augment=False)
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, num_workers=0)
    
    # Build model
    print(f"\n🏗️  Building {args.model_type} model...")
    
    if args.model_type == 'LSTM':
        model = build_lstm_model(
            input_size=NUM_CHANNELS,
            num_classes=num_classes
        )
    else:  # CNNLSTM
        model = build_cnn_lstm_model(
            n_channels=NUM_CHANNELS,
            seq_len=X.shape[1],
            num_classes=num_classes
        )
    
    # Count parameters
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Model parameters: {n_params:,}")
    
    # Train model
    print(f"\n🚀 Training for {args.epochs} epochs...")
    model, history = train_model(
        model, train_loader, val_loader,
        epochs=args.epochs,
        lr=args.lr
    )
    
    # Save model
    model_name = f"pretrained_{args.model_type.lower()}_{args.task}"
    if args.conditions != 'all':
        model_name += f"_{args.conditions}"
    model_name += ".pth"
    
    model_path = output_dir / model_name
    
    # Save with metadata
    save_dict = {
        'model_state_dict': model.state_dict(),
        'model_type': args.model_type,
        'task': args.task,
        'conditions': conditions,
        'subjects': subjects,
        'n_channels': NUM_CHANNELS,
        'window_ms': args.window_ms,
        'overlap_ms': args.overlap_ms,
        'num_classes': num_classes,
        'norm_params': norm_params,  # Include normalization params for transfer learning
        'history': history,
        'best_val_acc': max(history['val_acc']),
        'best_val_loss': min(history['val_loss'])
    }
    
    torch.save(save_dict, model_path)
    print(f"\n✅ Model saved to: {model_path}")
    
    # Save training config
    config_path = output_dir / f"{model_name.replace('.pth', '_config.yaml')}"
    config = {
        'model_type': args.model_type,
        'task': args.task,
        'conditions': conditions,
        'subjects': subjects,
        'n_channels': NUM_CHANNELS,
        'window_ms': args.window_ms,
        'overlap_ms': args.overlap_ms,
        'epochs': args.epochs,
        'batch_size': args.batch_size,
        'lr': args.lr,
        'best_val_acc': float(max(history['val_acc'])),
        'best_val_loss': float(min(history['val_loss'])),
        'total_segments': total_segments,
        'total_windows': len(X)
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"  Config saved to: {config_path}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Training Summary")
    print("="*60)
    print(f"  Best Validation Accuracy: {max(history['val_acc']):.4f}")
    print(f"  Best Validation Loss: {min(history['val_loss']):.4f}")
    print(f"  Final Train Accuracy: {history['train_acc'][-1]:.4f}")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
