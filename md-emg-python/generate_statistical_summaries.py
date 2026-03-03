"""
Generate statistical test summaries for all EMG analyses
Saves results to markdown files with references to figure files
"""
import numpy as np
from collections import defaultdict
import pandas as pd
from pathlib import Path
from scipy import stats
from emg_comparative_analysis import load_real_data, EMGDataLoader, EMGAnalyzer
from datetime import datetime

CONDITIONS = ['Passive glove', 'Active glove', 'No glove']

def format_pvalue(p):
    """Format p-value with significance stars"""
    if np.isnan(p):
        return "- ns"
    if p < 0.001:
        return f"{p:.4f} ***"
    elif p < 0.01:
        return f"{p:.4f} **"
    elif p < 0.05:
        return f"{p:.4f} *"
    else:
        return f"{p:.4f} ns"


def test_normality(values, name=""):
    """
    Test normality using Shapiro-Wilk test.
    Returns: (W-statistic, p-value, is_normal)
    Note: Shapiro-Wilk is suitable for small samples (n < 50)
    """
    if len(values) < 3:
        return np.nan, np.nan, False
    try:
        w_stat, p_value = stats.shapiro(values)
        is_normal = p_value >= 0.05  # Fail to reject H0 => normal
        return w_stat, p_value, is_normal
    except Exception:
        return np.nan, np.nan, False


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

    # 3. Wilcoxon signed-rank (paired, one-tailed: Active < Other)
    w_stat = np.nan
    p_wilcoxon = np.nan
    min_len = min(len(active_values), len(other_values))
    if min_len > 0:
        try:
            w_stat, p_wilcoxon = stats.wilcoxon(
                active_values[:min_len],
                other_values[:min_len],
                alternative='less'
            )
        except ValueError:
            p_wilcoxon = np.nan
    
    # 4. Cohen's d effect size
    cohens = cohens_d(active_values, other_values)
    effect_interpretation = interpret_cohens_d(cohens)
    
    # 5. Descriptive statistics (mean as primary, median alongside)
    mean_active = np.mean(active_values)
    mean_other = np.mean(other_values)
    mean_diff = mean_active - mean_other
    percent_diff = ((mean_active - mean_other) / mean_other) * 100 if mean_other != 0 else 0
    # % Reduction: (other - active) / other * 100  (positive = active is lower)
    percent_reduction = ((mean_other - mean_active) / mean_other) * 100 if mean_other != 0 else 0
    
    # Also compute median for reporting alongside
    median_active = np.median(active_values)
    median_other = np.median(other_values)
    median_diff = median_active - median_other
    median_percent_diff = ((median_active - median_other) / median_other) * 100 if median_other != 0 else 0
    median_percent_reduction = ((median_other - median_active) / median_other) * 100 if median_other != 0 else 0
    
    # 6. Hypothesis support (use mean for direction)
    hypothesis_supported_welch = (mean_active < mean_other) and (p_welch < 0.05)
    hypothesis_supported_mw = (mean_active < mean_other) and (p_mw_one < 0.05)
    hypothesis_supported_wilcoxon = (mean_active < mean_other) and (p_wilcoxon < 0.05)
    
    return {
        't_stat': t_stat,
        'p_welch': p_welch,
        'u_stat': u_stat,
        'p_mannwhitney': p_mw_one,
        'w_stat': w_stat,
        'p_wilcoxon': p_wilcoxon,
        'cohens_d': cohens,
        'effect_size': effect_interpretation,
        'mean_diff': mean_diff,
        'median_diff': median_diff,
        'percent_diff': percent_diff,
        'median_percent_diff': median_percent_diff,
        'percent_reduction': percent_reduction,
        'median_percent_reduction': median_percent_reduction,
        'hypothesis_supported_welch': hypothesis_supported_welch,
        'hypothesis_supported_mw': hypothesis_supported_mw,
        'hypothesis_supported_wilcoxon': hypothesis_supported_wilcoxon,
        'mean_active': mean_active,
        'mean_other': mean_other,
        'median_active': median_active,
        'median_other': median_other
    }

def test_hypothesis_active_lower(active_values, other_values, other_name):
    """
    Test if Active < Other using one-tailed t-test (backward compatibility)
    Returns: (t_stat, p_value, median_diff, percent_diff, hypothesis_supported)
    """
    results = test_hypothesis_comprehensive(active_values, other_values, other_name)
    return (results['t_stat'], results['p_welch'], results['mean_diff'], 
            results['percent_diff'], results['hypothesis_supported_welch'])


def test_pairwise_comparison(group1_values, group2_values, group1_name, group2_name):
    """
    Pairwise comparison between any two groups (two-tailed tests)
    Returns: dict with all test results
    """
    # 1. Welch's t-test (two-tailed)
    t_stat, p_welch = stats.ttest_ind(group1_values, group2_values, equal_var=False)
    
    # 2. Mann-Whitney U test (non-parametric, two-tailed)
    u_stat, p_mw = stats.mannwhitneyu(group1_values, group2_values, alternative='two-sided')

    # 3. Wilcoxon signed-rank (paired, two-tailed)
    w_stat = np.nan
    p_wilcoxon = np.nan
    min_len = min(len(group1_values), len(group2_values))
    if min_len > 0:
        try:
            w_stat, p_wilcoxon = stats.wilcoxon(
                group1_values[:min_len],
                group2_values[:min_len],
                alternative='two-sided'
            )
        except ValueError:
            p_wilcoxon = np.nan
    
    # 4. Cohen's d effect size
    cohens = cohens_d(group1_values, group2_values)
    effect_interpretation = interpret_cohens_d(cohens)
    
    # 5. Descriptive statistics (mean as primary, median alongside)
    mean_group1 = np.mean(group1_values)
    mean_group2 = np.mean(group2_values)
    mean_diff = mean_group1 - mean_group2
    percent_diff = ((mean_group1 - mean_group2) / mean_group2) * 100 if mean_group2 != 0 else 0
    # % Reduction: (cond1 - cond2) / cond1 * 100  (positive = cond2 is lower)
    percent_reduction = ((mean_group1 - mean_group2) / mean_group1) * 100 if mean_group1 != 0 else 0
    
    # Also compute median for reporting alongside
    median_group1 = np.median(group1_values)
    median_group2 = np.median(group2_values)
    median_diff = median_group1 - median_group2
    median_percent_diff = ((median_group1 - median_group2) / median_group2) * 100 if median_group2 != 0 else 0
    median_percent_reduction = ((median_group1 - median_group2) / median_group1) * 100 if median_group1 != 0 else 0
    
    # Also compute median for reporting alongside
    median_group1 = np.median(group1_values)
    median_group2 = np.median(group2_values)
    median_diff = median_group1 - median_group2
    median_percent_diff = ((median_group1 - median_group2) / median_group2) * 100 if median_group2 != 0 else 0
    
    # 6. Significance (two-tailed)
    is_significant_welch = p_welch < 0.05
    is_significant_mw = p_mw < 0.05
    is_significant_wilcoxon = p_wilcoxon < 0.05
    
    return {
        't_stat': t_stat,
        'p_welch': p_welch,
        'u_stat': u_stat,
        'p_mannwhitney': p_mw,
        'w_stat': w_stat,
        'p_wilcoxon': p_wilcoxon,
        'cohens_d': cohens,
        'effect_size': effect_interpretation,
        'mean_diff': mean_diff,
        'median_diff': median_diff,
        'percent_diff': percent_diff,
        'median_percent_diff': median_percent_diff,
        'percent_reduction': percent_reduction,
        'median_percent_reduction': median_percent_reduction,
        'is_significant_welch': is_significant_welch,
        'is_significant_mw': is_significant_mw,
        'is_significant_wilcoxon': is_significant_wilcoxon,
        'mean_group1': mean_group1,
        'mean_group2': mean_group2,
        'median_group1': median_group1,
        'median_group2': median_group2,
        'group1_name': group1_name,
        'group2_name': group2_name
    }


def collect_subject_level_metric(data_dict, analyzer, object_ids, metric):
    """Build subject-level means for a metric across objects and conditions.

    Supported metrics:
    - duration: segment duration in seconds
    - mvc: mean RMS (%MVC)
    - amplitude: 90th percentile RMS across channels (%MVC)
    - rate: amplitude per second (amplitude / duration)

    Returns (subject_means, rows_df) where subject_means[condition][obj][subject] = mean_value.
    """
    subject_means = defaultdict(lambda: defaultdict(dict))
    subject_medians = defaultdict(lambda: defaultdict(dict))
    rows = []

    for condition in CONDITIONS:
        if condition not in data_dict:
            continue
        for obj_id in object_ids:
            if obj_id not in data_dict[condition]:
                continue

            per_subject = defaultdict(list)
            for record in data_dict[condition][obj_id]:
                if metric == 'duration':
                    value = analyzer._segment_duration(record)
                elif metric == 'mvc':
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    value = float(np.mean(rms))
                elif metric in ('amplitude', 'rate'):
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    percentile_per_channel = np.percentile(rms, 90.0, axis=0)
                    amplitude = float(np.mean(percentile_per_channel))
                    if metric == 'rate':
                        duration = analyzer._segment_duration(record)
                        value = amplitude / duration if duration > 0 else 0.0
                    else:
                        value = amplitude
                else:
                    continue

                per_subject[record.subject].append(value)

            for subject, values in per_subject.items():
                mean_val = float(np.mean(values))
                median_val = float(np.median(values))
                subject_means[condition][obj_id][subject] = mean_val
                subject_medians[condition][obj_id][subject] = median_val
                rows.append({
                    'Condition': condition,
                    'Object': obj_id,
                    'Subject': subject,
                    'Value': mean_val,
                    'Value_median': median_val
                })

    return subject_means, subject_medians, pd.DataFrame(rows)


