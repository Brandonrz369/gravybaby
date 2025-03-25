#!/usr/bin/env python3

"""
Test script for VPN Manager with commercial proxy services

This script demonstrates how to use the VPN Manager with different
commercial proxy services to access websites that might block standard requests.

Usage:
  python test_proxies.py
"""

import argparse
import os
import sys
import time
from vpn_manager import VPNManager

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test VPN Manager with commercial proxy services")
    parser.add_argument("--service", type=str, default=None,
                        choices=["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"],
                        help="Specific service to test (tests all enabled services if not specified)")
    parser.add_argument("--url", type=str, default="https://httpbin.org/ip", 
                        help="URL to use for testing (default: https://httpbin.org/ip)")
    parser.add_argument("--setup", action="store_true",
                        help="Run interactive setup for a proxy service")
    return parser.parse_args()

def interactive_setup():
    """Interactive setup for a proxy service"""
    print("\n=== Commercial Proxy Service Setup ===")
    print("Available services:")
    print("1. Bright Data (formerly Luminati)")
    print("2. Oxylabs")
    print("3. SmartProxy")
    print("4. ProxyMesh")
    print("5. ZenRows")
    print("6. ScraperAPI")
    
    try:
        choice = int(input("\nSelect a service (1-6): "))
        if choice < 1 or choice > 6:
            print("Invalid choice. Please select a number between 1 and 6.")
            return False
    except ValueError:
        print("Invalid input. Please enter a number.")
        return False
    
    services = ["brightdata", "oxylabs", "smartproxy", "proxymesh", "zenrows", "scraperapi"]
    selected_service = services[choice - 1]
    
    print(f"\nSetting up {selected_service}...")
    
    # Initialize VPN Manager
    vpn = VPNManager()
    
    # Collect credentials based on the service
    if selected_service in ["brightdata", "oxylabs", "smartproxy", "proxymesh"]:
        username = input("Enter username: ")
        password = input("Enter password: ")
        
        if selected_service == "brightdata":
            zone = input("Enter zone (e.g., 'data_center'): ")
            country = input("Enter country code (e.g., 'us', 'uk'): ")
            session_id = input("Enter session ID (or press Enter for default): ") or "gravy_jobs_session"
            
            vpn.enable_commercial_proxy(selected_service, 
                                        username=username, 
                                        password=password,
                                        zone=zone,
                                        country=country,
                                        session_id=session_id)
        
        elif selected_service == "oxylabs":
            country = input("Enter country code (e.g., 'us', 'uk'): ")
            
            vpn.enable_commercial_proxy(selected_service, 
                                        username=username, 
                                        password=password,
                                        country=country)
        
        else:  # smartproxy or proxymesh
            vpn.enable_commercial_proxy(selected_service, 
                                        username=username, 
                                        password=password)
    
    else:  # zenrows or scraperapi
        api_key = input("Enter API key: ")
        vpn.enable_commercial_proxy(selected_service, api_key=api_key)
    
    print(f"\n✅ Successfully configured {selected_service}!")
    return True

def test_service(vpn, service_name=None, test_url="https://httpbin.org/ip"):
    """Test a specific proxy service"""
    if service_name:
        # Enable only the specified service
        status = vpn.get_commercial_proxy_status()
        
        if not status["services"][service_name]["enabled"]:
            print(f"⚠️  {service_name} is not enabled. Please configure it first.")
            return False
        
        # Set the current service to the one we want to test
        vpn.config["proxy_services"]["current_service"] = service_name
        vpn.config["proxy_services"]["enabled"] = True
        
        print(f"\n=== Testing {service_name} ===")
        print(f"Accessing {test_url}...")
        
        start_time = time.time()
        content = vpn.get(test_url, force_fresh=True)
        elapsed = time.time() - start_time
        
        if content:
            print(f"✅ Successfully accessed {test_url} using {service_name}")
            print(f"   Response time: {elapsed:.2f} seconds")
            print(f"   Response content: {content[:200]}...")
            return True
        else:
            print(f"❌ Failed to access {test_url} using {service_name}")
            return False
    else:
        # Test all enabled services
        status = vpn.get_commercial_proxy_status()
        
        if not status["enabled"]:
            print("⚠️  Commercial proxy services are not enabled.")
            return False
        
        success_count = 0
        total_enabled = 0
        
        for service_name, service_status in status["services"].items():
            if service_status["enabled"]:
                total_enabled += 1
                if test_service(vpn, service_name, test_url):
                    success_count += 1
        
        if total_enabled == 0:
            print("⚠️  No commercial proxy services are enabled.")
            return False
        
        print(f"\n=== Test Summary ===")
        print(f"Successful services: {success_count}/{total_enabled}")
        return success_count > 0

def main():
    """Main function"""
    args = parse_arguments()
    
    if args.setup:
        if interactive_setup():
            print("\nSetup complete. You can now test the service.")
        return
    
    # Initialize VPN Manager
    vpn = VPNManager()
    
    # Display current status
    status = vpn.get_commercial_proxy_status()
    print("\n=== Current Proxy Status ===")
    print(f"Commercial proxies enabled: {'✅ Yes' if status['enabled'] else '❌ No'}")
    print(f"Current service: {status['current_service'] or 'None'}")
    
    print("\nAvailable services:")
    for service_name, service_status in status["services"].items():
        enabled = "✅ Enabled" if service_status["enabled"] else "❌ Disabled"
        print(f"- {service_name}: {enabled}")
    
    # Test services
    if not test_service(vpn, args.service, args.url):
        print("\nTip: You can set up a proxy service with: python test_proxies.py --setup")
    
    # Print example code
    print("\n=== Example Code for This Service ===")
    service = args.service or status["current_service"] or "brightdata"
    print(f"""
from vpn_manager import VPNManager

# Initialize VPN Manager
vpn = VPNManager()

# Enable {service} (replace with your credentials)
vpn.enable_commercial_proxy(
    "{service}",
    # Add your credentials here:
    username="your_username", 
    password="your_password"
)

# Use the VPN manager to access a site
content = vpn.get("https://www.indeed.com/jobs?q=python")
if content:
    print(f"Success! Received {len(content)} bytes of data")
else:
    print("Failed to access the site")
""")

if __name__ == "__main__":
    main()