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

def cohens_d(group1, group2):
    """Calculate Cohen's d effect size"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
    return (np.mean(group1) - np.mean(group2)) / pooled_std if pooled_std != 0 else 0

def interpret_cohens_d(d):
    """Interpret Cohen's d effect size"""
    d_abs = abs(d)
    if d_abs < 0.2:
        return "negligible"
    elif d_abs < 0.5:
        return "small"
    elif d_abs < 0.8:
        return "medium"
    else:
        return "large"

def test_hypothesis_comprehensive(active_values, other_values, other_name):
    """
    Comprehensive statistical testing with multiple tests
    Returns: dict with all test results
    """
    # 1. Welch's t-test (one-tailed)
    t_stat, p_two = stats.ttest_ind(active_values, other_values, equal_var=False)
    p_welch = p_two / 2 if t_stat < 0 else 1 - (p_two / 2)
    
    # 2. Mann-Whitney U test (non-parametric, one-tailed)
    u_stat, p_mw_two = stats.mannwhitneyu(active_values, other_values, alternative='two-sided')
    _, p_mw_one = stats.mannwhitneyu(active_values, other_values, alternative='less')
    
    # 3. Cohen's d effect size
    cohens = cohens_d(active_values, other_values)
    effect_interpretation = interpret_cohens_d(cohens)
    
    # 4. Descriptive statistics
    mean_active = np.mean(active_values)
    mean_other = np.mean(other_values)
    mean_diff = mean_active - mean_other
    percent_diff = ((mean_active - mean_other) / mean_other) * 100 if mean_other != 0 else 0
    
    # 5. Hypothesis support (both parametric and non-parametric)
    hypothesis_supported_welch = (mean_active < mean_other) and (p_welch < 0.05)
    hypothesis_supported_mw = (mean_active < mean_other) and (p_mw_one < 0.05)
    
    return {
        't_stat': t_stat,
        'p_welch': p_welch,
        'u_stat': u_stat,
        'p_mannwhitney': p_mw_one,
        'cohens_d': cohens,
        'effect_size': effect_interpretation,
        'mean_diff': mean_diff,
        'percent_diff': percent_diff,
        'hypothesis_supported_welch': hypothesis_supported_welch,
        'hypothesis_supported_mw': hypothesis_supported_mw,
        'mean_active': mean_active,
        'mean_other': mean_other
    }

def test_hypothesis_active_lower(active_values, other_values, other_name):
    """
    Test if Active < Other using one-tailed t-test (backward compatibility)
    Returns: (t_stat, p_value, mean_diff, percent_diff, hypothesis_supported)
    """
    results = test_hypothesis_comprehensive(active_values, other_values, other_name)
    return (results['t_stat'], results['p_welch'], results['mean_diff'], 
            results['percent_diff'], results['hypothesis_supported_welch'])


