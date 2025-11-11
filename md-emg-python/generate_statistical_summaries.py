"""
Generate statistical test summaries for all EMG analyses
Saves results to markdown files with references to figure files
"""
import numpy as np
from pathlib import Path
from scipy import stats
from emg_comparative_analysis import load_real_data, EMGDataLoader, EMGAnalyzer
from datetime import datetime

CONDITIONS = ['Passive glove', 'Active glove', 'No glove']

def format_pvalue(p):
    """Format p-value with significance stars"""
    if p < 0.001:
        return f"{p:.4f} ***"
    elif p < 0.01:
        return f"{p:.4f} **"
    elif p < 0.05:
        return f"{p:.4f} *"
    else:
        return f"{p:.4f} ns"

def test_hypothesis_active_lower(active_values, other_values, other_name):
    """
    Test if Active < Other using one-tailed t-test
    Returns: (t_stat, p_value, mean_diff, percent_diff, hypothesis_supported)
    """
    # Two-sample t-test (two-tailed)
    t_stat, p_two = stats.ttest_ind(active_values, other_values)
    
    # One-tailed test: Active < Other
    # If mean(active) < mean(other), then t_stat should be negative
    p_one = p_two / 2 if t_stat < 0 else 1 - (p_two / 2)
    
    mean_active = np.mean(active_values)
    mean_other = np.mean(other_values)
    mean_diff = mean_active - mean_other
    percent_diff = ((mean_active - mean_other) / mean_other) * 100 if mean_other != 0 else 0
    
    hypothesis_supported = (mean_active < mean_other) and (p_one < 0.05)
    
    return t_stat, p_one, mean_diff, percent_diff, hypothesis_supported


def generate_amplitude_statistics():
    """Generate statistical tests for amplitude (RMS) comparisons"""
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data
    data_dict, inferred_fs = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for amplitude statistics")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs)
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_amplitude.md'
    
    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: Amplitude (RMS) Comparisons\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1-S10 (84 sessions, S0 excluded)\n\n")
        f.write("**Related Figures:**\n")
        f.write("- `figureB_object_*.svg` (temporal comparisons)\n")
        f.write("- `figureB_summary_object_1.svg` (amplitude summary)\n")
        f.write("- `figureD_channels_bar_object_1.svg` (channel-wise RMS)\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")
            
            # Collect RMS values per condition
            condition_rms = {}
            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue
                
                rms_values = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    mean_rms = np.abs(rms).mean()
                    rms_values.append(mean_rms)
                
                condition_rms[condition] = np.array(rms_values)
            
            if 'Active glove' not in condition_rms:
                f.write("*No Active glove data available*\n\n")
                continue
            
            # Summary statistics
            f.write("### Summary Statistics\n\n")
            f.write("| Condition | N | Mean RMS | Std | Min | Max |\n")
            f.write("|-----------|---|----------|-----|-----|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_rms:
                    vals = condition_rms[condition]
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.2f} | "
                           f"{np.std(vals):.2f} | {np.min(vals):.2f} | {np.max(vals):.2f} |\n")
            f.write("\n")
            
            # Hypothesis testing: Active < Others
            f.write("### Hypothesis Test: Active glove < Other conditions\n\n")
            f.write("*One-tailed t-test (H₀: Active ≥ Other; H₁: Active < Other)*\n\n")
            f.write("| Comparison | t-statistic | p-value | Mean Diff | % Change | Hypothesis Supported? |\n")
            f.write("|------------|-------------|---------|-----------|----------|-----------------------|\n")
            
            active_vals = condition_rms['Active glove']
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_rms:
                    other_vals = condition_rms[other_cond]
                    t_stat, p_val, mean_diff, pct_diff, supported = test_hypothesis_active_lower(
                        active_vals, other_vals, other_cond
                    )
                    
                    support_text = "✓ YES" if supported else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {t_stat:.3f} | {format_pvalue(p_val)} | "
                           f"{mean_diff:.2f} | {pct_diff:+.1f}% | **{support_text}** |\n")
            
            f.write("\n")
            
            # Two-tailed tests for completeness
            f.write("### Additional Tests (Two-tailed)\n\n")
            f.write("| Comparison | t-statistic | p-value (2-tail) |\n")
            f.write("|------------|-------------|------------------|\n")
            
            for i, cond1 in enumerate(CONDITIONS):
                if cond1 not in condition_rms:
                    continue
                for cond2 in CONDITIONS[i+1:]:
                    if cond2 not in condition_rms:
                        continue
                    vals1 = condition_rms[cond1]
                    vals2 = condition_rms[cond2]
                    t_stat, p_val = stats.ttest_ind(vals1, vals2)
                    f.write(f"| {cond1} vs {cond2} | {t_stat:.3f} | {format_pvalue(p_val)} |\n")
            
            f.write("\n---\n\n")
    
    print(f"✓ Saved amplitude statistics: {report_path}")
    return report_path


