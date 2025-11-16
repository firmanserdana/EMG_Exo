"""
Simplified EMG Comparative Analysis - Publication Quality Figures
Generates only essential figures in SVG format
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Configuration
NUM_CHANNELS = 32
CONDITION_COLORS = {
    'No glove': '#95E1D3',
    'Passive glove': '#FF6B6B',
    'Active glove': '#4ECDC4'
}

@dataclass
class SegmentRecord:
    samples: np.ndarray
    subject: str
    session: str
    start_time: float
    end_time: float

# Import load functions from main script
import sys
sys.path.insert(0, str(Path(__file__).parent))
from emg_comparative_analysis import (
    load_real_data,
    EMGDataLoader,
    EMGAnalyzer,
    summarize_condition_values,
    format_stats_text,
    CONDITIONS as ANALYSIS_CONDITIONS,
    get_svg_heatmap_layout,
    draw_svg_heatmap
)

CONDITIONS = list(ANALYSIS_CONDITIONS)

def create_temporal_comparison_per_object(data_dict, analyzer, results_dir):
    """Figure B: Temporal comparison using mean absolute value for each object"""
    
    for obj_id in range(6):
        fig, ax = plt.subplots(figsize=(12, 6))
        
        condition_segment_means = defaultdict(list)
        valid_conditions = []
        for condition in CONDITIONS:
            if condition not in data_dict or obj_id not in data_dict[condition]:
                continue
            records = data_dict[condition][obj_id]
            if not records:
                continue
            valid_conditions.append(condition)
        
        if not valid_conditions:
            plt.close(fig)
            continue
        
        # Find minimum length across all conditions
        min_len = float('inf')
        condition_data = {}
        
        for condition in valid_conditions:
            records = data_dict[condition][obj_id]
            all_segments = []
            for record in records:
                segment = analyzer._normalize_segment(record.samples, record.subject)
                rms = analyzer.compute_rms(segment, window_ms=100)
                # Use mean absolute value across channels
                mean_abs = np.abs(rms).mean(axis=1)
                all_segments.append(mean_abs)
                condition_segment_means[condition].append(float(mean_abs.mean()))
            
            # Truncate to shortest segment
            min_seg_len = min(seg.shape[0] for seg in all_segments)
            trimmed = [seg[:min_seg_len] for seg in all_segments]
            avg = np.mean(trimmed, axis=0)
            
            condition_data[condition] = avg
            min_len = min(min_len, len(avg))
        
        if not condition_data:
            plt.close(fig)
            continue

        plot_conditions, summary_stats, comparisons = summarize_condition_values(condition_segment_means)
        if not plot_conditions:
            plot_conditions = [c for c in CONDITIONS if c in condition_data]
        # Truncate all to minimum length (no padding)
        for condition in plot_conditions:
            condition_data[condition] = condition_data[condition][:min_len]
        
        # Plot
        time_axis = np.arange(min_len) / 1000.0  # Convert to seconds (assuming 1000 Hz)
        
        for condition in plot_conditions:
            data = condition_data[condition]
            color = CONDITION_COLORS.get(condition, '#1f77b4')
            n_samples = len(data_dict[condition][obj_id])
            ax.plot(time_axis, data, label=f'{condition} (n={n_samples})',
                   linewidth=2.5, alpha=0.85, color=color)
        
        ax.set_xlabel('Time (s)', fontsize=13, fontweight='bold')
        ax.set_ylabel('Mean Absolute RMS (a.u.)', fontsize=13, fontweight='bold')
        ax.set_title(f'Temporal Comparison - Object {obj_id}', fontsize=15, fontweight='bold')
        ax.legend(fontsize=11, frameon=True, loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

        stats_text = format_stats_text(plot_conditions, summary_stats, comparisons)
        if stats_text:
            fig.text(
                0.01,
                0.01,
                stats_text,
                ha='left',
                va='bottom',
                fontsize=9,
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9)
            )
        
        plt.tight_layout()
        save_path = results_dir / f'figureB_temporal_object_{obj_id}.svg'
        plt.savefig(save_path, format='svg', bbox_inches='tight')
        print(f"Saved: {save_path}")
        plt.close(fig)

def create_spatial_heatmap_single_subject(data_dict, analyzer, results_dir, obj_id=1):
    """Figure C: Spatial heatmap using one example subject"""
    
    # Find a subject that has all conditions for this object
    subject_data = defaultdict(lambda: defaultdict(list))
    
    for condition in CONDITIONS:
        if condition not in data_dict or obj_id not in data_dict[condition]:
            continue
        for record in data_dict[condition][obj_id]:
            subject_data[record.subject][condition].append(record)
    
    # Find subject with all 3 conditions
    example_subject = None
    for subject, cond_records in subject_data.items():
        if len(cond_records) == 3:  # Has all 3 conditions
            example_subject = subject
            break
    
    if not example_subject:
        print(f"No subject found with all 3 conditions for object {obj_id}")
        return
    
    # Create 2x16 spatial grid
    fig, axes = plt.subplots(3, 1, figsize=(16, 10))
    fig.patch.set_alpha(0.0)
    fig.suptitle(f'Spatial EMG Activity Map - Object {obj_id} - Subject {example_subject}',
                fontsize=16, fontweight='bold')
    
    # Calculate RMS for each condition
    vmin, vmax = float('inf'), float('-inf')
    condition_rms = {}
    condition_segment_means = defaultdict(list)
    
    for condition in CONDITIONS:
        records = subject_data[example_subject][condition]
        if records:
            channel_rms_list = []
            for record in records:
                segment = analyzer._normalize_segment(record.samples, record.subject)
                rms = analyzer.compute_rms(segment, window_ms=100)
                channel_rms = rms.mean(axis=0)  # Mean over time
                channel_rms_list.append(channel_rms)
                condition_segment_means[condition].append(float(channel_rms.mean()))

            if channel_rms_list:
                avg_rms = np.mean(channel_rms_list, axis=0)
                condition_rms[condition] = avg_rms
                vmin = min(vmin, avg_rms.min())
                vmax = max(vmax, avg_rms.max())
    
    layout = get_svg_heatmap_layout()
    # Plot each condition
    for idx, condition in enumerate(CONDITIONS):
        if condition not in condition_rms:
            continue
        
        ax = axes[idx]
        channel_rms = condition_rms[condition]
        sm = draw_svg_heatmap(
            ax,
            channel_rms,
            layout=layout,
            vmin=vmin,
            vmax=vmax,
            cmap='magma'
        )
        ax.set_title(f'{condition} - Mean RMS: {channel_rms.mean():.1f} a.u.',
                    fontsize=14, fontweight='bold')

    # Shared colorbar
    fig.colorbar(sm, ax=axes, label='RMS Amplitude (a.u.)', shrink=0.8, pad=0.02)
    stats_conditions, summary_stats, comparisons = summarize_condition_values(condition_segment_means)
    stats_text = format_stats_text(stats_conditions, summary_stats, comparisons)
    if stats_text:
        fig.text(
            0.01,
            0.01,
            stats_text,
            ha='left',
            va='bottom',
            fontsize=9,
            family='monospace',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9)
        )
    
    plt.tight_layout()
    save_path = results_dir / f'figureC_spatial_object_{obj_id}.svg'
    plt.savefig(save_path, format='svg', bbox_inches='tight')
    print(f"Saved: {save_path}")
    plt.close(fig)

def create_pca_per_object(data_dict, analyzer, results_dir):
    """Figure C: PCA analysis for each object separately"""
    
    for obj_id in range(6):
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f'PCA Analysis - Object {obj_id}', fontsize=16, fontweight='bold')
        
        # Extract features
        all_features = []
        segment_meta = []
        
        for condition in CONDITIONS:
            if condition not in data_dict or obj_id not in data_dict[condition]:
                continue
            
            for record in data_dict[condition][obj_id]:
                normalized = analyzer._normalize_segment(record.samples, record.subject)
                window_size = max(1, int(0.25 * analyzer.fs_hz))
                step_size = max(1, int(0.125 * analyzer.fs_hz))
                features = analyzer._extract_rms_features(normalized, window_size, step_size)
                if features.size == 0:
                    continue
                all_features.append(features)
                segment_meta.append((condition, record.subject, features.shape[0]))
        
        if len(all_features) < 3:
            plt.close(fig)
            continue
        
        # PCA
        X = np.vstack(all_features)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        pca = PCA(n_components=3)
        scores = pca.fit_transform(X_scaled)
        scores = np.abs(scores)  # Use absolute values
        
        # Group by condition
        condition_scores = defaultdict(list)
        offset = 0
        for condition, subject, length in segment_meta:
            segment_scores = scores[offset:offset + length]
            offset += length
            if segment_scores.size > 0:
                condition_scores[condition].append(segment_scores.mean(axis=0))
        
        condition_arrays = {cond: np.vstack(scores_list)  
                           for cond, scores_list in condition_scores.items()
                           if scores_list}
        
        # Plot each PC
        for pc_idx in range(3):
            ax = axes[pc_idx]
            
            positions = np.arange(len(condition_arrays))
            means = []
            stds = []
            colors_list = []
            labels = []
            
            for condition in CONDITIONS:
                if condition in condition_arrays:
                    pc_values = condition_arrays[condition][:, pc_idx]
                    means.append(np.mean(pc_values))
                    stds.append(np.std(pc_values, ddof=1) if len(pc_values) > 1 else 0)
                    colors_list.append(CONDITION_COLORS[condition])
                    labels.append(condition)
            
            if not means:
                continue
            
            bars = ax.bar(positions[:len(means)], means, yerr=stds,
                         color=colors_list, alpha=0.8, capsize=5, width=0.6,
                         edgecolor='black', linewidth=1.5)
            
            # Add scatter points
            for idx, condition in enumerate(labels):
                pc_values = condition_arrays[condition][:, pc_idx]
                x_scatter = np.random.normal(idx, 0.08, size=len(pc_values))
                ax.scatter(x_scatter, pc_values, color=colors_list[idx],
                          edgecolors='black', linewidth=0.5, s=50, alpha=0.7, zorder=3)
            
            ax.set_xticks(positions[:len(means)])
            ax.set_xticklabels(labels, rotation=20, ha='right')
            ax.set_ylabel(f'PC{pc_idx+1} Score (abs)', fontsize=12, fontweight='bold')
            ax.set_title(f'PC{pc_idx+1} ({pca.explained_variance_ratio_[pc_idx]*100:.1f}%)',
                        fontsize=13, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_ylim(bottom=0)
        
        # Add summary statistics (mean magnitudes only, no hypothesis testing)
        if 'Active glove' in condition_arrays:
            active_mag = np.linalg.norm(condition_arrays['Active glove'], axis=1).mean()
            passive_mag = np.linalg.norm(condition_arrays['Passive glove'], axis=1).mean() if 'Passive glove' in condition_arrays else 0
            no_mag = np.linalg.norm(condition_arrays['No glove'], axis=1).mean() if 'No glove' in condition_arrays else 0
            
            stats_text = f"Mean Magnitude: Active={active_mag:.2f}, Passive={passive_mag:.2f}, No={no_mag:.2f}"
            stats_text += "\n(See statistical_summary_pca.md for significance tests)"
            
            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=11,
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
        
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.12)
        save_path = results_dir / f'figureC_pca_object_{obj_id}.svg'
        plt.savefig(save_path, format='svg', bbox_inches='tight')
        print(f"Saved: {save_path}")
        plt.close(fig)

def create_duration_stats(data_dict, results_dir):
    """Task duration comparison with statistics"""
    
    # Collect durations
    duration_data = defaultdict(lambda: defaultdict(list))
    duration_summary = defaultdict(list)
    
    for condition in CONDITIONS:
        if condition not in data_dict:
            continue
        for obj_id in range(6):
            if obj_id not in data_dict[condition]:
                continue
            for record in data_dict[condition][obj_id]:
                duration = record.end_time - record.start_time
                duration_data[obj_id][condition].append(duration)
                duration_summary[condition].append(duration)
    
    # Create figure
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    for obj_id in range(6):
        ax = axes[obj_id]
        
        valid_conditions = [c for c in CONDITIONS if c in duration_data[obj_id]]
        if not valid_conditions:
            continue
        
        positions = np.arange(len(valid_conditions))
        means = []
        stds = []
        colors_list = []
        
        for condition in valid_conditions:
            durations = duration_data[obj_id][condition]
            means.append(np.mean(durations))
            stds.append(np.std(durations, ddof=1))
            colors_list.append(CONDITION_COLORS[condition])
        
        bars = ax.bar(positions, means, yerr=stds, color=colors_list,
                     alpha=0.8, capsize=5, width=0.6, edgecolor='black', linewidth=1.5)
        
        # Add points
        for idx, condition in enumerate(valid_conditions):
            durations = duration_data[obj_id][condition]
            x_scatter = np.random.normal(idx, 0.05, size=len(durations))
            ax.scatter(x_scatter, durations, color=colors_list[idx],
                      edgecolors='black', linewidth=0.5, s=40, alpha=0.6)
        
        # Statistical tests
        if 'Active glove' in duration_data[obj_id] and len(valid_conditions) >= 2:
            active_dur = duration_data[obj_id]['Active glove']
            stats_text = ""
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in duration_data[obj_id]:
                    other_dur = duration_data[obj_id][other_cond]
                    t_stat, p_val = stats.ttest_ind(active_dur, other_dur)
                    sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
                    stats_text += f"Active vs {other_cond}: p={p_val:.4f} {sig}\n"
            
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   fontsize=9, verticalalignment='top', family='monospace',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
        
        ax.set_xticks(positions)
        ax.set_xticklabels(valid_conditions, rotation=20, ha='right')
        ax.set_ylabel('Duration (s)', fontsize=11, fontweight='bold')
        ax.set_title(f'Object {obj_id}', fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim(bottom=0)
    
    fig.suptitle('Task Duration Comparison with Statistical Tests', fontsize=16, fontweight='bold')
    summary_conditions, summary_stats, summary_comparisons = summarize_condition_values(duration_summary)
    stats_text = format_stats_text(summary_conditions, summary_stats, summary_comparisons)
    if stats_text:
        fig.text(
            0.5,
            0.01,
            stats_text,
            ha='center',
            va='bottom',
            fontsize=9,
            family='monospace',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9)
        )
    plt.tight_layout(rect=(0, 0.05, 1, 1))
    
    save_path = results_dir / 'figure_duration_stats.svg'
    plt.savefig(save_path, format='svg', bbox_inches='tight')
    print(f"Saved: {save_path}")
    plt.close(fig)

def main():
    print("=" * 70)
    print("Simplified EMG Analysis - SVG Only")
    print("=" * 70)
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data")
        return
    
    print(f"Inferred sampling rate: {inferred_fs:.2f} Hz")
    
    if mvc_dict:
        print(f"MVC normalization enabled for {len(mvc_dict)} subjects")
        print("  All EMG values will be expressed as %MVC")
    else:
        print("Warning: No MVC data loaded - results will be in raw units")
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs, mvc_dict=mvc_dict)
    
    # Generate figures
    print("\n--- Figure B: Temporal Comparisons ---")
    create_temporal_comparison_per_object(data_dict, analyzer, results_dir)
    
    print("\n--- Figure C: Spatial Heatmap (Single Subject) ---")
    create_spatial_heatmap_single_subject(data_dict, analyzer, results_dir, obj_id=1)
    
    print("\n--- Figure C: PCA Per Object ---")
    create_pca_per_object(data_dict, analyzer, results_dir)
    
    print("\n--- Duration Statistics ---")
    create_duration_stats(data_dict, results_dir)
    
    print("\n" + "=" * 70)
    print("Analysis Complete!")
    print(f"All SVG figures saved in: {results_dir}")
    print("=" * 70)

if __name__ == '__main__':
    main()
