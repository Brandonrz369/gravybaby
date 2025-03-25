#!/usr/bin/env python3

"""
VPN Manager for Gravy Jobs
This module handles VPN switching and proxy management to help avoid 
getting blocked by job sites like Indeed and RemoteOK.

Features:
- Auto-switching between proxies when blocked
- Session management with cookies and headers
- Random user agent rotation
- Configurable delays between requests
- Fallback handling with cached data
- Support for commercial proxy rotation APIs:
  - Bright Data (formerly Luminati)
  - Oxylabs
  - SmartProxy
  - ProxyMesh
  - ZenRows
  - ScraperAPI

Requirements:
- requests
- requests[socks] (for SOCKS proxy support)
- beautifulsoup4
- playwright (optional, for headless browser mode)
"""

import os
import json
import time
import random
import logging
import requests
import subprocess
import socket
import platform
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='vpn_manager.log'
)
logger = logging.getLogger('vpn_manager')

# Base directory for cache and settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
CONFIG_FILE = os.path.join(BASE_DIR, "vpn_config.json")

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# Default configuration
DEFAULT_CONFIG = {
    "proxy_services": {
        "enabled": False,
        "current_service": None,
        "brightdata": {
            "enabled": False,
            "zone": "your_zone_here",
            "username": "your_username_here",
            "password": "your_password_here",
            "port": 22225,
            "country": "us",
            "session_id": "gravy_jobs_session",
            "country_pool": ["us", "uk", "ca", "au", "de", "fr", "jp", "sg"] # Countries to rotate through
        },
        "oxylabs": {
            "enabled": False,
            "username": "your_username_here",
            "password": "your_password_here",
            "port": 10000,
            "endpoint": "us.oxylabs.io",
            "country": "us",
            "country_pool": ["us", "gb", "ca", "au", "de", "fr", "jp", "sg"] # Countries to rotate through
        },
        "smartproxy": {
            "enabled": False,
            "username": "your_username_here",
            "password": "your_password_here",
            "endpoint": "us.smartproxy.com",
            "port": 10000,
            "country_pool": ["us", "gb", "ca", "au", "de", "fr", "jp", "sg"] # Countries to rotate through
        },
        "proxymesh": {
            "enabled": False,
            "username": "your_username_here",
            "password": "your_password_here",
            "endpoint": "us.proxymesh.com",
            "port": 31280
        },
        "zenrows": {
            "enabled": False,
            "api_key": "your_api_key_here",
            "endpoint": "https://api.zenrows.com/v1/",
            "country_pool": ["us", "gb", "ca", "au", "de", "fr", "jp", "sg"] # Countries to rotate through
        },
        "scraperapi": {
            "enabled": False,
            "api_key": "your_api_key_here",
            "endpoint": "http://api.scraperapi.com",
            "country_pool": ["us", "uk", "ca", "au", "de", "fr", "jp", "sg"] # Countries to rotate through
        }
    },
    "browser_fingerprints": {
        "enabled": True,
        "fingerprints": [],  # Will be populated on first run
        "current_fingerprint_index": 0
    },
    "licensing": {
        "license_key": "",
        "valid_until": None,
        "enabled_features": ["basic_scraping"],
        "license_server": "https://api.gravyjobs.com/license/verify",
        "last_verified": None
    },
    "claude_integration": {
        "enabled": False,
        "api_key": "",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "model": "claude-3-opus-20240229",
        "custom_search_templates": {
            "default": "Search for entry-level programming jobs with keywords like 'beginner', 'junior', 'html', 'css'.",
            "msp_provider": "Search for companies looking for Managed Service Providers (MSPs) with keywords like 'IT support', 'managed services', 'IT outsourcing'.",
            "data_science": "Search for data science and machine learning jobs with keywords like 'data scientist', 'machine learning', 'AI', 'analytics'.",
            "devops": "Search for DevOps and cloud infrastructure jobs with keywords like 'AWS', 'Azure', 'DevOps', 'Kubernetes', 'Docker'.",
            "remote_only": "Search for fully remote software development jobs with keywords like 'remote', 'work from home', 'distributed team'."
        }
    },
    "proxies": [
        None,  # Direct connection (no proxy)
        {
            "http": "socks5://127.0.0.1:8080",
            "https": "socks5://127.0.0.1:8080"
        },
        {
            "http": "socks5://127.0.0.1:8081", 
            "https": "socks5://127.0.0.1:8081"
        }
    ],
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ],
    "rotation_settings": {
        "delay_between_requests": {
            "min": 2,
            "max": 7
        },
        "retry_delay": {
            "min": 10,
            "max": 30
        },
        "max_retries": 5,
        "cache_expiry_hours": 24,
        "auto_rotate_on_block": True,
        "rotate_ip_with_fingerprint": True,  # When rotating browser fingerprint, also rotate IP
        "fingerprint_rotation_frequency": 10  # Rotate fingerprint every X requests
    },
    "site_settings": {
        "indeed.com": {
            "high_scrutiny": True,
            "extra_delay": 2,
            "max_requests_per_session": 10
        },
        "remoteok.com": {
            "high_scrutiny": True,
            "extra_delay": 1,
            "max_requests_per_session": 5
        },
        "linkedin.com": {
            "high_scrutiny": True,
            "extra_delay": 3,
            "max_requests_per_session": 8
        },
        "freelancer.com": {
            "high_scrutiny": False,
            "extra_delay": 0,
            "max_requests_per_session": 20
        },
        "craigslist.org": {
            "high_scrutiny": False,
            "extra_delay": 1,
            "max_requests_per_session": 15
        }
    },
    "current_proxy_index": 0,
    "current_user_agent_index": 0,
    "site_request_counts": {},
    "total_request_count": 0
}