def generate_rate_statistics():
    """Generate statistical tests for rate-based comparisons (EMG/second)"""
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data
    data_dict, inferred_fs = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for rate statistics")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs)
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_rate.md'
    
    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: Rate-Based Comparisons (EMG per second)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1-S10 (84 sessions, S0 excluded)\n\n")
        f.write("**Metric:** RMS amplitude normalized by task duration (amplitude/second)\n\n")
        f.write("**Related Figures:**\n")
        f.write("- `rate_temporal_comparison_object_*.svg`\n\n")
        f.write("**Rationale:** Active glove tasks take longer but require lower muscle activation intensity.\n")
        f.write("Rate-based metrics reveal this by normalizing amplitude by duration.\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")
            
            # Collect rate values per condition
            condition_rates = {}
            condition_durations = {}
            
            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue
                
                rates = []
                durations = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    mean_rms = np.abs(rms).mean()
                    
                    duration = record.end_time - record.start_time
                    rate = mean_rms / duration if duration > 0 else 0
                    
                    rates.append(rate)
                    durations.append(duration)
                
                condition_rates[condition] = np.array(rates)
                condition_durations[condition] = np.array(durations)
            
            if 'Active glove' not in condition_rates:
                f.write("*No Active glove data available*\n\n")
                continue
            
            # Summary statistics
            f.write("### Summary Statistics\n\n")
            f.write("| Condition | N | Mean Rate | Std | Mean Duration (s) |\n")
            f.write("|-----------|---|-----------|-----|-------------------|\n")
            for condition in CONDITIONS:
                if condition in condition_rates:
                    rates = condition_rates[condition]
                    durations = condition_durations[condition]
                    f.write(f"| {condition} | {len(rates)} | {np.mean(rates):.2f} | "
                           f"{np.std(rates):.2f} | {np.mean(durations):.2f} |\n")
            f.write("\n")
            
            # Hypothesis testing: Active < Others
            f.write("### Hypothesis Test: Active glove rate < Other conditions\n\n")
            f.write("*One-tailed t-test (H₀: Active ≥ Other; H₁: Active < Other)*\n\n")
            f.write("| Comparison | t-statistic | p-value | Mean Diff | % Change | Hypothesis Supported? |\n")
            f.write("|------------|-------------|---------|-----------|----------|-----------------------|\n")
            
            active_vals = condition_rates['Active glove']
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_rates:
                    other_vals = condition_rates[other_cond]
                    t_stat, p_val, mean_diff, pct_diff, supported = test_hypothesis_active_lower(
                        active_vals, other_vals, other_cond
                    )
                    
                    support_text = "✓ YES" if supported else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {t_stat:.3f} | {format_pvalue(p_val)} | "
                           f"{mean_diff:.2f} | {pct_diff:+.1f}% | **{support_text}** |\n")
            
            f.write("\n")
            
            # Duration comparison
            f.write("### Task Duration Comparison\n\n")
            f.write("*Two-tailed t-test*\n\n")
            f.write("| Comparison | Mean Diff (s) | t-statistic | p-value |\n")
            f.write("|------------|---------------|-------------|---------|\n")
            
            active_dur = condition_durations['Active glove']
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_durations:
                    other_dur = condition_durations[other_cond]
                    t_stat, p_val = stats.ttest_ind(active_dur, other_dur)
                    mean_diff = np.mean(active_dur) - np.mean(other_dur)
                    f.write(f"| Active vs {other_cond} | {mean_diff:+.2f} | {t_stat:.3f} | {format_pvalue(p_val)} |\n")
            
            f.write("\n---\n\n")
    
    print(f"✓ Saved rate statistics: {report_path}")
    return report_path