def build_paired_lists(active_map, other_map):
    """Align subject-level values for paired tests."""
    shared = sorted(set(active_map.keys()) & set(other_map.keys()))
    active_vals = [active_map[s] for s in shared]
    other_vals = [other_map[s] for s in shared]
    return active_vals, other_vals, shared


def compute_requested_reduction(values_a, values_b, cond_a, cond_b, use_median=True):
    """Compute requested pairwise % reduction for specific condition pairs.

    Requested formulations:
    - (No glove - Active glove) / No glove
    - (Passive glove - Active glove) / Passive glove
    - (No glove - Passive glove) / No glove

    Fallback for any other pair:
    - (cond_a - cond_b) / cond_a
    """
    agg = np.median if use_median else np.mean
    val_a = float(agg(values_a))
    val_b = float(agg(values_b))

    pair = {cond_a, cond_b}
    if pair == {'No glove', 'Active glove'}:
        baseline = 'No glove'
        target = 'Active glove'
    elif pair == {'Passive glove', 'Active glove'}:
        baseline = 'Passive glove'
        target = 'Active glove'
    elif pair == {'No glove', 'Passive glove'}:
        baseline = 'No glove'
        target = 'Passive glove'
    else:
        baseline = cond_a
        target = cond_b

    baseline_val = val_a if cond_a == baseline else val_b
    target_val = val_a if cond_a == target else val_b

    return ((baseline_val - target_val) / baseline_val) * 100 if baseline_val != 0 else 0.0


def write_median_aggregated_tests(f, condition_subject_medians, comparison_pairs, CONDITIONS, one_tailed=True, direction='less'):
    """Write a section showing statistical tests run on subject-level MEDIANS.
    
    This complements the main tests (run on subject-level means) by also running
    the same tests on subject-level medians, giving two perspectives.
    
    Args:
        f: file handle for writing
        condition_subject_medians: dict of {condition: {subject: median_value}} or
                                  {condition: {obj_id: {subject: median_value}}}
        comparison_pairs: list of (cond1, cond2) tuples
        CONDITIONS: list of condition names
        one_tailed: if True, write one-tailed hypothesis section
        direction: 'less' for Active < Other, 'greater' for Active > Other
    """
    f.write("### Statistical Tests on Subject-Level Medians\n\n")
    f.write("*Same tests as above, but each subject's value is their **median** across sessions (instead of mean).*\n\n")
    
    if one_tailed and 'Active glove' in condition_subject_medians:
        active_median_map = condition_subject_medians['Active glove']

        if direction == 'less':
            hyp_text = "Active glove < Other"
        else:
            hyp_text = "Active glove > Other"

        f.write(f"#### Hypothesis: {hyp_text} (subject-paired, median-aggregated)\n\n")
        f.write("| Comparison | Subjects | t-stat | p (Welch) | U | p (MW) | W | p (Wilcoxon) | % Reduction | Supported? (Wilcoxon) |\n")
        f.write("|------------|----------|--------|-----------|---|--------|---|--------------|-------------|------------------------|\n")

        for other_cond in ['Passive glove', 'No glove']:
            if other_cond not in condition_subject_medians:
                f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - | - | - | - |\n")
                continue
            active_vals, other_vals, shared = build_paired_lists(active_median_map, condition_subject_medians[other_cond])
            if not shared:
                f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - | - | - | - |\n")
                continue

            if direction == 'less':
                results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
            else:
                # Swap args: test_hypothesis_comprehensive tests arg1 < arg2
                # So passing (other, active) tests other < active ≡ active > other
                results = test_hypothesis_comprehensive(other_vals, active_vals, other_cond)

            support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"
            f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | {format_pvalue(results['p_welch'])} | "
                    f"{results['u_stat']:.1f} | {format_pvalue(results['p_mannwhitney'])} | "
                    f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | "
                    f"{results['percent_reduction']:+.1f}% | **{support_text}** |\n")
        f.write("\n")

    # Pairwise two-tailed
    f.write("#### Pairwise Comparisons (two-tailed, median-aggregated)\n\n")
    f.write("| Comparison | Subjects | t-stat | p (Welch) | W | p (Wilcoxon) | Mean Diff | Median Diff | % Reduction | Significant? (Wilcoxon) |\n")
    f.write("|------------|----------|--------|-----------|---|--------------|-----------|-------------|-------------|-------------------------|\n")
    for cond1, cond2 in comparison_pairs:
        if cond1 in condition_subject_medians and cond2 in condition_subject_medians:
            vals1, vals2, shared = build_paired_lists(condition_subject_medians[cond1], condition_subject_medians[cond2])
            if not shared:
                continue
            results = test_pairwise_comparison(vals1, vals2, cond1, cond2)
            sig_text = "✓ YES" if results['is_significant_wilcoxon'] else "✗ NO"
            f.write(f"| {cond1} vs {cond2} | {len(shared)} | {results['t_stat']:.3f} | "
                   f"{format_pvalue(results['p_welch'])} | "
                   f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | "
                   f"{results['mean_diff']:.3f} | {results['median_diff']:.3f} | "
                   f"{results['percent_reduction']:+.1f}% | **{sig_text}** |\n")
    f.write("\n")


def generate_amplitude_statistics():
    """Generate subject-level paired statistics for amplitude (90th percentile RMS)."""
    
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
    
    # Collect session-level values for CSV export and subject-level means for paired tests
    csv_data = []
    subject_rows = []
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_amplitude.md'
    
    with open(report_path, 'w') as f:
        f.write("# Comprehensive Statistical Analysis Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1–S10 (10 subjects, balanced 3 sessions per condition per subject)\n\n")
        f.write("**Note:** S7 has 9 sessions (3 no, 3 passive, 3 active) - now fully balanced\n\n")
        f.write("**Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")

            condition_subject_means = {}
            condition_subject_medians = {}

            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue

                per_subject = defaultdict(list)
                session_values = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    percentile_per_channel = np.percentile(rms, 90.0, axis=0)
                    amplitude = float(np.mean(percentile_per_channel))

                    per_subject[record.subject].append(amplitude)
                    session_values.append(amplitude)

                    csv_data.append({
                        'metric': 'amplitude',
                        'object': obj_id,
                        'condition': condition,
                        'subject': record.subject,
                        'session': record.session,
                        'value': amplitude,
                        'duration': record.end_time - record.start_time
                    })

                subj_mean_map = {subj: float(np.mean(vals)) for subj, vals in per_subject.items()}
                subj_median_map = {subj: float(np.median(vals)) for subj, vals in per_subject.items()}
                condition_subject_means[condition] = subj_mean_map
                condition_subject_medians[condition] = subj_median_map

                for subject, mean_val in subj_mean_map.items():
                    subject_rows.append({
                        'Condition': condition,
                        'Object': obj_id,
                        'Subject': subject,
                        'Amplitude (%MVC)': mean_val
                    })

            if 'Active glove' not in condition_subject_means:
                f.write("*No Active glove data available*\n\n")
                continue

            # Summary statistics (subject means)
            f.write("### Summary Statistics (subject means)\n\n")
            f.write("| Condition | Subjects | Mean (90th %ile) | Median (90th %ile) | Std | Min | Max |\n")
            f.write("|-----------|----------|--------------------|--------------------|-----|-----|-----|\n")
            for condition in CONDITIONS:
                subj_map = condition_subject_means.get(condition, {})
                vals = list(subj_map.values())
                if vals:
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.2f} | {np.median(vals):.2f} | "
                           f"{np.std(vals, ddof=1):.2f} | {np.min(vals):.2f} | {np.max(vals):.2f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - | - | - |\n")
            f.write("\n")

            active_map = condition_subject_means.get('Active glove', {})
            if not active_map:
                f.write("No Active glove data for this object.\n\n")
                continue

            f.write("### Hypothesis: Active glove < Other (subject-paired)\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p (Welch, one-tail) | U | p (MW, one-tail) | W | p (Wilcoxon, one-tail) | Supported? (Wilcoxon) |\n")
            f.write("|------------|-------------------|--------|---------------------|---|-------------------|---|------------------------|------------------------|\n")

            for other_cond in ['Passive glove', 'No glove']:
                if other_cond not in condition_subject_means:
                    f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                other_map = condition_subject_means[other_cond]
                active_vals, other_vals, shared = build_paired_lists(active_map, other_map)

                if len(shared) == 0:
                    f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"

                f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | {format_pvalue(results['p_welch'])} | "
                        f"{results['u_stat']:.1f} | {format_pvalue(results['p_mannwhitney'])} | "
                        f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | **{support_text}** |\n")

            f.write("\n")

            # Effect size on subject means
            f.write("#### Effect Size: Cohen's d (subject means)\n\n")
            f.write("| Comparison | Cohen's d | Interpretation |\n")
            f.write("|------------|-----------|----------------|\n")

            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_subject_means:
                    other_map = condition_subject_means[other_cond]
                    active_vals, other_vals, shared = build_paired_lists(active_map, other_map)
                    if not shared:
                        f.write(f"| Active vs {other_cond} | - | - |\n")
                        continue
                    results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                    f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | {results['effect_size']} |\n")

            f.write("\n")

            # ALL PAIRWISE COMPARISONS (two-tailed tests, subject-paired)
            f.write("### All Pairwise Comparisons (Two-tailed, subject-paired)\n\n")
            f.write("Comparing all condition pairs using subject-matched means.\n\n")

            comparison_pairs = [
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove'),
                ('Active glove', 'Passive glove')
            ]

            pairwise_results = {}

            f.write("#### Parametric Test: Welch's t-test (two-tailed)\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p-value | Mean Diff | Median Diff | % Change | Significant? |\n")
            f.write("|------------|-------------------|--------|---------|-----------|-------------|----------|--------------|\n")

            for cond1, cond2 in comparison_pairs:
                if cond1 in condition_subject_means and cond2 in condition_subject_means:
                    vals1, vals2, shared = build_paired_lists(condition_subject_means[cond1], condition_subject_means[cond2])
                    if not shared:
                        continue
                    results = test_pairwise_comparison(vals1, vals2, cond1, cond2)
                    pairwise_results[(cond1, cond2)] = (results, len(shared))

                    sig_text = "✓ YES" if results['is_significant_welch'] else "✗ NO"
                    f.write(f"| {cond1} vs {cond2} | {len(shared)} | {results['t_stat']:.3f} | "
                           f"{format_pvalue(results['p_welch'])} | "
                           f"{results['mean_diff']:.2f} | {results['median_diff']:.2f} | {results['percent_diff']:+.1f}% | **{sig_text}** |\n")

            f.write("\n")

            f.write("#### Non-Parametric Test: Mann-Whitney U (two-tailed)\n\n")
            f.write("| Comparison | Subjects (paired) | U-stat | p-value | Significant? |\n")
            f.write("|------------|-------------------|--------|---------|---------------|\n")

            for cond1, cond2 in comparison_pairs:
                if (cond1, cond2) in pairwise_results:
                    results, n_shared = pairwise_results[(cond1, cond2)]
                    sig_text = "✓ YES" if results['is_significant_mw'] else "✗ NO"
                    f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['u_stat']:.1f} | "
                           f"{format_pvalue(results['p_mannwhitney'])} | **{sig_text}** |\n")

            f.write("\n")

            f.write("#### Paired Non-Parametric Test: Wilcoxon signed-rank (two-tailed)\n\n")
            f.write("| Comparison | Subjects (paired) | W-stat | p-value | Significant? |\n")
            f.write("|------------|-------------------|--------|---------|---------------|\n")

            for cond1, cond2 in comparison_pairs:
                if (cond1, cond2) in pairwise_results:
                    results, n_shared = pairwise_results[(cond1, cond2)]
                    sig_text = "✓ YES" if results['is_significant_wilcoxon'] else "✗ NO"
                    f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['w_stat']:.1f} | "
                           f"{format_pvalue(results['p_wilcoxon'])} | **{sig_text}** |\n")

            f.write("\n")

            f.write("#### Effect Size: Cohen's d\n\n")
            f.write("| Comparison | Subjects (paired) | Cohen's d | Interpretation | Direction |\n")
            f.write("|------------|-------------------|-----------|----------------|------------|\n")

            for cond1, cond2 in comparison_pairs:
                if (cond1, cond2) in pairwise_results:
                    results, n_shared = pairwise_results[(cond1, cond2)]
                    direction = f"{cond1} > {cond2}" if results['mean_diff'] > 0 else f"{cond1} < {cond2}"
                    f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['cohens_d']:.3f} | "
                           f"{results['effect_size']} | {direction} |\n")

            f.write("\n")

            # === Tests on subject-level medians ===
            write_median_aggregated_tests(f, condition_subject_medians, comparison_pairs, CONDITIONS, one_tailed=True)

            f.write("---\n\n")
    
    # Export amplitude values to CSV
    import pandas as pd
    csv_path = results_dir / 'amplitude_values.csv'
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_path, index=False)
    print(f"✓ Saved amplitude values CSV: {csv_path}")

    subject_csv_path = results_dir / 'amplitude_subject_means.csv'
    df_subject = pd.DataFrame(subject_rows)
    if not df_subject.empty:
        df_subject.to_csv(subject_csv_path, index=False)
        print(f"✓ Saved amplitude subject means CSV: {subject_csv_path}")
    
    print(f"✓ Saved amplitude statistics: {report_path}")
    return report_path


