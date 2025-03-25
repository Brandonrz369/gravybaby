#!/usr/bin/env python3
import requests
import base64
import os
import json
import sys

# GitHub repository details
REPO_OWNER = "Brandonrz369"
REPO_NAME = "gravybaby"
WORKFLOW_PATH = ".github/workflows/build-windows.yml"

# GitHub token (should be provided as an argument)
if len(sys.argv) < 2:
    print("Usage: python update_github_workflow.py YOUR_GITHUB_TOKEN")
    sys.exit(1)
    
token = sys.argv[1]

# Workflow file content
workflow_content = """name: Build Windows Executable

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
        path: dist/GravyJobs.exe
"""

# Headers for GitHub API requests
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

# Get the current file (if it exists) to get its SHA
url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{WORKFLOW_PATH}"
response = requests.get(url, headers=headers)
sha = None

if response.status_code == 200:
    # File exists, get the SHA
    sha = response.json()["sha"]
    print(f"Found existing workflow file with SHA: {sha}")
elif response.status_code == 404:
    # File doesn't exist yet
    print("Workflow file does not exist yet, creating new file")
else:
    # Error occurred
    print(f"Error getting workflow file: {response.status_code}")
    print(response.text)
    sys.exit(1)

# Prepare the payload for the API request
payload = {
    "message": "Update build-windows.yml workflow file",
    "content": base64.b64encode(workflow_content.encode()).decode()
}

if sha:
    payload["sha"] = sha

# Create or update the workflow file
response = requests.put(url, headers=headers, json=payload)

if response.status_code in (200, 201):
    print("Successfully updated workflow file!")
else:
    print(f"Error updating workflow file: {response.status_code}")
    print(response.text)