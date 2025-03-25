#!/usr/bin/env python3

"""
Test script for Gravy Jobs features
This script demonstrates all the new features of Gravy Jobs including:
- VPN/proxy rotation with browser fingerprinting
- Commercial proxy integration
- Claude API integration for custom search parameters
- License validation
"""

import argparse
import json
import os
import sys
import time
from vpn_manager import VPNManager

def test_vpn_features():
    """Test VPN and proxy features"""
    print("\n=== Testing VPN and Proxy Features ===")
    
    vpn = VPNManager()
    
    # Test proxy rotation
    print("\nTesting proxy rotation...")
    current_proxy = vpn.config["current_proxy_index"]
    print(f"Current proxy index: {current_proxy}")
    
    for i in range(3):
        vpn.rotate_proxy()
        new_proxy = vpn.config["current_proxy_index"]
        print(f"Rotated to proxy index: {new_proxy}")
        time.sleep(1)
    
    # Test browser fingerprinting
    if vpn.config["browser_fingerprints"]["enabled"]:
        print("\nTesting browser fingerprinting...")
        current_fingerprint = vpn.current_fingerprint
        print(f"Current fingerprint ID: {current_fingerprint.get('id', 'Unknown')}")
        
        for i in range(2):
            new_fingerprint = vpn.rotate_fingerprint()
            if new_fingerprint:
                print(f"Rotated to fingerprint ID: {new_fingerprint.get('id', 'Unknown')}")
                print(f"User agent: {new_fingerprint.get('user_agent', 'Unknown')[:50]}...")
                time.sleep(1)
    else:
        print("\nBrowser fingerprinting is disabled. Enable with --fingerprint-on")
    
    # Test commercial proxy status
    print("\nCommercial proxy status:")
    status = vpn.get_commercial_proxy_status()
    print(f"Enabled: {status['enabled']}")
    print(f"Licensed: {status['licensed']}")
    print(f"Current service: {status['current_service']}")
    
    for service, service_status in status["services"].items():
        enabled = "✅ Enabled" if service_status["enabled"] else "❌ Disabled"
        country = service_status.get("country", "us")
        print(f"- {service}: {enabled} (Country: {country})")

def test_claude_integration():
    """Test Claude API integration"""
    print("\n=== Testing Claude API Integration ===")
    
    vpn = VPNManager()
    
    # Check if Claude is enabled and configured
    if not vpn.config["claude_integration"]["enabled"]:
        print("Claude integration is disabled. Configure with --configure-claude YOUR_API_KEY")
        return
    
    # Check if Claude is licensed
    license_status = vpn.get_license_status()
    if "claude_integration" not in license_status.get("enabled_features", []):
        print("Claude integration is not available with your license")
        return
    
    print("Claude API is configured and licensed")
    
    # Show available templates
    templates = vpn.get_custom_search_templates()
    print("\nAvailable search templates:")
    for name, template in templates.items():
        print(f"- {name}: {template[:50]}...")
    
    # Test custom search queries
    test_queries = [
        "Find DevOps jobs in Seattle",
        "Entry level data scientist positions in biotech",
        "Remote frontend developer jobs with React"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: '{query}'")
        params = vpn.generate_search_parameters(query)
        print("Generated search parameters:")
        print(f"- Keywords: {params.get('keywords', [])}")
        print(f"- Exclude: {params.get('exclude_keywords', [])}")
        print(f"- Locations: {params.get('locations', [])}")

def test_license_status():
    """Test license status and features"""
    print("\n=== Testing License Status ===")
    
    vpn = VPNManager()
    status = vpn.get_license_status()
    
    print(f"License status: {'Valid' if status.get('valid', False) else 'Invalid or missing'}")
    
    if status.get("valid", False):
        print(f"Valid until: {status.get('valid_until', 'Unknown')}")
        print(f"Enabled features: {status.get('enabled_features', [])}")
    else:
        print("No valid license. Get a license key for premium features.")
        print("You can set a test license with: --license-key TEST-1234")

def test_website_access():
    """Test website access with VPN/proxies"""
    print("\n=== Testing Website Access ===")
    
    vpn = VPNManager()
    test_urls = [
        "https://www.google.com",
        "https://www.indeed.com",
        "https://www.remoteok.com"
    ]
    
    for url in test_urls:
        print(f"\nTesting access to {url}...")
        start_time = time.time()
        
        try:
            content = vpn.get(url, timeout=15)
            elapsed = time.time() - start_time
            
            if content:
                print(f"✅ Successfully accessed {url} in {elapsed:.2f}s")
                print(f"   Response length: {len(content)} characters")
            else:
                print(f"❌ Failed to access {url}")
        except Exception as e:
            print(f"❌ Error accessing {url}: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test Gravy Jobs features")
    parser.add_argument("--vpn", action="store_true", help="Test VPN and proxy features")
    parser.add_argument("--claude", action="store_true", help="Test Claude API integration")
    parser.add_argument("--license", action="store_true", help="Test license status")
    parser.add_argument("--access", action="store_true", help="Test website access")
    parser.add_argument("--all", action="store_true", help="Test all features")
    args = parser.parse_args()
    
    # If no specific tests requested, show help
    if not any([args.vpn, args.claude, args.license, args.access, args.all]):
        parser.print_help()
        return
    
    print("Gravy Jobs Feature Test")
    print("======================")
    
    if args.all or args.vpn:
        test_vpn_features()
    
    if args.all or args.claude:
        test_claude_integration()
    
    if args.all or args.license:
        test_license_status()
    
    if args.all or args.access:
        test_website_access()
    
    print("\nTest completed!")

if __name__ == "__main__":
    main()