#!/usr/bin/env python3

import sys
import os
import json
import logging
import time
import http.server
import socketserver
import webbrowser
import threading
import argparse
import concurrent.futures
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from pathlib import Path
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gravy_jobs.log'
)
logger = logging.getLogger('gravy_jobs_app')

# Your Claude API key (hardcoded for convenience)
CLAUDE_API_KEY = "YOUR_API_KEY_HERE"  # Replace with your API key before using

# Configuration
CONFIG = {
    "keywords": ["simple", "basic", "beginner", "entry level", "junior", "wordpress", "html", "css", "remote"],
    "exclude_keywords": ["senior", "lead", "expert", "5+ years", "7+ years", "10+ years"],
    "major_cities": [
        "newyork", "losangeles", "chicago", "houston", "phoenix", "philadelphia", 
        "sanantonio", "sandiego", "dallas", "austin", "sanjose", "seattle", "denver",
        "boston", "remote"
    ],
    "job_sources": {
        "upwork": False,  # Set to False due to blocking (403 error)
        "fiverr": False,  # Fiverr is not primarily a job platform, difficult to scrape
        "freelancer": True,
        "craigslist": True,
        "indeed": True,
        "remoteok": True,
        "linkedin": True,
        "stackoverflow": True,
        "glassdoor": False  # Requires login
    },
    "check_interval_hours": 24,  # Check once a day
    "max_jobs_per_source": 20,  # Number of jobs to scrape per source
    "data_file": "all_jobs.json",
    "top_jobs_file": "top_jobs.json",
    "web_output": "gravy_jobs.html",
    "batch_size": 3,  # Number of jobs to send to Claude API at once
    "analysis_dir": "analysis_chunks"
}

