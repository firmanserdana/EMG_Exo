# EMG_Exo Project Cleanup Script
# This script creates backups and removes old files that have been refactored

# Define backup directory
$backupDir = "backup_old_files"

# Create backup directory if it doesn't exist
if (-not (Test-Path $backupDir)) {
    New-Item -Path $backupDir -ItemType Directory
    Write-Output "Created backup directory: $backupDir"
}

# Files that have been refactored into the new structure
$refactoredFiles = @(
    "emg_acquisition.py",
    "delsys_trigno_emg.py",
    "emg_processing.py",
    "emg_decoder.py",
    "unity_hand_interface.py",
    "emg_selector.py",
    "utilities.py",
    "ini.py",
    "main.py",
    "simple_demo.py",
    "delsys_trigno_demo.py"
)

# Make backup copies
foreach ($file in $refactoredFiles) {
    if (Test-Path $file) {
        Write-Output "Backing up $file to $backupDir"
        Copy-Item $file -Destination $backupDir
    } else {
        Write-Output "File not found: $file"
    }
}

# Default is dry-run mode (don't actually delete files)
$dryRun = $true

# Check if the -execute parameter was provided
if ($args -contains "-execute") {
    $dryRun = $false
}

# Remove files or simulate removal
if ($dryRun) {
    Write-Output "`nDRY RUN - No files will be deleted. Files that would be removed:"
    foreach ($file in $refactoredFiles) {
        if (Test-Path $file) {
            Write-Output "Would remove $file"
        }
    }
    Write-Output "`nThis was a dry run. No files were actually removed."
    Write-Output "To remove files, run with the -execute parameter:"
    Write-Output ".\cleanup.ps1 -execute"
} else {
    Write-Output "`nREMOVING FILES..."
    foreach ($file in $refactoredFiles) {
        if (Test-Path $file) {
            Write-Output "Removing $file"
            Remove-Item $file
        }
    }
    Write-Output "`nCleanup complete. Files were backed up to $backupDir directory."
}