def generate_amplitude_statistics():
    """Generate statistical tests for amplitude (90th percentile RMS) comparisons"""
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data with MVC normalization
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for amplitude statistics")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs, mvc_dict=mvc_dict)
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_amplitude.md'
    
    with open(report_path, 'w') as f:
        f.write("# Comprehensive Statistical Analysis Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1, S2, S5-S10 (8 subjects, balanced 3 sessions per condition per subject)\n\n")
        f.write("**Note:** S7 has 9 sessions (3 no, 3 passive, 3 active) - now fully balanced\n\n")
        f.write("**Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")
            
            # Collect 90th percentile amplitude values per condition
            condition_amplitudes = {}
            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue
                
                amplitude_values = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    # Use 90th percentile instead of mean
                    amplitude = analyzer.compute_percentile_amplitude(segment, percentile=90.0, window_ms=100)
                    amplitude_values.append(amplitude)
                
                condition_amplitudes[condition] = np.array(amplitude_values)
            
            if 'Active glove' not in condition_amplitudes:
                f.write("*No Active glove data available*\n\n")
                continue
            
            # Summary statistics
            f.write("### Summary Statistics\n\n")
            f.write("| Condition | N | Mean (90th %ile) | Std | Min | Max |\n")
            f.write("|-----------|---|------------------|-----|-----|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_amplitudes:
                    vals = condition_amplitudes[condition]
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.2f} | "
                           f"{np.std(vals):.2f} | {np.min(vals):.2f} | {np.max(vals):.2f} |\n")
            f.write("\n")
            
            # Hypothesis testing: Active < Others (COMPREHENSIVE)
            f.write("### Hypothesis Test: Active glove < Other conditions\n\n")
            f.write("#### Parametric Test: Welch's t-test (one-tailed)\n\n")
            f.write("| Comparison | t-stat | p-value | Mean Diff | % Change | Supported? |\n")
            f.write("|------------|--------|---------|-----------|----------|-----------|\n")
            
            active_vals = condition_amplitudes['Active glove']
            comprehensive_results = {}
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_amplitudes:
                    other_vals = condition_amplitudes[other_cond]
                    results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                    comprehensive_results[other_cond] = results
                    
                    support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {results['t_stat']:.3f} | "
                           f"{format_pvalue(results['p_welch'])} | "
                           f"{results['mean_diff']:.2f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")
            
            f.write("\n")
            
            # Non-parametric test
            f.write("#### Non-Parametric Test: Mann-Whitney U (one-tailed)\n\n")
            f.write("| Comparison | U-stat | p-value | Supported? |\n")
            f.write("|------------|--------|---------|------------|\n")
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in comprehensive_results:
                    results = comprehensive_results[other_cond]
                    support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {results['u_stat']:.1f} | "
                           f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")
            
            f.write("\n")
            
            # Effect size
            f.write("#### Effect Size: Cohen's d\n\n")
            f.write("| Comparison | Cohen's d | Interpretation |\n")
            f.write("|------------|-----------|----------------|\n")
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in comprehensive_results:
                    results = comprehensive_results[other_cond]
                    f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | "
                           f"{results['effect_size']} |\n")
            
            f.write("\n")
            
            # ANOVA for 3-way comparison
            if len(condition_amplitudes) == 3:
                f.write("#### ANOVA: Three-way comparison\n\n")
                groups = [condition_amplitudes[c] for c in CONDITIONS if c in condition_amplitudes]
                f_stat, p_anova = stats.f_oneway(*groups)
                f.write(f"**F-statistic:** {f_stat:.3f}  \n")
                f.write(f"**p-value:** {format_pvalue(p_anova)}  \n")
                
                if p_anova < 0.05:
                    f.write("**Interpretation:** Significant difference exists between conditions\n\n")
                else:
                    f.write("**Interpretation:** No significant difference between conditions\n\n")
            
            f.write("---\n\n")
    
    print(f"✓ Saved amplitude statistics: {report_path}")
    return report_path


