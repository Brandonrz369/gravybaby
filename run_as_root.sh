#!/bin/bash

# This script runs Gravy Jobs with root permissions to avoid permission issues
echo "🍯 Running Gravy Jobs as root 🍯"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs root privileges to fix permission issues."
    echo "Running with sudo..."
    sudo "$0" "$@"
    exit $?
fi

# We're now running as root
echo "Running as root. This will fix permission issues with files."

# Change to the script's directory
cd "$(dirname "$0")"

# Fix permissions on all data files
echo "Fixing permissions on data files..."
chown -R $SUDO_USER:$SUDO_USER .

# Make sure the execute permissions are set
chmod +x launch_gravy_jobs.sh
chmod +x vpn_setup.sh
chmod +x gravy_jobs_gui.py

# Run the app
echo "Launching Gravy Jobs..."
sudo -u $SUDO_USER ./launch_gravy_jobs.sh