# Quick Start Guide: EMG Comparative Analysis

This guide will get you up and running with the EMG comparative analysis in 5 minutes.

## Step 1: Install Dependencies (1 minute)

```bash
cd md-emg-python
pip install -r requirements.txt
```

## Step 2: Run Demo Analysis (1 minute)

Test the installation with synthetic data:

```bash
python emg_comparative_analysis.py
```

This will:
- Generate synthetic EMG data for demonstration
- Create all analysis figures
- Save outputs to `results-analysis/` directory

**Expected output:**
```
======================================================================
EMG Comparative Analysis
======================================================================
=== Generating example data ===
Note: Using synthetic data for demonstration.

--- Figure B: Raw Data Comparison ---
Generating Figure B for Object 0...
Saved: results-analysis/figureB_object_0.png
...

Analysis Complete!
All figures saved in: results-analysis
```

## Step 3: Check Generated Figures (1 minute)

View the generated figures:

```bash
# On Linux/Mac
xdg-open results-analysis/figureB_object_0.png
xdg-open results-analysis/figureC_heatmap_object_0.png
xdg-open results-analysis/figureC_pca_single_objects_0.png

# On Windows
start results-analysis/figureB_object_0.png
```

Or browse the directory:
```bash
ls -lh results-analysis/
```

## Step 4: Prepare Your Real Data (2 minutes)

### Option A: Simple Structure (No Timestamps)

```bash
# Create condition directories
mkdir -p data/healthy/passive_glove
mkdir -p data/healthy/active_glove
mkdir -p data/healthy/no_glove

# Place your .npy files
cp your_data/passive_session1.npy data/healthy/passive_glove/
cp your_data/active_session1.npy data/healthy/active_glove/
cp your_data/no_glove_session1.npy data/healthy/no_glove/
```

### Option B: With Timestamps (Recommended)

```bash
# Create condition directories
mkdir -p data/healthy/passive_glove
mkdir -p data/healthy/active_glove
mkdir -p data/healthy/no_glove

# Copy template and edit timestamps
cp timestamps_template.json data/healthy/passive_glove/timestamps.json
# Edit the JSON file with your gesture timing information

# Place your .npy files
cp your_data/passive_session1.npy data/healthy/passive_glove/
# ... repeat for other conditions
```

**Edit timestamps.json:**
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

## Step 5: Run Analysis with Your Data (30 seconds)

```bash
python emg_comparative_analysis.py
```

The script will automatically:
- Detect your data structure
- Load .npy files
- Parse timestamps (if available)
- Generate all figures
- Save results to `results-analysis/`

## What You Get

### 17 Output Files

**Figure B - Raw Data (6 files)**
- `figureB_object_0.png` through `figureB_object_5.png`
- Shows raw EMG traces across 3 conditions
- Use 1 in main text, 5 in supplementary

**Figure C - Heatmaps (6 files)**
- `figureC_heatmap_object_0.png` through `figureC_heatmap_object_5.png`
- Channel activity heatmaps for 3 conditions
- Select best one for main text

**Figure C - PCA (2 files)**
- `figureC_pca_single_objects_0.png` - Single object (main text)
- `figureC_pca_all_objects_0_1_2_3_4_5.png` - All objects (optional)

**Time Analysis (2 files)**
- `time_consumption_comparison.png` - Visual comparison
- `time_consumption_analysis.csv` - Statistics table

**Overview (1 file)**
- `analysis_overview.png` - All figure types in one view

## Common Issues & Quick Fixes

### Issue: "No module named 'numpy'"
**Fix:**
```bash
pip install -r requirements.txt
```

### Issue: "No subdirectories found in data/healthy"
**Fix:** 
- Check your data directory structure
- Make sure data is in subdirectories (one per condition)
- Or run with synthetic data first: `python emg_comparative_analysis.py`

### Issue: Figures look empty
**Fix:**
- Verify .npy file format (n_samples × n_channels, at least 32 channels)
- Check timestamps.json format if using gesture segmentation
- Verify sampling rate is 1000 Hz (or update `FS_HZ` in script)

### Issue: Memory error with large files
**Fix:**
- Process fewer objects at a time
- Downsample data before analysis
- Reduce window size in PCA analysis

## Next Steps

1. **Review All Figures**: Look at all 6 objects for each figure type
2. **Select Best for Publication**: Choose most representative figures for main text
3. **Customize if Needed**: Edit script to adjust colors, labels, etc.
4. **Read Full Documentation**: See `ANALYSIS_README.md` for detailed information

## Data Format Requirements

### .npy Files
- Shape: `(n_samples, n_channels)` where n_channels ≥ 32
- Data type: float or int
- First 32 channels will be used (indices 0-31)
- Sampling rate: 1000 Hz (default)

### timestamps.json (Optional)
- JSON format with "gesture_starts" and "gesture_ends"
- Keys: "0" through "5" (as strings)
- Values: Arrays of timestamps in seconds
- Must have same number of starts and ends per gesture

## Example Directory Structure

```
md-emg-python/
├── emg_comparative_analysis.py    # Main script
├── ANALYSIS_README.md              # Full documentation
├── QUICK_START.md                  # This file
├── timestamps_template.json        # Template for timestamps
├── data/
│   └── healthy/
│       ├── passive_glove/
│       │   ├── session_01.npy
│       │   └── timestamps.json
│       ├── active_glove/
│       │   ├── session_01.npy
│       │   └── timestamps.json
│       └── no_glove/
│           ├── session_01.npy
│           └── timestamps.json
└── results-analysis/              # Generated figures
    ├── figureB_object_*.png
    ├── figureC_heatmap_object_*.png
    ├── figureC_pca_*.png
    └── time_consumption_*.png/csv
```

## Getting Help

1. **Run Demo Mode**: Test with synthetic data to verify installation
2. **Check Documentation**: Read `ANALYSIS_README.md` for detailed info
3. **Verify Data Format**: Ensure .npy files match expected structure
4. **Test Small Dataset First**: Start with one condition to verify pipeline

## Tips for Success

✅ **DO:**
- Test with demo data first
- Use timestamps.json for accurate gesture segmentation
- Review all 6 objects before selecting for publication
- Save generated figures at 300 DPI (already default)

❌ **DON'T:**
- Mix different sampling rates in same analysis
- Forget to verify channel indices (0-31)
- Skip the demo run before using real data
- Delete the results-analysis folder before backing up

## Publication Checklist

- [ ] Run analysis on all conditions
- [ ] Review all 6 objects for each figure type
- [ ] Select best figure for main text (typically object 0)
- [ ] Prepare supplementary figures (objects 1-5)
- [ ] Check figure quality (300 DPI)
- [ ] Document which object is shown in main text
- [ ] Save time_consumption_analysis.csv for statistics
- [ ] Include methods description in paper

---

**Total Time:** 5 minutes to first results! 🚀

For more details, see `ANALYSIS_README.md`.
