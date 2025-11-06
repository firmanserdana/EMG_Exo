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
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import warnings

warnings.filterwarnings('ignore')

# Configuration
FS_HZ = 1000  # Sampling rate in Hz
CHANNEL_IDS = list(range(32))  # Channel indices 0-31
CONDITIONS = ['Passive glove', 'Active glove', 'No glove']
CONDITION_COLORS = {
    'Passive glove': '#1f77b4',
    'Active glove': '#ff7f0e', 
    'No glove': '#2ca02c'
}


class EMGDataLoader:
    """Load and preprocess EMG data from .npy files"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        
    def load_session(self, session_file: Path) -> np.ndarray:
        """Load EMG data from .npy file and extract channels 0-31"""
        data = np.load(session_file)
        
        # If data has more than 32 columns, assume last column is timestamp
        if data.shape[1] > 32:
            # Take only first 32 channels (0-31)
            data = data[:, :32]
        
        return data
    
    def load_timestamps(self, timestamps_file: Path) -> Dict:
        """Load timestamps.json file with gesture timing information"""
        if not timestamps_file.exists():
            return {}
        
        with open(timestamps_file, 'r') as f:
            timestamps = json.load(f)
        
        return timestamps
    
    def segment_by_gesture(self, emg_data: np.ndarray, timestamps: Dict, 
                          gesture_id: int) -> List[np.ndarray]:
        """Extract EMG segments corresponding to a specific gesture"""
        segments = []
        
        if 'gesture_starts' not in timestamps or 'gesture_ends' not in timestamps:
            return segments
        
        gesture_starts = timestamps.get('gesture_starts', {})
        gesture_ends = timestamps.get('gesture_ends', {})
        
        # Get timestamps for this specific gesture
        if str(gesture_id) in gesture_starts:
            starts = gesture_starts[str(gesture_id)]
            ends = gesture_ends.get(str(gesture_id), [])
            
            for start, end in zip(starts, ends):
                # Convert time to sample indices
                start_idx = int(start * FS_HZ)
                end_idx = int(end * FS_HZ)
                
                if end_idx <= emg_data.shape[0]:
                    segments.append(emg_data[start_idx:end_idx])
        
        return segments


class EMGAnalyzer:
    """Analyze and visualize EMG data across conditions"""
    
    def __init__(self, data_loader: EMGDataLoader):
        self.data_loader = data_loader
        self.results_dir = Path('results-analysis')
        self.results_dir.mkdir(exist_ok=True)
        
    def compute_rms(self, data: np.ndarray, window_ms: int = 100) -> np.ndarray:
        """Compute RMS envelope with sliding window"""
        window_samples = int(window_ms * FS_HZ / 1000)
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
    
    def figure_b_raw_comparison(self, data_dict: Dict[str, Dict[int, List[np.ndarray]]], 
                               object_id: int = 0, save_prefix: str = 'figB') -> plt.Figure:
        """
        Figure B: Compare raw EMG data across 3 conditions for one object
        
        Args:
            data_dict: {condition: {object_id: [segments]}}
            object_id: Which object/pattern to plot
            save_prefix: Prefix for saved figure
        """
        fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
        fig.suptitle(f'Raw EMG Data Comparison - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        
        for idx, condition in enumerate(CONDITIONS):
            ax = axes[idx]
            
            if condition not in data_dict or object_id not in data_dict[condition]:
                ax.text(0.5, 0.5, f'No data for {condition}', 
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_ylabel(condition)
                continue
            
            segments = data_dict[condition][object_id]
            if not segments:
                ax.text(0.5, 0.5, f'No data for {condition}', 
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_ylabel(condition)
                continue
            
            # Use first segment or concatenate multiple segments
            if len(segments) > 0:
                segment = segments[0]
                time = np.arange(segment.shape[0]) / FS_HZ
                
                # Plot a subset of channels for clarity (every 4th channel)
                for ch in range(0, 32, 4):
                    offset = ch * 50  # Vertical offset for visualization
                    ax.plot(time, segment[:, ch] + offset, 
                           linewidth=0.5, alpha=0.7, label=f'Ch{ch}' if idx == 0 else '')
                
                ax.set_ylabel(f'{condition}\nAmplitude (µV)', fontsize=12)
                ax.set_xlim(0, min(5, time[-1]))  # Show first 5 seconds
                ax.grid(True, alpha=0.3)
                
                if idx == 0:
                    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', 
                            ncol=1, fontsize=8)
        
        axes[-1].set_xlabel('Time (s)', fontsize=12)
        plt.tight_layout()
        
        # Save figure
        save_path = self.results_dir / f'{save_prefix}_object_{object_id}.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {save_path}")
        
        return fig
    
    def figure_c_heatmap(self, data_dict: Dict[str, Dict[int, List[np.ndarray]]], 
                        object_id: int = 0, save_prefix: str = 'figC_heatmap') -> plt.Figure:
        """
        Figure C: Heatmap visualization across 3 conditions
        
        Shows channel activity (RMS) over time for each condition
        """
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f'EMG Activity Heatmap - Object {object_id}', 
                    fontsize=16, fontweight='bold')
        
        for idx, condition in enumerate(CONDITIONS):
            ax = axes[idx]
            
            if condition not in data_dict or object_id not in data_dict[condition]:
                ax.text(0.5, 0.5, f'No data', ha='center', va='center', 
                       transform=ax.transAxes)
                ax.set_title(condition)
                continue
            
            segments = data_dict[condition][object_id]
            if not segments or len(segments) == 0:
                ax.text(0.5, 0.5, f'No data', ha='center', va='center', 
                       transform=ax.transAxes)
                ax.set_title(condition)
                continue
            
            # Compute RMS for visualization
            segment = segments[0]
            rms = self.compute_rms(segment, window_ms=50)
            
            # Downsample for visualization (every 10ms)
            downsample_factor = 10
            rms_downsampled = rms[::downsample_factor]
            
            # Transpose for heatmap (channels on y-axis, time on x-axis)
            im = ax.imshow(rms_downsampled.T, aspect='auto', cmap='hot', 
                          interpolation='nearest', origin='lower')
            
            ax.set_title(condition, fontsize=14, fontweight='bold')
            ax.set_xlabel('Time (samples, 10ms resolution)', fontsize=10)
            ax.set_ylabel('Channel', fontsize=10)
            ax.set_yticks(np.arange(0, 32, 4))
            ax.set_yticklabels(np.arange(0, 32, 4))
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('RMS (µV)', fontsize=10)
        
        plt.tight_layout()
        
        # Save figure
        save_path = self.results_dir / f'{save_prefix}_object_{object_id}.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {save_path}")
        
        return fig
    
    def figure_c_pca(self, data_dict: Dict[str, Dict[int, List[np.ndarray]]], 
                    object_ids: List[int] = None, save_prefix: str = 'figC_pca') -> plt.Figure:
        """
        Figure C: PCA analysis of EMG features across conditions
        
        Args:
            data_dict: {condition: {object_id: [segments]}}
            object_ids: List of object IDs to analyze (default: [0])
        """
        if object_ids is None:
            object_ids = [0]
        
        # Extract features from all conditions and objects
        features = []
        labels = []
        
        for condition in CONDITIONS:
            if condition not in data_dict:
                continue
            
            for obj_id in object_ids:
                if obj_id not in data_dict[condition]:
                    continue
                
                segments = data_dict[condition][obj_id]
                for segment in segments:
                    # Compute RMS features in windows
                    window_size = int(0.25 * FS_HZ)  # 250ms windows
                    step_size = int(0.125 * FS_HZ)   # 125ms step
                    
                    for i in range(0, segment.shape[0] - window_size, step_size):
                        window = segment[i:i+window_size]
                        # RMS per channel
                        rms_features = np.sqrt(np.mean(window**2, axis=0))
                        features.append(rms_features)
                        labels.append(f'{condition} (Obj {obj_id})')
        
        if len(features) < 3:
            print("Not enough data for PCA analysis")
            return None
        
        # Convert to array and standardize
        X = np.array(features)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Perform PCA
        pca = PCA(n_components=3)
        X_pca = pca.fit_transform(X_scaled)
        
        # Create dataframe for plotting
        pca_df = pd.DataFrame({
            'PC1': X_pca[:, 0],
            'PC2': X_pca[:, 1],
            'PC3': X_pca[:, 2],
            'Label': labels
        })
        
        # Create 3D scatter plot
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot each condition with different color
        unique_labels = list(set(labels))
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_labels)))
        
        for label, color in zip(unique_labels, colors):
            mask = pca_df['Label'] == label
            ax.scatter(pca_df.loc[mask, 'PC1'], 
                      pca_df.loc[mask, 'PC2'], 
                      pca_df.loc[mask, 'PC3'],
                      label=label, alpha=0.6, s=30, color=color)
        
        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} var)', fontsize=12)
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} var)', fontsize=12)
        ax.set_zlabel(f'PC3 ({pca.explained_variance_ratio_[2]:.1%} var)', fontsize=12)
        ax.set_title('PCA of EMG Features Across Conditions', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.15, 1), loc='upper left')
        
        plt.tight_layout()
        
        # Save figure
        save_path = self.results_dir / f'{save_prefix}_objects_{"_".join(map(str, object_ids))}.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {save_path}")
        
        return fig
    
    def analyze_time_consumption(self, data_dict: Dict[str, Dict[int, List[np.ndarray]]],
                                object_ids: List[int] = None) -> pd.DataFrame:
        """
        Analyze time consumption differences across conditions
        
        Returns DataFrame with timing statistics
        """
        if object_ids is None:
            object_ids = list(range(6))
        
        results = []
        
        for condition in CONDITIONS:
            if condition not in data_dict:
                continue
            
            for obj_id in object_ids:
                if obj_id not in data_dict[condition]:
                    continue
                
                segments = data_dict[condition][obj_id]
                
                for seg_idx, segment in enumerate(segments):
                    duration_sec = segment.shape[0] / FS_HZ
                    
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
        
        save_path = self.results_dir / 'time_consumption_comparison.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {save_path}")
        plt.close()


def generate_example_data() -> Dict[str, Dict[int, List[np.ndarray]]]:
    """
    Generate example data for demonstration
    
    This creates synthetic EMG-like data to demonstrate the analysis pipeline
    when real data is not available.
    """
    print("\n=== Generating example data ===")
    print("Note: Using synthetic data for demonstration.")
    print("Replace with actual .npy files from md-emg-python/data/healthy/\n")
    
    data_dict = {}
    
    # Different activation patterns for each condition
    condition_params = {
        'Passive glove': {'amplitude': 30, 'noise': 5, 'duration': 3},
        'Active glove': {'amplitude': 50, 'noise': 8, 'duration': 4},
        'No glove': {'amplitude': 40, 'noise': 6, 'duration': 3.5}
    }
    
    for condition, params in condition_params.items():
        data_dict[condition] = {}
        
        # Generate data for 6 objects
        for obj_id in range(6):
            segments = []
            
            # Generate 2-3 segments per object
            n_segments = np.random.randint(2, 4)
            for _ in range(n_segments):
                duration = params['duration'] + np.random.randn() * 0.5
                n_samples = int(duration * FS_HZ)
                
                # Create synthetic EMG with different patterns per channel
                emg = np.zeros((n_samples, 32))
                
                for ch in range(32):
                    # Base signal with some temporal structure
                    t = np.linspace(0, duration, n_samples)
                    freq = 20 + ch * 2  # Different frequency per channel
                    
                    # Muscle activation pattern (burst-like)
                    activation = np.exp(-((t - duration/2)**2) / (duration/4)**2)
                    signal = params['amplitude'] * activation * np.sin(2 * np.pi * freq * t)
                    
                    # Add noise
                    noise = np.random.randn(n_samples) * params['noise']
                    
                    emg[:, ch] = signal + noise
                
                segments.append(emg)
            
            data_dict[condition][obj_id] = segments
    
    return data_dict


def load_real_data(data_dir: Path) -> Optional[Dict[str, Dict[int, List[np.ndarray]]]]:
    """
    Load real EMG data from .npy files
    
    Expected structure:
        data_dir/
            condition1/
                session_X.npy
                timestamps.json
            condition2/
                session_Y.npy
                timestamps.json
            ...
    """
    data_dir = Path(data_dir)
    
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return None
    
    loader = EMGDataLoader(data_dir)
    data_dict = {}
    
    # Try to find condition directories
    condition_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    
    if not condition_dirs:
        print(f"No subdirectories found in {data_dir}")
        return None
    
    for condition_dir in condition_dirs:
        condition_name = condition_dir.name
        print(f"Loading data from: {condition_dir}")
        
        # Find .npy files
        npy_files = list(condition_dir.glob('*.npy'))
        
        if not npy_files:
            print(f"  No .npy files found in {condition_dir}")
            continue
        
        # Load timestamps if available
        timestamps_file = condition_dir / 'timestamps.json'
        timestamps = loader.load_timestamps(timestamps_file)
        
        data_dict[condition_name] = {}
        
        # Load each session file
        for npy_file in npy_files:
            print(f"  Loading: {npy_file.name}")
            emg_data = loader.load_session(npy_file)
            
            # If timestamps available, segment by gesture
            if timestamps:
                for gesture_id in range(6):  # Assume 6 gestures/objects
                    segments = loader.segment_by_gesture(emg_data, timestamps, gesture_id)
                    if segments:
                        if gesture_id not in data_dict[condition_name]:
                            data_dict[condition_name][gesture_id] = []
                        data_dict[condition_name][gesture_id].extend(segments)
            else:
                # Without timestamps, treat whole session as one segment for object 0
                if 0 not in data_dict[condition_name]:
                    data_dict[condition_name][0] = []
                data_dict[condition_name][0].append(emg_data)
    
    return data_dict if data_dict else None


def main():
    """Main analysis pipeline"""
    print("=" * 70)
    print("EMG Comparative Analysis")
    print("=" * 70)
    
    # Try to load real data
    data_dir = Path('data/healthy')
    data_dict = load_real_data(data_dir)
    
    # If no real data, generate example data
    if data_dict is None:
        data_dict = generate_example_data()
    
    # Initialize analyzer
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader)
    
    print("\n" + "=" * 70)
    print("Generating Figures")
    print("=" * 70)
    
    # Generate Figure B for all 6 objects
    print("\n--- Figure B: Raw Data Comparison ---")
    for obj_id in range(6):
        print(f"\nGenerating Figure B for Object {obj_id}...")
        try:
            analyzer.figure_b_raw_comparison(data_dict, object_id=obj_id, 
                                           save_prefix=f'figureB')
            plt.close('all')
        except Exception as e:
            print(f"  Error generating Figure B for object {obj_id}: {e}")
    
    # Generate Figure C heatmaps for all 6 objects
    print("\n--- Figure C: Heatmaps ---")
    for obj_id in range(6):
        print(f"\nGenerating heatmap for Object {obj_id}...")
        try:
            analyzer.figure_c_heatmap(data_dict, object_id=obj_id, 
                                    save_prefix='figureC_heatmap')
            plt.close('all')
        except Exception as e:
            print(f"  Error generating heatmap for object {obj_id}: {e}")
    
    # Generate Figure C PCA
    print("\n--- Figure C: PCA Analysis ---")
    
    # Option 1: PCA for single best object
    print("\nGenerating PCA for Object 0 (best object)...")
    try:
        analyzer.figure_c_pca(data_dict, object_ids=[0], 
                            save_prefix='figureC_pca_single')
        plt.close('all')
    except Exception as e:
        print(f"  Error generating PCA for single object: {e}")
    
    # Option 2: PCA for all 6 objects
    print("\nGenerating PCA for all 6 objects...")
    try:
        analyzer.figure_c_pca(data_dict, object_ids=list(range(6)), 
                            save_prefix='figureC_pca_all')
        plt.close('all')
    except Exception as e:
        print(f"  Error generating PCA for all objects: {e}")
    
    # Time consumption analysis
    print("\n--- Time Consumption Analysis ---")
    try:
        analyzer.analyze_time_consumption(data_dict, object_ids=list(range(6)))
    except Exception as e:
        print(f"  Error in time consumption analysis: {e}")
    
    print("\n" + "=" * 70)
    print("Analysis Complete!")
    print("=" * 70)
    print(f"\nAll figures saved in: {analyzer.results_dir}")
    print("\nGenerated files:")
    print("  - figureB_object_*.png (6 files, 1 for main text + 5 for supplementary)")
    print("  - figureC_heatmap_object_*.png (6 files, 1 for main text + 5 for supplementary)")
    print("  - figureC_pca_single_objects_0.png (for main text)")
    print("  - figureC_pca_all_objects_0_1_2_3_4_5.png (optional, all objects)")
    print("  - time_consumption_comparison.png")
    print("  - time_consumption_analysis.csv")


if __name__ == '__main__':
    main()
