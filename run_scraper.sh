#!/bin/bash

# Script to run the Gravy Jobs scraper with custom search queries and license management

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                   Show this help message"
    echo "  -q, --query QUERY            Custom search query for Claude to process"
    echo "  -l, --license-key KEY        Set license key for premium features"
    echo "  -c, --configure-claude KEY   Configure Claude API key"
    echo "  -s, --setup-proxy SERVICE    Setup a commercial proxy service"
    echo "  --fingerprint-on             Enable browser fingerprinting"
    echo "  --fingerprint-off            Disable browser fingerprinting"
    echo "  --test                       Run in test mode without scraping"
    echo ""
    echo "Examples:"
    echo "  $0 --query \"Find DevOps jobs in Seattle\""
    echo "  $0 --license-key TEST-KEY-12345"
    echo "  $0 --setup-proxy brightdata"
    echo ""
}

# Default values
CUSTOM_QUERY=""
LICENSE_KEY=""
CLAUDE_KEY=""
SETUP_PROXY=""
FINGERPRINT_SETTING=""
TEST_MODE=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -q|--query)
            CUSTOM_QUERY="$2"
            shift 2
            ;;
        -l|--license-key)
            LICENSE_KEY="$2"
            shift 2
            ;;
        -c|--configure-claude)
            CLAUDE_KEY="$2"
            shift 2
            ;;
        -s|--setup-proxy)
            SETUP_PROXY="$2"
            shift 2
            ;;
        --fingerprint-on)
            FINGERPRINT_SETTING="on"
            shift
            ;;
        --fingerprint-off)
            FINGERPRINT_SETTING="off"
            shift
            ;;
        --test)
            TEST_MODE=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
    echo "Python 3 is required but not installed."
    exit 1
fi

# Check if required packages are installed
pip3 install -q requests "requests[socks]" beautifulsoup4

# If license key is provided, set it using a Python script
if [[ -n "$LICENSE_KEY" ]]; then
    echo "Setting license key..."
    python3 -c "
import sys
try:
    from vpn_manager import VPNManager
    vpn = VPNManager()
    status = vpn.set_license_key('$LICENSE_KEY')
    print(f\"License status: {'Valid' if status.get('valid', False) else 'Invalid'}. Valid until: {status.get('valid_until', 'N/A')}\")
    print(f\"Enabled features: {', '.join(status.get('enabled_features', ['basic_scraping']))}\")
except Exception as e:
    print(f\"Error setting license key: {e}\")
    sys.exit(1)
"
fi

# If Claude API key is provided, configure it
if [[ -n "$CLAUDE_KEY" ]]; then
    echo "Configuring Claude API..."
    python3 -c "
import sys
try:
    from vpn_manager import VPNManager
    vpn = VPNManager()
    vpn.configure_claude_integration(api_key='$CLAUDE_KEY')
    print(\"Claude API key configured successfully\")
except Exception as e:
    print(f\"Error configuring Claude API: {e}\")
    sys.exit(1)
"
fi

# If proxy setup is requested
if [[ -n "$SETUP_PROXY" ]]; then
    echo "Setting up proxy service: $SETUP_PROXY"
    python3 test_proxies.py --setup --service "$SETUP_PROXY"
fi

# If fingerprint setting is provided
if [[ "$FINGERPRINT_SETTING" == "on" ]]; then
    echo "Enabling browser fingerprinting..."
    python3 -c "
import json
import os
try:
    config_file = 'vpn_config.json'
    with open(config_file, 'r') as f:
        config = json.load(f)
    config['browser_fingerprints']['enabled'] = True
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    print('Browser fingerprinting enabled')
except Exception as e:
    print(f'Error: {e}')
"
elif [[ "$FINGERPRINT_SETTING" == "off" ]]; then
    echo "Disabling browser fingerprinting..."
    python3 -c "
import json
import os
try:
    config_file = 'vpn_config.json'
    with open(config_file, 'r') as f:
        config = json.load(f)
    config['browser_fingerprints']['enabled'] = False
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    print('Browser fingerprinting disabled')
except Exception as e:
    print(f'Error: {e}')
"
fi

# Check if email password is set (original requirement)
if [ -z "$EMAIL_PASSWORD" ]; then
  echo "Please set your EMAIL_PASSWORD environment variable first."
  echo "Example: export EMAIL_PASSWORD='your-email-app-password'"
  exit 1
fi

# Run the job scraper
echo "Starting Gravy Jobs scraper..."

# Build the command with options
COMMAND="python job_scraper.py"

# Add query if provided
if [[ -n "$CUSTOM_QUERY" ]]; then
    COMMAND="$COMMAND --query \"$CUSTOM_QUERY\""
fi

# Add test mode if requested
if [[ "$TEST_MODE" -eq 1 ]]; then
    COMMAND="$COMMAND --test"
fi

# Run the command in the background
eval "$COMMAND &"

echo "Job scraper started in background. Check job_scraper.log for details."
echo "To stop the scraper, run: pkill -f job_scraper.py"