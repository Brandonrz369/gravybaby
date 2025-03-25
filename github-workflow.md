# GitHub Workflow File Content

## Copy everything below this line:

name: Build Windows Executable

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
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests beautifulsoup4 pyinstaller

    - name: Build with PyInstaller
      run: |
        pyinstaller gravy_jobs.spec

    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: GravyJobs-Windows
        path: dist/GravyJobs.exe