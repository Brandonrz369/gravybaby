#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_scraper')

# Configuration
CONFIG = {
    "keywords": ["simple", "basic", "beginner", "wordpress", "html", "css"],
    "max_jobs": 5
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def contains_keywords(text, keywords):
    """Check if text contains any of the specified keywords"""
    if not text:
        return False
    text = text.lower()
    return any(keyword.lower() in text for keyword in keywords)

def test_scrape_upwork():
    """Test scraping Upwork"""
    print("\n===== Testing Upwork Scraping =====")
    jobs = []
    try:
        url = "https://www.upwork.com/nx/jobs/search/?q=programming&sort=recency"
        logger.info(f"Fetching: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch Upwork: Status {response.status_code}")
            return jobs
            
        print(f"Successfully fetched Upwork (Status: {response.status_code})")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Print page title to verify we got the right page
        print(f"Page title: {soup.title.text if soup.title else 'No title'}")
        
        # Look for job listings
        # Print some sample HTML to help identify the correct selectors
        print("Sample HTML structure:")
        job_container = soup.select('.job-tile-list, .air3-card')
        if job_container:
            print(f"Found potential job containers: {len(job_container)} items")
            sample = job_container[0]
            print(f"First container sample: {sample.prettify()[:500]}...")
        else:
            print("No job containers found. This could be due to:")
            print("1. Upwork's HTML structure has changed")
            print("2. Upwork is blocking the scraper")
            print("3. The selectors need to be updated")
    
    except Exception as e:
        print(f"Error testing Upwork: {str(e)}")
    
    return jobs

def test_scrape_freelancer():
    """Test scraping Freelancer"""
    print("\n===== Testing Freelancer Scraping =====")
    jobs = []
    try:
        url = "https://www.freelancer.com/jobs/programming/"
        logger.info(f"Fetching: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch Freelancer: Status {response.status_code}")
            return jobs
            
        print(f"Successfully fetched Freelancer (Status: {response.status_code})")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Print page title to verify we got the right page
        print(f"Page title: {soup.title.text if soup.title else 'No title'}")
        
        # Look for job listings
        # Print some sample HTML to help identify the correct selectors
        print("Sample HTML structure:")
        job_container = soup.select('.JobSearchCard-item, .project-card')
        if job_container:
            print(f"Found potential job containers: {len(job_container)} items")
            sample = job_container[0]
            print(f"First container sample: {sample.prettify()[:500]}...")
        else:
            print("No job containers found. This could be due to:")
            print("1. Freelancer's HTML structure has changed")
            print("2. Freelancer is blocking the scraper")
            print("3. The selectors need to be updated")
    
    except Exception as e:
        print(f"Error testing Freelancer: {str(e)}")
    
    return jobs

def test_scrape_craigslist():
    """Test scraping Craigslist"""
    print("\n===== Testing Craigslist Scraping =====")
    jobs = []
    try:
        url = "https://newyork.craigslist.org/search/web"
        logger.info(f"Fetching: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch Craigslist: Status {response.status_code}")
            return jobs
            
        print(f"Successfully fetched Craigslist (Status: {response.status_code})")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Print page title to verify we got the right page
        print(f"Page title: {soup.title.text if soup.title else 'No title'}")
        
        # Look for job listings
        job_listings = soup.select('.result-info')[:CONFIG["max_jobs"]]
        if job_listings:
            print(f"Found {len(job_listings)} job listings")
            
            for job in job_listings:
                title_elem = job.select_one('.result-title')
                link_elem = job.select_one('a.result-title')
                
                if title_elem and link_elem:
                    title = title_elem.text.strip()
                    url = link_elem['href']
                    print(f"Job found: {title} - {url}")
                    
                    # Check if job matches keywords
                    if contains_keywords(title, CONFIG["keywords"]):
                        print(f"✓ Matches keywords: {title}")
                        jobs.append({
                            'title': title,
                            'url': url,
                            'source': 'Craigslist'
                        })
        else:
            print("No job listings found. This could be due to:")
            print("1. Craigslist's HTML structure has changed")
            print("2. The selectors need to be updated")
    
    except Exception as e:
        print(f"Error testing Craigslist: {str(e)}")
    
    return jobs

if __name__ == "__main__":
    print("=== Job Scraper Test ===")
    print("This will test the scraper's ability to connect to job sites and parse listings")
    print(f"Keywords: {CONFIG['keywords']}")
    
    try:
        import requests
        from bs4 import BeautifulSoup
        print("Required packages are installed")
    except ImportError:
        print("Required packages not found. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "requests", "beautifulsoup4"])
        print("Packages installed")
    
    # Test each platform
    upwork_jobs = test_scrape_upwork()
    freelancer_jobs = test_scrape_freelancer()
    craigslist_jobs = test_scrape_craigslist()
    
    # Summary
    print("\n=== Test Summary ===")
    print(f"Upwork: {len(upwork_jobs)} matching jobs found")
    print(f"Freelancer: {len(freelancer_jobs)} matching jobs found")
    print(f"Craigslist: {len(craigslist_jobs)} matching jobs found")
    
    total_jobs = len(upwork_jobs) + len(freelancer_jobs) + len(craigslist_jobs)
    print(f"\nTotal matching jobs: {total_jobs}")
    print("\nNote: This is just a test of connectivity and parsing. The actual scraper")
    print("might find different results and will run continuously to find new jobs.")