def generate_pca_statistics():
    """Generate statistical tests for PCA analysis"""
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data
    data_dict, inferred_fs = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for PCA statistics")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs)
    
    from sklearn.decomposition import PCA
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_pca.md'
    
    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: PCA Magnitude Comparisons\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1-S10 (84 sessions, S0 excluded)\n\n")
        f.write("**Metric:** Euclidean magnitude in PC1-PC2 space\n\n")
        f.write("**Related Figures:**\n")
        f.write("- `figureC_pca_single_objects_1.svg`\n")
        f.write("- `figureC_pca_all_objects_0_1_2_3_4_5.svg`\n")
        f.write("- `figureC_pca_object_*.svg` (per-object PCA)\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")
            
            # Collect data for PCA
            condition_features = {}
            
            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue
                
                features_list = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    mean_rms = np.abs(rms).mean(axis=0)  # Mean over time, per channel
                    features_list.append(mean_rms)
                
                condition_features[condition] = np.array(features_list)
            
            if len(condition_features) < 2:
                f.write("*Insufficient data for PCA analysis*\n\n")
                continue
            
            # Perform PCA
            all_features = np.vstack([condition_features[c] for c in CONDITIONS if c in condition_features])
            pca = PCA(n_components=2)
            pca.fit(all_features)
            
            f.write(f"### PCA Results\n\n")
            f.write(f"- **Explained variance:** PC1={pca.explained_variance_ratio_[0]*100:.1f}%, ")
            f.write(f"PC2={pca.explained_variance_ratio_[1]*100:.1f}%\n\n")
            
            # Transform and compute magnitudes
            condition_magnitudes = {}
            for condition in CONDITIONS:
                if condition in condition_features:
                    transformed = pca.transform(condition_features[condition])
                    magnitudes = np.sqrt(transformed[:, 0]**2 + transformed[:, 1]**2)
                    condition_magnitudes[condition] = magnitudes
            
            # Summary statistics
            f.write("### PCA Magnitude Statistics\n\n")
            f.write("| Condition | N | Mean Magnitude | Std |\n")
            f.write("|-----------|---|----------------|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_magnitudes:
                    mags = condition_magnitudes[condition]
                    f.write(f"| {condition} | {len(mags)} | {np.mean(mags):.3f} | {np.std(mags):.3f} |\n")
            f.write("\n")
            
            # Hypothesis testing
            if 'Active glove' in condition_magnitudes:
                f.write("### Hypothesis Test: Active glove magnitude < Others\n\n")
                f.write("*One-tailed t-test*\n\n")
                f.write("| Comparison | t-statistic | p-value | Mean Diff | % Change | Hypothesis Supported? |\n")
                f.write("|------------|-------------|---------|-----------|----------|-----------------------|\n")
                
                active_mags = condition_magnitudes['Active glove']
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in condition_magnitudes:
                        other_mags = condition_magnitudes[other_cond]
                        t_stat, p_val, mean_diff, pct_diff, supported = test_hypothesis_active_lower(
                            active_mags, other_mags, other_cond
                        )
                        
                        support_text = "✓ YES" if supported else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {t_stat:.3f} | {format_pvalue(p_val)} | "
                               f"{mean_diff:.3f} | {pct_diff:+.1f}% | **{support_text}** |\n")
                
                f.write("\n")
            
            f.write("---\n\n")
    
    print(f"✓ Saved PCA statistics: {report_path}")
    return report_path


