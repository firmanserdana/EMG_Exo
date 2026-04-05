"""
Quick diagnostic to verify condition differences
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# Process all objects
results_dir = Path('results-analysis')
csv_files = sorted(results_dir.glob('channel_rms_stats_object_*.csv'))

if not csv_files:
    print("Error: No channel statistics CSV files found!")
    exit(1)

print("="*70)
print(f"FOUND {len(csv_files)} OBJECTS TO ANALYZE")
print("="*70)

for csv_file in csv_files:
    # Extract object ID from filename
    object_id = csv_file.stem.split('_')[-1]
    
    # Read the statistics
    df = pd.read_csv(csv_file)

    # Overall statistics
    print("\n" + "="*70)
    print(f"CONDITION COMPARISON - Object {object_id}")
    print("="*70)
    summary = df.groupby('Condition')['Mean_RMS'].agg(['mean', 'std', 'median', 'min', 'max', 'count'])
    print("\nOverall RMS Statistics by Condition:")
    print(summary.to_string())

    print("\n" + "="*70)
    print("EXPECTED vs ACTUAL")
    print("="*70)
    print("Expected pattern: Active glove < Passive glove ≈ No glove")
    print("  (Active glove should assist movement, reducing muscle effort)")

    active_mean = df[df['Condition']=='Active glove']['Mean_RMS'].mean()
    passive_mean = df[df['Condition']=='Passive glove']['Mean_RMS'].mean()
    noglove_mean = df[df['Condition']=='No glove']['Mean_RMS'].mean()

    print(f"\nActual pattern:")
    print(f"  Active glove:  {active_mean:6.2f} (1.00x)")
    if active_mean > 1e-9:  # Guard against division by zero
        print(f"  Passive glove: {passive_mean:6.2f} ({passive_mean/active_mean:.2f}x)")
        print(f"  No glove:      {noglove_mean:6.2f} ({noglove_mean/active_mean:.2f}x)")
    else:
        print(f"  Passive glove: {passive_mean:6.2f} (ratio N/A - active mean too low)")
        print(f"  No glove:      {noglove_mean:6.2f} (ratio N/A - active mean too low)")

    if active_mean < passive_mean and active_mean < noglove_mean:
        print("\n✓ Pattern MATCHES expectation")
    elif active_mean > passive_mean and active_mean > noglove_mean:
        print("\n✗ Pattern REVERSED - Active glove shows HIGHEST activation")
        print("  Possible causes:")
        print("  1. Condition labels may be swapped in data files")
        print("  2. Active glove increases compensatory muscle effort")
        print("  3. Data preprocessing issue")
    else:
        print("\n? Pattern is MIXED - needs investigation")

    # Create visualization
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Box plot - order: No glove, Passive, Active
    ax = axes[0, 0]
    order = ['No glove', 'Passive glove', 'Active glove']
    sns.boxplot(data=df, x='Condition', y='Mean_RMS', order=order, ax=ax, palette='Set2')
    ax.set_title('RMS Distribution by Condition', fontweight='bold', fontsize=12)
    ax.set_ylabel('Mean RMS (% MVC)', fontsize=10)
    ax.set_xlabel('')
    ax.grid(True, alpha=0.3, axis='y')

    # 2. Bar plot with error bars - order: No glove, Passive, Active
    ax = axes[0, 1]
    summary_plot = df.groupby('Condition')['Mean_RMS'].agg(['mean', 'std']).reindex(order)
    x = np.arange(len(order))
    bars = ax.bar(x, summary_plot['mean'], yerr=summary_plot['std'], 
                  capsize=5, alpha=0.7, edgecolor='black', linewidth=1.5)
    bars[0].set_color('#2ca02c')  # No glove - green
    bars[1].set_color('#1f77b4')  # Passive - blue
    bars[2].set_color('#ff7f0e')  # Active - orange
    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=15, ha='right')
    ax.set_ylabel('Mean RMS (% MVC)', fontsize=10)
    ax.set_title('Mean RMS by Condition (±SD)', fontweight='bold', fontsize=12)
    ax.grid(True, alpha=0.3, axis='y')

    # 3. Per-channel comparison
    ax = axes[1, 0]
    for condition in order:
        cond_data = df[df['Condition'] == condition].sort_values('Channel')
        color = {'Active glove': '#ff7f0e', 'Passive glove': '#1f77b4', 'No glove': '#2ca02c'}[condition]
        ax.plot(cond_data['Channel'], cond_data['Mean_RMS'], 
                marker='o', label=condition, linewidth=2, alpha=0.8, color=color)

    ax.set_xlabel('Channel', fontsize=10)
    ax.set_ylabel('Mean RMS (% MVC)', fontsize=10)
    ax.set_title('Per-Channel RMS Comparison', fontweight='bold', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 4. Ratio visualization - Passive/NoGlove and Active/NoGlove ratios
    # Ratio > 1 means reduction compared to No glove baseline (good)
    ax = axes[1, 1]
    ratios_data = []
    clip_val = 10.0  # cap ratios to limit visual spikes from very small denominators

    # Get actual channel list from data
    channels = sorted(df['Channel'].dropna().unique())

    for ch in channels:
        active_val = df[(df['Condition']=='Active glove') & (df['Channel']==ch)]['Mean_RMS'].values
        passive_val = df[(df['Condition']=='Passive glove') & (df['Channel']==ch)]['Mean_RMS'].values
        noglove_val = df[(df['Condition']=='No glove') & (df['Channel']==ch)]['Mean_RMS'].values

        if len(noglove_val) > 0 and noglove_val[0] > 1e-9:
            ratios_data.append({
                'Channel': ch,
                'Passive/NoGlove': noglove_val[0] / (passive_val[0] + 1e-9) if len(passive_val) > 0 else np.nan,
                'Active/NoGlove': noglove_val[0] / (active_val[0] + 1e-9) if len(active_val) > 0 else np.nan
            })

    if ratios_data:
        ratios_df = pd.DataFrame(ratios_data)
        ratios_df['Passive/NoGlove'] = ratios_df['Passive/NoGlove'].clip(upper=clip_val)
        ratios_df['Active/NoGlove'] = ratios_df['Active/NoGlove'].clip(upper=clip_val)
        ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=1.5, label='Equal (ratio=1.0)')
        ax.plot(ratios_df['Channel'], ratios_df['Passive/NoGlove'], 
                marker='s', label='NoGlove/Passive', linewidth=2, color='#1f77b4')
        ax.plot(ratios_df['Channel'], ratios_df['Active/NoGlove'], 
                marker='^', label='NoGlove/Active', linewidth=2, color='#ff7f0e')
        
        # Fill: >1 means condition reduces EMG vs NoGlove (good)
        finite_max = np.nanmax(ratios_df[['Passive/NoGlove', 'Active/NoGlove']].values)
        upper_lim = max(3.0, (finite_max * 1.1) if finite_max and finite_max > 0 else 3.0)
        shade_top = max(upper_lim, 5.0)
        ax.fill_between(ratios_df['Channel'], 1.0, shade_top, alpha=0.1, color='green', 
                         label='Reduction vs No glove (>1 = good)')
        ax.fill_between(ratios_df['Channel'], 0, 1.0, alpha=0.1, color='red',
                         label='Increase vs No glove (<1 = bad)')
    else:
        upper_lim = 3.0
        shade_top = 5.0

    ax.set_xlabel('Channel', fontsize=10)
    ax.set_ylabel('EMG Reduction Ratio (NoGlove / Condition)', fontsize=10)
    ax.set_title('EMG Reduction Ratios (> 1.0 = muscle effort reduced)', fontweight='bold', fontsize=12)
    ax.legend(fontsize=8, loc='upper right')
    ax.set_ylim(0, upper_lim)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    
    # Save as both PNG and SVG
    output_png = results_dir / f'diagnostic_condition_comparison_object_{object_id}.png'
    output_svg = results_dir / f'diagnostic_condition_comparison_object_{object_id}.svg'
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    plt.savefig(output_svg, bbox_inches='tight', format='svg')
    print(f"✓ Diagnostic plots saved:")
    print(f"  - {output_png}")
    print(f"  - {output_svg}")
    plt.close()

print("\n" + "="*70)
print("ALL DIAGNOSTICS COMPLETE")
print("="*70)