def load_config():
    """Load VPN/proxy configuration from file, or create default if not exists"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            # Initialize browser fingerprints if not already present
            if "browser_fingerprints" not in config:
                config["browser_fingerprints"] = DEFAULT_CONFIG["browser_fingerprints"]
            
            # Generate initial fingerprints if none exist
            if not config["browser_fingerprints"]["fingerprints"]:
                # Generate 5 default fingerprints
                fingerprints = []
                for _ in range(5):
                    fingerprints.append(generate_browser_fingerprint())
                config["browser_fingerprints"]["fingerprints"] = fingerprints
                
            # Add licensing section if not present
            if "licensing" not in config:
                config["licensing"] = DEFAULT_CONFIG["licensing"]
                
            # Add Claude integration if not present
            if "claude_integration" not in config:
                config["claude_integration"] = DEFAULT_CONFIG["claude_integration"]
                
            # Ensure every proxy service has a country_pool
            for service in ["brightdata", "oxylabs", "smartproxy", "zenrows", "scraperapi"]:
                if service in config["proxy_services"] and "country_pool" not in config["proxy_services"][service]:
                    config["proxy_services"][service]["country_pool"] = DEFAULT_CONFIG["proxy_services"][service]["country_pool"]
            
            # Initialize total_request_count if not present
            if "total_request_count" not in config:
                config["total_request_count"] = 0
                
            # Add new rotation settings if not present
            if "rotate_ip_with_fingerprint" not in config["rotation_settings"]:
                config["rotation_settings"]["rotate_ip_with_fingerprint"] = DEFAULT_CONFIG["rotation_settings"]["rotate_ip_with_fingerprint"]
                config["rotation_settings"]["fingerprint_rotation_frequency"] = DEFAULT_CONFIG["rotation_settings"]["fingerprint_rotation_frequency"]
            
            # Save updated config
            save_config(config)
            return config
        except Exception as e:
            logger.error(f"Error loading VPN config: {e}")
    
    # Create default config if file doesn't exist or had errors
    config = DEFAULT_CONFIG.copy()
    
    # Generate initial fingerprints
    fingerprints = []
    for _ in range(5):
        fingerprints.append(generate_browser_fingerprint())
    config["browser_fingerprints"]["fingerprints"] = fingerprints
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config

def save_config(config):
    """Save updated configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def is_proxy_working(proxy):
    """Test if a proxy is working by making a request to a test URL"""
    if proxy is None:
        return True  # Direct connection is assumed to work
    
    try:
        test_url = "https://www.google.com"
        response = requests.get(
            test_url, 
            proxies=proxy, 
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Proxy test failed: {e}")
        return False

def rotate_proxy(config):
    """Switch to the next available proxy"""
    current_index = config["current_proxy_index"]
    proxies = config["proxies"]
    
    # Try each proxy in sequence until we find a working one
    for _ in range(len(proxies)):
        current_index = (current_index + 1) % len(proxies)
        current_proxy = proxies[current_index]
        
        if is_proxy_working(current_proxy):
            config["current_proxy_index"] = current_index
            save_config(config)
            
            # Log the proxy change
            proxy_info = current_proxy if current_proxy else "Direct Connection"
            logger.info(f"Switched to proxy: {proxy_info}")
            
            return current_proxy
    
    # If no proxy works, return None (direct connection)
    logger.warning("No working proxies found, using direct connection")
    config["current_proxy_index"] = proxies.index(None) if None in proxies else 0
    save_config(config)
    return None

def get_random_user_agent(config):
    """Get a random user agent from the config"""
    current_index = config["current_user_agent_index"]
    user_agents = config["user_agents"]
    
    # Rotate to next user agent
    current_index = (current_index + 1) % len(user_agents)
    config["current_user_agent_index"] = current_index
    save_config(config)
    
    return user_agents[current_index]

def generate_browser_fingerprint():
    """
    Generate a consistent browser fingerprint with realistic properties
    
    Returns:
        Dictionary containing browser fingerprint properties
    """
    # List of common screen resolutions
    screen_resolutions = [
        "1920x1080", "1366x768", "1536x864", "1440x900", 
        "1280x720", "1600x900", "1280x800", "1920x1200",
        "2560x1440", "3840x2160", "1280x1024", "1024x768"
    ]
    
    # List of common color depths
    color_depths = [24, 32, 16]
    
    # List of common platforms
    platforms = [
        "Win32", "MacIntel", "Linux x86_64", "Win64", "Linux armv8l"
    ]
    
    # List of common languages
    languages = [
        "en-US", "en-GB", "en-CA", "en", "fr-FR", "de-DE", 
        "es-ES", "it-IT", "pt-BR", "ru-RU", "ja-JP", "zh-CN"
    ]
    
    # Generate a consistent fingerprint
    import hashlib
    import random
    
    # Generate a random seed that will be consistent across sessions
    seed = random.randint(1, 1000000)
    random.seed(seed)
    
    # Select fingerprint properties
    resolution = random.choice(screen_resolutions)
    width, height = map(int, resolution.split('x'))
    color_depth = random.choice(color_depths)
    platform = random.choice(platforms)
    language = random.choice(languages)
    
    # Generate WebGL renderer and vendor
    webgl_vendors = ["Google Inc.", "Intel Inc.", "NVIDIA Corporation", "AMD", "Apple"]
    webgl_renderers = [
        "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)",
        "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0)",
        "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)",
        "ANGLE (Intel, Intel(R) HD Graphics 620 Direct3D11 vs_5_0 ps_5_0)",
        "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)",
        "Apple M1",
        "Apple M2"
    ]
    
    webgl_vendor = random.choice(webgl_vendors)
    webgl_renderer = random.choice(webgl_renderers)
    
    # Generate a canvas fingerprint hash (simulated)
    canvas_hash = hashlib.md5(f"{seed}".encode()).hexdigest()
    
    # Generate font list length (simulated)
    font_list_length = random.randint(30, 200)
    
    # Generate time zone offset
    timezone_offset = random.choice([-480, -420, -360, -300, -240, -180, -120, -60, 0, 60, 120, 180, 240, 300, 360, 420])
    
    # Generate audio fingerprint (simulated)
    audio_hash = hashlib.sha1(f"{seed}+audio".encode()).hexdigest()
    
    # Create fingerprint dictionary
    fingerprint = {
        "user_agent": None,  # Will be set later
        "screen": {
            "width": width,
            "height": height,
            "color_depth": color_depth
        },
        "platform": platform,
        "languages": [language],
        "timezone_offset": timezone_offset,
        "webgl": {
            "vendor": webgl_vendor,
            "renderer": webgl_renderer
        },
        "canvas_hash": canvas_hash,
        "audio_hash": audio_hash,
        "font_list_length": font_list_length,
        # Add a unique identifier for this fingerprint
        "id": hashlib.sha256(f"{seed}+{resolution}+{platform}+{webgl_vendor}".encode()).hexdigest()[:16]
    }
    
    return fingerprint

def get_browser_headers(config, referer=None, fingerprint=None):
    """
    Generate realistic browser headers based on fingerprint
    
    Args:
        config: Configuration dictionary
        referer: Optional referrer URL
        fingerprint: Optional browser fingerprint dictionary
        
    Returns:
        Dictionary of HTTP headers
    """
    # Get user agent
    user_agent = get_random_user_agent(config)
    
    # Create base headers
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Cache-Control': 'max-age=0',
    }
    
    # Add referer if provided
    if referer:
        headers['Referer'] = referer
    else:
        headers['Referer'] = 'https://www.google.com/'
    
    # Add additional headers if fingerprint is provided
    if fingerprint:
        # Store the user agent in the fingerprint
        fingerprint['user_agent'] = user_agent
        
        # Add Accept-Language based on fingerprint
        if fingerprint.get('languages') and len(fingerprint['languages']) > 0:
            primary_lang = fingerprint['languages'][0]
            headers['Accept-Language'] = f"{primary_lang},en-US;q=0.9,en;q=0.8"
        
        # Add Sec-Ch-UA headers for browser identification (Chrome-specific)
        if "Chrome" in user_agent:
            chrome_version = None
            if "Chrome/" in user_agent:
                chrome_part = user_agent.split("Chrome/")[1]
                chrome_version = chrome_part.split(" ")[0].split(".")[0]
            
            if chrome_version:
                headers['Sec-Ch-UA'] = f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", ";Not A Brand";v="99"'
                headers['Sec-Ch-UA-Mobile'] = '?0'
                headers['Sec-Ch-UA-Platform'] = f'"{fingerprint.get("platform", "Windows")}"'
        
        # Add viewport and device memory (Chrome-specific)
        if "Chrome" in user_agent:
            screen = fingerprint.get('screen', {})
            if 'width' in screen and 'height' in screen:
                # Calculate a reasonable viewport based on screen size
                viewport_width = min(screen['width'], 1920)  # Cap at 1920 to be realistic
                viewport_height = min(screen['height'], 1080)  # Cap at 1080 to be realistic
                headers['Viewport-Width'] = str(viewport_width)
                headers['Viewport-Height'] = str(viewport_height)
            
            # Add device memory header (Chrome-specific)
            import random
            headers['Device-Memory'] = random.choice(['0.5', '1', '2', '4', '8'])
    
    return headers

def get_cache_key(url, params=None):
    """Generate a cache key from URL and params"""
    if params:
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{url}?{param_str}"
    return url

def get_cached_response(url, params=None, config=None):
    """Check if there's a valid cached response for this URL"""
    if config is None:
        config = load_config()
        
    cache_key = get_cache_key(url, params)
    cache_file = os.path.join(CACHE_DIR, cache_key.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")[:200] + ".json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if cache is still valid
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            expiry_hours = config["rotation_settings"]["cache_expiry_hours"]
            
            if datetime.now() < cache_time + timedelta(hours=expiry_hours):
                logger.info(f"Using cached response for {url}")
                return cache_data["content"]
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
    
    return None

def cache_response(url, content, params=None):
    """Cache a response for future use"""
    cache_key = get_cache_key(url, params)
    cache_file = os.path.join(CACHE_DIR, cache_key.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")[:200] + ".json")
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "content": content
            }, f, ensure_ascii=False)
        logger.info(f"Cached response for {url}")
    except Exception as e:
        logger.error(f"Error caching response: {e}")