def generate_master_summary():
    """Generate a master summary combining all statistical tests"""
    
    script_dir = Path(__file__).resolve().parent
    results_dir = script_dir / 'results-analysis'
    
    report_path = results_dir / 'statistical_summary_master.md'
    
    with open(report_path, 'w') as f:
        f.write("# Master Statistical Summary: EMG Comparative Analysis\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1-S10 (84 sessions total, S0 excluded)\n")
        f.write("- S1-S5: 40 sessions (iPhone stopwatch OCR timestamps)\n")
        f.write("- S6-S10: 44 sessions (direct gesture marking)\n\n")
        f.write("---\n\n")
        
        f.write("## Research Question\n\n")
        f.write("**Does the active glove reduce muscle activation compared to passive glove and no glove conditions?**\n\n")
        f.write("---\n\n")
        
        f.write("## Analysis Methods\n\n")
        f.write("### 1. Amplitude Analysis (RMS)\n")
        f.write("- **Metric:** Root Mean Square (RMS) of EMG signals\n")
        f.write("- **Figures:** `figureB_*.svg`, `figureD_*.svg`\n")
        f.write("- **Statistics:** `statistical_summary_amplitude.md`\n\n")
        
        f.write("### 2. Rate-Based Analysis\n")
        f.write("- **Metric:** RMS amplitude per second (normalized by task duration)\n")
        f.write("- **Rationale:** Active tasks take longer but may require lower intensity\n")
        f.write("- **Figures:** `rate_temporal_comparison_object_*.svg`\n")
        f.write("- **Statistics:** `statistical_summary_rate.md`\n\n")
        
        f.write("### 3. PCA Analysis\n")
        f.write("- **Metric:** Magnitude in PC1-PC2 space\n")
        f.write("- **Purpose:** Multivariate comparison of muscle coordination patterns\n")
        f.write("- **Figures:** `figureC_pca_*.svg`\n")
        f.write("- **Statistics:** `statistical_summary_pca.md`\n\n")
        
        f.write("---\n\n")
        
        f.write("## Statistical Testing Approach\n\n")
        f.write("### Primary Hypothesis Test\n")
        f.write("- **H₀:** Active glove ≥ Other conditions (Passive/No glove)\n")
        f.write("- **H₁:** Active glove < Other conditions\n")
        f.write("- **Test:** One-tailed independent t-test\n")
        f.write("- **Significance level:** α = 0.05\n\n")
        
        f.write("### Significance Markers\n")
        f.write("- `***` : p < 0.001\n")
        f.write("- `**`  : p < 0.01\n")
        f.write("- `*`   : p < 0.05\n")
        f.write("- `ns`  : p ≥ 0.05 (not significant)\n\n")
        
        f.write("---\n\n")
        
        f.write("## Summary of Results\n\n")
        f.write("See individual statistical summary files for detailed results:\n\n")
        f.write("1. **Amplitude comparisons:** `statistical_summary_amplitude.md`\n")
        f.write("2. **Rate-based comparisons:** `statistical_summary_rate.md`\n")
        f.write("3. **PCA comparisons:** `statistical_summary_pca.md`\n\n")
        
        f.write("---\n\n")
        
        f.write("## Figure Reference Guide\n\n")
        f.write("| Figure File | Analysis Type | Statistics File |\n")
        f.write("|-------------|---------------|------------------|\n")
        f.write("| `figureB_object_*.svg` | Temporal comparison (RMS) | `statistical_summary_amplitude.md` |\n")
        f.write("| `figureB_summary_object_1.svg` | Amplitude summary | `statistical_summary_amplitude.md` |\n")
        f.write("| `figureD_channels_*.svg` | Channel-wise RMS | `statistical_summary_amplitude.md` |\n")
        f.write("| `rate_temporal_comparison_object_*.svg` | Rate-based comparison | `statistical_summary_rate.md` |\n")
        f.write("| `figureC_pca_*.svg` | PCA analysis | `statistical_summary_pca.md` |\n")
        f.write("| `figure_duration_stats.svg` | Task duration | `statistical_summary_rate.md` |\n\n")
        
        f.write("---\n\n")
        f.write("*End of master summary*\n")
    
    print(f"✓ Saved master summary: {report_path}")
    return report_path


if __name__ == '__main__':
    print("="*70)
    print("GENERATING STATISTICAL SUMMARIES")
    print("="*70)
    print()
    
    # Generate all statistical summaries
    amp_path = generate_amplitude_statistics()
    print()
    
    rate_path = generate_rate_statistics()
    print()
    
    pca_path = generate_pca_statistics()
    print()
    
    master_path = generate_master_summary()
    print()
    
    print("="*70)
    print("ALL STATISTICAL SUMMARIES GENERATED")
    print("="*70)
    print("\nGenerated files:")
    print(f"  1. {amp_path.name}")
    print(f"  2. {rate_path.name}")
    print(f"  3. {pca_path.name}")
    print(f"  4. {master_path.name}")
    print("\nThese files contain all statistical tests without cluttering figures.")
    print("="*70)
