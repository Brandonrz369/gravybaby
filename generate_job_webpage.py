#!/usr/bin/env python3

import sys
import os
import json
import logging
from datetime import datetime

# Add the current directory to the path so we can import the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the JobScraper class
from job_scraper import JobScraper, CONFIG, logger

def main():
    """Run the job scraper once and generate the HTML report"""
    print("=== Job Scraper Webpage Generator ===")
    print("This will find jobs from multiple sources and create an interactive webpage")
    
    # Create the scraper
    scraper = JobScraper(CONFIG)
    
    # Run the scraping
    print("Scraping for jobs... (this may take a few minutes)")
    jobs = scraper.scrape_all_sources()
    
    if jobs:
        print(f"\nFound {len(jobs)} matching jobs!")
        
        # Combine with previous jobs if any
        all_jobs = scraper.previous_jobs + jobs
        scraper.all_jobs = all_jobs
        
        # Save all jobs
        print("Saving all jobs to file...")
        scraper.save_jobs()
        
        # Rank jobs
        print("Ranking jobs by relevance...")
        top_jobs = scraper.rank_top_jobs(limit=100)
        print(f"Selected top {len(top_jobs)} jobs")
        
        # Generate HTML report
        print("Generating HTML report...")
        scraper.generate_html_report(top_jobs)
        
        print(f"\nDone! Web page created at: {os.path.abspath(CONFIG['web_output'])}")
        print(f"Open the file in your browser to view the interactive job listings")
    else:
        print("\nNo matching jobs found. Try adjusting your keywords.")

if __name__ == "__main__":
    # Configure logging to console as well as file
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    main()