def generate_activation_statistics():
    """Generate subject-level paired statistics for rate-based comparisons (amplitude / duration)."""
    
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
    
    # Collect session-level values for CSV export and subject-level means for paired tests
    csv_data = []
    subject_rows = []
    
    # Create markdown report
    report_path = results_dir / 'statistical_summary_activation.md'
    
    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: Rate-Based Comparisons (Amplitude per Second)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1–S10 (10 subjects, balanced 3 sessions per condition per subject)\n\n")
        f.write("**Note:** S7 has 8 sessions (3 no, 2 passive, 3 active)\n\n")
        f.write("**Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
        f.write("**Metric:** RMS amplitude per second (amplitude / task_duration)\n\n")
        f.write("**Rationale:** Normalizes by task duration to account for speed differences. ")
        f.write("Active tasks take longer but we want to know if the intensity per unit time is lower.\n\n")
        f.write("---\n\n")
        
        # Test for each object
        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")

            condition_rate_means = {}
            condition_rate_medians = {}
            condition_duration_means = {}

            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue

                per_subject_rates = defaultdict(list)
                per_subject_durations = defaultdict(list)

                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    rms = analyzer.compute_rms(segment, window_ms=100)
                    percentile_per_channel = np.percentile(rms, 90.0, axis=0)
                    amplitude = float(np.mean(percentile_per_channel))

                    duration = analyzer._segment_duration(record)
                    rate = amplitude / duration if duration > 0 else 0.0

                    per_subject_rates[record.subject].append(rate)
                    per_subject_durations[record.subject].append(duration)

                    csv_data.append({
                        'metric': 'rate',
                        'object': obj_id,
                        'condition': condition,
                        'subject': record.subject,
                        'session': record.session,
                        'amplitude': amplitude,
                        'duration': duration,
                        'rate': rate
                    })

                rate_map = {subj: float(np.mean(vals)) for subj, vals in per_subject_rates.items()}
                rate_median_map = {subj: float(np.median(vals)) for subj, vals in per_subject_rates.items()}
                dur_map = {subj: float(np.mean(vals)) for subj, vals in per_subject_durations.items()}

                condition_rate_means[condition] = rate_map
                condition_rate_medians[condition] = rate_median_map
                condition_duration_means[condition] = dur_map

                for subject, mean_rate in rate_map.items():
                    subject_rows.append({
                        'Condition': condition,
                        'Object': obj_id,
                        'Subject': subject,
                        'Rate (amp/s)': mean_rate,
                        'Duration (s)': dur_map.get(subject, np.nan)
                    })

            if 'Active glove' not in condition_rate_means:
                f.write("*No Active glove data available*\n\n")
                continue

            f.write("### Summary Statistics: Rate (subject means)\n\n")
            f.write("| Condition | Subjects | Mean Rate | Median Rate | Std | Mean Duration (s) |\n")
            f.write("|-----------|----------|-----------|-------------|-----|-------------------|\n")
            for condition in CONDITIONS:
                rates = list(condition_rate_means.get(condition, {}).values())
                durs = list(condition_duration_means.get(condition, {}).values())
                if rates:
                    f.write(f"| {condition} | {len(rates)} | {np.mean(rates):.2f} | {np.median(rates):.2f} | "
                           f"{np.std(rates):.2f} | {np.mean(durs) if durs else np.nan:.2f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - | - |\n")
            f.write("\n")

            active_map = condition_rate_means.get('Active glove', {})
            if not active_map:
                f.write("No Active glove data for this object.\n\n")
                continue

            f.write("### Hypothesis (Rate): Active glove < Other (subject-paired)\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p (Welch, one-tail) | U | p (MW, one-tail) | W | p (Wilcoxon, one-tail) | Supported? (Wilcoxon) |\n")
            f.write("|------------|-------------------|--------|---------------------|---|-------------------|---|------------------------|------------------------|\n")

            for other_cond in ['Passive glove', 'No glove']:
                if other_cond not in condition_rate_means:
                    f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                other_map = condition_rate_means[other_cond]
                active_vals, other_vals, shared = build_paired_lists(active_map, other_map)

                if len(shared) == 0:
                    f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"

                f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | {format_pvalue(results['p_welch'])} | "
                        f"{results['u_stat']:.1f} | {format_pvalue(results['p_mannwhitney'])} | "
                        f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | **{support_text}** |\n")

            f.write("\n")

            f.write("#### Effect Size: Cohen's d (subject means)\n\n")
            f.write("| Comparison | Cohen's d | Interpretation |\n")
            f.write("|------------|-----------|----------------|\n")

            for other_cond in ['Passive glove', 'No glove']:
                if other_cond in condition_rate_means:
                    other_map = condition_rate_means[other_cond]
                    active_vals, other_vals, shared = build_paired_lists(active_map, other_map)
                    if not shared:
                        f.write(f"| Active vs {other_cond} | - | - |\n")
                        continue
                    results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                    f.write(f"| Active vs {other_cond} | {results['cohens_d']:.3f} | {results['effect_size']} |\n")

            f.write("\n")

            f.write("### All Pairwise Comparisons - Rate (Two-tailed, subject-paired)\n\n")
            f.write("Comparing all condition pairs using subject-matched mean rates.\n\n")

            comparison_pairs = [
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove'),
                ('Active glove', 'Passive glove')
            ]

            pairwise_rate_results = {}

            f.write("#### Parametric Test: Welch's t-test (two-tailed)\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p-value | Mean Diff | Median Diff | % Change | Significant? |\n")
            f.write("|------------|-------------------|--------|---------|-----------|-------------|----------|--------------|\n")

            for cond1, cond2 in comparison_pairs:
                if cond1 in condition_rate_means and cond2 in condition_rate_means:
                    vals1, vals2, shared = build_paired_lists(condition_rate_means[cond1], condition_rate_means[cond2])
                    if not shared:
                        continue
                    results = test_pairwise_comparison(vals1, vals2, cond1, cond2)
                    pairwise_rate_results[(cond1, cond2)] = (results, len(shared))

                    sig_text = "✓ YES" if results['is_significant_welch'] else "✗ NO"
                    f.write(f"| {cond1} vs {cond2} | {len(shared)} | {results['t_stat']:.3f} | "
                           f"{format_pvalue(results['p_welch'])} | "
                           f"{results['mean_diff']:.2f} | {results['median_diff']:.2f} | {results['percent_diff']:+.1f}% | **{sig_text}** |\n")

            f.write("\n")

            f.write("#### Non-Parametric Test: Mann-Whitney U (two-tailed)\n\n")
            f.write("| Comparison | Subjects (paired) | U-stat | p-value | Significant? |\n")
            f.write("|------------|-------------------|--------|---------|---------------|\n")

            for cond1, cond2 in comparison_pairs:
                if (cond1, cond2) in pairwise_rate_results:
                    results, n_shared = pairwise_rate_results[(cond1, cond2)]
                    sig_text = "✓ YES" if results['is_significant_mw'] else "✗ NO"
                    f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['u_stat']:.1f} | "
                           f"{format_pvalue(results['p_mannwhitney'])} | **{sig_text}** |\n")

            f.write("\n")

            f.write("#### Paired Non-Parametric Test: Wilcoxon signed-rank (two-tailed)\n\n")
            f.write("| Comparison | Subjects (paired) | W-stat | p-value | Significant? |\n")
            f.write("|------------|-------------------|--------|---------|---------------|\n")

            for cond1, cond2 in comparison_pairs:
                if (cond1, cond2) in pairwise_rate_results:
                    results, n_shared = pairwise_rate_results[(cond1, cond2)]
                    sig_text = "✓ YES" if results['is_significant_wilcoxon'] else "✗ NO"
                    f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['w_stat']:.1f} | "
                           f"{format_pvalue(results['p_wilcoxon'])} | **{sig_text}** |\n")

            f.write("\n")

            f.write("#### Effect Size: Cohen's d\n\n")
            f.write("| Comparison | Subjects (paired) | Cohen's d | Interpretation | Direction |\n")
            f.write("|------------|-------------------|-----------|----------------|------------|\n")

            for cond1, cond2 in comparison_pairs:
                if (cond1, cond2) in pairwise_rate_results:
                    results, n_shared = pairwise_rate_results[(cond1, cond2)]
                    direction = f"{cond1} > {cond2}" if results['mean_diff'] > 0 else f"{cond1} < {cond2}"
                    f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['cohens_d']:.3f} | "
                           f"{results['effect_size']} | {direction} |\n")

            f.write("\n")

            f.write("### Task Duration Comparison (subject-paired)\n\n")
            f.write("| Comparison | Subjects (paired) | Mean Diff (s) | Median Diff (s) | t-statistic (paired) | p-value |\n")
            f.write("|------------|-------------------|---------------|-----------------|----------------------|---------|\n")

            active_dur_map = condition_duration_means.get('Active glove', {})
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond not in condition_duration_means:
                    f.write(f"| Active vs {other_cond} | 0 | - | - | - | - |\n")
                    continue

                other_dur_map = condition_duration_means[other_cond]
                active_durs, other_durs, shared = build_paired_lists(active_dur_map, other_dur_map)
                if not shared:
                    f.write(f"| Active vs {other_cond} | 0 | - | - | - | - |\n")
                    continue

                t_stat, p_val = stats.ttest_rel(active_durs, other_durs)
                mean_diff = np.mean(active_durs) - np.mean(other_durs)
                median_diff = np.median(active_durs) - np.median(other_durs)
                f.write(f"| Active vs {other_cond} | {len(shared)} | {mean_diff:+.2f} | {median_diff:+.2f} | {t_stat:.3f} | {format_pvalue(p_val)} |\n")

            f.write("\n")

            # --- Median-aggregated tests for activation rate ---
            comparison_pairs = [
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove'),
                ('Active glove', 'Passive glove')
            ]
            write_median_aggregated_tests(f, condition_rate_medians, comparison_pairs, CONDITIONS, one_tailed=True)

            f.write("---\n\n")
    
    # Export rate values to CSV
    import pandas as pd
    csv_path = results_dir / 'rate_values.csv'
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_path, index=False)
    print(f"✓ Saved rate values CSV: {csv_path}")

    subject_csv_path = results_dir / 'rate_subject_means.csv'
    df_subject = pd.DataFrame(subject_rows)
    if not df_subject.empty:
        df_subject.to_csv(subject_csv_path, index=False)
        print(f"✓ Saved rate subject means CSV: {subject_csv_path}")
    
    print(f"✓ Saved rate statistics: {report_path}")
    return report_path