class JobScraper:
    def __init__(self, config):
        self.config = config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.all_jobs = []
        self.previous_jobs = self.load_previous_jobs()
        self.new_jobs = []

    def load_previous_jobs(self):
        """Load previously scraped jobs from file"""
        try:
            if os.path.exists(self.config["data_file"]):
                with open(self.config["data_file"], 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading previous jobs: {e}")
            return []

    def save_jobs(self):
        """Save current jobs to file"""
        try:
            # Combine previous and new jobs, keeping only unique entries
            all_jobs = self.previous_jobs + self.new_jobs
            # Create a set of job URLs to identify unique jobs
            unique_urls = set()
            unique_jobs = []
            
            for job in all_jobs:
                if job['url'] not in unique_urls:
                    unique_urls.add(job['url'])
                    unique_jobs.append(job)
            
            # Limit the number of saved jobs to prevent the file from growing too large
            unique_jobs = sorted(unique_jobs, key=lambda x: x.get('date', ''), reverse=True)[:1000]
            
            with open(self.config["data_file"], 'w', encoding='utf-8') as f:
                json.dump(unique_jobs, f, indent=2, ensure_ascii=False)
            
            self.previous_jobs = unique_jobs
            self.all_jobs = unique_jobs
        except Exception as e:
            logger.error(f"Error saving jobs: {e}")

    def contains_keywords(self, text):
        """Check if text contains any of the specified keywords"""
        if not text:
            return False
        text = text.lower()
        return any(keyword.lower() in text for keyword in self.config["keywords"])

    def contains_excluded_keywords(self, text):
        """Check if text contains any of the excluded keywords"""
        if not text:
            return False
        text = text.lower()
        return any(keyword.lower() in text for keyword in self.config["exclude_keywords"])

    def is_new_job(self, job):
        """Check if a job is new (not in previous jobs)"""
        for prev_job in self.previous_jobs:
            if prev_job['url'] == job['url']:
                return False
        return True

    def scrape_freelancer(self):
        """Scrape entry-level programming jobs from Freelancer"""
        jobs = []
        try:
            url = "https://www.freelancer.com/jobs/programming"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Freelancer: Status {response.status_code}")
                return jobs
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Updated selectors based on current Freelancer HTML structure
            job_listings = soup.select('.JobSearchCard-item')[:self.config["max_jobs_per_source"]]
            
            for job in job_listings:
                title_elem = job.select_one('.JobSearchCard-primary-heading-link')
                desc_elem = job.select_one('.JobSearchCard-primary-description')
                price_elem = job.select_one('.JobSearchCard-primary-price')
                
                if title_elem:
                    title = title_elem.text.strip()
                    url = "https://www.freelancer.com" + title_elem['href'] if title_elem.has_attr('href') else ""
                    description = desc_elem.text.strip() if desc_elem else ""
                    salary = price_elem.text.strip() if price_elem else None
                    
                    # Log the job for debugging
                    logger.info(f"Freelancer job found: {title}")
                    
                    # We'll accept all jobs since we're ranking them later
                    job_data = {
                        'title': title,
                        'description': description[:300] + "..." if len(description) > 300 else description,
                        'url': url,
                        'source': 'Freelancer',
                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'salary': salary
                    }
                    jobs.append(job_data)
                    logger.info(f"Added Freelancer job: {title}")
        except Exception as e:
            logger.error(f"Error scraping Freelancer: {e}")
        
        return jobs

    def scrape_craigslist(self):
        """Scrape entry-level programming jobs from Craigslist in multiple cities"""
        all_jobs = []
        
        for city in self.config["major_cities"]:
            try:
                # For each city, try both general and web dev jobs
                categories = ["web", "sof"]  # web dev and software jobs
                
                for category in categories:
                    url = f"https://{city}.craigslist.org/search/{category}"
                    logger.info(f"Fetching Craigslist: {url}")
                    
                    try:
                        response = requests.get(url, headers=self.headers)
                        
                        if response.status_code != 200:
                            logger.error(f"Failed to fetch Craigslist {city}/{category}: Status {response.status_code}")
                            continue
                            
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Try different selectors for Craigslist
                        job_listings = []
                        selectors = [
                            'li.cl-static-search-result', 
                            '.result-info',
                            'div.result-row',
                            'li.result-row'
                        ]
                        
                        for selector in selectors:
                            listings = soup.select(selector)
                            if listings:
                                logger.info(f"Found {len(listings)} job listings in {city}/{category} with selector: {selector}")
                                job_listings = listings[:self.config["max_jobs_per_source"]]
                                break
                        
                        if not job_listings:
                            logger.error(f"Could not find job listings on Craigslist {city}/{category}")
                            continue
                        
                        city_jobs = []
                        for job in job_listings:
                            # Try different title selectors
                            title_elem = None
                            title_selectors = ['div.title', 'a.result-title', 'h3.result-heading', '.title']
                            for selector in title_selectors:
                                title_elem = job.select_one(selector)
                                if title_elem:
                                    break
                            
                            # Try different link selectors
                            link_elem = None
                            link_selectors = ['a.posting-title', 'a.result-title', 'a[href*="/web/"]', 'a[href*="/sof/"]']
                            for selector in link_selectors:
                                link_elem = job.select_one(selector)
                                if link_elem:
                                    break
                            
                            if title_elem and link_elem:
                                title = title_elem.text.strip()
                                url = link_elem['href']
                                
                                logger.info(f"Craigslist job found in {city}: {title}")
                                
                                try:
                                    # Visit job page to get details
                                    job_response = requests.get(url, headers=self.headers)
                                    job_soup = BeautifulSoup(job_response.text, 'html.parser')
                                    
                                    # Try different selectors for job description
                                    description_elem = None
                                    desc_selectors = ['#postingbody', '.body', '.posting-body']
                                    for selector in desc_selectors:
                                        description_elem = job_soup.select_one(selector)
                                        if description_elem:
                                            break
                                    
                                    description = description_elem.text.strip() if description_elem else ""
                                    
                                    # Extract compensation if available
                                    compensation = None
                                    comp_elem = job_soup.select_one('p.attrgroup:contains("compensation")')
                                    if comp_elem:
                                        compensation = comp_elem.text.strip()
                                    else:
                                        # Try to find it in the description
                                        salary_patterns = [
                                            r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', 
                                            r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|dollars)',
                                            r'\d{1,3}(?:,\d{3})*(?:k|K)',
                                            r'\$\d{1,3}(?:,\d{3})*\s*-\s*\$\d{1,3}(?:,\d{3})*',
                                            r'\$\d{1,2}(?:\.\d{2})?\s*(?:per hour|\/hr|\/hour|an hour)',
                                            r'\d{2,3}\s*(?:per hour|\/hr|\/hour|an hour)',
                                        ]
                                        
                                        for pattern in salary_patterns:
                                            salary_match = re.search(pattern, description)
                                            if salary_match:
                                                compensation = salary_match.group(0)
                                                break
                                    
                                    job_data = {
                                        'title': title,
                                        'description': description[:300] + "..." if len(description) > 300 else description,
                                        'url': url,
                                        'source': f'Craigslist ({city})',
                                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        'salary': compensation
                                    }
                                    city_jobs.append(job_data)
                                    logger.info(f"Added Craigslist job from {city}: {title}")
                                except Exception as e:
                                    logger.error(f"Error getting Craigslist job details: {e}")
                        
                        # Add to all jobs
                        all_jobs.extend(city_jobs)
                        
                        # Sleep to avoid rate limiting
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Error scraping Craigslist {city}/{category}: {e}")
                
            except Exception as e:
                logger.error(f"Error setting up Craigslist scraper for {city}: {e}")
                
        return all_jobs

    def scrape_linkedin(self):
        """Scrape entry-level programming jobs from LinkedIn"""
        all_jobs = []
        
        # Search terms to try
        search_terms = [
            "entry level programming",
            "junior developer",
            "beginner programmer",
            "html css developer",
            "wordpress developer"
        ]
        
        for search in search_terms:
            logger.info(f"Searching LinkedIn for: {search}")
            jobs = []
            
            try:
                encoded_search = search.replace(' ', '%20')
                url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_search}&sortBy=R"
                
                # Note: LinkedIn might block scraping attempts
                response = requests.get(url, headers=self.headers)
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch LinkedIn for '{search}': Status {response.status_code}")
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try to find job listings
                job_listings = soup.select('li.result-card')[:self.config["max_jobs_per_source"]]
                
                if not job_listings:
                    job_listings = soup.select('div.base-search-card')[:self.config["max_jobs_per_source"]]
                
                if not job_listings:
                    logger.error(f"Could not find job listings on LinkedIn for '{search}'")
                    continue
                
                logger.info(f"Found {len(job_listings)} LinkedIn job listings for '{search}'")
                
                for job in job_listings:
                    title_elem = job.select_one('h3.base-search-card__title')
                    company_elem = job.select_one('h4.base-search-card__subtitle')
                    link_elem = job.select_one('a.base-card__full-link')
                    location_elem = job.select_one('span.job-search-card__location')
                    
                    if title_elem and link_elem:
                        title = title_elem.text.strip()
                        company = company_elem.text.strip() if company_elem else "Unknown"
                        url = link_elem['href']
                        location = location_elem.text.strip() if location_elem else ""
                        
                        # We would need to visit each job page to get the description
                        # This can be slow and might get blocked, so we'll use a placeholder
                        description = f"Location: {location}"
                        
                        job_data = {
                            'title': title,
                            'company': company,
                            'description': description,
                            'url': url,
                            'source': 'LinkedIn',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        jobs.append(job_data)
                        logger.info(f"Added LinkedIn job: {title} at {company}")
                
                # Add this search's jobs to all_jobs
                all_jobs.extend(jobs)
                
                # Sleep to avoid rate limiting
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error scraping LinkedIn for '{search}': {e}")
        
        return all_jobs

    def scrape_indeed(self):
        """Scrape entry-level programming jobs from Indeed"""
        all_jobs = []
        
        # Search terms to try
        search_terms = [
            "entry level programming",
            "junior developer",
            "beginner programmer",
            "html css developer",
            "wordpress developer"
        ]
        
        for search in search_terms:
            logger.info(f"Searching Indeed for: {search}")
            jobs = []
            
            try:
                encoded_search = search.replace(' ', '+')
                url = f"https://www.indeed.com/jobs?q={encoded_search}&sort=date"
                response = requests.get(url, headers=self.headers)
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch Indeed for '{search}': Status {response.status_code}")
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                logger.info(f"Indeed page title: {soup.title.text if soup.title else 'No title'}")
                
                # Try different selectors for Indeed jobs
                job_listings = []
                selectors = [
                    'div.job_seen_beacon',
                    'div.jobsearch-ResultsList > div',
                    'div.result'
                ]
                
                for selector in selectors:
                    listings = soup.select(selector)
                    if listings:
                        logger.info(f"Found {len(listings)} job listings for '{search}' with selector: {selector}")
                        job_listings = listings[:self.config["max_jobs_per_source"]]
                        break
                
                if not job_listings:
                    logger.error(f"Could not find job listings on Indeed for '{search}'")
                    continue
                
                for i, job in enumerate(job_listings):
                    # Try different title selectors
                    title_elem = None
                    title_selectors = ['h2.jobTitle', 'h2.title', 'a.jobtitle', 'a.jcs-JobTitle']
                    for selector in title_selectors:
                        title_elem = job.select_one(selector)
                        if title_elem:
                            break
                    
                    # Try different company selectors
                    company_elem = None
                    company_selectors = ['span.companyName', 'div.company', 'span.company']
                    for selector in company_selectors:
                        company_elem = job.select_one(selector)
                        if company_elem:
                            break
                    
                    # Try different description selectors
                    desc_elem = None
                    desc_selectors = ['div.job-snippet', 'div.summary', 'span.summary']
                    for selector in desc_selectors:
                        desc_elem = job.select_one(selector)
                        if desc_elem:
                            break
                    
                    # Try different salary selectors
                    salary_elem = None
                    salary_selectors = ['div.salary-snippet', 'span.salaryText']
                    for selector in salary_selectors:
                        salary_elem = job.select_one(selector)
                        if salary_elem:
                            break
                    
                    # Extract job URL (Indeed uses different patterns)
                    job_url = ""
                    link_elem = None
                    link_selectors = ['a[id^="job_"]', 'a.jcs-JobTitle', 'a.jobtitle']
                    
                    for selector in link_selectors:
                        link_elem = job.select_one(selector)
                        if link_elem:
                            if 'href' in link_elem.attrs:
                                href = link_elem['href']
                                if href.startswith('/'):
                                    job_url = f"https://www.indeed.com{href}"
                                else:
                                    job_url = href
                                break
                            elif 'id' in link_elem.attrs:
                                job_id = link_elem['id'].replace('job_', '')
                                job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                                break
                    
                    if title_elem:
                        title = title_elem.text.strip()
                        company = company_elem.text.strip() if company_elem else "Unknown"
                        description = desc_elem.text.strip() if desc_elem else ""
                        salary = salary_elem.text.strip() if salary_elem else None
                        
                        # If no salary in dedicated field, try to extract from description
                        if not salary:
                            salary_patterns = [
                                r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', 
                                r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|dollars)',
                                r'\d{1,3}(?:,\d{3})*(?:k|K)',
                                r'\$\d{1,3}(?:,\d{3})*\s*-\s*\$\d{1,3}(?:,\d{3})*',
                                r'\$\d{1,2}(?:\.\d{2})?\s*(?:per hour|\/hr|\/hour|an hour)',
                                r'\d{2,3}\s*(?:per hour|\/hr|\/hour|an hour)',
                            ]
                            
                            for pattern in salary_patterns:
                                salary_match = re.search(pattern, description)
                                if salary_match:
                                    salary = salary_match.group(0)
                                    break
                        
                        logger.info(f"Indeed job found: {title} at {company}")
                        
                        # Accept all jobs during testing
                        job_data = {
                            'title': title,
                            'company': company,
                            'description': description[:300] + "..." if len(description) > 300 else description,
                            'url': job_url,
                            'source': 'Indeed',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'salary': salary
                        }
                        jobs.append(job_data)
                        logger.info(f"Added Indeed job: {title}")
                
                # Add this search's jobs to all_jobs
                all_jobs.extend(jobs)
                
                # Sleep to avoid rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scraping Indeed for '{search}': {e}")
        
        return all_jobs

    def scrape_remoteok(self):
        """Scrape entry-level programming jobs from RemoteOK"""
        jobs = []
        try:
            url = "https://remoteok.com/remote-dev-jobs"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch RemoteOK: Status {response.status_code}")
                return jobs
                
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.info(f"RemoteOK page title: {soup.title.text if soup.title else 'No title'}")
            
            # Try to find the job listings
            job_listings = soup.select('tr.job')[:self.config["max_jobs_per_source"]]
            
            if not job_listings:
                logger.error("Could not find job listings on RemoteOK")
                return jobs
            
            logger.info(f"Found {len(job_listings)} job listings on RemoteOK")
            
            for job in job_listings:
                # Extract job details
                title_elem = job.select_one('h2.position')
                company_elem = job.select_one('h3.company')
                desc_elem = job.select_one('div.description')
                link_elem = job.select_one('a.preventLink')
                salary_elem = job.select_one('div.salary')
                
                if title_elem and link_elem:
                    title = title_elem.text.strip()
                    href = link_elem.get('href', '')
                    url = f"https://remoteok.com{href}" if href.startswith('/') else href
                    company = company_elem.text.strip() if company_elem else "Unknown"
                    description = desc_elem.text.strip() if desc_elem else ""
                    salary = salary_elem.text.strip() if salary_elem else None
                    
                    logger.info(f"RemoteOK job found: {title} at {company}")
                    
                    # Accept all jobs during testing
                    job_data = {
                        'title': title,
                        'company': company,
                        'description': description[:300] + "..." if len(description) > 300 else description,
                        'url': url,
                        'source': 'RemoteOK',
                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'salary': salary
                    }
                    jobs.append(job_data)
                    logger.info(f"Added RemoteOK job: {title}")
        except Exception as e:
            logger.error(f"Error scraping RemoteOK: {e}")
        
        return jobs

    def scrape_all_sources(self):
        """Scrape jobs from all enabled sources in parallel"""
        self.new_jobs = []
        tasks = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            if self.config["job_sources"]["upwork"]:
                # Upwork tends to block scrapers (403)
                logger.info("Upwork scraping is disabled due to blocking")
            if self.config["job_sources"]["fiverr"]:
                # Fiverr is not primarily a job listing site
                logger.info("Fiverr scraping is disabled due to platform structure")
            if self.config["job_sources"]["freelancer"]:
                tasks.append(executor.submit(self.scrape_freelancer))
            if self.config["job_sources"]["craigslist"]:
                tasks.append(executor.submit(self.scrape_craigslist))
            if self.config["job_sources"]["indeed"]:
                tasks.append(executor.submit(self.scrape_indeed))
            if self.config["job_sources"]["remoteok"]:
                tasks.append(executor.submit(self.scrape_remoteok))
            if self.config["job_sources"]["linkedin"]:
                tasks.append(executor.submit(self.scrape_linkedin))
            
            for future in concurrent.futures.as_completed(tasks):
                try:
                    jobs = future.result()
                    for job in jobs:
                        if self.is_new_job(job):
                            self.new_jobs.append(job)
                except Exception as e:
                    logger.error(f"Error in job scraping task: {e}")
        
        return self.new_jobs

    def rank_top_jobs(self, jobs=None, limit=100):
        """Rank jobs by relevance score and return top ones"""
        if jobs is None:
            jobs = self.all_jobs
        
        # Use algorithm ranking as fallback in case Claude analysis fails
        for job in jobs:
            if 'score' not in job:
                score = 0
                title = job.get('title', '').lower()
                desc = job.get('description', '').lower()
                salary = job.get('salary', '')
                
                # Add points for keywords
                for keyword in self.config["keywords"]:
                    if keyword.lower() in title:
                        score += 10
                    if keyword.lower() in desc:
                        score += 5
                
                # Deduct points for excluded keywords
                for keyword in self.config["exclude_keywords"]:
                    if keyword.lower() in title:
                        score -= 15
                    if keyword.lower() in desc:
                        score -= 10
                
                # Add points for salary
                if salary:
                    score += 20
                
                # Add points for remote work
                if 'remote' in title or 'remote' in desc or 'work from home' in title or 'work from home' in desc:
                    score += 15
                
                job['score'] = score
            
        # Sort by score (highest first)
        ranked_jobs = sorted(jobs, key=lambda x: x.get('score', 0), reverse=True)
        
        # Take top jobs up to limit
        top_jobs = ranked_jobs[:limit]
        
        # Save top jobs to file
        with open(self.config["top_jobs_file"], 'w', encoding='utf-8') as f:
            json.dump(top_jobs, f, indent=2, ensure_ascii=False)
            
        return top_jobs