def generate_activation_statistics():
    """Generate statistical tests for activation-based comparisons (burst frequency)"""
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data with MVC normalization
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for activation statistics")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs, mvc_dict=mvc_dict)
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_activation.md'
    
    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: Activation-Based Comparisons (Burst Frequency)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1, S2, S5-S10 (8 subjects, balanced 3 sessions per condition per subject)\n\n")
        f.write("**Note:** S7 has 8 sessions (3 no, 2 passive, 3 active)\n\n")
        f.write("**Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
        f.write("**Metric:** Muscle burst frequency (activations per second)\n\n")
        f.write("**Rationale:** Burst frequency quantifies how often muscles activate, independent of duration or amplitude. ")
        f.write("This is more physiologically meaningful than dividing amplitude by duration. ")
        f.write("Higher burst frequency indicates more frequent muscle activation events.\n\n")
        f.write("**References:**\n")
        f.write("- Tenan et al. (2017). Muscle onset detection algorithms. *PloS One* 12(5):e0177312.\n")
        f.write("- Konrad (2005). The ABC of EMG. *Noraxon USA Inc*.\n\n")
        f.write("**Related Metrics:**\n")
        f.write("- **Activation Duration:** Proportion of task time with muscle activity above baseline\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")
            
            # Collect burst frequency and activation duration per condition
            condition_burst_freq = {}
            condition_activation_dur = {}
            condition_durations = {}
            
            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue
                
                burst_freqs = []
                activation_durs = []
                durations = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    
                    # Compute burst frequency
                    burst_freq = analyzer.compute_burst_frequency(segment, window_ms=100)
                    burst_freqs.append(burst_freq)
                    
                    # Compute activation duration
                    activation_dur = analyzer.compute_activation_duration(segment, window_ms=100)
                    activation_durs.append(activation_dur)
                    
                    # Record task duration for reference
                    duration = record.end_time - record.start_time
                    durations.append(duration)
                
                condition_burst_freq[condition] = np.array(burst_freqs)
                condition_activation_dur[condition] = np.array(activation_durs)
                condition_durations[condition] = np.array(durations)
            
            if 'Active glove' not in condition_burst_freq:
                f.write("*No Active glove data available*\n\n")
                continue
            
            # Summary statistics for burst frequency
            f.write("### Summary Statistics: Burst Frequency\n\n")
            f.write("| Condition | N | Mean (Hz) | Std | Mean Duration (s) |\n")
            f.write("|-----------|---|-----------|-----|-------------------|\n")
            for condition in CONDITIONS:
                if condition in condition_burst_freq:
                    freqs = condition_burst_freq[condition]
                    durations = condition_durations[condition]
                    f.write(f"| {condition} | {len(freqs)} | {np.mean(freqs):.2f} | "
                           f"{np.std(freqs):.2f} | {np.mean(durations):.2f} |\n")
            f.write("\n")
            
            # Summary statistics for activation duration
            f.write("### Summary Statistics: Activation Duration\n\n")
            f.write("| Condition | N | Mean (proportion) | Std |\n")
            f.write("|-----------|---|-------------------|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_activation_dur:
                    durs = condition_activation_dur[condition]
                    f.write(f"| {condition} | {len(durs)} | {np.mean(durs):.3f} | "
                           f"{np.std(durs):.3f} |\n")
            f.write("\n")
            
            # Hypothesis testing for BURST FREQUENCY: Active < Others (COMPREHENSIVE)
            f.write("### Hypothesis Test (Burst Frequency): Active glove < Other conditions\n\n")
            f.write("#### Parametric Test: Welch's t-test (one-tailed)\n\n")
            f.write("| Comparison | t-stat | p-value | Mean Diff | % Change | Supported? |\n")
            f.write("|------------|--------|---------|-----------|----------|-----------|\n")
            
            active_vals = condition_burst_freq['Active glove']
            comprehensive_results = {}
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_burst_freq:
                    other_vals = condition_burst_freq[other_cond]
                    results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                    comprehensive_results[other_cond] = results
                    
                    support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {results['t_stat']:.3f} | "
                           f"{format_pvalue(results['p_welch'])} | "
                           f"{results['mean_diff']:.2f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")
            
            f.write("\n")
            
            # Non-parametric test
            f.write("#### Non-Parametric Test: Mann-Whitney U (one-tailed)\n\n")
            f.write("| Comparison | U-stat | p-value | Supported? |\n")
            f.write("|------------|--------|---------|------------|\n")
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in comprehensive_results:
                    results = comprehensive_results[other_cond]
                    support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {results['u_stat']:.1f} | "
                           f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")
            
            f.write("\n")
            
            # Effect size
            f.write("#### Effect Size: Cohen's d\n\n")
            f.write("| Comparison | Cohen's d | Interpretation |\n")
            f.write("|------------|-----------|----------------|\n")
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in comprehensive_results:
                    results = comprehensive_results[other_cond]
                    f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | "
                           f"{results['effect_size']} |\n")
            
            f.write("\n")
            
            # ANOVA for 3-way comparison (burst frequency)
            if len(condition_burst_freq) == 3:
                f.write("#### ANOVA: Three-way comparison (Burst Frequency)\n\n")
                groups = [condition_burst_freq[c] for c in CONDITIONS if c in condition_burst_freq]
                f_stat, p_anova = stats.f_oneway(*groups)
                f.write(f"**F-statistic:** {f_stat:.3f}  \n")
                f.write(f"**p-value:** {format_pvalue(p_anova)}  \n")
                
                if p_anova < 0.05:
                    f.write("**Interpretation:** Significant difference exists between conditions\n\n")
                else:
                    f.write("**Interpretation:** No significant difference between conditions\n\n")
            
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
    """Generate statistical tests for PCA analysis with feature-based approach"""
    
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)
    
    # Load data with MVC normalization
    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for PCA statistics")
        return
    
    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs, mvc_dict=mvc_dict)
    
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_pca.md'
    
    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: PCA Feature-Based Comparisons\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1, S2, S5-S10 (8 subjects, balanced 3 sessions per condition per subject)\n\n")
        f.write("**Note:** S7 has 8 sessions (3 no, 2 passive, 3 active)\n\n")
        f.write("**Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
        f.write("**Metric:** PCA on temporal features (duration-independent)\n\n")
        f.write("**Rationale:** Each segment contributes equally to PCA (one feature vector per segment) ")
        f.write("regardless of duration. This removes sample size bias where longer tasks would dominate principal components.\n\n")
        f.write("**Features per segment:**\n")
        f.write("- Per-channel statistics: mean, std, 90th percentile, peak amplitude\n")
        f.write("- Global statistics: mean/std/percentile/peak across channels\n")
        f.write("- Temporal metrics: activation duration, burst frequency\n")
        f.write("- Cross-channel coordination: mean correlation\n\n")
        f.write("**References:**\n")
        f.write("- Phinyomark et al. (2012). Feature extraction for EMG classification. *Expert Syst Appl* 39(8):7420-7431.\n\n")
        f.write("**Related Figures:**\n")
        f.write("- `figureC_pca_single_objects_1.svg`\n")
        f.write("- `figureC_pca_all_objects_0_1_2_3_4_5.svg`\n")
        f.write("- `figureC_pca_object_*.svg` (per-object PCA)\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")
            
            # Collect temporal features for PCA (equal samples per segment)
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
                    # Extract temporal features: 1 row per segment (duration-independent)
                    features = analyzer.extract_temporal_features(segment, window_ms=100)
                    features_list.append(features)
                
                condition_features[condition] = np.array(features_list)
            
            if len(condition_features) < 2:
                f.write("*Insufficient data for PCA analysis*\n\n")
                continue
            
            # Perform PCA with StandardScaler
            all_features = np.vstack([condition_features[c] for c in CONDITIONS if c in condition_features])
            scaler = StandardScaler()
            all_features_scaled = scaler.fit_transform(all_features)
            
            pca = PCA(n_components=2)
            pca.fit(all_features_scaled)
            
            f.write(f"### PCA Results\n\n")
            f.write(f"- **Explained variance:** PC1={pca.explained_variance_ratio_[0]*100:.1f}%, ")
            f.write(f"PC2={pca.explained_variance_ratio_[1]*100:.1f}%\n")
            f.write(f"- **Total variance explained:** {(pca.explained_variance_ratio_[0] + pca.explained_variance_ratio_[1])*100:.1f}%\n\n")
            
            # Transform and compute PC values and magnitudes
            condition_magnitudes = {}
            condition_pc1 = {}
            condition_pc2 = {}
            
            for condition in CONDITIONS:
                if condition in condition_features:
                    # Scale and transform
                    scaled = scaler.transform(condition_features[condition])
                    transformed = pca.transform(scaled)
                    condition_pc1[condition] = np.abs(transformed[:, 0])  # Use absolute for magnitude
                    condition_pc2[condition] = np.abs(transformed[:, 1])
                    magnitudes = np.sqrt(transformed[:, 0]**2 + transformed[:, 1]**2)
                    condition_magnitudes[condition] = magnitudes
            
            # Summary statistics for PC1
            f.write("### PC1 Values (Absolute)\n\n")
            f.write("| Condition | N | Mean PC1 | Std |\n")
            f.write("|-----------|---|----------|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_pc1:
                    vals = condition_pc1[condition]
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.3f} | {np.std(vals):.3f} |\n")
            f.write("\n")
            
            # Hypothesis testing for PC1 (COMPREHENSIVE)
            if 'Active glove' in condition_pc1:
                f.write("**PC1 Hypothesis Test: Active glove < Others**\n\n")
                f.write("##### Welch's t-test (one-tailed)\n\n")
                f.write("| Comparison | t-stat | p-value | Mean Diff | % Change | Supported? |\n")
                f.write("|------------|--------|---------|-----------|----------|-----------|\n")
                
                active_pc1 = condition_pc1['Active glove']
                pc1_results = {}
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in condition_pc1:
                        other_pc1 = condition_pc1[other_cond]
                        results = test_hypothesis_comprehensive(active_pc1, other_pc1, other_cond)
                        pc1_results[other_cond] = results
                        
                        support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")
                
                f.write("\n")
                
                # Non-parametric for PC1
                f.write("##### Mann-Whitney U (one-tailed)\n\n")
                f.write("| Comparison | U-stat | p-value | Supported? |\n")
                f.write("|------------|--------|---------|------------|\n")
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc1_results:
                        results = pc1_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")
                
                f.write("\n")
                
                # Effect size for PC1
                f.write("##### Cohen's d\n\n")
                f.write("| Comparison | Cohen's d | Interpretation |\n")
                f.write("|------------|-----------|----------------|\n")
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc1_results:
                        results = pc1_results[other_cond]
                        f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | "
                               f"{results['effect_size']} |\n")
                
                f.write("\n")
            
            # Summary statistics for PC2
            f.write("### PC2 Values\n\n")
            f.write("| Condition | N | Mean PC2 | Std |\n")
            f.write("|-----------|---|----------|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_pc2:
                    vals = condition_pc2[condition]
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.3f} | {np.std(vals):.3f} |\n")
            f.write("\n")
            
            # Hypothesis testing for PC2 (COMPREHENSIVE)
            if 'Active glove' in condition_pc2:
                f.write("**PC2 Hypothesis Test: Active glove < Others**\n\n")
                f.write("##### Welch's t-test (one-tailed, absolute values)\n\n")
                f.write("| Comparison | t-stat | p-value | Mean Diff | % Change | Supported? |\n")
                f.write("|------------|--------|---------|-----------|----------|-----------|\n")
                
                active_pc2 = condition_pc2['Active glove']
                pc2_results = {}
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in condition_pc2:
                        other_pc2 = condition_pc2[other_cond]
                        results = test_hypothesis_comprehensive(np.abs(active_pc2), np.abs(other_pc2), other_cond)
                        pc2_results[other_cond] = results
                        
                        support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} (abs) | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")
                
                f.write("\n")
                
                # Non-parametric for PC2
                f.write("##### Mann-Whitney U (one-tailed, absolute values)\n\n")
                f.write("| Comparison | U-stat | p-value | Supported? |\n")
                f.write("|------------|--------|---------|------------|\n")
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc2_results:
                        results = pc2_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")
                
                f.write("\n")
                
                # Effect size for PC2
                f.write("##### Cohen's d\n\n")
                f.write("| Comparison | Cohen's d | Interpretation |\n")
                f.write("|------------|-----------|----------------|\n")
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc2_results:
                        results = pc2_results[other_cond]
                        f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | "
                               f"{results['effect_size']} |\n")
                
                f.write("\n")
            
            # Summary statistics for magnitude
            f.write("### PCA Magnitude Statistics\n\n")
            f.write("| Condition | N | Mean Magnitude | Std |\n")
            f.write("|-----------|---|----------------|-----|\n")
            for condition in CONDITIONS:
                if condition in condition_magnitudes:
                    mags = condition_magnitudes[condition]
                    f.write(f"| {condition} | {len(mags)} | {np.mean(mags):.3f} | {np.std(mags):.3f} |\n")
            f.write("\n")
            
            # Hypothesis testing for magnitude (COMPREHENSIVE)
            if 'Active glove' in condition_magnitudes:
                f.write("### Hypothesis Test: Active glove magnitude < Others\n\n")
                f.write("#### Parametric Test: Welch's t-test (one-tailed)\n\n")
                f.write("| Comparison | t-stat | p-value | Mean Diff | % Change | Supported? |\n")
                f.write("|------------|--------|---------|-----------|----------|-----------|\n")
                
                active_mags = condition_magnitudes['Active glove']
                mag_results = {}
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in condition_magnitudes:
                        other_mags = condition_magnitudes[other_cond]
                        results = test_hypothesis_comprehensive(active_mags, other_mags, other_cond)
                        mag_results[other_cond] = results
                        
                        support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")
                
                f.write("\n")
                
                # Non-parametric test
                f.write("#### Non-Parametric Test: Mann-Whitney U (one-tailed)\n\n")
                f.write("| Comparison | U-stat | p-value | Supported? |\n")
                f.write("|------------|--------|---------|------------|\n")
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in mag_results:
                        results = mag_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")
                
                f.write("\n")
                
                # Effect size
                f.write("#### Effect Size: Cohen's d\n\n")
                f.write("| Comparison | Cohen's d | Interpretation |\n")
                f.write("|------------|-----------|----------------|\n")
                
                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in mag_results:
                        results = mag_results[other_cond]
                        f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | "
                               f"{results['effect_size']} |\n")
                
                f.write("\n")
                
                # ANOVA for 3-way comparison
                if len(condition_magnitudes) == 3:
                    f.write("#### ANOVA: Three-way comparison\n\n")
                    groups = [condition_magnitudes[c] for c in CONDITIONS if c in condition_magnitudes]
                    f_stat, p_anova = stats.f_oneway(*groups)
                    f.write(f"**F-statistic:** {f_stat:.3f}  \n")
                    f.write(f"**p-value:** {format_pvalue(p_anova)}  \n")
                    
                    if p_anova < 0.05:
                        f.write("**Interpretation:** Significant difference exists between conditions\n\n")
                    else:
                        f.write("**Interpretation:** No significant difference between conditions\n\n")
            
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
        f.write("**Dataset:** S1, S2, S5-S10 (8 subjects, balanced 3 sessions per condition per subject)\n")
        f.write("- 70 sessions total: S7 has 8 sessions (3 no, 2 passive, 3 active), all others have 9 sessions\n")
        f.write("- **Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
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
        
        f.write("### Comprehensive Testing Suite\n\n")
        f.write("Each comparison uses multiple statistical tests:\n\n")
        
        f.write("#### 1. Parametric Test: Welch's t-test\n")
        f.write("- **Type:** Independent samples t-test (one-tailed)\n")
        f.write("- **Assumption:** Does not assume equal variances\n")
        f.write("- **H₀:** Active glove ≥ Other condition\n")
        f.write("- **H₁:** Active glove < Other condition\n")
        f.write("- **Use:** Primary hypothesis test\n\n")
        
        f.write("#### 2. Non-Parametric Test: Mann-Whitney U\n")
        f.write("- **Type:** Rank-based test (one-tailed)\n")
        f.write("- **Assumption:** Distribution-free\n")
        f.write("- **Use:** Validate parametric results, robust to outliers\n\n")
        
        f.write("#### 3. Effect Size: Cohen's d\n")
        f.write("- **Metric:** Standardized mean difference\n")
        f.write("- **Interpretation:**\n")
        f.write("  - |d| < 0.2: negligible effect\n")
        f.write("  - |d| < 0.5: small effect\n")
        f.write("  - |d| < 0.8: medium effect\n")
        f.write("  - |d| ≥ 0.8: large effect\n\n")
        
        f.write("#### 4. ANOVA: Three-way comparison\n")
        f.write("- **Type:** One-way ANOVA\n")
        f.write("- **Use:** Test if any significant difference exists between all three conditions\n")
        f.write("- **Note:** Omnibus test, followed by pairwise comparisons\n\n")
        
        f.write("### Multiple Comparisons\n\n")
        f.write("**Bonferroni Correction:**\n")
        f.write("- Number of objects tested: 6 (Objects 0-5)\n")
        f.write("- Comparisons per object: 2 (Active vs Passive, Active vs No)\n")
        f.write("- Total comparisons: 12\n")
        f.write("- Adjusted significance level: α_adjusted = 0.05/12 ≈ 0.004\n")
        f.write("- **Note:** Results marked with standard α = 0.05, but Bonferroni adjustment available\n\n")
        
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
    
    activation_path = generate_activation_statistics()
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
    print(f"  2. {activation_path.name}")
    print(f"  3. {pca_path.name}")
    print(f"  4. {master_path.name}")
    print("\nThese files contain all statistical tests without cluttering figures.")
    print("="*70)