def generate_duration_statistics():
    """Generate subject-level duration stats (per object, per condition) with paired Wilcoxon."""
    import pandas as pd

    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)

    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for duration statistics")
        return

    analyzer = EMGAnalyzer(EMGDataLoader(data_dir), fs_hz=inferred_fs, mvc_dict=mvc_dict)
    object_ids = list(range(6))

    subject_means, subject_medians, df_subject = collect_subject_level_metric(data_dict, analyzer, object_ids, metric='duration')
    df_subject = df_subject.rename(columns={'Value': 'Duration (s)'})

    # Save subject-level means
    duration_csv = results_dir / 'duration_subject_means.csv'
    df_subject.to_csv(duration_csv, index=False)
    print(f"✓ Saved duration subject means: {duration_csv}")

    report_path = results_dir / 'statistical_summary_duration.md'

    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: Task Duration (Subject-Level)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Metric:** Mean segment duration per subject, per object, per condition (seconds).\n\n")
        f.write("**Tests:**\n")
        f.write("- One-tailed: Welch t-test, Mann-Whitney, Wilcoxon (Active > Other, since active tasks take longer)\n")
        f.write("- Two-tailed: Welch t-test, Mann-Whitney, Wilcoxon (any difference)\n\n")
        f.write("**Why Welch's t-test instead of Student's t-test?**\n")
        f.write("- Welch's t-test does NOT assume equal variances between groups\n")
        f.write("- More robust when sample sizes or variances differ between conditions\n")
        f.write("- Student's t-test assumes equal variances (homoscedasticity), which is often violated\n")
        f.write("- Welch's test is generally recommended as the default for comparing two groups\n\n")
        f.write("**Pairing rule:** Wilcoxon uses only subjects present in both conditions for each object.\n\n")
        f.write("---\n\n")

        for obj_id in object_ids:
            f.write(f"## Object {obj_id}\n\n")

            # Summary stats
            f.write("### Summary Statistics (subject means)\n\n")
            f.write("| Condition | Subjects | Mean (s) | Median (s) | Std (s) |\n")
            f.write("|-----------|----------|----------|-----------|---------|\n")
            for condition in CONDITIONS:
                vals = list(subject_means.get(condition, {}).get(obj_id, {}).values())
                if vals:
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.3f} | {np.median(vals):.3f} | {np.std(vals, ddof=1):.3f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - |\n")
            f.write("\n")

            # Normality tests
            f.write("### Normality Tests (Shapiro-Wilk)\n\n")
            f.write("Tests whether data follows a normal distribution. p < 0.05 suggests non-normality.\n\n")
            f.write("| Condition | W-statistic | p-value | Normal? |\n")
            f.write("|-----------|-------------|---------|--------|\n")
            for condition in CONDITIONS:
                vals = list(subject_means.get(condition, {}).get(obj_id, {}).values())
                if vals and len(vals) >= 3:
                    w_stat, p_val, is_normal = test_normality(vals, condition)
                    normal_text = "✓ Yes" if is_normal else "✗ No"
                    f.write(f"| {condition} | {w_stat:.4f} | {format_pvalue(p_val)} | {normal_text} |\n")
                else:
                    f.write(f"| {condition} | - | - | n<3 |\n")
            f.write("\n")

            # Hypothesis testing Active vs others
            if 'Active glove' not in subject_means or obj_id not in subject_means['Active glove']:
                f.write("No Active glove data for this object.\n\n")
                continue

            active_map = subject_means['Active glove'][obj_id]
            
            # One-tailed tests (Active > Other for duration - active tasks take longer)
            f.write("### One-Tailed Tests: Active glove > Other (duration expected longer with assistance)\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p (Welch) | U | p (MW) | W | p (Wilcoxon) | % Reduction (median) | Supported? |\n")
            f.write("|------------|-------------------|--------|-----------|---|--------|---|--------------|----------------------|------------|\n")

            one_tailed_specs = [
                ('Active glove', 'Passive glove', 'greater'),
                ('Active glove', 'No glove', 'greater'),
                ('Passive glove', 'No glove', 'greater')
            ]

            for cond_a, cond_b, alternative in one_tailed_specs:
                if cond_a not in subject_means or obj_id not in subject_means[cond_a] or \
                   cond_b not in subject_means or obj_id not in subject_means[cond_b]:
                    f.write(f"| {cond_a} vs {cond_b} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                vals_a, vals_b, shared = build_paired_lists(subject_means[cond_a][obj_id], subject_means[cond_b][obj_id])
                if len(shared) == 0:
                    f.write(f"| {cond_a} vs {cond_b} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                t_stat, p_two = stats.ttest_ind(vals_a, vals_b, equal_var=False)
                p_welch_one = p_two / 2 if t_stat > 0 else 1 - (p_two / 2)

                u_stat, _ = stats.mannwhitneyu(vals_a, vals_b, alternative='two-sided')
                _, p_mw_one = stats.mannwhitneyu(vals_a, vals_b, alternative=alternative)

                w_stat = np.nan
                p_wilcoxon_one = np.nan
                try:
                    w_stat, p_wilcoxon_one = stats.wilcoxon(vals_a, vals_b, alternative=alternative)
                except ValueError:
                    pass

                mean_a = np.mean(vals_a)
                mean_b = np.mean(vals_b)
                median_reduction = compute_requested_reduction(vals_a, vals_b, cond_a, cond_b, use_median=True)
                supported = (mean_a > mean_b) and (p_wilcoxon_one < 0.05 if not np.isnan(p_wilcoxon_one) else False)
                support_text = "✓ YES" if supported else "✗ NO"

                f.write(f"| {cond_a} vs {cond_b} | {len(shared)} | {t_stat:.3f} | {format_pvalue(p_welch_one)} | "
                        f"{u_stat:.1f} | {format_pvalue(p_mw_one)} | "
                        f"{w_stat:.1f} | {format_pvalue(p_wilcoxon_one)} | {median_reduction:+.1f}% | **{support_text}** |\n")

            f.write("\n")
            
            # Two-tailed tests (any difference)
            f.write("### Two-Tailed Tests: Any significant difference\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p (Welch) | U | p (MW) | W | p (Wilcoxon) | % Reduction (median) | Significant? |\n")
            f.write("|------------|-------------------|--------|-----------|---|--------|---|--------------|----------------------|-------------|\n")

            two_tailed_specs = [
                ('Active glove', 'Passive glove'),
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove')
            ]

            for cond_a, cond_b in two_tailed_specs:
                if cond_a not in subject_means or obj_id not in subject_means[cond_a] or \
                   cond_b not in subject_means or obj_id not in subject_means[cond_b]:
                    f.write(f"| {cond_a} vs {cond_b} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                vals_a, vals_b, shared = build_paired_lists(subject_means[cond_a][obj_id], subject_means[cond_b][obj_id])
                if len(shared) == 0:
                    f.write(f"| {cond_a} vs {cond_b} | 0 | - | - | - | - | - | - | - |\n")
                    continue

                results = test_pairwise_comparison(vals_a, vals_b, cond_a, cond_b)
                median_reduction = compute_requested_reduction(vals_a, vals_b, cond_a, cond_b, use_median=True)
                sig_text = "✓ YES" if results['is_significant_wilcoxon'] else "✗ NO"

                f.write(f"| {cond_a} vs {cond_b} | {len(shared)} | {results['t_stat']:.3f} | {format_pvalue(results['p_welch'])} | "
                        f"{results['u_stat']:.1f} | {format_pvalue(results['p_mannwhitney'])} | "
                        f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | {median_reduction:+.1f}% | **{sig_text}** |\n")

            f.write("\n")
            
            # Effect sizes
            f.write("### Effect Size (Cohen's d)\n\n")
            f.write("| Comparison | Cohen's d | Interpretation | Mean Diff (s) | Median Diff (s) | % Change |\n")
            f.write("|------------|-----------|----------------|---------------|-----------------|----------|\n")
            
            for other_cond in ['Passive glove', 'No glove']:
                if other_cond not in subject_means or obj_id not in subject_means[other_cond]:
                    continue
                other_map = subject_means[other_cond][obj_id]
                active_vals, other_vals, shared = build_paired_lists(active_map, other_map)
                if len(shared) == 0:
                    continue
                d = cohens_d(active_vals, other_vals)
                interp = interpret_cohens_d(d)
                mean_diff = np.mean(active_vals) - np.mean(other_vals)
                median_diff = np.median(active_vals) - np.median(other_vals)
                median_other = np.median(other_vals)
                pct_change = (median_diff / median_other) * 100 if median_other != 0 else 0
                f.write(f"| Active vs {other_cond} | {d:.3f} | {interp} | {mean_diff:+.3f} | {median_diff:+.3f} | {pct_change:+.1f}% |\n")
            
            f.write("\n")

            # --- Median-aggregated tests for duration ---
            comparison_pairs = [
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove'),
                ('Active glove', 'Passive glove')
            ]
            dur_median_maps = {}
            for condition in CONDITIONS:
                if condition in subject_medians and obj_id in subject_medians[condition]:
                    dur_median_maps[condition] = subject_medians[condition][obj_id]
            write_median_aggregated_tests(f, dur_median_maps, comparison_pairs, CONDITIONS, one_tailed=True, direction='greater')

            f.write("---\n\n")

    print(f"✓ Saved duration statistics: {report_path}")
    return report_path


def generate_mvc_statistics():
    """Generate subject-level %MVC stats (per object, per condition) with paired Wilcoxon."""
    import pandas as pd

    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)

    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for MVC statistics")
        return

    analyzer = EMGAnalyzer(EMGDataLoader(data_dir), fs_hz=inferred_fs, mvc_dict=mvc_dict)
    object_ids = list(range(6))

    subject_means, subject_medians, df_subject = collect_subject_level_metric(data_dict, analyzer, object_ids, metric='mvc')
    df_subject = df_subject.rename(columns={'Value': '%MVC'})

    mvc_csv = results_dir / 'mvc_subject_means.csv'
    df_subject.to_csv(mvc_csv, index=False)
    print(f"✓ Saved MVC subject means: {mvc_csv}")

    report_path = results_dir / 'statistical_summary_mvc.md'

    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: %MVC (Subject-Level)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Metric:** Mean RMS (%MVC) per subject, per object, per condition.\n\n")
        f.write("**Tests:** Welch (one-tailed Active < Other), Mann-Whitney (one-tailed), Wilcoxon paired (Active < Other, subject-matched).\n\n")
        f.write("**Why Welch's t-test?** Does not assume equal variances between groups (more robust than Student's t-test).\n\n")
        f.write("**Pairing rule:** Wilcoxon uses only subjects present in both conditions for each object.\n\n")
        f.write("---\n\n")

        for obj_id in object_ids:
            f.write(f"## Object {obj_id}\n\n")

            f.write("### Summary Statistics (subject means)\n\n")
            f.write("| Condition | Subjects | Mean %MVC | Median %MVC | Std %MVC |\n")
            f.write("|-----------|----------|-----------|-------------|----------|\n")
            for condition in CONDITIONS:
                vals = list(subject_means.get(condition, {}).get(obj_id, {}).values())
                if vals:
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.3f} | {np.median(vals):.3f} | {np.std(vals, ddof=1):.3f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - | - |\n")
            f.write("\n")

            # Normality tests
            f.write("### Normality Tests (Shapiro-Wilk)\n\n")
            f.write("| Condition | W-statistic | p-value | Normal? |\n")
            f.write("|-----------|-------------|---------|--------|\n")
            for condition in CONDITIONS:
                vals = list(subject_means.get(condition, {}).get(obj_id, {}).values())
                if vals and len(vals) >= 3:
                    w_stat, p_val, is_normal = test_normality(vals, condition)
                    normal_text = "✓ Yes" if is_normal else "✗ No"
                    f.write(f"| {condition} | {w_stat:.4f} | {format_pvalue(p_val)} | {normal_text} |\n")
                else:
                    f.write(f"| {condition} | - | - | n<3 |\n")
            f.write("\n")

            # Normality tests
            f.write("### Normality Tests (Shapiro-Wilk)\n\n")
            f.write("| Condition | W-statistic | p-value | Normal? |\n")
            f.write("|-----------|-------------|---------|--------|\n")
            for condition in CONDITIONS:
                vals = list(subject_means.get(condition, {}).get(obj_id, {}).values())
                if vals and len(vals) >= 3:
                    w_stat, p_val, is_normal = test_normality(vals, condition)
                    normal_text = "✓ Yes" if is_normal else "✗ No"
                    f.write(f"| {condition} | {w_stat:.4f} | {format_pvalue(p_val)} | {normal_text} |\n")
                else:
                    f.write(f"| {condition} | - | - | n<3 |\n")
            f.write("\n")

            if 'Active glove' not in subject_means or obj_id not in subject_means['Active glove']:
                f.write("No Active glove data for this object.\n\n")
                continue

            active_map = subject_means['Active glove'][obj_id]
            f.write("### Hypothesis: Active glove < Other\n\n")
            f.write("| Comparison | Subjects (paired) | t-stat | p (Welch, one-tail) | U | p (MW, one-tail) | W | p (Wilcoxon, one-tail) | % Reduction (median) | Supported? (Wilcoxon) |\n")
            f.write("|------------|-------------------|--------|---------------------|---|-------------------|---|------------------------|-------------|------------------------|\n")

            one_tailed_specs = [
                ('Active glove', 'Passive glove', 'less'),
                ('Active glove', 'No glove', 'less'),
                ('Passive glove', 'No glove', 'less')
            ]

            for cond_a, cond_b, alternative in one_tailed_specs:
                if cond_a not in subject_means or obj_id not in subject_means[cond_a] or \
                   cond_b not in subject_means or obj_id not in subject_means[cond_b]:
                    f.write(f"| {cond_a} vs {cond_b} | 0 | - | - | - | - | - | - | - | - |\n")
                    continue

                vals_a, vals_b, shared = build_paired_lists(subject_means[cond_a][obj_id], subject_means[cond_b][obj_id])
                if len(shared) == 0:
                    f.write(f"| {cond_a} vs {cond_b} | 0 | - | - | - | - | - | - | - | - |\n")
                    continue

                t_stat, p_two = stats.ttest_ind(vals_a, vals_b, equal_var=False)
                p_welch_one = p_two / 2 if t_stat < 0 else 1 - (p_two / 2)

                u_stat, _ = stats.mannwhitneyu(vals_a, vals_b, alternative='two-sided')
                _, p_mw_one = stats.mannwhitneyu(vals_a, vals_b, alternative=alternative)

                w_stat = np.nan
                p_wilcoxon_one = np.nan
                try:
                    w_stat, p_wilcoxon_one = stats.wilcoxon(vals_a, vals_b, alternative=alternative)
                except ValueError:
                    pass

                mean_a = np.mean(vals_a)
                mean_b = np.mean(vals_b)
                reduction = compute_requested_reduction(vals_a, vals_b, cond_a, cond_b, use_median=True)
                support_text = "✓ YES" if ((mean_a < mean_b) and (p_wilcoxon_one < 0.05 if not np.isnan(p_wilcoxon_one) else False)) else "✗ NO"

                f.write(f"| {cond_a} vs {cond_b} | {len(shared)} | {t_stat:.3f} | {format_pvalue(p_welch_one)} | "
                        f"{u_stat:.1f} | {format_pvalue(p_mw_one)} | "
                        f"{w_stat:.1f} | {format_pvalue(p_wilcoxon_one)} | "
                        f"{reduction:+.1f}% | **{support_text}** |\n")

            f.write("\n")

            # Median reduction table using mean-aggregated subject values
            f.write("### Median % Reduction (Mean-Aggregated Subject Values)\n\n")
            f.write("Formulas: ((No glove-Active glove)/No glove), ((Passive glove-Active glove)/Passive glove), ((No glove-Passive glove)/No glove).\n\n")
            f.write("| Comparison (cond1 -> cond2) | Median cond1 | Median cond2 | % Reduction |\n")
            f.write("|-----------------------------|--------------|--------------|-------------|\n")

            for other_cond in ['Passive glove', 'No glove']:
                if other_cond not in subject_means or obj_id not in subject_means[other_cond]:
                    f.write(f"| {other_cond} -> Active glove | - | - | - |\n")
                    continue

                other_map = subject_means[other_cond][obj_id]
                active_vals, other_vals, shared = build_paired_lists(active_map, other_map)
                if len(shared) == 0:
                    f.write(f"| {other_cond} -> Active glove | - | - | - |\n")
                    continue

                median_active = np.median(active_vals)
                median_other = np.median(other_vals)
                reduction = ((median_other - median_active) / median_other) * 100 if median_other != 0 else 0
                f.write(f"| {other_cond} -> Active glove | {median_other:.3f} | {median_active:.3f} | {reduction:+.1f}% |\n")

            # Requested additional reduction: No glove -> Passive glove
            if 'No glove' in subject_means and obj_id in subject_means['No glove'] and \
               'Passive glove' in subject_means and obj_id in subject_means['Passive glove']:
                no_vals, passive_vals, shared = build_paired_lists(subject_means['No glove'][obj_id], subject_means['Passive glove'][obj_id])
                if len(shared) > 0:
                    median_no = np.median(no_vals)
                    median_passive = np.median(passive_vals)
                    reduction_np = ((median_no - median_passive) / median_no) * 100 if median_no != 0 else 0
                    f.write(f"| No glove -> Passive glove | {median_no:.3f} | {median_passive:.3f} | {reduction_np:+.1f}% |\n")

            f.write("\n")

            # --- Median-aggregated tests for %MVC ---
            comparison_pairs = [
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove'),
                ('Active glove', 'Passive glove')
            ]
            mvc_median_maps = {}
            for condition in CONDITIONS:
                if condition in subject_medians and obj_id in subject_medians[condition]:
                    mvc_median_maps[condition] = subject_medians[condition][obj_id]
            write_median_aggregated_tests(f, mvc_median_maps, comparison_pairs, CONDITIONS, one_tailed=True, direction='less')

            f.write("---\n\n")

    print(f"✓ Saved MVC statistics: {report_path}")
    return report_path


def generate_pca_statistics():
    """Generate subject-level paired statistics for PCA analysis with feature-based approach."""

    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / 'data' / 'healthy'
    results_dir = script_dir / 'results-analysis'
    results_dir.mkdir(exist_ok=True)

    data_dict, inferred_fs, mvc_dict = load_real_data(data_dir)
    if data_dict is None:
        print("Failed to load data for PCA statistics")
        return

    loader = EMGDataLoader(data_dir)
    analyzer = EMGAnalyzer(loader, fs_hz=inferred_fs, mvc_dict=mvc_dict)

    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    csv_data = []
    subject_rows = []

    report_path = results_dir / 'statistical_summary_pca.md'

    with open(report_path, 'w') as f:
        f.write("# Statistical Analysis: PCA Feature-Based Comparisons\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**Dataset:** S1–S10 (10 subjects, balanced 3 sessions per condition per subject)\n\n")
        f.write("**Note:** S7 has 8 sessions (3 no, 2 passive, 3 active)\n\n")
        f.write("**Normalization:** MVC (Maximum Voluntary Contraction) - all values expressed as %MVC\n\n")
        f.write("**Metric:** PCA on temporal features (duration-independent); tests run on subject-level means.\n\n")
        f.write("**Rationale:** Each segment contributes equally to PCA (one feature vector per segment) ")
        f.write("regardless of duration. This removes sample size bias where longer tasks would dominate principal components.\n\n")
        f.write("**Features per segment:**\n")
        f.write("- Per-channel statistics: mean, std, 90th percentile, peak amplitude\n")
        f.write("- Global statistics: mean/std/percentile/peak across channels\n")
        f.write("- Temporal metrics: activation duration, burst frequency\n")
        f.write("- Cross-channel coordination: mean correlation\n\n")
        f.write("**Related Figures:**\n")
        f.write("- `figureC_pca_single_objects_1.svg`\n")
        f.write("- `figureC_pca_all_objects_0_1_2_3_4_5.svg`\n")
        f.write("- `figureC_pca_object_*.svg` (per-object PCA)\n\n")
        f.write("---\n\n")

        for obj_id in range(6):
            f.write(f"## Object {obj_id}\n\n")

            condition_features = {}
            condition_records = {}

            for condition in CONDITIONS:
                if condition not in data_dict or obj_id not in data_dict[condition]:
                    continue
                records = data_dict[condition][obj_id]
                if not records:
                    continue

                features_list = []
                for record in records:
                    segment = analyzer._normalize_segment(record.samples, record.subject)
                    features = analyzer.extract_temporal_features(segment, window_ms=100)
                    features_list.append(features)
                condition_features[condition] = np.array(features_list)
                condition_records[condition] = records

            if len(condition_features) < 2:
                f.write("*Insufficient data for PCA analysis*\n\n")
                continue

            all_features = np.vstack([condition_features[c] for c in CONDITIONS if c in condition_features])
            scaler = StandardScaler()
            all_features_scaled = scaler.fit_transform(all_features)

            pca = PCA(n_components=2)
            pca.fit(all_features_scaled)

            f.write(f"### PCA Results\n\n")
            f.write(f"- **Explained variance:** PC1={pca.explained_variance_ratio_[0]*100:.1f}%, ")
            f.write(f"PC2={pca.explained_variance_ratio_[1]*100:.1f}%\n")
            f.write(f"- **Total variance explained:** {(pca.explained_variance_ratio_[0] + pca.explained_variance_ratio_[1])*100:.1f}%\n\n")

            pc1_maps = {}
            pc2_maps = {}
            mag_maps = {}
            pc1_median_maps = {}
            pc2_median_maps = {}
            mag_median_maps = {}

            for condition in CONDITIONS:
                if condition in condition_features:
                    scaled = scaler.transform(condition_features[condition])
                    transformed = pca.transform(scaled)
                    pc1_vals = np.abs(transformed[:, 0])
                    pc2_vals = np.abs(transformed[:, 1])
                    magnitudes = np.linalg.norm(transformed[:, :2], axis=1)

                    per_subject = defaultdict(lambda: {'pc1': [], 'pc2': [], 'mag': []})
                    records = condition_records[condition]
                    for pc1_val, pc2_val, mag, record in zip(pc1_vals, pc2_vals, magnitudes, records):
                        per_subject[record.subject]['pc1'].append(pc1_val)
                        per_subject[record.subject]['pc2'].append(pc2_val)
                        per_subject[record.subject]['mag'].append(mag)

                        csv_data.append({
                            'metric': 'pca_magnitude',
                            'object': obj_id,
                            'condition': condition,
                            'subject': record.subject,
                            'session': record.session,
                            'pca_magnitude': float(mag),
                            'pc1_abs': float(pc1_val),
                            'pc2_abs': float(pc2_val),
                            'explained_var_pc1': pca.explained_variance_ratio_[0],
                            'explained_var_pc2': pca.explained_variance_ratio_[1]
                        })

                    pc1_maps[condition] = {subj: float(np.mean(vals['pc1'])) for subj, vals in per_subject.items()}
                    pc2_maps[condition] = {subj: float(np.mean(vals['pc2'])) for subj, vals in per_subject.items()}
                    mag_maps[condition] = {subj: float(np.mean(vals['mag'])) for subj, vals in per_subject.items()}
                    pc1_median_maps[condition] = {subj: float(np.median(vals['pc1'])) for subj, vals in per_subject.items()}
                    pc2_median_maps[condition] = {subj: float(np.median(vals['pc2'])) for subj, vals in per_subject.items()}
                    mag_median_maps[condition] = {subj: float(np.median(vals['mag'])) for subj, vals in per_subject.items()}

                    for subject in per_subject:
                        subject_rows.append({
                            'Condition': condition,
                            'Object': obj_id,
                            'Subject': subject,
                            'PC1_abs': pc1_maps[condition][subject],
                            'PC2_abs': pc2_maps[condition][subject],
                            'Magnitude': mag_maps[condition][subject]
                        })

            # Summary statistics for PC1 (subject means)
            f.write("### PC1 Values (subject means, absolute)\n\n")
            f.write("| Condition | Subjects | Mean PC1 | Median PC1 | Std |\n")
            f.write("|-----------|----------|----------|------------|-----|\n")
            for condition in CONDITIONS:
                vals = list(pc1_maps.get(condition, {}).values())
                if vals:
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.3f} | {np.median(vals):.3f} | {np.std(vals, ddof=1):.3f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - |\n")
            f.write("\n")

            if pc1_maps.get('Active glove'):
                f.write("**PC1 Hypothesis Test (subject-paired): Active glove < Others**\n\n")
                f.write("##### Welch's t-test (one-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | t-stat | p-value | Mean Diff | Median Diff | % Change | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|-----------|-------------|----------|-----------|\n")

                active_pc1_map = pc1_maps['Active glove']
                pc1_results = {}

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc1_maps:
                        active_vals, other_vals, shared = build_paired_lists(active_pc1_map, pc1_maps[other_cond])
                        if not shared:
                            continue
                        results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                        pc1_results[other_cond] = (results, len(shared))
                        support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['median_diff']:.3f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")

                f.write("\n")

                f.write("##### Wilcoxon signed-rank (one-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | W-stat | p-value | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc1_results:
                        results, n_shared = pc1_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['w_stat']:.1f} | "
                               f"{format_pvalue(results['p_wilcoxon'])} | **{support_text}** |\n")

                f.write("\n")

                f.write("##### Mann-Whitney U (one-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | U-stat | p-value | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc1_results:
                        results, n_shared = pc1_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")

                f.write("\n")

                f.write("##### Cohen's d\n\n")
                f.write("| Comparison | Subjects (paired) | Cohen's d | Interpretation |\n")
                f.write("|------------|-------------------|-----------|----------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc1_results:
                        results, n_shared = pc1_results[other_cond]
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['cohens_d']:.3f} | {results['effect_size']} |\n")

                f.write("\n")

            # Summary statistics for PC2 (subject means)
            f.write("### PC2 Values (subject means)\n\n")
            f.write("| Condition | Subjects | Mean PC2 | Median PC2 | Std |\n")
            f.write("|-----------|----------|----------|------------|-----|\n")
            for condition in CONDITIONS:
                vals = list(pc2_maps.get(condition, {}).values())
                if vals:
                    f.write(f"| {condition} | {len(vals)} | {np.mean(vals):.3f} | {np.median(vals):.3f} | {np.std(vals, ddof=1):.3f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - |\n")
            f.write("\n")

            if pc2_maps.get('Active glove'):
                f.write("**PC2 Hypothesis Test (subject-paired): Active glove < Others**\n\n")
                f.write("##### Welch's t-test (one-tailed, absolute values)\n\n")
                f.write("| Comparison | Subjects (paired) | t-stat | p-value | Mean Diff | Median Diff | % Change | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|-----------|-------------|----------|-----------|\n")

                active_pc2_map = pc2_maps['Active glove']
                pc2_results = {}

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc2_maps:
                        active_vals, other_vals, shared = build_paired_lists(active_pc2_map, pc2_maps[other_cond])
                        if not shared:
                            continue
                        results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                        pc2_results[other_cond] = (results, len(shared))
                        support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['median_diff']:.3f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")

                f.write("\n")

                f.write("##### Mann-Whitney U (one-tailed, absolute values)\n\n")
                f.write("| Comparison | Subjects (paired) | U-stat | p-value | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc2_results:
                        results, n_shared = pc2_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")

                f.write("\n")

                f.write("##### Wilcoxon signed-rank (one-tailed, absolute values)\n\n")
                f.write("| Comparison | Subjects (paired) | W-stat | p-value | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc2_results:
                        results, n_shared = pc2_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['w_stat']:.1f} | "
                               f"{format_pvalue(results['p_wilcoxon'])} | **{support_text}** |\n")

                f.write("\n")

                f.write("##### Cohen's d\n\n")
                f.write("| Comparison | Subjects (paired) | Cohen's d | Interpretation |\n")
                f.write("|------------|-------------------|-----------|----------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in pc2_results:
                        results, n_shared = pc2_results[other_cond]
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['cohens_d']:.3f} | {results['effect_size']} |\n")

                f.write("\n")

            # Summary statistics for magnitude (subject means)
            f.write("### PCA Magnitude Statistics (subject means)\n\n")
            f.write("| Condition | Subjects | Mean Magnitude | Median Magnitude | Std |\n")
            f.write("|-----------|----------|----------------|------------------|-----|\n")
            for condition in CONDITIONS:
                mags = list(mag_maps.get(condition, {}).values())
                if mags:
                    f.write(f"| {condition} | {len(mags)} | {np.mean(mags):.3f} | {np.median(mags):.3f} | {np.std(mags):.3f} |\n")
                else:
                    f.write(f"| {condition} | 0 | - | - |\n")
            f.write("\n")

            if mag_maps.get('Active glove'):
                f.write("### Hypothesis Test: Active glove magnitude < Others (subject-paired)\n\n")
                f.write("#### Parametric Test: Welch's t-test (one-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | t-stat | p-value | Mean Diff | Median Diff | % Change | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|-----------|-------------|----------|-----------|\n")

                active_mag_map = mag_maps['Active glove']
                mag_results = {}

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in mag_maps:
                        active_vals, other_vals, shared = build_paired_lists(active_mag_map, mag_maps[other_cond])
                        if not shared:
                            continue
                        results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                        mag_results[other_cond] = (results, len(shared))
                        support_text = "✓ YES" if results['hypothesis_supported_welch'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['median_diff']:.3f} | {results['percent_diff']:+.1f}% | **{support_text}** |\n")

                f.write("\n")

                f.write("#### Non-Parametric Test: Mann-Whitney U (one-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | U-stat | p-value | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in mag_results:
                        results, n_shared = mag_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_mw'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{support_text}** |\n")

                f.write("\n")

                f.write("#### Paired Non-Parametric Test: Wilcoxon signed-rank (one-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | W-stat | p-value | Supported? |\n")
                f.write("|------------|-------------------|--------|---------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in mag_results:
                        results, n_shared = mag_results[other_cond]
                        support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['w_stat']:.1f} | "
                               f"{format_pvalue(results['p_wilcoxon'])} | **{support_text}** |\n")

                f.write("\n")

                f.write("#### Effect Size: Cohen's d\n\n")
                f.write("| Comparison | Subjects (paired) | Cohen's d | Interpretation |\n")
                f.write("|------------|-------------------|-----------|----------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond in mag_results:
                        results, n_shared = mag_results[other_cond]
                        f.write(f"| Active vs {other_cond} | {n_shared} | {results['cohens_d']:.3f} | {results['effect_size']} |\n")

                f.write("\n")

                if len([m for m in mag_maps.values() if m]) == 3:
                    groups = [np.array(list(mag_maps[c].values())) for c in CONDITIONS if mag_maps.get(c)]
                    if all(len(g) > 0 for g in groups):
                        f.write("#### ANOVA: Three-way comparison\n\n")
                        f_stat, p_anova = stats.f_oneway(*groups)
                        f.write(f"**F-statistic:** {f_stat:.3f}  \n")
                        f.write(f"**p-value:** {format_pvalue(p_anova)}  \n")
                        if p_anova < 0.05:
                            f.write("**Interpretation:** Significant difference exists between conditions\n\n")
                        else:
                            f.write("**Interpretation:** No significant difference between conditions\n\n")

            if len([m for m in mag_maps.values() if m]) >= 2:
                f.write("### All Pairwise Comparisons - PCA Magnitude (Two-tailed, subject-paired)\n\n")
                f.write("Comparing all condition pairs for PCA magnitude differences using subject means.\n\n")

                comparison_pairs = [
                    ('Active glove', 'No glove'),
                    ('Passive glove', 'No glove'),
                    ('Active glove', 'Passive glove')
                ]

                pairwise_mag_results = {}

                f.write("#### Parametric Test: Welch's t-test (two-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | t-stat | p-value | Mean Diff | Median Diff | % Change | Significant? |\n")
                f.write("|------------|-------------------|--------|---------|-----------|-------------|----------|--------------|\n")

                for cond1, cond2 in comparison_pairs:
                    if cond1 in mag_maps and cond2 in mag_maps:
                        vals1, vals2, shared = build_paired_lists(mag_maps[cond1], mag_maps[cond2])
                        if not shared:
                            continue
                        results = test_pairwise_comparison(vals1, vals2, cond1, cond2)
                        pairwise_mag_results[(cond1, cond2)] = (results, len(shared))

                        sig_text = "✓ YES" if results['is_significant_welch'] else "✗ NO"
                        f.write(f"| {cond1} vs {cond2} | {len(shared)} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['mean_diff']:.3f} | {results['median_diff']:.3f} | {results['percent_diff']:+.1f}% | **{sig_text}** |\n")

                f.write("\n")

                f.write("#### Non-Parametric Test: Mann-Whitney U (two-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | U-stat | p-value | Significant? |\n")
                f.write("|------------|-------------------|--------|---------|---------------|\n")

                for cond1, cond2 in comparison_pairs:
                    if (cond1, cond2) in pairwise_mag_results:
                        results, n_shared = pairwise_mag_results[(cond1, cond2)]
                        sig_text = "✓ YES" if results['is_significant_mw'] else "✗ NO"
                        f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['u_stat']:.1f} | "
                               f"{format_pvalue(results['p_mannwhitney'])} | **{sig_text}** |\n")

                f.write("\n")

                f.write("#### Paired Non-Parametric Test: Wilcoxon signed-rank (two-tailed)\n\n")
                f.write("| Comparison | Subjects (paired) | W-stat | p-value | Significant? |\n")
                f.write("|------------|-------------------|--------|---------|---------------|\n")

                for cond1, cond2 in comparison_pairs:
                    if (cond1, cond2) in pairwise_mag_results:
                        results, n_shared = pairwise_mag_results[(cond1, cond2)]
                        sig_text = "✓ YES" if results['is_significant_wilcoxon'] else "✗ NO"
                        f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['w_stat']:.1f} | "
                               f"{format_pvalue(results['p_wilcoxon'])} | **{sig_text}** |\n")

                f.write("\n")

                f.write("#### Effect Size: Cohen's d\n\n")
                f.write("| Comparison | Subjects (paired) | Cohen's d | Interpretation | Direction |\n")
                f.write("|------------|-------------------|-----------|----------------|------------|\n")

                for cond1, cond2 in comparison_pairs:
                    if (cond1, cond2) in pairwise_mag_results:
                        results, n_shared = pairwise_mag_results[(cond1, cond2)]
                        direction = f"{cond1} > {cond2}" if results['mean_diff'] > 0 else f"{cond1} < {cond2}"
                        f.write(f"| {cond1} vs {cond2} | {n_shared} | {results['cohens_d']:.3f} | "
                               f"{results['effect_size']} | {direction} |\n")

                f.write("\n")

            # --- Median-aggregated tests for PCA metrics ---
            comparison_pairs_pca = [
                ('Active glove', 'No glove'),
                ('Passive glove', 'No glove'),
                ('Active glove', 'Passive glove')
            ]

            f.write("### Statistical Tests on Subject-Level Medians (PCA)\n\n")
            f.write("*Same tests as above, but each subject's value is their **median** across sessions (instead of mean).*\n\n")

            for metric_name, median_map in [('PC1', pc1_median_maps), ('PC2', pc2_median_maps), ('Magnitude', mag_median_maps)]:
                if 'Active glove' not in median_map:
                    continue
                active_median_map = median_map['Active glove']

                f.write(f"#### {metric_name} — Hypothesis: Active < Other (median-aggregated)\n\n")
                f.write("| Comparison | Subjects | t-stat | p (Welch) | W | p (Wilcoxon) | Supported? |\n")
                f.write("|------------|----------|--------|-----------|---|--------------|------------|\n")

                for other_cond in ['Passive glove', 'No glove']:
                    if other_cond not in median_map:
                        f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - |\n")
                        continue
                    active_vals, other_vals, shared = build_paired_lists(active_median_map, median_map[other_cond])
                    if not shared:
                        f.write(f"| Active vs {other_cond} | 0 | - | - | - | - | - |\n")
                        continue
                    results = test_hypothesis_comprehensive(active_vals, other_vals, other_cond)
                    support_text = "✓ YES" if results['hypothesis_supported_wilcoxon'] else "✗ NO"
                    f.write(f"| Active vs {other_cond} | {len(shared)} | {results['t_stat']:.3f} | "
                            f"{format_pvalue(results['p_welch'])} | "
                            f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | **{support_text}** |\n")
                f.write("\n")

                f.write(f"#### {metric_name} — Pairwise (two-tailed, median-aggregated)\n\n")
                f.write("| Comparison | Subjects | t-stat | p (Welch) | W | p (Wilcoxon) | Mean Diff | Median Diff | Significant? |\n")
                f.write("|------------|----------|--------|-----------|---|--------------|-----------|-------------|---------------|\n")
                for cond1, cond2 in comparison_pairs_pca:
                    if cond1 in median_map and cond2 in median_map:
                        vals1, vals2, shared = build_paired_lists(median_map[cond1], median_map[cond2])
                        if not shared:
                            continue
                        results = test_pairwise_comparison(vals1, vals2, cond1, cond2)
                        sig_text = "✓ YES" if results['is_significant_wilcoxon'] else "✗ NO"
                        f.write(f"| {cond1} vs {cond2} | {len(shared)} | {results['t_stat']:.3f} | "
                               f"{format_pvalue(results['p_welch'])} | "
                               f"{results['w_stat']:.1f} | {format_pvalue(results['p_wilcoxon'])} | "
                               f"{results['mean_diff']:.3f} | {results['median_diff']:.3f} | **{sig_text}** |\n")
                f.write("\n")

            f.write("---\n\n")

    import pandas as pd
    csv_path = results_dir / 'pca_values.csv'
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_path, index=False)
    print(f"✓ Saved PCA values CSV: {csv_path}")

    subject_csv_path = results_dir / 'pca_subject_means.csv'
    df_subject = pd.DataFrame(subject_rows)
    if not df_subject.empty:
        df_subject.to_csv(subject_csv_path, index=False)
        print(f"✓ Saved PCA subject means CSV: {subject_csv_path}")

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
        f.write("**Dataset:** S1–S10 (10 subjects, balanced 3 sessions per condition per subject)\n")
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
        f.write("- **Statistics:** `statistical_summary_activation.md`\n\n")
        
        f.write("### 3. PCA Analysis\n")
        f.write("- **Metric:** Magnitude in PC1-PC2 space\n")
        f.write("- **Purpose:** Multivariate comparison of muscle coordination patterns\n")
        f.write("- **Figures:** `figureC_pca_*.svg`\n")
        f.write("- **Statistics:** `statistical_summary_pca.md`\n\n")
        
        f.write("---\n\n")
        
        f.write("## Statistical Testing Approach\n\n")
        
        f.write("### Why Welch's t-test instead of Student's t-test?\n\n")
        f.write("We use **Welch's t-test** (not Student's t-test) because:\n\n")
        f.write("1. **No equal variance assumption:** Student's t-test assumes equal variances (homoscedasticity) between groups, which is often violated in biological data\n")
        f.write("2. **Robust to unequal sample sizes:** Welch's test performs better when group sizes differ\n")
        f.write("3. **Conservative:** When variances are actually equal, Welch's test gives similar results to Student's\n")
        f.write("4. **Recommended default:** Modern statistical guidance recommends Welch's as the default two-sample t-test\n\n")
        f.write("### Normality Assessment: Shapiro-Wilk Test\n\n")
        f.write("We use the **Shapiro-Wilk test** to check if data follows a normal distribution:\n\n")
        f.write("- **H₀:** Data is normally distributed\n")
        f.write("- **H₁:** Data is not normally distributed\n")
        f.write("- **Interpretation:** p ≥ 0.05 suggests normality (fail to reject H₀)\n")
        f.write("- **Note:** Shapiro-Wilk is preferred for small samples (n < 50)\n")
        f.write("- **When non-normal:** Non-parametric tests (Mann-Whitney, Wilcoxon) are more appropriate\n\n")
        
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
        
        f.write("#### 3. Paired Non-Parametric Test: Wilcoxon signed-rank\n")
        f.write("- **Type:** Paired rank-based test\n")
        f.write("- **Assumption:** Matched pairs (same subjects across conditions)\n")
        f.write("- **Use:** Most appropriate for within-subject comparisons\n\n")
        
        f.write("#### 4. Effect Size: Cohen's d\n")
        f.write("- **Metric:** Standardized mean difference\n")
        f.write("- **Interpretation:**\n")
        f.write("  - |d| < 0.2: negligible effect\n")
        f.write("  - |d| < 0.5: small effect\n")
        f.write("  - |d| < 0.8: medium effect\n")
        f.write("  - |d| ≥ 0.8: large effect\n\n")
        
        f.write("#### 5. ANOVA: Three-way comparison\n")
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
        f.write("2. **Rate-based comparisons:** `statistical_summary_activation.md`\n")
        f.write("3. **Task duration (subject-level):** `statistical_summary_duration.md`\n")
        f.write("4. **%MVC (subject-level):** `statistical_summary_mvc.md`\n")
        f.write("5. **PCA comparisons:** `statistical_summary_pca.md`\n\n")
        
        f.write("---\n\n")
        
        f.write("## Figure Reference Guide\n\n")
        f.write("| Figure File | Analysis Type | Statistics File |\n")
        f.write("|-------------|---------------|------------------|\n")
        f.write("| `figureB_object_*.svg` | Temporal comparison (RMS) | `statistical_summary_amplitude.md` |\n")
        f.write("| `figureB_summary_object_1.svg` | Amplitude summary | `statistical_summary_amplitude.md` |\n")
        f.write("| `figureD_channels_*.svg` | Channel-wise RMS | `statistical_summary_amplitude.md` |\n")
        f.write("| `rate_temporal_comparison_object_*.svg` | Rate-based comparison | `statistical_summary_activation.md` |\n")
        f.write("| `figureC_pca_*.svg` | PCA analysis | `statistical_summary_pca.md` |\n")
        f.write("| `mvc_duration_box_violin_bar_combined.svg` | Duration + %MVC overview | `statistical_summary_duration.md`, `statistical_summary_mvc.md` |\n")
        f.write("| `figure_duration_stats.svg` | Task duration | `statistical_summary_duration.md` |\n\n")
        
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

    duration_path = generate_duration_statistics()
    print()

    mvc_path = generate_mvc_statistics()
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
    print(f"  3. {duration_path.name}")
    print(f"  4. {mvc_path.name}")
    print(f"  5. {pca_path.name}")
    print(f"  6. {master_path.name}")
    print("\nThese files contain all statistical tests without cluttering figures.")
    print("="*70)
