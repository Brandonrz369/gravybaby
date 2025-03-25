#!/bin/bash

# Gravy Jobs GUI Launcher
# This script ensures all dependencies are installed and launches the GUI app
# with improved handling for Windows environments

echo "🍯 Launching Gravy Jobs GUI... 🍯"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    exit 1
fi

# Check for tkinter (this is a system package in many Linux distributions)
# Try to import tkinter
if ! python3 -c "import tkinter" &> /dev/null; then
    echo "Tkinter is not installed. Attempting to install..."
    
    # Try to detect the package manager and install tkinter
    # Note: Only use sudo for the package installation, not for running the app
    if command -v apt-get &> /dev/null; then
        echo "Detected apt package manager. Installing python3-tk..."
        sudo apt-get install -y python3-tk
    elif command -v dnf &> /dev/null; then
        echo "Detected dnf package manager. Installing python3-tkinter..."
        sudo dnf install -y python3-tkinter
    elif command -v yum &> /dev/null; then
        echo "Detected yum package manager. Installing python3-tkinter..."
        sudo yum install -y python3-tkinter
    elif command -v pacman &> /dev/null; then
        echo "Detected pacman package manager. Installing python-tkinter..."
        sudo pacman -S --noconfirm python-tkinter
    else
        echo "ERROR: Could not detect package manager to install tkinter."
        echo "Please install tkinter manually:"
        echo "  - For Ubuntu/Debian: sudo apt-get install python3-tk"
        echo "  - For Fedora: sudo dnf install python3-tkinter"
        echo "  - For RHEL/CentOS: sudo yum install python3-tkinter"
        echo "  - For Arch Linux: sudo pacman -S python-tkinter"
        exit 1
    fi
    
    # Check if installation was successful
    if ! python3 -c "import tkinter" &> /dev/null; then
        echo "ERROR: Failed to install tkinter."
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages (except tkinter, which is a system package)
echo "Installing dependencies..."
pip install --quiet requests beautifulsoup4

# Don't try to fix permissions as non-root
# Just inform the user about potential permission issues
echo "Note: Some files may have permission issues if previously created as root."
echo "If you have issues accessing files, try running with sudo or fixing permissions."

# Launch the GUI as the regular user (not as root)
echo "Starting Gravy Jobs GUI..."
python gravy_jobs_gui.py --headless

# Deactivate virtual environment when done
deactivate