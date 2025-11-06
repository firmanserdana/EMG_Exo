# EMG Comparative Analysis - Usage Guide

## Quick Reference

### Run the Analysis
```bash
cd md-emg-python
python emg_comparative_analysis.py
```

### Generated Files (17 total)
```
results-analysis/
├── figureB_object_0.png through figureB_object_5.png        (6 files, ~2.4 MB each)
├── figureC_heatmap_object_0.png through _5.png              (6 files, ~260 KB each)
├── figureC_pca_single_objects_0.png                         (1 file, ~880 KB)
├── figureC_pca_all_objects_0_1_2_3_4_5.png                 (1 file, ~1.7 MB)
├── time_consumption_comparison.png                          (1 file, ~300 KB)
└── time_consumption_analysis.csv                            (1 file, ~1 KB)
```

## What You Get

### Figure B: Raw EMG Data Comparison
- **Files**: `figureB_object_0.png` through `figureB_object_5.png`
- **Content**: Raw EMG signal traces across 3 conditions
- **Use**: Select 1 for main text, 5 for supplementary materials
- **Shows**: 
  - Passive glove (top)
  - Active glove (middle)
  - No glove (bottom)
  - Multiple channels with vertical offset for clarity

### Figure C: Heatmaps
- **Files**: `figureC_heatmap_object_0.png` through `figureC_heatmap_object_5.png`
- **Content**: Channel activity heatmaps (3 conditions side-by-side)
- **Use**: Select the clearest pattern for main text
- **Shows**:
  - Spatial distribution (channels on Y-axis)
  - Temporal progression (time on X-axis)
  - Activation intensity (color coded)

### Figure C: PCA Analysis
- **Files**: 
  - `figureC_pca_single_objects_0.png` (for main text)
  - `figureC_pca_all_objects_0_1_2_3_4_5.png` (optional)
- **Content**: 3D scatter plot showing condition separability
- **Shows**:
  - Principal components 1, 2, 3
  - Explained variance ratios
  - Color-coded by condition and object

### Time Consumption Analysis
- **Files**: 
  - `time_consumption_comparison.png` (visualization)
  - `time_consumption_analysis.csv` (statistics)
- **Content**: Task duration comparison across conditions
- **Shows**:
  - Box plots by condition
  - Violin plots by object and condition
  - Count, mean, std, min, max statistics

## For Your First Run

### Option 1: Demo Mode (No Data Needed)
Just run the script! It will generate synthetic data automatically:
```bash
python emg_comparative_analysis.py
```

### Option 2: With Your Data
1. **Organize your data:**
```
data/healthy/
├── passive_glove/
│   ├── session_01.npy
│   └── timestamps.json  (optional)
├── active_glove/
│   └── session_01.npy
└── no_glove/
    └── session_01.npy
```

2. **Run the analysis:**
```bash
python emg_comparative_analysis.py
```

3. **Find your results:**
```bash
ls results-analysis/
```

## Data Format Requirements

### .npy Files
- 2D array: (n_samples, n_channels) where n_channels ≥ 32
- First 32 channels (0-31) will be used
- Sampling rate: 1000 Hz (default, configurable)

### timestamps.json (Optional)
Use the provided template:
```bash
cp timestamps_template.json data/healthy/passive_glove/timestamps.json
# Edit the file with your gesture timing information
```

Format:
```json
{
  "gesture_starts": {
    "0": [1.5, 5.2, 8.9],
    "1": [2.1, 6.3, 9.5],
    ...
  },
  "gesture_ends": {
    "0": [2.0, 5.7, 9.4],
    "1": [2.6, 6.8, 10.0],
    ...
  }
}
```

## Documentation

- **QUICK_START.md** - 5-minute tutorial
- **ANALYSIS_README.md** - Comprehensive guide
- **IMPLEMENTATION_SUMMARY_ANALYSIS.md** - Technical details
- **timestamps_template.json** - Data annotation template

## Customization

### Change Number of Gestures
Edit `emg_comparative_analysis.py`:
```python
NUM_GESTURES = 4  # Change from 6 to 4
```

### Change Conditions
```python
CONDITIONS = ['Condition A', 'Condition B', 'Condition C']
CONDITION_COLORS = {
    'Condition A': '#FF0000',
    'Condition B': '#00FF00',
    'Condition C': '#0000FF'
}
```

### Change Sampling Rate
```python
FS_HZ = 2000  # Change from 1000 to 2000 Hz
```

## Troubleshooting

### No data found
- Check that data is in `data/healthy/`
- Data should be in subdirectories (one per condition)
- Or just run in demo mode to test

### Figures look empty
- Verify .npy file format
- Check timestamps.json format
- Ensure sampling rate is correct

### Memory error
- Process fewer objects at a time
- Reduce window size in PCA analysis
- Downsample data before analysis

## Tips for Publication

1. **Review all 6 objects** before selecting for main text
2. **Use consistent object** across all figure types
3. **Save high-quality versions** (already 300 DPI)
4. **Document selection criteria** in methods section
5. **Include all 6 in supplementary** materials

## Example Output

When you run the analysis, you'll see:
```
======================================================================
EMG Comparative Analysis
======================================================================

=== Generating example data ===
Note: Using synthetic data for demonstration.

======================================================================
Generating Figures
======================================================================

--- Figure B: Raw Data Comparison ---
Generating Figure B for Object 0...
Saved: results-analysis/figureB_object_0.png
...

--- Figure C: Heatmaps ---
Generating heatmap for Object 0...
Saved: results-analysis/figureC_heatmap_object_0.png
...

--- Figure C: PCA Analysis ---
Generating PCA for Object 0 (best object)...
Saved: results-analysis/figureC_pca_single_objects_0.png
...

--- Time Consumption Analysis ---
=== Time Consumption Analysis ===
        Condition  Object  count      mean       std    min    max
0    Active glove       0      3  3.837667  0.549458  3.206  4.205
...

======================================================================
Analysis Complete!
======================================================================

All figures saved in: results-analysis
```

## Next Steps

1. ✅ Run demo mode to verify installation
2. ✅ Review generated figures
3. ✅ Organize your real data
4. ✅ Run analysis with your data
5. ✅ Select best figures for publication
6. ✅ Prepare supplementary materials

---

**Need Help?**
- Read `QUICK_START.md` for step-by-step instructions
- See `ANALYSIS_README.md` for detailed documentation
- Check `timestamps_template.json` for data format example

**Ready to Start?**
```bash
cd md-emg-python
python emg_comparative_analysis.py
```
