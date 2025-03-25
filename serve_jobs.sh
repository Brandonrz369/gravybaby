#!/bin/bash

# Simple web server to view job reports
# This is useful if browsers have trouble opening local files directly

echo "🌐 Starting web server for Gravy Jobs reports"

# Check if we're in the right directory
if [ ! -f "gravy_jobs.html" ] && [ ! -f "gravy_jobs_app.py" ]; then
    echo "Error: Not in the Gravy Jobs directory."
    echo "Please run this script from the Gravy Jobs directory."
    exit 1
fi

# Function to find an available port
find_port() {
    local port=$1
    while netstat -tuln | grep ":$port " > /dev/null; do
        port=$((port + 1))
    done
    echo $port
}

# Find an available port starting from 8000
PORT=$(find_port 8000)

echo "Starting server on port $PORT..."
echo "You can view your job reports at:"
echo "    http://localhost:$PORT/gravy_jobs.html"
echo ""
echo "Press Ctrl+C to stop the server when done"

# Check which Python version is available
if command -v python3 &> /dev/null; then
    # Python 3 server
    python3 -m http.server $PORT
elif command -v python &> /dev/null; then
    # Try Python (might be Python 3)
    python -m http.server $PORT 2>/dev/null || python -m SimpleHTTPServer $PORT
else
    echo "Error: Python not found. Please install Python to use this feature."
    exit 1
fi