# Claude API Functions
def prepare_prompt_for_claude(jobs_batch):
    """Prepare a prompt for Claude to analyze a batch of jobs"""
    prompt = """You are analyzing entry-level programming jobs to determine how "gravy" they are. A "gravy" job is one that is easy for beginners, pays well relative to the work required, and is accessible to those with limited experience.

Please analyze each job based on:
1. How beginner-friendly it appears (terms like "entry-level", "junior", "beginner")
2. Whether the work seems easy/straightforward
3. Salary information (if available)
4. Remote work options
5. Technologies required (prioritize HTML/CSS, WordPress as more beginner-friendly)
6. Red flags (senior positions, advanced skills, years of experience required)

For each job, provide:
1. A "Gravy Score" from 0-100 (higher = more gravy)
2. 3-5 bullet points explaining your reasoning
3. A categorization (Amazing: 70-100, Great: 50-69, Good: 30-49, Decent: 10-29, Challenging: 0-9)

Here are the jobs to analyze:

"""
    
    for i, job in enumerate(jobs_batch):
        prompt += f"""
JOB {i+1}:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown') if 'company' in job else 'Unknown'}
Source: {job.get('source', 'Unknown')}
{"Salary: " + job.get('salary', '') if job.get('salary', '') else "Salary: Not specified"}
Description: {job.get('description', 'No description available')}
URL: {job.get('url', '')}

"""
    
    prompt += """
Respond ONLY in the following JSON format for each job:
```json
[
  {
    "job_id": 1,
    "gravy_score": 85,
    "category": "Amazing",
    "reasoning": [
      "Entry-level position explicitly mentioned in title",
      "Remote work available",
      "Good salary of $25/hour",
      "Only requires basic HTML/CSS knowledge",
      "No advanced skills mentioned"
    ]
  },
  {
    "job_id": 2,
    ...
  }
]
```
"""
    
    return prompt

