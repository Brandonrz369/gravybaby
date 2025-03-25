#!/bin/bash

# VPN Setup Script for Gravy Jobs
# This script helps set up proxy and VPN configurations for web scraping

# Check if required packages are installed
echo "Checking for required packages..."
if ! command -v pip &> /dev/null; then
    echo "pip not found. Installing pip..."
    sudo apt-get update
    sudo apt-get install -y python3-pip
fi

echo "Installing required Python packages..."
pip install requests "requests[socks]" beautifulsoup4

# Create default configuration
echo "Setting up VPN configuration..."
python3 -c "
import os
import json
from pathlib import Path

CONFIG_FILE = 'vpn_config.json'

# Default configuration
DEFAULT_CONFIG = {
    \"proxy_services\": {
        \"enabled\": False,
        \"current_service\": None,
        \"brightdata\": {
            \"enabled\": False,
            \"zone\": \"your_zone_here\",
            \"username\": \"your_username_here\",
            \"password\": \"your_password_here\",
            \"port\": 22225,
            \"country\": \"us\",
            \"session_id\": \"gravy_jobs_session\"
        },
        \"oxylabs\": {
            \"enabled\": False,
            \"username\": \"your_username_here\",
            \"password\": \"your_password_here\",
            \"port\": 10000,
            \"endpoint\": \"us.oxylabs.io\",
            \"country\": \"us\"
        },
        \"smartproxy\": {
            \"enabled\": False,
            \"username\": \"your_username_here\",
            \"password\": \"your_password_here\",
            \"endpoint\": \"us.smartproxy.com\",
            \"port\": 10000
        },
        \"proxymesh\": {
            \"enabled\": False,
            \"username\": \"your_username_here\",
            \"password\": \"your_password_here\",
            \"endpoint\": \"us.proxymesh.com\",
            \"port\": 31280
        },
        \"zenrows\": {
            \"enabled\": False,
            \"api_key\": \"your_api_key_here\",
            \"endpoint\": \"https://api.zenrows.com/v1/\"
        },
        \"scraperapi\": {
            \"enabled\": False,
            \"api_key\": \"your_api_key_here\",
            \"endpoint\": \"http://api.scraperapi.com\"
        }
    },
    \"proxies\": [
        None,  # Direct connection (no proxy)
        {
            \"http\": \"socks5://127.0.0.1:8080\",
            \"https\": \"socks5://127.0.0.1:8080\"
        },
        {
            \"http\": \"socks5://127.0.0.1:8081\", 
            \"https\": \"socks5://127.0.0.1:8081\"
        }
    ],
    \"rotation_settings\": {
        \"delay_between_requests\": {
            \"min\": 2,
            \"max\": 7
        },
        \"retry_delay\": {
            \"min\": 10,
            \"max\": 30
        },
        \"max_retries\": 5,
        \"cache_expiry_hours\": 24,
        \"auto_rotate_on_block\": True
    }
}

# Create or update the config file
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f'Created default configuration in {CONFIG_FILE}')
else:
    print(f'Configuration file {CONFIG_FILE} already exists')
"

# Set up SSH for proxy tunneling (optional)
read -p "Do you want to set up an SSH tunnel for proxy? (y/n): " setup_ssh

if [[ "$setup_ssh" == "y" || "$setup_ssh" == "Y" ]]; then
    echo "Setting up SSH tunnel for proxy..."
    read -p "Enter SSH server (user@hostname): " ssh_server
    
    # Export the SSH server as an environment variable
    echo "export SSH_SERVER=\"$ssh_server\"" >> ~/.bashrc
    export SSH_SERVER="$ssh_server"
    
    # Test SSH connection
    echo "Testing SSH connection..."
    ssh -o BatchMode=yes -o ConnectTimeout=5 $ssh_server echo "SSH connection successful!" || {
        echo "SSH connection failed. Make sure you have SSH keys set up properly."
        echo "You can set up SSH keys with:"
        echo "  ssh-keygen -t rsa"
        echo "  ssh-copy-id $ssh_server"
    }
    
    # Create a test tunnel
    echo "Testing SSH tunnel..."
    ssh -D 8080 -C -q -N -f $ssh_server
    if [ $? -eq 0 ]; then
        echo "SSH tunnel started successfully on port 8080"
        echo "You can use this as a SOCKS proxy in your configuration"
        echo "Killing test tunnel..."
        pkill -f "ssh -D 8080"
    else
        echo "Failed to start SSH tunnel"
    fi
else
    echo "Skipping SSH tunnel setup"
fi

# Create cache directory
mkdir -p cache

echo "VPN setup complete!"
echo "You can now configure commercial proxy services in vpn_config.json"
echo "or use the VPNManager.enable_commercial_proxy() method in your code."
echo "Example usage:"
echo "from vpn_manager import VPNManager"
echo "vpn = VPNManager()"
echo "vpn.enable_commercial_proxy('brightdata', username='your_user', password='your_pass')"