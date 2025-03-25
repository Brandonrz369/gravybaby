#!/bin/bash

# Gravy Jobs Launcher Script
# This script launches the Gravy Jobs app with minimal setup

echo "🍯 Starting Gravy Jobs App... 🍯"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages
echo "Installing dependencies..."
pip install --quiet requests beautifulsoup4

# Launch the app
echo "Launching Gravy Jobs App..."
python gravy_jobs_app.py

# Deactivate virtual environment when done
deactivate