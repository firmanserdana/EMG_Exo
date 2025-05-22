# Next Steps in EMG_Exo Refactoring

This document outlines the remaining tasks to complete the EMG_Exo project refactoring.

## Remaining Modules to Migrate

- [ ] `data_recorder.py` → `emg_exo/apps/data_recorder.py`
- [ ] `emg_visualizer.py` → `emg_exo/apps/visualizer.py`
- [ ] `demo.py` → `emg_exo/apps/demo.py`

## Testing Infrastructure

- [ ] Add more comprehensive unit tests
  - [ ] Test acquisition modules with mock hardware
  - [ ] Test signal processing with known test data
  - [ ] Test decoder with pre-recorded datasets
  - [ ] Test Unity interface with mock socket connections

## Documentation

- [ ] Set up Sphinx documentation
- [ ] Write detailed API documentation
- [ ] Create architecture diagrams
- [ ] Prepare user tutorials and examples

## Configuration

- [ ] Add more detailed configuration options
- [ ] Create user-friendly configuration utilities
- [ ] Add validation for configuration parameters

## User Experience

- [ ] Create a graphical configuration tool
- [ ] Improve command-line interfaces
- [ ] Add progress indicators for long operations

## Cleanup

- [ ] Remove old files (see `CLEANUP_GUIDE.md`)
- [ ] Update imports in any remaining modules
- [ ] Verify package installation and execution

## Next Features

- [ ] Add support for more EMG hardware
- [ ] Implement more advanced signal processing algorithms
- [ ] Add real-time data visualization improvements
- [ ] Implement adaptive calibration procedures