def call_claude_api(prompt, api_key=None, model="claude-3-haiku-20240307", temperature=0.0):
    """Call the Claude API to analyze jobs"""
    # Use provided API key or fall back to global key
    if api_key is None:
        api_key = CLAUDE_API_KEY
        
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        error_msg = "No Claude API key provided. Please add your API key in the Settings tab."
        raise ValueError(error_msg)
    
    url = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": 4096
    }
    
    try:
        # Use safe print for Windows console
        try:
            print(f"Calling Claude API with model: {model}...")
        except UnicodeEncodeError:
            print("Calling Claude API...")
            
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            try:
                print(f"API error: Status code {response.status_code}")
                print(f"Response: {response.text}")
            except UnicodeEncodeError:
                print(f"API error: Status code {response.status_code}")
                print("Response contains non-ASCII characters that cannot be displayed")
            return None
            
        result = response.json()
        try:
            print("API call successful!")
        except UnicodeEncodeError:
            print("API call successful! (Some text may not display properly in Windows console)")
        
        # Extract content from response
        if "content" in result and len(result["content"]) > 0:
            for content_block in result["content"]:
                if content_block["type"] == "text":
                    text_response = content_block["text"]
                    try:
                        print(f"Received response from Claude: {text_response[:100]}...")
                    except UnicodeEncodeError:
                        print("Received response from Claude (contains non-ASCII characters)")
                    return text_response
        else:
            try:
                print(f"Unexpected response format: {result}")
            except UnicodeEncodeError:
                print("Unexpected response format (contains non-ASCII characters)")
        
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error calling Claude API: {e}")
        return None