def start_ssh_tunnel(port, server):
    """Start an SSH tunnel for SOCKS proxy"""
    try:
        # Check if we're on Windows
        if platform.system() == "Windows":
            # Use Plink (PuTTY's command line interface) on Windows
            if os.path.exists("plink.exe"):
                cmd = ["plink.exe", "-D", str(port), "-N", server]
                subprocess.Popen(cmd)
                logger.info(f"Started SSH tunnel on port {port} using Plink")
            else:
                logger.error("plink.exe not found. Please install PuTTY.")
                return False
        else:
            # Use SSH on Unix/Linux/Mac
            cmd = ["ssh", "-D", str(port), "-C", "-q", "-N", server]
            subprocess.Popen(cmd)
            logger.info(f"Started SSH tunnel on port {port}")
        
        # Wait for the tunnel to be established
        time.sleep(2)
        
        # Check if the tunnel is working by trying to connect to the SOCKS port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            logger.info(f"SSH tunnel is active on port {port}")
            return True
        else:
            logger.error(f"SSH tunnel doesn't seem to be active on port {port}")
            return False
            
    except Exception as e:
        logger.error(f"Error starting SSH tunnel: {e}")
        return False

def setup_vpn_tunnels(config):
    """Set up multiple VPN tunnels for rotation"""
    # Check if we need to set up SSH tunnels
    ssh_tunnels_needed = False
    for proxy in config["proxies"]:
        if proxy and ("socks5://127.0.0.1" in proxy.get("http", "") or "socks5://127.0.0.1" in proxy.get("https", "")):
            ssh_tunnels_needed = True
            break
    
    if not ssh_tunnels_needed:
        logger.info("No local SOCKS proxies configured, skipping SSH tunnel setup")
        return True
    
    # Look for SSH server information
    ssh_server = os.environ.get("SSH_SERVER")
    if not ssh_server:
        logger.warning("No SSH_SERVER environment variable found")
        logger.info("You can set it up manually using vpn_setup.sh")
        return False
    
    # Set up tunnels on different ports
    success = False
    for i, proxy in enumerate(config["proxies"]):
        if proxy:
            for protocol in ["http", "https"]:
                proxy_url = proxy.get(protocol, "")
                if "socks5://127.0.0.1" in proxy_url:
                    port = int(proxy_url.split(":")[-1])
                    if start_ssh_tunnel(port, ssh_server):
                        success = True
    
    return success

def reset_site_request_counts(config):
    """Reset the request counts for all sites"""
    config["site_request_counts"] = {}
    save_config(config)

def get_domain(url):
    """Extract the base domain from a URL"""
    parsed = urlparse(url)
    domain = parsed.netloc
    
    # Extract the base domain (e.g., example.com from www.example.com)
    parts = domain.split('.')
    if len(parts) > 2:
        domain = '.'.join(parts[-2:])
    
    return domain

