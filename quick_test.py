#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime

# Add the current directory to the path so we can import the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the JobScraper class
from job_scraper import JobScraper, CONFIG

def main():
    """Run a quick test of the job scraper without sending emails"""
    print("=== Job Scraper Quick Test ===")
    print(f"Keywords: {CONFIG['keywords']}")
    print("This will check for jobs but NOT send emails\n")
    
    # Modify config for testing
    test_config = CONFIG.copy()
    test_config["max_jobs_per_source"] = 3  # Limit to 3 jobs per source for quick testing
    
    # Create the scraper
    scraper = JobScraper(test_config)
    
    # Run the scraping
    print("Scraping for jobs...")
    jobs = scraper.scrape_all_sources()
    
    # Display results
    if jobs:
        print(f"\nFound {len(jobs)} matching jobs!")
        
        # Group jobs by source
        jobs_by_source = {}
        for job in jobs:
            source = job['source']
            if source not in jobs_by_source:
                jobs_by_source[source] = []
            jobs_by_source[source].append(job)
        
        # Display jobs by source
        for source, source_jobs in jobs_by_source.items():
            print(f"\n=== {source} ({len(source_jobs)}) ===")
            for job in source_jobs:
                print(f"Title: {job['title']}")
                if 'company' in job:
                    print(f"Company: {job['company']}")
                print(f"URL: {job['url']}")
                print(f"Description: {job['description'][:100]}...")
                print("-" * 50)
        
        # Save jobs to a test file
        test_file = "test_jobs.json"
        with open(test_file, 'w') as f:
            json.dump(jobs, f, indent=2)
        print(f"\nJobs saved to {test_file}")
    else:
        print("\nNo matching jobs found. Try adjusting your keywords.")
    
    print("\nTest complete!")

if __name__ == "__main__":
    main()