def extract_json_from_claude_response(response):
    """Extract JSON data from Claude's response"""
    if not response:
        return []
    
    # Find JSON block in response
    try:
        json_start = response.find("```json")
        if json_start == -1:
            json_start = response.find("```")
        
        if json_start != -1:
            json_start = response.find("[", json_start)
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        else:
            # Try to find JSON array directly
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from Claude response: {e}")
        print(f"Response snippet: {response[:500]}...")
    
    return []

def analyze_jobs_with_claude(jobs, batch_size=3):
    """Analyze jobs using Claude API"""
    try:
        print(f"Analyzing {len(jobs)} jobs with Claude...")
    except UnicodeEncodeError:
        print("Analyzing jobs with Claude...")
    
    results = []
    
    # Process jobs in batches
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i+batch_size]
        try:
            print(f"Processing batch {i//batch_size + 1}/{(len(jobs) + batch_size - 1)//batch_size} ({len(batch)} jobs)")
        except UnicodeEncodeError:
            print(f"Processing batch {i//batch_size + 1}/{(len(jobs) + batch_size - 1)//batch_size}")
        
        # Prepare prompt for this batch
        prompt = prepare_prompt_for_claude(batch)
        
        # Call Claude API
        response = call_claude_api(prompt=prompt)
        
        # Extract JSON data from response
        analyzed_jobs = extract_json_from_claude_response(response)
        
        # Map Claude's analysis back to the original jobs
        if analyzed_jobs:
            for j, analysis in enumerate(analyzed_jobs):
                if i + j < len(jobs):
                    job_id = analysis.get("job_id", j+1) - 1  # Claude's job_id is 1-based, we need 0-based
                    batch_idx = job_id if 0 <= job_id < len(batch) else j
                    
                    if i + batch_idx < len(jobs):
                        jobs[i + batch_idx]['gravy_score'] = analysis.get('gravy_score', 0)
                        jobs[i + batch_idx]['gravy_category'] = analysis.get('category', 'Uncategorized')
                        jobs[i + batch_idx]['gravy_reasoning'] = analysis.get('reasoning', [])
        
        # Add processed batch to results
        results.extend(batch)
        
        # Sleep to avoid hitting API rate limits
        time.sleep(1)
    
    # Sort jobs by gravy score
    results.sort(key=lambda x: x.get('gravy_score', 0), reverse=True)
    return results

def split_jobs_into_chunks(all_jobs, output_dir, chunk_size=3):
    """Split jobs into smaller chunks for analysis"""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    total_jobs = len(all_jobs)
    print(f"Splitting {total_jobs} jobs into chunks of {chunk_size}")
    
    # Split into chunks
    for i in range(0, total_jobs, chunk_size):
        chunk = all_jobs[i:i+chunk_size]
        chunk_file = os.path.join(output_dir, f"jobs_chunk_{i//chunk_size + 1}.json")
        
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, indent=2, ensure_ascii=False)
        
        print(f"Created chunk {i//chunk_size + 1}/{(total_jobs + chunk_size - 1)//chunk_size} with {len(chunk)} jobs: {chunk_file}")
    
    return (total_jobs + chunk_size - 1) // chunk_size  # Return number of chunks

def analyze_chunk(chunk_number, output_dir):
    """Analyze a specific chunk of jobs using Claude API"""
    chunk_file = os.path.join(output_dir, f"jobs_chunk_{chunk_number}.json")
    output_file = os.path.join(output_dir, f"analyzed_chunk_{chunk_number}.json")
    
    # Skip if already analyzed
    if os.path.exists(output_file):
        print(f"Chunk {chunk_number} already analyzed, skipping...")
        with open(output_file, 'r') as f:
            return json.load(f)
    
    print(f"Analyzing chunk {chunk_number}...")
    
    # Load jobs from chunk
    with open(chunk_file, 'r') as f:
        jobs = json.load(f)
    
    # Analyze jobs
    analyzed_jobs = analyze_jobs_with_claude(jobs, batch_size=len(jobs))
    
    # Save analyzed jobs
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analyzed_jobs, f, indent=2, ensure_ascii=False)
    
    print(f"Chunk {chunk_number} analyzed and saved to {output_file}")
    return analyzed_jobs


