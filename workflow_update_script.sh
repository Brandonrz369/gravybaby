#!/bin/bash

# This script creates/updates a GitHub workflow file using the GitHub API
# You'll need to run this script with your GitHub token as an environment variable

# Get the current content of the workflow file to get the SHA
CONTENT=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/Brandonrz369/gravybaby/contents/.github/workflows/build-windows.yml)

# Extract the SHA if the file exists
if [[ $CONTENT != *"Not Found"* ]]; then
  SHA=$(echo $CONTENT | jq -r .sha)
  echo "Found existing file with SHA: $SHA"
else
  SHA=""
  echo "No existing file found, will create new file"
fi

# Contents of the workflow file
WORKFLOW_CONTENT='name: Build Windows Executable

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build-windows:
    runs-on: windows-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.9"

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests beautifulsoup4 pyinstaller

    - name: Build with PyInstaller
      run: |
        pyinstaller --onefile --name GravyJobs --add-data "*.html;." --add-data "*.json;." --hidden-import tkinter --hidden-import tkinter.ttk --hidden-import tkinter.scrolledtext --hidden-import tkinter.messagebox gravy_jobs_gui.py

    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: GravyJobs-Windows
        path: dist/GravyJobs.exe'

# Base64 encode the content
ENCODED_CONTENT=$(echo "$WORKFLOW_CONTENT" | base64 -w 0)

# Commit message
COMMIT_MESSAGE="Update build-windows.yml workflow"

# JSON payload
if [[ -n "$SHA" ]]; then
  # Update existing file
  JSON="{\"message\":\"$COMMIT_MESSAGE\",\"content\":\"$ENCODED_CONTENT\",\"sha\":\"$SHA\"}"
else
  # Create new file
  JSON="{\"message\":\"$COMMIT_MESSAGE\",\"content\":\"$ENCODED_CONTENT\"}"
fi

# Update the file on GitHub
curl -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  -d "$JSON" \
  https://api.github.com/repos/Brandonrz369/gravybaby/contents/.github/workflows/build-windows.yml