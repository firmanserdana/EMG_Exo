# EMG Comparative Analysis

This document explains how to use the `emg_comparative_analysis.py` script to generate publication-ready figures comparing EMG data across different experimental conditions.

## Overview

The analysis script generates the following figures for research papers:

- **Figure B**: Raw EMG data comparison across 3 conditions (6 objects analyzed, 1 shown in main text + 5 in supplementary materials)
- **Figure C (Heatmaps)**: Channel activity heatmaps for 3 conditions (6 objects analyzed, best one shown in main text)
- **Figure C (PCA)**: Principal Component Analysis visualization (flexible: show 1 or all 6 objects depending on space)
- **Time Consumption Analysis**: Statistical comparison of task duration across conditions

## Data Requirements

### Expected Data Structure

The script expects EMG data in the following structure:

```
md-emg-python/data/healthy/
├── condition1/
│   ├── session_01.npy
│   ├── session_02.npy
│   └── timestamps.json
├── condition2/
│   ├── session_01.npy
│   └── timestamps.json
└── condition3/
    ├── session_01.npy
    └── timestamps.json
```

### Data Format

#### .npy Files
- Each `.npy` file should contain EMG data as a 2D NumPy array
- Shape: `(n_samples, n_channels)` where `n_channels` >= 32
- The script automatically extracts channels 0-31 (first 32 channels)
- Sampling rate assumed: 1000 Hz

#### timestamps.json Format (Optional but Recommended)

The `timestamps.json` file identifies when specific gestures/objects start and end:

```json
{
  "gesture_starts": {
    "0": [1.5, 5.2, 8.9],
    "1": [2.1, 6.3, 9.5],
    "2": [3.0, 7.1, 10.2],
    "3": [3.8, 7.9, 11.0],
    "4": [4.5, 8.5, 11.8],
    "5": [5.2, 9.2, 12.5]
  },
  "gesture_ends": {
    "0": [2.0, 5.7, 9.4],
    "1": [2.6, 6.8, 10.0],
    "2": [3.5, 7.6, 10.7],
    "3": [4.3, 8.4, 11.5],
    "4": [5.0, 9.0, 12.3],
    "5": [5.7, 9.7, 13.0]
  }
}
```

- Keys "0" through "5" represent the 6 different objects/gestures
- Times are in seconds
- Each array contains start/end times for multiple trials of that gesture

**Without timestamps.json**: The script will treat each entire session as a single segment for object 0.

## Installation

1. Install required Python packages:

```bash
cd md-emg-python
pip install -r requirements.txt
```

Required packages:
- numpy
- pandas
- matplotlib
- seaborn
- scikit-learn

## Usage

### Basic Usage

Simply run the script from the `md-emg-python` directory:

```bash
cd md-emg-python
python emg_comparative_analysis.py
```

### With Real Data

1. Organize your data according to the structure shown above
2. Place data in `md-emg-python/data/healthy/`
3. Run the script:

```bash
python emg_comparative_analysis.py
```

### Demo Mode (Without Real Data)

The script automatically generates synthetic example data if no real data is found. This is useful for:
- Testing the installation
- Understanding the output format
- Verifying the analysis pipeline

## Output

### Generated Files

All output files are saved in `md-emg-python/results-analysis/`:

#### Figure B: Raw Data Comparison
- `figureB_object_0.png` through `figureB_object_5.png` (6 files)
- Shows raw EMG traces across 3 conditions
- Each subplot shows one condition with multiple channels
- **Recommendation**: Use object 0 in main text, others in supplementary materials

#### Figure C: Heatmaps
- `figureC_heatmap_object_0.png` through `figureC_heatmap_object_5.png` (6 files)
- Shows channel activity (RMS) over time as a heatmap
- One heatmap per condition (3 conditions side-by-side)
- **Recommendation**: Select the clearest/most representative object for main text

#### Figure C: PCA Analysis
- `figureC_pca_single_objects_0.png` - Single object PCA (for main text)
- `figureC_pca_all_objects_0_1_2_3_4_5.png` - All 6 objects (optional)
- 3D scatter plot showing separation between conditions
- Includes explained variance ratios for each principal component

#### Time Consumption Analysis
- `time_consumption_comparison.png` - Visual comparison (box plots and violin plots)
- `time_consumption_analysis.csv` - Statistical summary table

### Example Output Structure

```
results-analysis/
├── figureB_object_0.png          # Main text candidate
├── figureB_object_1.png          # Supplementary
├── figureB_object_2.png          # Supplementary
├── figureB_object_3.png          # Supplementary
├── figureB_object_4.png          # Supplementary
├── figureB_object_5.png          # Supplementary
├── figureC_heatmap_object_0.png  # Main text candidate
├── figureC_heatmap_object_1.png  # Supplementary
├── ... (more heatmaps)
├── figureC_pca_single_objects_0.png    # Main text (1 object)
├── figureC_pca_all_objects_0_1_2_3_4_5.png  # Optional (all objects)
├── time_consumption_comparison.png
└── time_consumption_analysis.csv
```