# HTML Generation Functions
def generate_html_report(jobs, output_file='gravy_jobs.html'):
    """Generate an HTML report of the top gravy jobs"""
    if not jobs:
        return "No jobs to display"
    
    try:
        print("Generating HTML report...")
    except UnicodeEncodeError:
        print("Generating HTML report (suppressing encoding errors)")
    
    # Group jobs by category
    amazing_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Amazing']
    great_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Great']
    good_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Good']
    decent_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Decent']
    challenging_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Challenging']
    
    # Handle jobs without Claude categorization
    other_jobs = [j for j in jobs if 'gravy_category' not in j]
    for job in other_jobs:
        score = job.get('gravy_score', job.get('score', 0))
        if score >= 70:
            job['gravy_category'] = 'Amazing'
            amazing_jobs.append(job)
        elif score >= 50:
            job['gravy_category'] = 'Great'
            great_jobs.append(job)
        elif score >= 30:
            job['gravy_category'] = 'Good'
            good_jobs.append(job)
        elif score >= 10:
            job['gravy_category'] = 'Decent'
            decent_jobs.append(job)
        else:
            job['gravy_category'] = 'Challenging'
            challenging_jobs.append(job)
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🍯 Gravy Jobs | Easy + Good Pay + Beginner-Friendly</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 0;
                color: #333;
                background-color: #f4f4f4;
            }}
            .container {{
                width: 85%;
                margin: 0 auto;
                padding: 20px;
            }}
            h1 {{
                text-align: center;
                margin-bottom: 20px;
                color: #2c3e50;
            }}
            h2 {{
                color: #3498db;
                padding-bottom: 5px;
                border-bottom: 2px solid #3498db;
                margin-top: 30px;
            }}
            .job-list {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .job-card {{
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                padding: 15px;
                transition: transform 0.3s ease;
            }}
            .job-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            .amazing {{
                border-left: 5px solid #2ecc71;
            }}
            .great {{
                border-left: 5px solid #3498db;
            }}
            .good {{
                border-left: 5px solid #f39c12;
            }}
            .decent {{
                border-left: 5px solid #95a5a6;
            }}
            .challenging {{
                border-left: 5px solid #e74c3c;
            }}
            .job-title {{
                color: #2c3e50;
                font-size: 18px;
                margin-top: 0;
                margin-bottom: 10px;
            }}
            .job-details {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
            }}
            .job-company {{
                color: #7f8c8d;
                font-weight: bold;
            }}
            .job-source {{
                color: #95a5a6;
                font-size: 14px;
            }}
            .job-salary {{
                color: #27ae60;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .gravy-score {{
                display: inline-block;
                font-size: 14px;
                padding: 3px 8px;
                border-radius: 12px;
                color: white;
                margin-bottom: 10px;
            }}
            .score-amazing {{
                background-color: #2ecc71;
            }}
            .score-great {{
                background-color: #3498db;
            }}
            .score-good {{
                background-color: #f39c12;
            }}
            .score-decent {{
                background-color: #95a5a6;
            }}
            .score-challenging {{
                background-color: #e74c3c;
            }}
            .job-description {{
                font-size: 14px;
                color: #555;
                margin-bottom: 15px;
            }}
            .gravy-reasons {{
                font-size: 13px;
                padding: 10px;
                background-color: #f9f9f9;
                border-radius: 5px;
                margin-bottom: 15px;
            }}
            .gravy-reasons ul {{
                margin: 0;
                padding-left: 20px;
            }}
            .gravy-reasons li {{
                margin-bottom: 3px;
            }}
            .job-link {{
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 8px 15px;
                text-decoration: none;
                border-radius: 4px;
                font-size: 14px;
                transition: background 0.3s ease;
            }}
            .job-link:hover {{
                background: #2980b9;
            }}
            .search-filters {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .filters-title {{
                margin-top: 0;
                color: #2c3e50;
            }}
            .filter-options {{
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin-top: 15px;
            }}
            .filter-tag {{
                background: #e0e0e0;
                padding: 5px 12px;
                border-radius: 15px;
                font-size: 14px;
                cursor: pointer;
                transition: background 0.3s ease;
            }}
            .filter-tag:hover, .filter-tag.active {{
                background: #3498db;
                color: white;
            }}
            .explanation {{
                background: #eaf4fd;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 30px;
                font-size: 15px;
                line-height: 1.5;
            }}
            .text-warning {{
                color: #e74c3c;
            }}
            .gravy-tag {{
                display: inline-block;
                font-size: 12px;
                background: #2ecc71;
                color: white;
                padding: 1px 6px;
                border-radius: 10px;
                margin-right: 5px;
                margin-bottom: 5px;
            }}
            @media (max-width: 768px) {{
                .container {{
                    width: 95%;
                }}
                .job-list {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Gravy Jobs for Beginners</h1>
            
            <div class="explanation">
                <p><strong>What makes a job "gravy"?</strong> Jobs are analyzed based on:</p>
                <ul>
                    <li>How easy/entry-level the job appears to be</li>
                    <li>Salary information (higher pay = more gravy)</li>
                    <li>Remote work options</li>
                    <li>Beginner-friendly technologies (HTML/CSS, WordPress, etc.)</li>
                    <li>Red flags (advanced skills, senior positions)</li>
                </ul>
                <p>Each job has been assigned a "Gravy Score" from 0-100. The higher the score, the more this job is considered easy, well-paying, and beginner-friendly.</p>
                <p>The categories are:</p>
                <ul>
                    <li><strong>Amazing</strong> (70-100): Super easy + great pay</li>
                    <li><strong>Great</strong> (50-69): Very good beginner opportunities</li>
                    <li><strong>Good</strong> (30-49): Solid entry-level jobs</li>
                    <li><strong>Decent</strong> (10-29): Worth considering</li>
                    <li><strong>Challenging</strong> (0-9): May be more difficult for beginners</li>
                </ul>
            </div>
            
            <div class="search-filters">
                <h3 class="filters-title">Quick Filters</h3>
                <div class="filter-options">
                    <div class="filter-tag active" onclick="filterJobs('all')">All Jobs</div>
                    <div class="filter-tag" onclick="filterJobs('remote')">Remote Only</div>
                    <div class="filter-tag" onclick="filterJobs('salary')">Has Salary</div>
                    <div class="filter-tag" onclick="filterJobs('amazing')">Amazing Only</div>
                    <div class="filter-tag" onclick="filterJobs('great')">Great & Above</div>
                    <div class="filter-tag" onclick="filterJobs('good')">Good & Above</div>
                </div>
            </div>
    """
    
    # Add amazing jobs section
    if amazing_jobs:
        html += f"""
            <h2>🔥 Amazing Opportunities ({len(amazing_jobs)})</h2>
            <div class="job-list">
        """
        
        for job in amazing_jobs:
            html += generate_job_card(job, 'amazing')
            
        html += """
            </div>
        """
    
    # Add great jobs section
    if great_jobs:
        html += f"""
            <h2>💎 Great Opportunities ({len(great_jobs)})</h2>
            <div class="job-list">
        """
        
        for job in great_jobs:
            html += generate_job_card(job, 'great')
            
        html += """
            </div>
        """
    
    # Add good jobs section
    if good_jobs:
        html += f"""
            <h2>👍 Good Opportunities ({len(good_jobs)})</h2>
            <div class="job-list">
        """
        
        for job in good_jobs:
            html += generate_job_card(job, 'good')
            
        html += """
            </div>
        """
    
    # Add decent jobs section
    if decent_jobs:
        html += f"""
            <h2>🙂 Decent Opportunities ({len(decent_jobs)})</h2>
            <div class="job-list">
        """
        
        for job in decent_jobs:
            html += generate_job_card(job, 'decent')
            
        html += """
            </div>
        """
    
    # Add challenging jobs section
    if challenging_jobs:
        html += f"""
            <h2>⚠️ Challenging Jobs ({len(challenging_jobs)})</h2>
            <p>These jobs may be more challenging for beginners, but are still worth considering if you have some experience.</p>
            <div class="job-list">
        """
        
        for job in challenging_jobs:
            html += generate_job_card(job, 'challenging')
            
        html += """
            </div>
        """
    
    # Add JavaScript for filtering
    html += """
        </div>
        
        <script>
            function filterJobs(filter) {
                // Remove active class from all filters
                document.querySelectorAll('.filter-tag').forEach(tag => {
                    tag.classList.remove('active');
                });
                
                // Add active class to clicked filter
                event.target.classList.add('active');
                
                // Get all job cards
                const jobs = document.querySelectorAll('.job-card');
                
                // Show all jobs first
                jobs.forEach(job => {
                    job.style.display = 'block';
                });
                
                // Apply specific filter
                switch(filter) {
                    case 'remote':
                        jobs.forEach(job => {
                            if (!job.getAttribute('data-remote')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                    case 'salary':
                        jobs.forEach(job => {
                            if (!job.getAttribute('data-salary')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                    case 'amazing':
                        jobs.forEach(job => {
                            if (!job.classList.contains('amazing')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                    case 'great':
                        jobs.forEach(job => {
                            if (!job.classList.contains('amazing') && !job.classList.contains('great')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                    case 'good':
                        jobs.forEach(job => {
                            if (!job.classList.contains('amazing') && !job.classList.contains('great') && !job.classList.contains('good')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                }
            }
            
            // Set default filter to all
            document.addEventListener('DOMContentLoaded', function() {
                filterJobs('all');
            });
        </script>
    </body>
    </html>
    """
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
        
    return output_file

def generate_job_card(job, category):
    """Generate HTML for a job card"""
    title = job.get('title', 'No Title')
    company = job.get('company', 'Unknown')
    source = job.get('source', 'Unknown')
    salary = job.get('salary', '')
    description = job.get('description', 'No description available.')
    url = job.get('url', '#')
    
    # Get the gravy score, fallback to regular score if not available
    gravy_score = job.get('gravy_score', job.get('score', 0))
    gravy_category = job.get('gravy_category', category.capitalize())
    gravy_reasoning = job.get('gravy_reasoning', [])
    
    # Determine score class
    score_class = 'score-challenging'
    if gravy_category == 'Amazing':
        score_class = 'score-amazing'
    elif gravy_category == 'Great':
        score_class = 'score-great'
    elif gravy_category == 'Good':
        score_class = 'score-good'
    elif gravy_category == 'Decent':
        score_class = 'score-decent'
    
    # Generate data attributes for filtering
    data_attrs = []
    
    # Remote attribute
    if ('remote' in title.lower() or 'work from home' in title.lower() or 
        'remote' in description.lower() or 'work from home' in description.lower() or
        any('remote' in reason.lower() for reason in gravy_reasoning)):
        data_attrs.append('data-remote="true"')
    
    # Salary attribute
    if salary or any('salary' in reason.lower() for reason in gravy_reasoning):
        data_attrs.append('data-salary="true"')
    
    # Join data attributes
    data_attrs_str = ' '.join(data_attrs)
    
    # Generate job tags
    job_tags = []
    if 'remote' in title.lower() or 'work from home' in title.lower() or 'remote' in description.lower():
        job_tags.append('<span class="gravy-tag">Remote</span>')
    
    if 'html' in title.lower() or 'css' in title.lower():
        job_tags.append('<span class="gravy-tag">HTML/CSS</span>')
    
    if 'wordpress' in title.lower():
        job_tags.append('<span class="gravy-tag">WordPress</span>')
        
    if 'entry' in title.lower() or 'junior' in title.lower() or 'beginner' in title.lower():
        job_tags.append('<span class="gravy-tag">Entry-Level</span>')
    
    if salary:
        job_tags.append('<span class="gravy-tag">Has Salary</span>')
        
    # Join tags
    job_tags_str = ''.join(job_tags)
    
    # Generate reasons HTML
    reasons_html = ""
    if gravy_reasoning:
        reasons_html = """
        <div class="gravy-reasons">
            <ul>
        """
        for reason in gravy_reasoning:
            reasons_html += f"<li>{reason}</li>"
        
        reasons_html += """
            </ul>
        </div>
        """
    
    # Generate HTML for job card
    html = f"""
        <div class="job-card {category}" {data_attrs_str}>
            <h3 class="job-title">{title}</h3>
            <div class="job-details">
                <div class="job-company">{company}</div>
                <div class="job-source">{source}</div>
            </div>
            <div class="gravy-score {score_class}">Gravy Score: {gravy_score}</div>
            <div class="job-tags">{job_tags_str}</div>
    """
    
    if salary:
        html += f'<div class="job-salary">$ {salary}</div>'
        
    html += f"""
            <div class="job-description">{description}</div>
            {reasons_html}
            <a href="{url}" class="job-link" target="_blank">Apply Now</a>
        </div>
    """
    
    return html


# Web Server Functions
def start_server(port=8000, html_file='gravy_jobs.html'):
    """Start a simple HTTP server to serve the jobs webpage"""
    class GravyJobsHTTPHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            # Redirect root to the HTML file
            if self.path == '/':
                self.path = f'/{html_file}'
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    try:
        with socketserver.TCPServer(("", port), GravyJobsHTTPHandler) as httpd:
            print(f"Server started at http://localhost:{port}")
            print(f"View gravy jobs at http://localhost:{port}/{html_file}")
            print("Press Ctrl+C to stop the server")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    except OSError as e:
        print(f"Error starting server: {e}")
        print(f"Make sure port {port} is available, or specify a different port with --port")


# Main Application Functions
def scrape_jobs():
    """Scrape jobs from all sources"""
    print("Scraping for jobs... (this may take a few minutes)")
    
    # Create scraper
    scraper = JobScraper(CONFIG)
    
    # Run scraping
    new_jobs = scraper.scrape_all_sources()
    
    if new_jobs:
        print(f"\nFound {len(new_jobs)} new jobs!")
        
        # Combine with previous jobs if any
        all_jobs = scraper.previous_jobs + new_jobs
        scraper.all_jobs = all_jobs
        
        # Save all jobs
        print("Saving all jobs to file...")
        scraper.save_jobs()
        
        # Rank jobs
        print("Ranking jobs by relevance...")
        top_jobs = scraper.rank_top_jobs(limit=100)
        print(f"Selected top {len(top_jobs)} jobs for analysis")
        
        return top_jobs
    else:
        print("\nNo new jobs found.")
        
        # Try to use existing jobs
        if os.path.exists(CONFIG["top_jobs_file"]):
            print(f"Using existing top jobs from {CONFIG['top_jobs_file']}...")
            with open(CONFIG["top_jobs_file"], 'r') as f:
                return json.load(f)
        elif os.path.exists(CONFIG["data_file"]):
            print(f"Using existing all jobs from {CONFIG['data_file']}...")
            with open(CONFIG["data_file"], 'r') as f:
                all_jobs = json.load(f)
                return scraper.rank_top_jobs(all_jobs)
        
        print("No existing jobs found.")
        return []

def analyze_jobs(jobs):
    """Analyze jobs with Claude"""
    print("Analyzing jobs with Claude... (this may take a few minutes)")
    
    # Create analysis directory
    os.makedirs(CONFIG["analysis_dir"], exist_ok=True)
    
    # Split jobs into chunks
    total_chunks = split_jobs_into_chunks(jobs, CONFIG["analysis_dir"], CONFIG["batch_size"])
    
    # Analyze each chunk
    analyzed_jobs = []
    
    for chunk_number in range(1, total_chunks + 1):
        chunk_results = analyze_chunk(chunk_number, CONFIG["analysis_dir"])
        analyzed_jobs.extend(chunk_results)
    
    print(f"Analysis complete! Analyzed {len(analyzed_jobs)} jobs")
    return analyzed_jobs

def safe_print(message):
    """Print a message while handling encoding errors on Windows"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Try to encode as ASCII, replacing problematic characters
        print(message.encode('ascii', 'replace').decode('ascii'))

def load_sample_jobs():
    """Load sample jobs from included file for testing without scraping"""
    safe_print("Loading sample jobs for testing...")
    sample_paths = [
        "sample_jobs.json",
        "test_jobs.json",
        "jobs_for_claude.json",
        "top_jobs.json",
        "all_jobs.json"
    ]
    
    for path in sample_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    sample_jobs = json.load(f)
                    if sample_jobs and len(sample_jobs) > 0:
                        safe_print(f"Loaded {len(sample_jobs)} sample jobs from {path}")
                        return sample_jobs
            except Exception as e:
                safe_print(f"Error loading {path}: {e}")
    
    # If no sample files found, create a basic sample
    safe_print("No sample job files found, creating basic sample...")
    return [
        {
            "title": "Sample Job 1: Entry Level Web Developer",
            "company": "Test Company",
            "description": "This is a sample job for testing. No scraping required.",
            "url": "https://example.com/job1",
            "source": "Sample",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "salary": "$20/hr",
            "score": 75
        },
        {
            "title": "Sample Job 2: Junior Python Developer",
            "company": "Another Company",
            "description": "Another sample job for testing the HTML generation.",
            "url": "https://example.com/job2",
            "source": "Sample",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "salary": "$60,000/year",
            "score": 65
        },
        {
            "title": "Sample Job 3: Beginner Wordpress Developer",
            "company": "Test Corp",
            "description": "Remote work available. HTML/CSS skills required.",
            "url": "https://example.com/job3",
            "source": "Sample",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": 45
        }
    ]

def main():
    """Main entry point for the Gravy Jobs App"""
    parser = argparse.ArgumentParser(description="Gravy Jobs App - Find entry-level programming jobs that are easy and pay well")
    parser.add_argument("--scrape-only", action="store_true", help="Only scrape jobs, don't analyze or start server")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze existing jobs, don't scrape or start server")
    parser.add_argument("--server-only", action="store_true", help="Only start server, don't scrape or analyze")
    parser.add_argument("--port", type=int, default=8000, help="Port for the web server (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no console window on Windows)")
    parser.add_argument("--no-emoji", action="store_true", help="Disable emoji characters to avoid encoding issues", default=True)
    parser.add_argument("--test", action="store_true", help="Use sample jobs data for testing without scraping")
    
    args = parser.parse_args()
    
    # Hide console window on Windows when running in headless mode
    if args.headless and os.name == 'nt':
        # This will detach the console from the process
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        kernel32.FreeConsole()
    else:
        print("=======================================")
        print("🍯 Gravy Jobs App - Find Easy, Well-Paying Programming Jobs for Beginners 🍯")
        print("=======================================")
    
    # Handle different modes
    if args.scrape_only:
        # Just scrape and save jobs
        jobs = scrape_jobs()
        print(f"Scraped {len(jobs)} jobs and saved to {CONFIG['top_jobs_file']}")
        return
        
    elif args.analyze_only:
        # Just analyze existing jobs
        if os.path.exists(CONFIG["top_jobs_file"]):
            with open(CONFIG["top_jobs_file"], 'r') as f:
                jobs = json.load(f)
            analyzed_jobs = analyze_jobs(jobs)
            generate_html_report(analyzed_jobs, CONFIG["web_output"])
            print(f"Analysis complete! Results saved to {CONFIG['web_output']}")
        else:
            print(f"Error: No existing jobs found in {CONFIG['top_jobs_file']}")
        return
        
    elif args.server_only:
        # Just start the server
        if not os.path.exists(CONFIG["web_output"]):
            print(f"Error: HTML file {CONFIG['web_output']} not found. Run with --scrape-only or --analyze-only first.")
            return
        
        # Open browser if requested
        if not args.no_browser:
            webbrowser.open(f"http://localhost:{args.port}/{CONFIG['web_output']}")
        
        # Start server
        start_server(args.port, CONFIG["web_output"])
        return
    
    # Default: full workflow (scrape, analyze, serve)
    jobs = scrape_jobs()
    
    if jobs:
        analyzed_jobs = analyze_jobs(jobs)
        generate_html_report(analyzed_jobs, CONFIG["web_output"])
        
        print(f"\nDone! Web page created at: {os.path.abspath(CONFIG['web_output'])}")
        
        # Open browser if requested
        if not args.no_browser:
            webbrowser.open(f"http://localhost:{args.port}/{CONFIG['web_output']}")
        
        # Start server
        start_server(args.port, CONFIG["web_output"])
    else:
        print("No jobs to analyze. Please try again later.")


if __name__ == "__main__":
    main()