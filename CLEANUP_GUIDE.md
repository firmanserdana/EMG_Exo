# EMG_Exo Project Cleanup Guide

After restructuring the EMG_Exo project into a proper Python package, several old files are now redundant and should be removed or archived. This document outlines which files should be handled and why.

## Files to Remove

These files have been refactored into the new package structure and are no longer needed:

| Old File | New Location |
|----------|-------------|
| `emg_acquisition.py` | `emg_exo/core/acquisition/sessantaquatro.py` |
| `delsys_trigno_emg.py` | `emg_exo/core/acquisition/trigno.py` |
| `emg_processing.py` | `emg_exo/core/processing/processor.py` |
| `emg_decoder.py` | `emg_exo/core/decoder/decoder.py` |
| `unity_hand_interface.py` | `emg_exo/core/interface/unity.py` |
| `emg_selector.py` | `emg_exo/core/acquisition/factory.py` |
| `utilities.py` | `emg_exo/core/utils/utils.py` |
| `ini.py` | `emg_exo/config/config.py` and `emg_exo/config/default_config.json` |
| `main.py` | `emg_exo/apps/main_app.py` |
| `simple_demo.py` | To be reimplemented as `emg_exo/apps/simple_demo.py` |
| `delsys_trigno_demo.py` | To be reimplemented as `emg_exo/apps/delsys_trigno_demo.py` |

## Files to Preserve (For Now)

These files either haven't been migrated yet or are still needed for reference:

| File | Reason |
|------|--------|
| `data_recorder.py` | Still needed for raw data recording (to be migrated) |
| `emg_visualizer.py` | Still needed for visualization (to be migrated) |
| `demo.py` | Still needed for demonstration purposes (to be migrated) |
| `requirements.txt` | Keep for reference, but `setup.py` is now the main dependency source |
| Documentation files | Keep all documentation (`.md` files) |

## Cleanup Steps

1. **Backup**: Before removing any files, create a backup:
   ```
   mkdir backup_old_files
   Copy-Item "emg_acquisition.py", "delsys_trigno_emg.py", "emg_processing.py", "emg_decoder.py", "unity_hand_interface.py", "emg_selector.py", "utilities.py", "ini.py", "main.py", "simple_demo.py", "delsys_trigno_demo.py" -Destination "backup_old_files"
   ```

2. **Removal**: After confirming backups, remove the old files:
   ```
   Remove-Item "emg_acquisition.py", "delsys_trigno_emg.py", "emg_processing.py", "emg_decoder.py", "unity_hand_interface.py", "emg_selector.py", "utilities.py", "ini.py", "main.py", "simple_demo.py", "delsys_trigno_demo.py"
   ```

3. **Pending Migrations**: Take note of modules that still need to be migrated:
   - `data_recorder.py` → `emg_exo/apps/data_recorder.py`
   - `emg_visualizer.py` → `emg_exo/apps/emg_visualizer.py` 
   - `demo.py` → `emg_exo/apps/demo.py`

## Next Steps

1. Complete the migration of remaining modules
2. Create more comprehensive unit tests in `emg_exo/tests/`
3. Update and expand documentation in `emg_exo/docs/`
4. Add proper documentation strings to all modules