## Customization

### Modifying the Script

The script is modular and can be easily customized:

#### Change Conditions
Edit the `CONDITIONS` list at the top of the script:

```python
CONDITIONS = ['Passive glove', 'Active glove', 'No glove']
```

#### Change Number of Objects
Modify the range in the main function:

```python
# For 4 objects instead of 6
for obj_id in range(4):
    analyzer.figure_b_raw_comparison(data_dict, object_id=obj_id)
```

#### Change Sampling Rate
Edit the `FS_HZ` constant:

```python
FS_HZ = 2000  # For 2 kHz sampling rate
```

#### Customize Colors
Modify the `CONDITION_COLORS` dictionary:

```python
CONDITION_COLORS = {
    'Passive glove': '#FF0000',  # Red
    'Active glove': '#00FF00',   # Green
    'No glove': '#0000FF'        # Blue
}
```

### Advanced Customization

The `EMGAnalyzer` class contains methods that can be overridden or modified:

```python
# Change RMS window size
def compute_rms(self, data, window_ms=100):  # Default: 100ms
    # Change to 50ms:
    window_ms = 50
    # ... rest of method
```

```python
# Change PCA window parameters
def figure_c_pca(self, ...):
    window_size = int(0.25 * FS_HZ)  # 250ms windows
    step_size = int(0.125 * FS_HZ)   # 125ms step
    # Modify these values as needed
```

## Interpretation Guide

### Figure B: Raw Data Comparison
- **Purpose**: Show raw EMG signal characteristics across conditions
- **What to look for**: 
  - Amplitude differences between conditions
  - Temporal patterns and burst characteristics
  - Channel-to-channel variability
- **Selection criteria**: Choose the object that shows the clearest differences

### Figure C: Heatmaps
- **Purpose**: Visualize spatial-temporal activation patterns
- **What to look for**:
  - Hot spots indicate high muscle activity
  - Temporal progression of activation (left to right)
  - Channel distribution (vertical axis)
- **Selection criteria**: Choose the object with most distinct patterns across conditions

### Figure C: PCA
- **Purpose**: Demonstrate condition separability in feature space
- **What to look for**:
  - Cluster separation between conditions
  - Explained variance (higher is better)
  - Overlap indicates similar muscle activation patterns
- **Decision**: Show single object if space is limited, all 6 if space allows

### Time Consumption Analysis
- **Purpose**: Quantify task completion time differences
- **Metrics**:
  - Mean duration per condition
  - Variability (std, min, max)
  - Statistical comparisons via box/violin plots
- **Interpretation**: Longer durations may indicate difficulty or different strategies

## Troubleshooting

### No data found
**Problem**: Script reports "No subdirectories found in data/healthy"

**Solution**: 
1. Check that data is in `md-emg-python/data/healthy/`
2. Ensure data is organized in subdirectories (one per condition)
3. Verify .npy files exist in subdirectories

### Memory errors with large files
**Problem**: Script crashes with large .npy files

**Solution**:
1. Process data in smaller chunks
2. Reduce the number of segments analyzed
3. Downsample data before analysis

### Figures look wrong
**Problem**: Generated figures don't match expected patterns

**Solution**:
1. Verify data format (channels, sampling rate)
2. Check timestamps.json format
3. Ensure conditions are correctly labeled
4. Review channel indices (should be 0-31)

### Import errors
**Problem**: `ModuleNotFoundError` when running script

**Solution**:
```bash
pip install -r requirements.txt
```

## Tips for Publication

1. **Figure Selection**:
   - Review all 6 objects for each figure type
   - Select the most representative/clearest for main text
   - Include all 6 in supplementary materials

2. **Figure Quality**:
   - Generated at 300 DPI (publication quality)
   - Can be further edited in vector graphics software if needed
   - Consider adjusting font sizes for your target journal

3. **Statistical Analysis**:
   - Use the time_consumption_analysis.csv for statistical tests
   - Consider adding statistical significance markers to plots
   - Report effect sizes and confidence intervals

4. **Reproducibility**:
   - Document which object was selected for main text
   - Keep the timestamps.json files for reproducibility
   - Save the analysis script version with your data

## Support

For questions or issues:
1. Check that your data matches the expected format
2. Run in demo mode first to verify installation
3. Review error messages carefully
4. Check that all dependencies are installed

## Citation

If you use this analysis pipeline in your research, please cite the relevant papers and acknowledge the EMG_Exo repository.
