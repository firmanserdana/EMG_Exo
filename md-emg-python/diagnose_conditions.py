"""
Quick diagnostic to verify condition differences
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Read the statistics
df = pd.read_csv('results-analysis/channel_rms_stats_object_1.csv')

# Overall statistics
print("="*70)
print("CONDITION COMPARISON - Object 1")
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
print(f"  Passive glove: {passive_mean:6.2f} ({passive_mean/active_mean:.2f}x)")
print(f"  No glove:      {noglove_mean:6.2f} ({noglove_mean/active_mean:.2f}x)")

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

# 1. Box plot
ax = axes[0, 0]
order = ['Active glove', 'Passive glove', 'No glove']
sns.boxplot(data=df, x='Condition', y='Mean_RMS', order=order, ax=ax, palette='Set2')
ax.set_title('RMS Distribution by Condition', fontweight='bold', fontsize=12)
ax.set_ylabel('Mean RMS (a.u.)', fontsize=10)
ax.set_xlabel('')
ax.grid(True, alpha=0.3, axis='y')

# 2. Bar plot with error bars
ax = axes[0, 1]
summary_plot = df.groupby('Condition')['Mean_RMS'].agg(['mean', 'std']).reindex(order)
x = np.arange(len(order))
bars = ax.bar(x, summary_plot['mean'], yerr=summary_plot['std'], 
              capsize=5, alpha=0.7, edgecolor='black', linewidth=1.5)
bars[0].set_color('#ff7f0e')  # Active - orange
bars[1].set_color('#1f77b4')  # Passive - blue
bars[2].set_color('#2ca02c')  # No glove - green
ax.set_xticks(x)
ax.set_xticklabels(order, rotation=15, ha='right')
ax.set_ylabel('Mean RMS (a.u.)', fontsize=10)
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
ax.set_ylabel('Mean RMS (a.u.)', fontsize=10)
ax.set_title('Per-Channel RMS Comparison', fontweight='bold', fontsize=12)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# 4. Ratio visualization
ax = axes[1, 1]
ratios_data = []
for ch in range(32):
    active_val = df[(df['Condition']=='Active glove') & (df['Channel']==ch)]['Mean_RMS'].values
    passive_val = df[(df['Condition']=='Passive glove') & (df['Channel']==ch)]['Mean_RMS'].values
    noglove_val = df[(df['Condition']=='No glove') & (df['Channel']==ch)]['Mean_RMS'].values
    
    if len(active_val) > 0 and len(passive_val) > 0:
        ratios_data.append({
            'Channel': ch,
            'Active/Passive': active_val[0] / (passive_val[0] + 1e-9),
            'Active/NoGlove': active_val[0] / (noglove_val[0] + 1e-9) if len(noglove_val) > 0 else np.nan
        })

if ratios_data:
    ratios_df = pd.DataFrame(ratios_data)
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=1.5, label='Equal (ratio=1.0)')
    ax.plot(ratios_df['Channel'], ratios_df['Active/Passive'], 
            marker='s', label='Active/Passive', linewidth=2, color='#e377c2')
    if 'Active/NoGlove' in ratios_df.columns:
        ax.plot(ratios_df['Channel'], ratios_df['Active/NoGlove'], 
                marker='^', label='Active/NoGlove', linewidth=2, color='#9467bd')
    
    ax.fill_between(ratios_df['Channel'], 0, 1.0, alpha=0.1, color='green', 
                     label='Active < comparison (expected)')
    ax.fill_between(ratios_df['Channel'], 1.0, ax.get_ylim()[1], alpha=0.1, color='red',
                     label='Active > comparison')

ax.set_xlabel('Channel', fontsize=10)
ax.set_ylabel('Amplitude Ratio', fontsize=10)
ax.set_title('Active Glove Ratios (< 1.0 expected)', fontweight='bold', fontsize=12)
ax.legend(fontsize=8, loc='upper right')
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('results-analysis/diagnostic_condition_comparison.png', dpi=300, bbox_inches='tight')
print(f"\n✓ Diagnostic plot saved: results-analysis/diagnostic_condition_comparison.png")
plt.close()

print("\n" + "="*70)
