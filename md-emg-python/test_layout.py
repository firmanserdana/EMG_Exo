#!/usr/bin/env python3
"""Test script to visualize the offset channel layout"""
import numpy as np
import matplotlib.pyplot as plt
from emg_comparative_analysis import get_svg_heatmap_layout, draw_svg_heatmap

# Load the layout
layout = get_svg_heatmap_layout()

print(f"Layout loaded: {len(layout.nodes)} channels in {len(layout.rows)} rows")
print(f"Rows: {[len(r) for r in layout.rows]}")

# Create test data - gradient values to show the offset pattern
test_values = np.arange(32, dtype=float)

# Create figure
fig, ax = plt.subplots(figsize=(12, 8))
fig.patch.set_alpha(0.0)
ax.set_facecolor('white')

# Draw heatmap with test gradient
sm = draw_svg_heatmap(
    ax,
    test_values,
    layout=layout,
    cmap='viridis',
    annotate=True,
    spacing_scale=0.9,
    blur_sigma=3.0
)

# Add colorbar
cbar = plt.colorbar(sm, ax=ax, label='Channel Index')

# Add title
ax.set_title('EMG Channel Layout with Offset Pattern\n' +
             'Upper band: 3 rows (6 channels each, 2nd row offset)\n' +
             'Lower band: 2 rows (7 channels each, 1st row offset)',
             fontsize=14, fontweight='bold', pad=20)

# Remove axis
ax.set_aspect('equal')
ax.axis('off')

plt.tight_layout()
plt.savefig('/home/runner/work/EMG_Exo/EMG_Exo/md-emg-python/results-analysis/test_layout_visualization.svg',
            format='svg', bbox_inches='tight', dpi=150)
plt.savefig('/home/runner/work/EMG_Exo/EMG_Exo/md-emg-python/results-analysis/test_layout_visualization.png',
            format='png', bbox_inches='tight', dpi=150)
print("\n✓ Test visualization saved to results-analysis/test_layout_visualization.svg/.png")
