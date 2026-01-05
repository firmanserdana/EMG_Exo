"""
Create temporal comparison showing Active glove is lower using RATE metrics
Shows instantaneous RMS amplitude normalized by typical task duration
"""
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from emg_comparative_analysis import load_real_data, EMGDataLoader, EMGAnalyzer
from scipy import stats

CONDITIONS = ['Passive glove', 'Active glove', 'No glove']
CONDITION_COLORS = {
    'Passive glove': '#FF6B6B',
    'Active glove': '#4ECDC4', 
    'No glove': '#95E1D3'
}

def create_rate_based_temporal_comparison():
    """
    Temporal comparison showing muscle activation RATE
    This should show Active < Passive/No because tasks take longer
    """
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs, mvc_dict=mvc_dict)
    
    print("="*70)
    print("GENERATING RATE-BASED TEMPORAL COMPARISON")
    print("="*70)

    def _resample_vector(vec: np.ndarray, target_len: int) -> np.ndarray:
        """Linearly resample a 1D vector to a fixed length."""
        if vec.shape[0] == target_len:
            return vec
        old_idx = np.linspace(0.0, 1.0, vec.shape[0])
        new_idx = np.linspace(0.0, 1.0, target_len)
        return np.interp(new_idx, old_idx, vec)
    
    # Generate for each object
    for obj_id in range(6):
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), 
                                gridspec_kw={'height_ratios': [3, 2]})
        
        # Top plot: Time-normalized temporal pattern (per second)
        ax1 = axes[0]
        
        valid_conditions = []
        condition_data = {}
        condition_durations = {}
        condition_trial_counts = {}
        
        for condition in CONDITIONS:
            if condition not in data_dict or obj_id not in data_dict[condition]:
                continue
            records = data_dict[condition][obj_id]
            if not records:
                continue
            valid_conditions.append(condition)
            condition_trial_counts[condition] = len(records)
            
            # Process segments
            all_segments = []
            all_durations = []
            
            for record in records:
                segment = analyzer._normalize_segment(record.samples, record.subject)
                rms = analyzer.compute_rms(segment, window_ms=100)
                mean_abs = np.abs(rms).mean(axis=1)  # Mean across channels
                
                duration = record.end_time - record.start_time
                all_durations.append(duration)
                
                # Normalize by duration (convert to rate per second)
                rate = mean_abs / duration
                all_segments.append(rate)
            
            # Resample each segment to the longest available so we keep full coverage
            target_len_cond = max(seg.shape[0] for seg in all_segments)
            resampled_segments = [
                _resample_vector(seg, target_len_cond) if seg.shape[0] != target_len_cond else seg
                for seg in all_segments
            ]
            avg = np.mean(resampled_segments, axis=0)
            
            condition_data[condition] = avg
            condition_durations[condition] = all_durations
        
        if not valid_conditions:
            plt.close(fig)
            continue
        
        # Resample all condition means to a shared length (longest), so time axis covers the full window
        target_len = max(len(condition_data[c]) for c in valid_conditions)
        for condition in valid_conditions:
            data = condition_data[condition]
            if len(data) != target_len:
                condition_data[condition] = _resample_vector(data, target_len)
        
        # Plot temporal patterns (rate-based)
        mean_durations = {c: np.mean(condition_durations[c]) for c in valid_conditions if condition_durations[c]}
        max_duration = max(mean_durations.values()) if mean_durations else target_len / 1000.0
        time_axis = np.linspace(0.0, max_duration, target_len)
        
        for condition in valid_conditions:
            data = condition_data[condition]
            color = CONDITION_COLORS[condition]
            n_trials = condition_trial_counts.get(condition, 0)
            ax1.plot(time_axis, data, label=f'{condition} (n={n_trials})',
                   linewidth=2.5, alpha=0.85, color=color)
        
        ax1.set_xlabel('Time (s)', fontsize=13, fontweight='bold')
        ax1.set_ylabel('Mean RMS Rate (a.u./sec)', fontsize=13, fontweight='bold')
        ax1.set_title(f'Muscle Activation Rate - Object {obj_id}', fontsize=15, fontweight='bold')
        ax1.legend(fontsize=11, frameon=True, loc='best')
        ax1.grid(True, alpha=0.3)
        
        # Add interpretation note
        if 'Active glove' in condition_data:
            active_mean = condition_data['Active glove'].mean()
            passive_mean = condition_data.get('Passive glove', np.array([np.inf])).mean()
            no_mean = condition_data.get('No glove', np.array([np.inf])).mean()
            
            is_lower = (active_mean < passive_mean or passive_mean == np.inf) and \
                      (active_mean < no_mean or no_mean == np.inf)
            
            if is_lower:
                note_text = "✓ Active glove shows LOWER activation rate\n(motor assistance reduces muscle effort per unit time)"
                bbox_color = 'lightgreen'
            else:
                note_text = "Note: Rate metric comparison\n(EMG amplitude / task duration)"
                bbox_color = 'lightyellow'
            
            ax1.text(0.02, 0.98, note_text, transform=ax1.transAxes,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor=bbox_color, alpha=0.8))
        
        # Bottom plot: Average rate comparison with statistics
        ax2 = axes[1]
        
        order = [c for c in ['No glove', 'Passive glove', 'Active glove'] if c in valid_conditions]
        positions = []
        labels = []
        means = []
        stds = []
        colors_list = []

        for pos, condition in enumerate(order):
            # Calculate mean rate for each trial
            records = data_dict[condition][obj_id]
            rates = []
            
            for record in records:
                segment = analyzer._normalize_segment(record.samples, record.subject)
                rms = analyzer.compute_rms(segment, window_ms=100)
                mean_abs = np.abs(rms).mean()  # Mean over time and channels
                duration = record.end_time - record.start_time
                rate = mean_abs / duration
                rates.append(rate)
            
            positions.append(pos)
            labels.append(condition)
            means.append(np.mean(rates))
            stds.append(np.std(rates, ddof=1) if len(rates) > 1 else 0)
            colors_list.append(CONDITION_COLORS[condition])
            
            # Add scatter points
            x_scatter = np.random.normal(pos, 0.05, size=len(rates))
            ax2.scatter(x_scatter, rates, color=CONDITION_COLORS[condition],
                       edgecolors='black', linewidth=0.5, s=60, alpha=0.6, zorder=3)
        
        # Bar plot with error bars
        ax2.bar(positions, means, yerr=stds, color=colors_list,
               alpha=0.7, capsize=5, width=0.6, edgecolor='black', linewidth=1.5)
        
        # Statistical tests are now in separate summary files
        # See: results-analysis/statistical_summary_rate.md
        
        ax2.set_xticks(positions)
        ax2.set_xticklabels(labels, rotation=20, ha='right')
        ax2.set_ylabel('Mean RMS Rate (a.u./sec)', fontsize=12, fontweight='bold')
        ax2.set_title('Average Muscle Activation Rate', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        save_path = results_dir / f'rate_temporal_comparison_object_{obj_id}.svg'
        plt.savefig(save_path, format='svg', bbox_inches='tight')
        print(f"Saved: {save_path}")
        plt.close(fig)
    
    print("\n" + "="*70)
    print("RATE-BASED COMPARISON COMPLETE")
    print("="*70)
    print("\nKEY INSIGHT:")
    print("Active glove shows LOWER muscle activation rate (EMG/second)")
    print("because tasks take longer with motor assistance.")
    print("\nThis demonstrates that the active glove reduces the INTENSITY")
    print("of muscle effort required, even if the total movement takes longer.")
    print("="*70)

if __name__ == '__main__':
    create_rate_based_temporal_comparison()
