#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cleanup script to remove old Python files that have been migrated to the new package structure.
"""

import os
import sys
import shutil
import argparse


# Files that have been refactored into the new structure
REFACTORED_FILES = [
    # Core functionality
    "emg_acquisition.py",
    "delsys_trigno_emg.py",
    "emg_processing.py",
    "emg_decoder.py",
    "unity_hand_interface.py",
    "emg_selector.py",
    "utilities.py",
    "ini.py",
    
    # Demo/sample files
    "simple_demo.py",
    "delsys_trigno_demo.py",
    
    # Main application
    "main.py"
]

# Files to preserve (not migrated yet or still needed)
PRESERVE_FILES = [
    # Data handling
    "data_recorder.py",
    "emg_visualizer.py",
    "demo.py",
    
    # Documentation and config
    "README.md",
    "INSTALLATION.md",
    "API_DOCUMENTATION.md",
    "FEATURES_GUIDE.md",
    "MIGRATION_GUIDE.md",
    "summary.md",
    "requirements.txt",
    "setup.py"
]


def backup_files(files, backup_dir):
    """Backup specified files to backup directory.
    
    Args:
        files: List of files to backup
        backup_dir: Directory to back up files to
    """
    os.makedirs(backup_dir, exist_ok=True)
    
    for file in files:
        if os.path.exists(file):
            print(f"Backing up {file} to {backup_dir}")
            shutil.copy2(file, os.path.join(backup_dir, file))


def remove_files(files, dry_run=True):
    """Remove specified files.
    
    Args:
        files: List of files to remove
        dry_run: If True, only print files that would be removed
    """
    for file in files:
        if os.path.exists(file):
            if dry_run:
                print(f"Would remove {file}")
            else:
                print(f"Removing {file}")
                os.remove(file)
        else:
            print(f"File not found: {file}")


def main():
    """Main function for cleanup script."""
    parser = argparse.ArgumentParser(description="Clean up old Python files after migration")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup of files")
    parser.add_argument("--execute", action="store_true", help="Actually remove files (default: dry run)")
    
    args = parser.parse_args()
    
    # Create backup if requested
    if not args.no_backup:
        backup_dir = "backup_old_files"
        backup_files(REFACTORED_FILES, backup_dir)
        print(f"\nFiles backed up to '{backup_dir}' directory")
    
    # Remove files or simulate removal
    print("\nFiles to be removed:")
    remove_files(REFACTORED_FILES, dry_run=not args.execute)
    
    if not args.execute:
        print("\nThis was a dry run. No files were actually removed.")
        print("To remove files, run with --execute")


if __name__ == "__main__":
    main()
