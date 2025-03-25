# Gravy Jobs - Windows Setup Guide

This guide provides step-by-step instructions for setting up and using Gravy Jobs on Windows, including the VPN rotation, browser fingerprinting, and Claude AI integration features.

## Installation

1. **Download the Latest Release**:
   - Download the latest GravyJobs-Windows.zip from the releases page
   - Extract the zip file to a location of your choice

2. **Install Required Dependencies**:
   - Run the included `install_dependencies.bat` file to install required Python packages
   - If you plan to use SSH tunneling, install PuTTY from [putty.org](https://www.putty.org/)

3. **Configure Email Notifications** (Optional):
   - Create a file named `email_config.txt` in the application directory
   - Add your email credentials in the format: `EMAIL_PASSWORD=your_app_password`

## Basic Usage

1. **Running the Application**:
   - Double-click `GravyJobs.exe` to start the application
   - Or run from command prompt: `GravyJobs.exe`

2. **Command Line Options**:
   ```
   GravyJobs.exe --query "Find remote developer jobs"
   GravyJobs.exe --headless
   GravyJobs.exe --location "Seattle, WA"
   ```

## Premium Features Setup

### Setting Up VPN Rotation

1. **Configure Standard Proxies**:
   - Edit `vpn_config.json` to add your proxy information
   - Or use the SSH tunneling feature with PuTTY

2. **Enable Browser Fingerprinting**:
   ```
   GravyJobs.exe --fingerprint-on
   ```

3. **Set Up Commercial Proxy Services**:
   - Get credentials from your proxy provider (Bright Data, Oxylabs, etc.)
   - Configure using the command line:
   ```
   GravyJobs.exe --setup-proxy brightdata
   ```
   - Or edit `vpn_config.json` directly to add your credentials

### Claude AI Integration

1. **Get Claude API Key**:
   - Sign up for Claude API access at [anthropic.com](https://www.anthropic.com/)
   - Generate an API key in your account dashboard

2. **Configure Claude API**:
   ```
   GravyJobs.exe --configure-claude YOUR_API_KEY
   ```

3. **Create Custom Search Templates** (Optional):
   - Edit `vpn_config.json` and add custom templates to the `custom_search_templates` section

### License Activation

1. **Purchase a License Key**:
   - Contact us to purchase a license for premium features

2. **Activate Your License**:
   ```
   GravyJobs.exe --license-key YOUR_LICENSE_KEY
   ```

## Troubleshooting

### Common Issues

1. **Application won't start**:
   - Make sure you have the latest .NET runtime installed
   - Try running as administrator

2. **403 Errors from job sites**:
   - Enable browser fingerprinting with `--fingerprint-on`
   - Set up a commercial proxy service for better results

3. **VPN issues**:
   - Check your proxy settings in `vpn_config.json`
   - If using SSH tunnels, ensure PuTTY is properly installed and configured

4. **Claude API not working**:
   - Verify your API key is correct and active
   - Check your internet connection

## Testing Features

Use the included test script to check if features are working correctly:

```
GravyJobs.exe --test-features all
```

Or test specific features:

```
GravyJobs.exe --test-features vpn
GravyJobs.exe --test-features claude
GravyJobs.exe --test-features license
```

## Upgrading

To upgrade to a newer version:

1. Download the latest release
2. Extract to a new folder
3. Copy your existing `vpn_config.json` to the new folder
4. If you had an `email_config.txt` file, copy that as well

Your existing configuration and license will be preserved.

## Getting Help

If you encounter issues not covered in this guide:

1. Check the full documentation in the `docs` folder
2. Run with the `--debug` flag to generate detailed logs
3. Contact our support team with the generated logs