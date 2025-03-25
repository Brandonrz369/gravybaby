#\!/usr/bin/env python3

"""
Quick test script for Gravy Jobs features
Run this to test the application without getting stuck in infinite loops
"""

import sys
import json
from datetime import datetime
from vpn_manager import VPNManager
from job_scraper import JobScraper, CONFIG

def test_claude_api(vpn):
    """Test Claude API integration"""
    print("\n=== Testing Claude API ===")
    
    # Check if configured
    claude_config = vpn.config["claude_integration"]
    api_key = claude_config.get("api_key", "")
    model = claude_config.get("model", "")
    enabled = claude_config.get("enabled", False)
    
    print(f"Claude API enabled: {enabled}")
    print(f"API key configured: {'Yes' if api_key else 'No'}")
    print(f"Model: {model}")
    
    # Test query
    if api_key and enabled:
        print("\nTesting with query: 'Find remote Python developer jobs with Django experience'")
        try:
            params = vpn.generate_search_parameters("Find remote Python developer jobs with Django experience")
            print("\nGenerated search parameters:")
            print(json.dumps(params, indent=2))
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("\nClaude API not configured. To configure:")
        print("1. Set your license key first: TEST-GRAVY-JOBS-12345")
        print("2. Configure Claude API key: your-claude-api-key")
        
def test_license(vpn):
    """Test license verification"""
    print("\n=== Testing License System ===")
    
    # Get current status
    status = vpn.get_license_status()
    print(f"License valid: {status.get('valid', False)}")
    print(f"Enabled features: {', '.join(status.get('enabled_features', ['None']))}")
    
    # Try setting test key if not already set
    if not status.get("valid", False):
        print("\nSetting test license key: TEST-GRAVY-JOBS-12345")
        vpn.set_license_key("TEST-GRAVY-JOBS-12345")
        
        # Check status again
        status = vpn.get_license_status()
        print(f"License now valid: {status.get('valid', False)}")
        print(f"Enabled features: {', '.join(status.get('enabled_features', ['None']))}")

def generate_test_jobs():
    """Generate test job data"""
    return [
        {
            "title": "Python Developer (Remote)",
            "company": "TestCorp Inc.",
            "description": "Entry-level position for Python developers. Work from anywhere\!",
            "url": "https://example.com/jobs/1",
            "source": "Indeed",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "salary": "$70,000 - $90,000"
        },
        {
            "title": "Junior Web Developer",
            "company": "WebSolutions LLC",
            "description": "Looking for a junior developer with HTML, CSS, and JavaScript skills.",
            "url": "https://example.com/jobs/2", 
            "source": "RemoteOK",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "salary": "$25/hour"
        },
        {
            "title": "Entry-Level Software Engineer",
            "company": "StartupCo",
            "description": "Great opportunity for new graduates. Remote work available.",
            "url": "https://example.com/jobs/3",
            "source": "LinkedIn",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

def main():
    print("=== Gravy Jobs Quick Test ===")
    
    # Initialize VPN Manager
    print("\nInitializing VPN Manager...")
    vpn = VPNManager()
    
    # Test license system
    test_license(vpn)
    
    # Test Claude API
    test_claude_api(vpn)
    
    # Test job scraper HTML generation
    print("\n=== Testing Job Scraper HTML Generation ===")
    scraper = JobScraper(CONFIG)
    test_jobs = generate_test_jobs()
    print(f"Generating HTML report with {len(test_jobs)} sample jobs...")
    scraper.generate_html_report(test_jobs)
    print("HTML report generated successfully. Open jobs.html to view results.")
    
    print("\nAll tests completed successfully\!")
    
if __name__ == "__main__":
    main()