def verify_license(config=None):
    """
    Verify the license key locally (no server call)
    
    Args:
        config: Optional config dictionary
        
    Returns:
        Dictionary with license verification status
    """
    if config is None:
        config = load_config()
    
    # Extract license information
    license_config = config["licensing"]
    license_key = license_config["license_key"]
    
    # Don't verify if no license key is provided
    if not license_key:
        logger.warning("No license key provided")
        license_config["valid_until"] = None
        license_config["enabled_features"] = ["basic_scraping"]
        return {
            "valid": False,
            "message": "No license key provided",
            "valid_until": None,
            "enabled_features": ["basic_scraping"]
        }
    
    import datetime
    
    # Local validation only - accept specific keys
    valid_keys = {
        # Test key - enables all features
        "TEST-GRAVY-JOBS-12345": {
            "valid": True,
            "message": "Test license active",
            "valid_until": (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat(),
            "enabled_features": [
                "basic_scraping", 
                "commercial_proxies", 
                "advanced_scraping", 
                "claude_integration",
                "general_scraping"
            ]
        },
        
        # Developer key - never expires
        "DEV-GRAVY-JOBS-ACCESS": {
            "valid": True,
            "message": "Developer license active",
            "valid_until": (datetime.datetime.now() + datetime.timedelta(days=3650)).isoformat(),
            "enabled_features": [
                "basic_scraping", 
                "commercial_proxies", 
                "advanced_scraping", 
                "claude_integration",
                "general_scraping"
            ]
        }
    }
    
    # Check if license key matches any valid key
    if license_key in valid_keys:
        result = valid_keys[license_key]
        
        # Update license config with verification result
        license_config["valid_until"] = result["valid_until"]
        license_config["enabled_features"] = result["enabled_features"]
        license_config["last_verified"] = datetime.datetime.now().isoformat()
        save_config(config)
        
        logger.info(f"License verified: {result['message']}")
        return result
    else:
        # Also consider partial key matches (for demo purposes)
        for valid_key in valid_keys:
            if license_key.startswith(valid_key[:8]):
                result = valid_keys[valid_key].copy()
                result["message"] = "License key partially matched (for demo)"
                
                # Update license config with verification result
                license_config["valid_until"] = result["valid_until"]
                license_config["enabled_features"] = result["enabled_features"]
                license_config["last_verified"] = datetime.datetime.now().isoformat()
                save_config(config)
                
                logger.info(f"License verified via partial match: {result['message']}")
                return result
    
    # Invalid key
    logger.warning(f"Invalid license key: {license_key}")
    license_config["valid_until"] = None
    license_config["enabled_features"] = ["basic_scraping"]
    license_config["last_verified"] = datetime.datetime.now().isoformat()
    save_config(config)
    
    return {
        "valid": False,
        "message": "Invalid license key",
        "valid_until": None,
        "enabled_features": ["basic_scraping"]
    }

def get_machine_id():
    """
    Get a unique identifier for this machine for license validation
    
    Returns:
        String containing a machine ID
    """
    import hashlib
    import platform
    import uuid
    
    # Combination of platform info and hardware identifiers
    system_info = platform.system() + platform.node() + platform.machine()
    
    # Add MAC address if available
    try:
        mac = uuid.getnode()
        system_info += str(mac)
    except:
        pass
    
    # Create a hash to anonymize the actual system details
    return hashlib.sha256(system_info.encode()).hexdigest()

def rotate_fingerprint(config=None):
    """
    Rotate to the next browser fingerprint
    
    Args:
        config: Optional config dictionary
        
    Returns:
        Dictionary containing the new fingerprint
    """
    if config is None:
        config = load_config()
    
    # Check if fingerprinting is enabled
    if not config["browser_fingerprints"]["enabled"]:
        logger.info("Browser fingerprinting is disabled")
        return None
    
    # Get current and next index
    current_index = config["browser_fingerprints"]["current_fingerprint_index"]
    fingerprints = config["browser_fingerprints"]["fingerprints"]
    
    if not fingerprints:
        # Generate fingerprints if none exist
        fingerprints = [generate_browser_fingerprint() for _ in range(5)]
        config["browser_fingerprints"]["fingerprints"] = fingerprints
    
    # Rotate to next fingerprint
    next_index = (current_index + 1) % len(fingerprints)
    config["browser_fingerprints"]["current_fingerprint_index"] = next_index
    
    # If configured to rotate IP with fingerprint, also rotate proxy
    if config["rotation_settings"]["rotate_ip_with_fingerprint"]:
        if config["proxy_services"]["enabled"]:
            # Rotate commercial proxy service and country
            rotate_commercial_proxy_country(config)
        else:
            # Rotate standard proxy
            rotate_proxy(config)
    
    # Save config
    save_config(config)
    
    # Return the new fingerprint
    return fingerprints[next_index]

def get_current_fingerprint(config=None):
    """
    Get the current browser fingerprint
    
    Args:
        config: Optional config dictionary
        
    Returns:
        Dictionary containing the current fingerprint
    """
    if config is None:
        config = load_config()
    
    # Check if fingerprinting is enabled
    if not config["browser_fingerprints"]["enabled"]:
        return None
    
    # Get current fingerprint
    fingerprints = config["browser_fingerprints"]["fingerprints"]
    current_index = config["browser_fingerprints"]["current_fingerprint_index"]
    
    if not fingerprints:
        # Generate fingerprints if none exist
        fingerprints = [generate_browser_fingerprint() for _ in range(5)]
        config["browser_fingerprints"]["fingerprints"] = fingerprints
        config["browser_fingerprints"]["current_fingerprint_index"] = 0
        current_index = 0
        save_config(config)
    
    return fingerprints[current_index]

def rotate_commercial_proxy_country(config=None):
    """
    Rotate the country within the current commercial proxy service
    
    Args:
        config: Optional config dictionary
        
    Returns:
        The new country code, or None if not applicable
    """
    if config is None:
        config = load_config()
    
    # Check if commercial proxies are enabled
    if not config["proxy_services"]["enabled"]:
        logger.info("Commercial proxy services are disabled")
        return None
    
    # Get current service
    current_service = config["proxy_services"]["current_service"]
    if not current_service:
        logger.error("No commercial proxy service is selected")
        return None
    
    # Get service configuration
    service_config = config["proxy_services"][current_service]
    if not service_config["enabled"]:
        logger.error(f"Selected proxy service {current_service} is not enabled")
        return None
    
    # Check if service has country_pool
    if "country_pool" not in service_config or not service_config["country_pool"]:
        logger.info(f"Proxy service {current_service} does not support country rotation")
        return None
    
    # Get current country and country_pool
    country_pool = service_config["country_pool"]
    current_country = service_config.get("country", country_pool[0])
    
    # Rotate to next country
    if current_country in country_pool:
        current_index = country_pool.index(current_country)
        next_index = (current_index + 1) % len(country_pool)
    else:
        next_index = 0
    
    new_country = country_pool[next_index]
    service_config["country"] = new_country
    save_config(config)
    
    logger.info(f"Rotated {current_service} country from {current_country} to {new_country}")
    return new_country

def increment_site_request_count(url, config):
    """Increment the request count for a site domain"""
    domain = get_domain(url)
    
    if "site_request_counts" not in config:
        config["site_request_counts"] = {}
    
    if domain not in config["site_request_counts"]:
        config["site_request_counts"][domain] = 0
    
    # Increment site-specific count
    config["site_request_counts"][domain] += 1
    
    # Increment total request count
    if "total_request_count" not in config:
        config["total_request_count"] = 0
    config["total_request_count"] += 1
    
    # Check if we should rotate fingerprint based on request count
    if (config["browser_fingerprints"]["enabled"] and 
        config["total_request_count"] % config["rotation_settings"]["fingerprint_rotation_frequency"] == 0):
        logger.info(f"Rotating browser fingerprint after {config['rotation_settings']['fingerprint_rotation_frequency']} requests")
        rotate_fingerprint(config)
    
    save_config(config)
    
    return config["site_request_counts"][domain]

def should_rotate_session(url, config):
    """Check if we should rotate the session for this site"""
    domain = get_domain(url)
    
    for site, settings in config["site_settings"].items():
        if site in domain:
            count = config["site_request_counts"].get(domain, 0)
            max_requests = settings["max_requests_per_session"]
            
            if count >= max_requests:
                logger.info(f"Request count for {domain} reached {count}, rotating session")
                return True
    
    return False

def generate_search_params_with_claude(user_query, config=None):
    """
    Generate optimized search parameters based on user query
    (Local implementation without API call to Claude)
    
    Args:
        user_query: The user's search query or request
        config: Optional config dictionary
        
    Returns:
        Dictionary with search parameters
    """
    if config is None:
        config = load_config()
    
    # Check if Claude integration is enabled in config (even though we're not using real API)
    claude_config = config["claude_integration"]
    
    # First, check if this is a predefined template
    if user_query.lower() in claude_config["custom_search_templates"]:
        template_key = user_query.lower()
        logger.info(f"Using predefined template: {template_key}")
        
        # Return predefined parameters for known templates
        predefined_params = {
            "default": {
                "keywords": ["entry level", "beginner", "junior", "html", "css", "remote"],
                "exclude_keywords": ["senior", "lead", "5+ years", "7+ years"],
                "locations": ["remote", "usa", "anywhere"]
            },
            "msp_provider": {
                "keywords": ["managed service provider", "MSP", "IT support", "managed services", "IT outsourcing"],
                "exclude_keywords": ["senior", "lead", "manager", "director"],
                "locations": ["remote", "usa", "anywhere"]
            },
            "data_science": {
                "keywords": ["data scientist", "machine learning", "AI", "Python", "pandas", "analytics"],
                "exclude_keywords": ["senior", "lead", "principal", "10+ years"],
                "locations": ["remote", "usa", "anywhere"]
            },
            "devops": {
                "keywords": ["DevOps", "AWS", "Azure", "Kubernetes", "Docker", "CI/CD"],
                "exclude_keywords": ["senior", "lead", "architect", "5+ years"],
                "locations": ["remote", "usa", "anywhere"]
            },
            "remote_only": {
                "keywords": ["remote", "work from home", "distributed team", "virtual"],
                "exclude_keywords": ["hybrid", "onsite", "on-site", "relocate"],
                "locations": ["remote", "virtual", "anywhere"]
            }
        }
        
        if template_key in predefined_params:
            return predefined_params[template_key]
        
    # Analyze the query to generate appropriate parameters
    # This is a simplified local version of what Claude would do
    
    # Convert to lowercase for easier matching
    query_lower = user_query.lower()
    
    # Initialize with some basic parameters
    keywords = []
    exclude_keywords = ["senior", "lead", "principal", "architect", "5+ years", "7+ years", "10+ years"]
    locations = ["remote", "usa", "anywhere"]
    
    # Check for key phrases and extract search parameters
    
    # Check for job roles
    roles = {
        "developer": ["developer", "programmer", "coder", "software engineer"],
        "data": ["data scientist", "data analyst", "data engineer", "machine learning"],
        "devops": ["devops", "sre", "site reliability", "infrastructure"],
        "design": ["designer", "ux", "ui", "user experience", "graphic"],
        "product": ["product manager", "project manager", "scrum master"],
        "support": ["support", "help desk", "service desk", "technical support"],
        "qa": ["qa", "quality assurance", "tester", "quality engineer"],
        "admin": ["administrator", "admin", "system admin"],
        "security": ["security", "cybersecurity", "infosec", "information security"],
        "web": ["web developer", "frontend", "front-end", "back-end", "backend", "full-stack"],
        "mobile": ["mobile", "android", "ios", "flutter", "react native"],
        "cloud": ["cloud", "aws", "azure", "gcp", "google cloud"],
        "database": ["database", "dba", "sql", "nosql", "mongodb", "postgres"],
        "ai": ["ai", "artificial intelligence", "machine learning", "ml engineer"],
        "analyst": ["analyst", "business analyst", "systems analyst", "data analyst"],
        "network": ["network", "networking", "network engineer"],
        "msp": ["msp", "managed service", "it service", "it support"],
        "data entry": ["data entry", "data input", "typing", "transcription"]
    }
    
    # Check for technologies
    technologies = {
        "languages": ["python", "javascript", "java", "c#", "typescript", "php", "ruby", "go", "rust", "c++"],
        "frontend": ["html", "css", "react", "angular", "vue", "javascript", "typescript", "jquery", "bootstrap"],
        "backend": ["node", "express", "django", "flask", "spring", "laravel", "rails", "asp.net"],
        "database": ["sql", "mysql", "postgresql", "mongodb", "oracle", "dynamodb", "redis", "elasticsearch"],
        "devops": ["docker", "kubernetes", "terraform", "ansible", "jenkins", "aws", "azure", "gcp"],
        "ai": ["tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "machine learning", "nlp"],
        "mobile": ["swift", "kotlin", "react native", "flutter", "android", "ios"],
        "cms": ["wordpress", "drupal", "shopify", "wix", "webflow", "contentful"]
    }
    
    # Check for experience levels
    experience_levels = {
        "beginner": ["entry level", "beginner", "junior", "trainee", "intern"],
        "intermediate": ["mid level", "intermediate", "associate"],
        "advanced": ["senior", "lead", "expert", "principal", "architect", "manager", "director"]
    }
    
    # Check for locations
    location_terms = [
        "remote", "work from home", "wfh", "virtual", "telecommute",
        "usa", "united states", "america", 
        "uk", "united kingdom", "england",
        "canada", "australia", "new zealand",
        "europe", "asia", "africa", "south america"
    ]
    
    # Check for specific cities
    cities = [
        "new york", "san francisco", "los angeles", "chicago", "boston", 
        "seattle", "austin", "denver", "miami", "washington dc",
        "london", "berlin", "paris", "toronto", "sydney", "singapore"
    ]
    
    # Extract keywords based on the query
    
    # Check for role matches
    for role_category, role_terms in roles.items():
        for term in role_terms:
            if term in query_lower:
                keywords.append(term)
                # Add related terms
                if role_category == "developer" and "web" in query_lower:
                    keywords.extend(["html", "css", "javascript"])
                elif role_category == "data" and "science" in query_lower:
                    keywords.extend(["python", "machine learning", "data analysis"])
                elif role_category == "devops":
                    keywords.extend(["cloud", "ci/cd", "automation"])
                break
    
    # Check for technology matches
    for tech_category, tech_terms in technologies.items():
        for term in tech_terms:
            if term in query_lower:
                keywords.append(term)
    
    # Check for experience level
    experience_level = "beginner"  # Default to beginner level
    for level, level_terms in experience_levels.items():
        for term in level_terms:
            if term in query_lower:
                experience_level = level
                if level != "beginner":  # Only add as keyword if not beginner (since that's default)
                    keywords.append(term)
                break
    
    # Always include some experience level terms for beginner
    if experience_level == "beginner":
        keywords.extend(["entry level", "junior", "beginner"])
    
    # Check for location matches
    found_locations = []
    for location in location_terms:
        if location in query_lower:
            found_locations.append(location)
    
    for city in cities:
        if city in query_lower:
            found_locations.append(city)
    
    if found_locations:
        locations = found_locations
    
    # If request specifically mentions remote
    if "remote" in query_lower or "work from home" in query_lower:
        if "remote" not in locations:
            locations.append("remote")
    
    # Deduplicate keywords
    keywords = list(set(keywords))
    
    # If "data entry" is a role, adjust keywords
    if "data entry" in query_lower:
        keywords = ["data entry", "data input", "typing", "transcription"]
        if "remote" in query_lower:
            keywords.append("remote data entry")
    
    # MSP specific adjustments
    if "msp" in query_lower or "managed service" in query_lower:
        keywords = ["managed service provider", "MSP", "IT support", "IT services", "outsourced IT"]
        exclude_keywords.extend(["developer", "programmer", "software engineer"])
    
    # If too few keywords, add some general ones
    if len(keywords) < 2:
        if "job" in query_lower or "work" in query_lower or "career" in query_lower:
            if "data" in query_lower:
                keywords.extend(["data", "analysis", "reporting"])
            elif "developer" in query_lower or "coding" in query_lower or "programming" in query_lower:
                keywords.extend(["developer", "software", "programming"])
            elif "support" in query_lower or "help" in query_lower:
                keywords.extend(["support", "technical support", "help desk"])
            else:
                keywords.extend(["job", "career", "work"])
    
    # Construct final result
    search_params = {
        "keywords": keywords,
        "exclude_keywords": exclude_keywords,
        "locations": locations
    }
    
    logger.info(f"Generated search parameters: {search_params}")
    return search_params

def fetch_with_retry(url, params=None, config=None, session=None, verify_ssl=True, timeout=30, force_fresh=False):
    """
    Fetch a URL with automatic retries, proxy rotation, and caching
    
    Args:
        url: The URL to fetch
        params: Optional dictionary of URL parameters
        config: Optional config dictionary (will be loaded if not provided)
        session: Optional requests session to use
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        force_fresh: Whether to force a fresh request (ignore cache)
        
    Returns:
        The response content as a string, or None if all retries failed
    """
    if config is None:
        config = load_config()
    
    # Try to get from cache first
    if not force_fresh:
        cached = get_cached_response(url, params, config)
        if cached:
            return cached
    
    # Check if we need to rotate the session
    if should_rotate_session(url, config):
        session = None  # Force new session
        rotate_proxy(config)  # Rotate proxy
        reset_site_request_counts(config)  # Reset request counts
    
    # Create a new session if needed
    if session is None:
        session = requests.Session()
    
    # Get the current proxy
    proxy_index = config["current_proxy_index"]
    proxy = config["proxies"][proxy_index]
    
    # Configure retry settings
    max_retries = config["rotation_settings"]["max_retries"]
    retry_delays = config["rotation_settings"]["retry_delay"]
    auto_rotate = config["rotation_settings"]["auto_rotate_on_block"]
    
    # Get domain-specific settings
    domain = get_domain(url)
    site_settings = None
    for site, settings in config["site_settings"].items():
        if site in domain:
            site_settings = settings
            break
    
    # Default settings if no specific site settings found
    if site_settings is None:
        site_settings = {
            "high_scrutiny": False,
            "extra_delay": 0,
            "max_requests_per_session": 20
        }
    
    # Increment request count for this site
    increment_site_request_count(url, config)
    
    # Variable to track if we've tried commercial proxies yet
    commercial_proxy_tried = False
    
    # Get current browser fingerprint
    fingerprint = get_current_fingerprint(config) if config["browser_fingerprints"]["enabled"] else None
    
    # Try multiple times
    for attempt in range(max_retries):
        try:
            # Add a randomized delay between requests
            base_delay = random.uniform(
                config["rotation_settings"]["delay_between_requests"]["min"],
                config["rotation_settings"]["delay_between_requests"]["max"]
            )
            total_delay = base_delay + site_settings["extra_delay"]
            
            if attempt > 0:
                logger.info(f"Sleeping for {total_delay:.2f} seconds before attempt {attempt+1}")
            time.sleep(total_delay)
            
            # Prepare browser-like headers with fingerprint
            headers = get_browser_headers(config, fingerprint=fingerprint)
            
            # Make the request
            response = session.get(
                url,
                params=params,
                headers=headers,
                proxies=proxy,
                verify=verify_ssl,
                timeout=timeout
            )
            
            # Check for blocking or captcha
            is_blocked = (
                response.status_code in [403, 429, 503] or
                "captcha" in response.text.lower() or
                "blocked" in response.text.lower() or
                "automated" in response.text.lower()
            )
            
            if is_blocked:
                logger.warning(f"Detected blocking on {url} (attempt {attempt+1})")
                
                # Try rotating fingerprint and IP together
                if config["browser_fingerprints"]["enabled"] and attempt == 0:
                    logger.info("Rotating browser fingerprint and IP due to blocking")
                    fingerprint = rotate_fingerprint(config)
                    if config["proxy_services"]["enabled"]:
                        # Get new proxy after fingerprint rotation (which may have changed it)
                        current_service = config["proxy_services"]["current_service"]
                        logger.info(f"Using commercial proxy service: {current_service} after fingerprint rotation")
                        commercial_proxy_tried = True
                        continue
                
                # Try commercial proxies if available and this is a high-scrutiny site
                if (not commercial_proxy_tried and 
                    config["proxy_services"]["enabled"] and 
                    site_settings.get("high_scrutiny", False)):
                    
                    logger.info("Site is blocking. Trying commercial proxy service...")
                    commercial_proxy_tried = True
                    
                    # Try each enabled commercial proxy service until one works
                    for service_name in ["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"]:
                        if config["proxy_services"][service_name]["enabled"]:
                            logger.info(f"Trying commercial proxy service: {service_name}")
                            config["proxy_services"]["current_service"] = service_name
                            save_config(config)
                            
                            # Try to fetch with this commercial proxy
                            if service_name == "brightdata":
                                content = fetch_using_brightdata(url, params, config, session, verify_ssl, timeout)
                            elif service_name == "oxylabs":
                                content = fetch_using_oxylabs(url, params, config, session, verify_ssl, timeout)
                            elif service_name == "smartproxy":
                                content = fetch_using_smartproxy(url, params, config, session, verify_ssl, timeout)
                            elif service_name == "proxymesh":
                                content = fetch_using_proxymesh(url, params, config, session, verify_ssl, timeout)
                            elif service_name == "zenrows":
                                content = fetch_using_zenrows(url, params, config, session, verify_ssl, timeout)
                            elif service_name == "scraperapi":
                                content = fetch_using_scraperapi(url, params, config, session, verify_ssl, timeout)
                            
                            if content:
                                logger.info(f"Successfully fetched {url} using {service_name}")
                                cache_response(url, content, params)
                                return content
                
                # If commercial proxies didn't work or aren't available, rotate standard proxy
                if auto_rotate:
                    logger.info("Auto-rotating proxy due to blocking")
                    proxy = rotate_proxy(config)
                
                # Wait longer between retries
                retry_delay = random.uniform(retry_delays["min"], retry_delays["max"])
                logger.info(f"Waiting {retry_delay:.2f} seconds before retry")
                time.sleep(retry_delay)
                continue
            
            # Success - cache and return the content
            if response.status_code == 200:
                logger.info(f"Successfully fetched {url}")
                cache_response(url, response.text, params)
                return response.text
            
            # Other error status
            logger.error(f"Request failed with status {response.status_code}: {url}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on attempt {attempt+1}: {e}")
            
            # Rotate proxy on connection errors
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                logger.info("Connection error, rotating proxy")
                proxy = rotate_proxy(config)
            
            # Wait before retrying
            retry_delay = random.uniform(retry_delays["min"], retry_delays["max"])
            logger.info(f"Waiting {retry_delay:.2f} seconds before retry")
            time.sleep(retry_delay)
    
    # All retries failed - try commercial proxies as a last resort if not tried yet
    if not commercial_proxy_tried and config["proxy_services"]["enabled"]:
        logger.info("All standard retries failed. Trying commercial proxy services as last resort...")
        content = fetch_using_commercial_proxy(url, params, config, session, verify_ssl, timeout)
        if content:
            logger.info(f"Successfully fetched {url} using commercial proxy")
            cache_response(url, content, params)
            return content
    
    # Check for fallback cached version
    cached = get_cached_response(url, params, config)
    if cached:
        logger.warning(f"Using expired cache as fallback for {url}")
        return cached
    
    logger.error(f"All retries failed for {url}")
    return None


def fetch_using_brightdata(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using Bright Data (formerly Luminati) proxy service
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary containing Bright Data credentials
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    if session is None:
        session = requests.Session()
    
    # Extract Bright Data configuration
    bright_config = config["proxy_services"]["brightdata"]
    username = bright_config["username"]
    password = bright_config["password"]
    zone = bright_config["zone"]
    port = bright_config["port"]
    country = bright_config["country"]
    session_id = bright_config["session_id"]
    
    # Format username with session and country info
    formatted_username = f"{username}-country-{country}-session-{session_id}"
    
    # Configure proxy with authentication
    proxy = {
        "http": f"http://{formatted_username}:{password}@zproxy.lum-superproxy.io:{port}",
        "https": f"http://{formatted_username}:{password}@zproxy.lum-superproxy.io:{port}"
    }
    
    # Make the request
    try:
        headers = get_browser_headers(config)
        response = session.get(
            url,
            params=params,
            headers=headers,
            proxies=proxy,
            verify=verify_ssl,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"Bright Data request successful: {url}")
            return response.text
        else:
            logger.error(f"Bright Data request failed with status {response.status_code}: {url}")
            return None
    except Exception as e:
        logger.error(f"Error using Bright Data proxy: {e}")
        return None

def fetch_using_oxylabs(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using Oxylabs proxy service
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary containing Oxylabs credentials
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    if session is None:
        session = requests.Session()
    
    # Extract Oxylabs configuration
    oxy_config = config["proxy_services"]["oxylabs"]
    username = oxy_config["username"]
    password = oxy_config["password"]
    endpoint = oxy_config["endpoint"]
    port = oxy_config["port"]
    country = oxy_config["country"]
    
    # Format username with country
    formatted_username = f"customer-{username}-country-{country}"
    
    # Configure proxy with authentication
    proxy = {
        "http": f"http://{formatted_username}:{password}@{endpoint}:{port}",
        "https": f"http://{formatted_username}:{password}@{endpoint}:{port}"
    }
    
    # Make the request
    try:
        headers = get_browser_headers(config)
        response = session.get(
            url,
            params=params,
            headers=headers,
            proxies=proxy,
            verify=verify_ssl,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"Oxylabs request successful: {url}")
            return response.text
        else:
            logger.error(f"Oxylabs request failed with status {response.status_code}: {url}")
            return None
    except Exception as e:
        logger.error(f"Error using Oxylabs proxy: {e}")
        return None

def fetch_using_smartproxy(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using SmartProxy service
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary containing SmartProxy credentials
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    if session is None:
        session = requests.Session()
    
    # Extract SmartProxy configuration
    smart_config = config["proxy_services"]["smartproxy"]
    username = smart_config["username"]
    password = smart_config["password"]
    endpoint = smart_config["endpoint"]
    port = smart_config["port"]
    
    # Configure proxy with authentication
    proxy = {
        "http": f"http://{username}:{password}@{endpoint}:{port}",
        "https": f"http://{username}:{password}@{endpoint}:{port}"
    }
    
    # Make the request
    try:
        headers = get_browser_headers(config)
        response = session.get(
            url,
            params=params,
            headers=headers,
            proxies=proxy,
            verify=verify_ssl,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"SmartProxy request successful: {url}")
            return response.text
        else:
            logger.error(f"SmartProxy request failed with status {response.status_code}: {url}")
            return None
    except Exception as e:
        logger.error(f"Error using SmartProxy: {e}")
        return None

def fetch_using_proxymesh(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using ProxyMesh service
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary containing ProxyMesh credentials
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    if session is None:
        session = requests.Session()
    
    # Extract ProxyMesh configuration
    mesh_config = config["proxy_services"]["proxymesh"]
    username = mesh_config["username"]
    password = mesh_config["password"]
    endpoint = mesh_config["endpoint"]
    port = mesh_config["port"]
    
    # Configure proxy with authentication
    proxy = {
        "http": f"http://{username}:{password}@{endpoint}:{port}",
        "https": f"http://{username}:{password}@{endpoint}:{port}"
    }
    
    # Make the request
    try:
        headers = get_browser_headers(config)
        response = session.get(
            url,
            params=params,
            headers=headers,
            proxies=proxy,
            verify=verify_ssl,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"ProxyMesh request successful: {url}")
            return response.text
        else:
            logger.error(f"ProxyMesh request failed with status {response.status_code}: {url}")
            return None
    except Exception as e:
        logger.error(f"Error using ProxyMesh: {e}")
        return None

def fetch_using_zenrows(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using ZenRows API
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary containing ZenRows credentials
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    if session is None:
        session = requests.Session()
    
    # Extract ZenRows configuration
    zenrows_config = config["proxy_services"]["zenrows"]
    api_key = zenrows_config["api_key"]
    api_endpoint = zenrows_config["endpoint"]
    
    # Prepare ZenRows API parameters
    zenrows_params = {
        "url": url,
        "apikey": api_key,
        "js_render": "true",  # Enable JavaScript rendering
        "premium_proxy": "true",  # Use premium proxy
        "antibot": "true",  # Enable anti-bot detection
        "wait_for": "body",  # Wait for body to load
    }
    
    # Add original params to the query string if provided
    if params:
        url_with_params = url
        if "?" not in url:
            url_with_params += "?"
        else:
            url_with_params += "&"
        url_with_params += "&".join(f"{k}={v}" for k, v in params.items())
        zenrows_params["url"] = url_with_params
    
    # Make the request to ZenRows API
    try:
        response = session.get(
            api_endpoint,
            params=zenrows_params,
            verify=verify_ssl,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"ZenRows request successful: {url}")
            return response.text
        else:
            logger.error(f"ZenRows request failed with status {response.status_code}: {url}")
            return None
    except Exception as e:
        logger.error(f"Error using ZenRows: {e}")
        return None

def fetch_using_scraperapi(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using ScraperAPI
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary containing ScraperAPI credentials
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    if session is None:
        session = requests.Session()
    
    # Extract ScraperAPI configuration
    scraper_config = config["proxy_services"]["scraperapi"]
    api_key = scraper_config["api_key"]
    api_endpoint = scraper_config["endpoint"]
    
    # Prepare ScraperAPI parameters
    scraper_params = {
        "api_key": api_key,
        "url": url,
        "country_code": "us",  # Default to US IPs
        "render": "true",  # Enable JavaScript rendering for complex sites
        "premium": "true",  # Use premium proxies for better success rate
    }
    
    # Add original params to the query string if provided
    if params:
        for key, value in params.items():
            if key not in scraper_params:  # Avoid overriding API params
                scraper_params[key] = value
    
    # Make the request
    try:
        response = session.get(
            api_endpoint,
            params=scraper_params,
            verify=verify_ssl,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"ScraperAPI request successful: {url}")
            return response.text
        else:
            logger.error(f"ScraperAPI request failed with status {response.status_code}: {url}")
            return None
    except Exception as e:
        logger.error(f"Error using ScraperAPI: {e}")
        return None

def fetch_using_commercial_proxy(url, params=None, config=None, session=None, verify_ssl=True, timeout=30):
    """
    Fetch a URL using the currently configured commercial proxy service
    
    Args:
        url: The URL to fetch
        params: Optional URL parameters
        config: The config dictionary
        session: Optional requests session
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        
    Returns:
        The response content as a string, or None on failure
    """
    if config is None:
        config = load_config()
    
    # Check if commercial proxies are enabled
    if not config["proxy_services"]["enabled"]:
        logger.info("Commercial proxy services are disabled")
        return None
    
    # Get the currently selected proxy service
    current_service = config["proxy_services"]["current_service"]
    if not current_service:
        # Find the first enabled service
        for service_name in ["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"]:
            if config["proxy_services"][service_name]["enabled"]:
                current_service = service_name
                config["proxy_services"]["current_service"] = current_service
                save_config(config)
                break
    
    if not current_service:
        logger.error("No commercial proxy services are enabled")
        return None
    
    # Check if the service is enabled
    if not config["proxy_services"][current_service]["enabled"]:
        logger.error(f"Selected proxy service {current_service} is not enabled")
        return None
    
    # Use the appropriate fetch function based on the service
    logger.info(f"Using commercial proxy service: {current_service}")
    
    if current_service == "brightdata":
        return fetch_using_brightdata(url, params, config, session, verify_ssl, timeout)
    elif current_service == "oxylabs":
        return fetch_using_oxylabs(url, params, config, session, verify_ssl, timeout)
    elif current_service == "smartproxy":
        return fetch_using_smartproxy(url, params, config, session, verify_ssl, timeout)
    elif current_service == "proxymesh":
        return fetch_using_proxymesh(url, params, config, session, verify_ssl, timeout)
    elif current_service == "zenrows":
        return fetch_using_zenrows(url, params, config, session, verify_ssl, timeout)
    elif current_service == "scraperapi":
        return fetch_using_scraperapi(url, params, config, session, verify_ssl, timeout)
    else:
        logger.error(f"Unknown proxy service: {current_service}")
        return None

def rotate_commercial_proxy(config=None):
    """
    Rotate to the next enabled commercial proxy service
    
    Args:
        config: Optional config dictionary
        
    Returns:
        The name of the new proxy service, or None if no services are enabled
    """
    if config is None:
        config = load_config()
    
    # Check if commercial proxies are enabled
    if not config["proxy_services"]["enabled"]:
        logger.info("Commercial proxy services are disabled")
        return None
    
    # Get available services
    services = ["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"]
    enabled_services = [s for s in services if config["proxy_services"][s]["enabled"]]
    
    if not enabled_services:
        logger.error("No commercial proxy services are enabled")
        return None
    
    # Get current service
    current_service = config["proxy_services"]["current_service"]
    
    # Find the next enabled service
    if current_service in enabled_services:
        current_index = enabled_services.index(current_service)
        next_index = (current_index + 1) % len(enabled_services)
    else:
        next_index = 0
    
    next_service = enabled_services[next_index]
    config["proxy_services"]["current_service"] = next_service
    save_config(config)
    
    logger.info(f"Rotated commercial proxy service from {current_service} to {next_service}")
    return next_service

class VPNManager:
    """Main class for managing VPN switching, browser fingerprinting, and requests"""
    
    def __init__(self):
        self.config = load_config()
        self.session = requests.Session()
        self.setup_tunnels()
        
        # Verify license on startup
        self.license_status = verify_license(self.config)
        
        # Initialize browser fingerprints if enabled
        if self.config["browser_fingerprints"]["enabled"]:
            self.current_fingerprint = get_current_fingerprint(self.config)
        else:
            self.current_fingerprint = None
    
    def setup_tunnels(self):
        """Set up VPN tunnels"""
        setup_vpn_tunnels(self.config)
    
    def get(self, url, params=None, verify_ssl=True, timeout=30, force_fresh=False):
        """Get a URL with all the proxy/VPN handling logic"""
        # Try commercial proxy services first if enabled and licensed
        if self.config["proxy_services"]["enabled"] and "commercial_proxies" in self.license_status.get("enabled_features", []):
            logger.info("Attempting to use commercial proxy service")
            content = fetch_using_commercial_proxy(
                url=url,
                params=params,
                config=self.config,
                session=self.session,
                verify_ssl=verify_ssl,
                timeout=timeout
            )
            if content:
                return content
            
            # If commercial proxy failed, try standard fetch with retry
            logger.warning("Commercial proxy failed, falling back to standard methods")
        
        # Fall back to the standard fetch with retry method
        return fetch_with_retry(
            url=url,
            params=params,
            config=self.config,
            session=self.session,
            verify_ssl=verify_ssl,
            timeout=timeout,
            force_fresh=force_fresh
        )
    
    def rotate_proxy(self):
        """Manually rotate to the next proxy"""
        # Try to rotate commercial proxy first if enabled and licensed
        if self.config["proxy_services"]["enabled"] and "commercial_proxies" in self.license_status.get("enabled_features", []):
            service = rotate_commercial_proxy(self.config)
            if service:
                logger.info(f"Rotated to commercial proxy service: {service}")
                return service
        
        # Fall back to standard proxy rotation
        return rotate_proxy(self.config)
    
    def reset_session(self):
        """Reset the current session and request counts"""
        self.session = requests.Session()
        reset_site_request_counts(self.config)
    
    def add_proxy(self, proxy_config):
        """Add a new proxy to the configuration"""
        if proxy_config not in self.config["proxies"]:
            self.config["proxies"].append(proxy_config)
            save_config(self.config)
            logger.info(f"Added new proxy: {proxy_config}")
    
    def add_user_agent(self, user_agent):
        """Add a new user agent to the configuration"""
        if user_agent not in self.config["user_agents"]:
            self.config["user_agents"].append(user_agent)
            save_config(self.config)
            logger.info(f"Added new user agent: {user_agent}")
    
    def enable_commercial_proxy(self, service_name, **credentials):
        """
        Enable and configure a commercial proxy service
        
        Args:
            service_name: Name of the proxy service (brightdata, oxylabs, etc.)
            **credentials: Dictionary of service-specific credentials
            
        Returns:
            True if successful, False otherwise
        """
        # Check if license allows commercial proxies
        if "commercial_proxies" not in self.license_status.get("enabled_features", []):
            logger.warning("Commercial proxy services not available with current license")
            return False
        
        if service_name not in self.config["proxy_services"]:
            logger.error(f"Unknown proxy service: {service_name}")
            return False
        
        # Update service configuration with credentials
        for key, value in credentials.items():
            if key in self.config["proxy_services"][service_name]:
                self.config["proxy_services"][service_name][key] = value
        
        # Enable the service
        self.config["proxy_services"][service_name]["enabled"] = True
        self.config["proxy_services"]["enabled"] = True
        self.config["proxy_services"]["current_service"] = service_name
        
        # Save the config
        save_config(self.config)
        logger.info(f"Enabled commercial proxy service: {service_name}")
        return True
        
    def disable_commercial_proxy(self, service_name=None):
        """
        Disable a commercial proxy service or all services
        
        Args:
            service_name: Name of the proxy service to disable, or None to disable all
            
        Returns:
            True if successful
        """
        if service_name:
            if service_name in self.config["proxy_services"]:
                self.config["proxy_services"][service_name]["enabled"] = False
                logger.info(f"Disabled commercial proxy service: {service_name}")
                
                # If this was the current service, find another enabled one
                if self.config["proxy_services"]["current_service"] == service_name:
                    self.config["proxy_services"]["current_service"] = None
                    rotate_commercial_proxy(self.config)
            else:
                logger.error(f"Unknown proxy service: {service_name}")
        else:
            # Disable all services
            for service in ["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"]:
                self.config["proxy_services"][service]["enabled"] = False
            self.config["proxy_services"]["enabled"] = False
            self.config["proxy_services"]["current_service"] = None
            logger.info("Disabled all commercial proxy services")
        
        save_config(self.config)
        return True
    
    def get_commercial_proxy_status(self):
        """
        Get the status of commercial proxy services
        
        Returns:
            Dictionary with status information
        """
        status = {
            "enabled": self.config["proxy_services"]["enabled"],
            "current_service": self.config["proxy_services"]["current_service"],
            "services": {},
            "licensed": "commercial_proxies" in self.license_status.get("enabled_features", [])
        }
        
        for service in ["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"]:
            service_config = self.config["proxy_services"][service]
            status["services"][service] = {
                "enabled": service_config["enabled"],
                "country": service_config.get("country", "us")
            }
            
            # Add country pool if available
            if "country_pool" in service_config:
                status["services"][service]["country_pool"] = service_config["country_pool"]
        
        return status
    
    def rotate_fingerprint(self):
        """
        Rotate to a new browser fingerprint
        
        Returns:
            Dictionary containing the new fingerprint
        """
        if not self.config["browser_fingerprints"]["enabled"]:
            logger.warning("Browser fingerprinting is disabled")
            return None
        
        # Check if advanced features are licensed
        if "advanced_scraping" not in self.license_status.get("enabled_features", []):
            logger.warning("Advanced fingerprinting not available with current license")
            return None
        
        # Rotate fingerprint
        new_fingerprint = rotate_fingerprint(self.config)
        self.current_fingerprint = new_fingerprint
        
        return new_fingerprint
    
    def set_license_key(self, license_key):
        """
        Set and verify a license key
        
        Args:
            license_key: The license key to set
            
        Returns:
            Dictionary with license verification status
        """
        # Update license key in config
        self.config["licensing"]["license_key"] = license_key
        save_config(self.config)
        
        # Verify the license
        self.license_status = verify_license(self.config)
        
        return self.license_status
    
    def get_license_status(self):
        """
        Get the current license status
        
        Returns:
            Dictionary with license status
        """
        # Refresh license status
        self.license_status = verify_license(self.config)
        
        return self.license_status
    
    def generate_search_parameters(self, query):
        """
        Generate search parameters for job search using Claude integration
        
        Args:
            query: User query string for job search
            
        Returns:
            Dictionary with search parameters
        """
        # Check if Claude integration is enabled and licensed
        if not self.config["claude_integration"]["enabled"]:
            logger.warning("Claude integration is disabled")
            return {
                "keywords": ["entry level", "beginner", "junior", "html", "css", "remote"],
                "exclude_keywords": ["senior", "lead", "5+ years", "7+ years"],
                "locations": ["remote", "usa", "anywhere"]
            }
        
        if "claude_integration" not in self.license_status.get("enabled_features", []):
            logger.warning("Claude integration not available with current license")
            return {
                "keywords": ["entry level", "beginner", "junior", "html", "css", "remote"],
                "exclude_keywords": ["senior", "lead", "5+ years", "7+ years"],
                "locations": ["remote", "usa", "anywhere"]
            }
        
        # Generate search parameters with Claude
        return generate_search_params_with_claude(query, self.config)
    
    def add_custom_search_template(self, name, template):
        """
        Add a custom search template for Claude
        
        Args:
            name: Name of the template
            template: Template content (prompt)
            
        Returns:
            True if successful
        """
        # Check if Claude integration is enabled and licensed
        if not self.config["claude_integration"]["enabled"]:
            logger.warning("Claude integration is disabled")
            return False
        
        if "claude_integration" not in self.license_status.get("enabled_features", []):
            logger.warning("Claude integration not available with current license")
            return False
        
        # Add template
        self.config["claude_integration"]["custom_search_templates"][name.lower()] = template
        save_config(self.config)
        
        logger.info(f"Added custom search template: {name}")
        return True
    
    def get_custom_search_templates(self):
        """
        Get all available custom search templates
        
        Returns:
            Dictionary of templates
        """
        return self.config["claude_integration"]["custom_search_templates"]
    
    def configure_claude_integration(self, api_key=None, model=None):
        """
        Configure Claude API settings
        
        Args:
            api_key: Claude API key
            model: Claude model to use
            
        Returns:
            True if successful
        """
        if api_key:
            self.config["claude_integration"]["api_key"] = api_key
        
        if model:
            self.config["claude_integration"]["model"] = model
        
        # Enable Claude integration if API key is set
        if api_key and api_key.strip():
            self.config["claude_integration"]["enabled"] = True
        
        save_config(self.config)
        logger.info("Updated Claude integration settings")
        
        return True


# Test the VPN manager if run directly
if __name__ == "__main__":
    print("Testing VPN Manager...")
    
    vpn = VPNManager()
    
    test_urls = [
        "https://www.google.com",
        "https://www.indeed.com",
        "https://www.remoteok.com"
    ]
    
    # First test standard proxies
    print("\n=== Testing Standard Proxies ===")
    for url in test_urls:
        print(f"Testing access to {url}...")
        result = vpn.get(url)
        
        if result:
            print(f"✅ Successfully accessed {url}")
            print(f"   Response length: {len(result)} characters")
        else:
            print(f"❌ Failed to access {url}")
    
    print("\nTesting proxy rotation...")
    old_proxy = vpn.config["proxies"][vpn.config["current_proxy_index"]]
    new_proxy = vpn.rotate_proxy()
    
    print(f"Rotated from proxy {old_proxy} to {new_proxy}")
    
    # Now test commercial proxy services if credentials are provided
    print("\n=== Testing Commercial Proxy Services ===")
    print("Note: You need to provide real credentials in vpn_config.json to test these services.")
    
    # Get the status of commercial proxy services
    status = vpn.get_commercial_proxy_status()
    if status["enabled"]:
        print(f"Commercial proxy services are enabled. Current service: {status['current_service']}")
        
        # Print status of each service
        for service_name, service_status in status["services"].items():
            enabled = "✅ Enabled" if service_status["enabled"] else "❌ Disabled"
            print(f"{service_name}: {enabled}")
        
        # Example: Test each enabled service with a test URL
        test_url = "https://httpbin.org/ip"
        print(f"\nTesting each enabled service with {test_url}...")
        
        for service_name, service_status in status["services"].items():
            if service_status["enabled"]:
                print(f"\nTesting {service_name}...")
                
                # Try to fetch using this service
                if service_name == "brightdata":
                    content = fetch_using_brightdata(test_url, config=vpn.config)
                elif service_name == "oxylabs":
                    content = fetch_using_oxylabs(test_url, config=vpn.config)
                elif service_name == "smartproxy":
                    content = fetch_using_smartproxy(test_url, config=vpn.config)
                elif service_name == "proxymesh":
                    content = fetch_using_proxymesh(test_url, config=vpn.config)
                elif service_name == "zenrows":
                    content = fetch_using_zenrows(test_url, config=vpn.config)
                elif service_name == "scraperapi":
                    content = fetch_using_scraperapi(test_url, config=vpn.config)
                else:
                    content = None
                
                if content:
                    print(f"✅ Successfully accessed {test_url} using {service_name}")
                    print(f"Response: {content[:200]}...")
                else:
                    print(f"❌ Failed to access {test_url} using {service_name}")
    else:
        print("Commercial proxy services are disabled. To enable them:")
        print("1. Edit vpn_config.json or use the vpn.enable_commercial_proxy() method")
        print("2. Set 'enabled' to true in the proxy_services section")
        print("3. Configure at least one service with valid credentials")
        print("\nExample code to enable a service:")
        print("    vpn.enable_commercial_proxy('brightdata', username='user123', password='pass123')")
    
    # Provide instructions for using the VPN Manager
    print("\n=== How to Use VPN Manager in Your Code ===")
    print("""
    # Initialize the VPN Manager
    from vpn_manager import VPNManager
    
    vpn = VPNManager()
    
    # Make a request with automatic proxy rotation and retries
    html = vpn.get("https://www.indeed.com/jobs?q=python")
    
    # Manually rotate to a different proxy
    vpn.rotate_proxy()
    
    # Enable a commercial proxy service
    vpn.enable_commercial_proxy(
        'brightdata',
        username='your_username',
        password='your_password',
        zone='your_zone',
        country='us'
    )
    """)
    
    print("\nVPN Manager test complete!")