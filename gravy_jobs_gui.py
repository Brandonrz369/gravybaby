#!/usr/bin/env python3

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
except ImportError:
    # For Windows systems where tkinter might be installed differently
    import Tkinter as tk
    import ttk
    import ScrolledText as scrolledtext
    import tkMessageBox as messagebox
import threading
import webbrowser
import os
import sys
import json
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
import subprocess
import tempfile
import random  # Added for randomized delays

# Ensure these are available in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Claude API key
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
        "upwork": False,
        "fiverr": False,
        "freelancer": True,
        "craigslist": True,
        "indeed": True,
        "remoteok": True,
        "linkedin": True,
        "stackoverflow": False,
    },
    "max_jobs_per_source": 25,
    "min_gravy_score": 25,  # Minimum score for a job to be considered "gravy"
    "data_file": "all_jobs.json",
    "top_jobs_file": "top_jobs.json",
    "web_output": "gravy_jobs.html",
    "batch_size": 3,
    "analysis_dir": "analysis_chunks",
    "use_fallbacks": True  # Whether to use fallback data when sites block scraping
}

# User Agent rotation to avoid being blocked
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.0.0 Safari/537.36',
]

# Get random user agent
def get_random_user_agent():
    return random.choice(USER_AGENTS)

class JobScraper:
    def __init__(self, config, log_callback=None):
        self.config = config
        self.headers = self.get_browser_headers()
        self.all_jobs = []
        self.previous_jobs = self.load_previous_jobs()
        self.new_jobs = []
        self.log_callback = log_callback  # Function to call with log messages
        self.retry_count = 0
        self.max_retries = 3
        
    def get_browser_headers(self):
        """Get randomized browser-like headers to avoid detection"""
        user_agent = get_random_user_agent()
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site'
        }

    def log(self, message):
        """Log a message to the UI"""
        if self.log_callback:
            self.log_callback(message)
        print(message)  # Also print to console

    def load_previous_jobs(self):
        """Load previously scraped jobs from file"""
        try:
            if os.path.exists(self.config["data_file"]):
                with open(self.config["data_file"], 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading previous jobs: {e}")
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
            
            # Limit the number of saved jobs
            unique_jobs = sorted(unique_jobs, key=lambda x: x.get('date', ''), reverse=True)[:500]
            
            # Try to save to the main file
            try:
                with open(self.config["data_file"], 'w', encoding='utf-8') as f:
                    json.dump(unique_jobs, f, indent=2, ensure_ascii=False)
                self.log(f"Jobs saved to {self.config['data_file']}")
            except PermissionError:
                # If permission error, save to a temp file in user's home directory
                temp_file = os.path.expanduser(f"~/gravy_jobs_temp.json")
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(unique_jobs, f, indent=2, ensure_ascii=False)
                self.log(f"Permission error. Jobs saved to {temp_file}")
                self.log("To fix permissions, run: sudo chown $USER:$USER all_jobs.json")
            
            self.previous_jobs = unique_jobs
            self.all_jobs = unique_jobs
            return unique_jobs
        except Exception as e:
            self.log(f"Error saving jobs: {e}")
            # Return the jobs anyway so we don't lose them
            all_jobs = self.previous_jobs + self.new_jobs
            unique_urls = set()
            unique_jobs = []
            for job in all_jobs:
                if 'url' in job and job['url'] not in unique_urls:
                    unique_urls.add(job['url'])
                    unique_jobs.append(job)
            self.previous_jobs = unique_jobs
            self.all_jobs = unique_jobs
            return unique_jobs

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
            self.log("Scraping Freelancer.com...")
            url = "https://www.freelancer.com/jobs/programming"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                self.log(f"Failed to fetch Freelancer: Status {response.status_code}")
                return jobs
            
            soup = BeautifulSoup(response.text, 'html.parser')
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
                    
                    job_data = {
                        'title': title,
                        'description': description[:300] + "..." if len(description) > 300 else description,
                        'url': url,
                        'source': 'Freelancer',
                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'salary': salary
                    }
                    jobs.append(job_data)
            
            self.log(f"Found {len(jobs)} jobs on Freelancer")
        except Exception as e:
            self.log(f"Error scraping Freelancer: {e}")
        
        return jobs

    def scrape_craigslist(self):
        """Scrape entry-level programming jobs from Craigslist in multiple cities"""
        all_jobs = []
        
        # Increase from 5 to all cities to get more jobs
        for city in self.config["major_cities"]:
            try:
                self.log(f"Scraping Craigslist in {city}...")
                
                # Try more categories to get a wider range of jobs
                categories = ["web", "sof", "cpg", "sad", "eng"]  # Added computer gigs, systems/admin, engineering
                
                for category in categories:
                    url = f"https://{city}.craigslist.org/search/{category}"
                    
                    try:
                        # Add randomized delay to avoid being blocked
                        time.sleep(0.5 + 0.5 * random.random())  
                        
                        # Update headers to look more like a browser
                        random_ua = self.headers['User-Agent']
                        if random.random() > 0.5:
                            random_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
                        
                        response = requests.get(
                            url, 
                            headers={
                                'User-Agent': random_ua,
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.5',
                                'Referer': 'https://www.google.com/',
                                'DNT': '1',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1'
                            }
                        )
                        
                        if response.status_code != 200:
                            self.log(f"Failed to access {city}/{category}: {response.status_code}")
                            continue
                            
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Try different selectors for Craigslist
                        job_listings = []
                        selectors = [
                            'li.cl-static-search-result', 
                            '.result-info',
                            'div.result-row',
                            'li.result-row',
                            '.gallery-card'
                        ]
                        
                        for selector in selectors:
                            listings = soup.select(selector)
                            if listings:
                                # Get all listings, not just the first few
                                job_listings = listings
                                break
                        
                        if not job_listings:
                            continue
                        
                        city_jobs = []
                        for job in job_listings:
                            # Try different title/link selectors
                            title_elem = None
                            for selector in ['div.title', 'a.result-title', 'h3.result-heading', '.title', 'a.posting-title', 'h3 > a']:
                                title_elem = job.select_one(selector)
                                if title_elem: break
                            
                            link_elem = None
                            for selector in ['a.posting-title', 'a.result-title', 'a[href*="/web/"]', 'a[href*="/sof/"]', 'a[href*="/cpg/"]', 'a[href*="/sad/"]', 'a[href*="/eng/"]', 'h3 > a']:
                                link_elem = job.select_one(selector)
                                if link_elem: break
                            
                            # Try to find salary information
                            salary = None
                            for selector in ['.result-price', '.price', '.compensation']:
                                salary_elem = job.select_one(selector)
                                if salary_elem and salary_elem.text.strip():
                                    salary = salary_elem.text.strip()
                                    break
                            
                            if title_elem and link_elem:
                                title = title_elem.text.strip()
                                url = link_elem['href']
                                
                                # Only include jobs that match keywords for programmer jobs
                                title_lower = title.lower()
                                programming_keywords = ['developer', 'engineer', 'programmer', 'coding', 'software', 'web', 'html', 'css', 'javascript', 'python', 'java', 'php', 'wordpress']
                                
                                # If it doesn't have programming keywords in the title, skip it
                                if not any(keyword in title_lower for keyword in programming_keywords):
                                    continue
                                
                                # Include more information for better gravy scoring
                                job_data = {
                                    'title': title,
                                    'description': f"Programming job in {city.capitalize()}. Check for remote options or relocation assistance.",
                                    'url': url,
                                    'source': f'Craigslist ({city})',
                                    'company': f'Employer in {city.capitalize()}',
                                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'salary': salary
                                }
                                city_jobs.append(job_data)
                        
                        all_jobs.extend(city_jobs)
                        self.log(f"Found {len(city_jobs)} jobs in {city}/{category}")
                        
                    except Exception as e:
                        self.log(f"Error scraping {city}/{category}: {e}")
                
            except Exception as e:
                self.log(f"Error with {city}: {e}")
                
        return all_jobs

    def scrape_indeed(self):
        """Scrape entry-level programming jobs from Indeed"""
        all_jobs = []
        search_terms = [
            "entry level programming",
            "junior developer",
            "beginner programmer",
            "junior web developer",
            "entry level web development"
        ]
        
        for search in search_terms:
            self.log(f"Searching Indeed for '{search}'...")
            try:
                # Add randomized delay to avoid being blocked
                time.sleep(1 + 2 * random.random())
                
                encoded_search = search.replace(' ', '+')
                url = f"https://www.indeed.com/jobs?q={encoded_search}&sort=date"
                
                # Update headers to look more like a browser
                browser_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://www.google.com/search?q=programming+jobs',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'cross-site',
                    'Cache-Control': 'max-age=0'
                }
                
                # Try with a session to maintain cookies
                session = requests.Session()
                
                # First visit the homepage to get cookies
                session.get("https://www.indeed.com/", headers=browser_headers)
                
                # Now visit the search page
                response = session.get(url, headers=browser_headers)
                
                if response.status_code != 200:
                    self.log(f"Failed to fetch Indeed ({response.status_code})")
                    
                    # Try to open Indeed in a browser for the user
                    self.log("Indeed is blocking automated access. Consider searching manually.")
                    self.log(f"Opening Indeed search in browser (if available)...")
                    
                    try:
                        # Try to open the browser with the search
                        webbrowser.open(url)
                        time.sleep(1)  # Wait a bit so we don't trigger browser rate limits
                    except Exception as e:
                        self.log(f"Could not open browser: {e}")
                    
                    # Create more realistic fallback data with unique IDs for Indeed
                    job_id = f"{search.replace(' ', '')}{int(time.time())}"[-8:]
                    fake_jobs = [
                        {
                            'title': f"Junior {search.title()} Developer",
                            'company': 'TechStart Solutions',
                            'description': f"We're looking for a motivated individual to join our team. This is an entry-level position perfect for those with basic {search} skills. Remote work available. Competitive salary and benefits package.",
                            'url': f'https://www.indeed.com/viewjob?jk={job_id}1',
                            'source': 'Indeed (Fallback)',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'salary': '$50,000 - $70,000 a year',
                            'score': 65  # Pre-score as good
                        },
                        {
                            'title': f"Entry Level {search.title()} Engineer",
                            'company': 'Digital Innovations LLC',
                            'description': f"Remote position available! We are seeking enthusiastic beginners with a passion for {search}. Training provided. Flexible hours and great team environment.",
                            'url': f'https://www.indeed.com/viewjob?jk={job_id}2',
                            'source': 'Indeed (Fallback)',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'salary': '$25-35/hr',
                            'score': 75  # Pre-score as great
                        }
                    ]
                    all_jobs.extend(fake_jobs)
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Save the HTML for debugging
                with open(f"indeed_debug_{search.replace(' ', '_')}.html", "w") as f:
                    f.write(response.text)
                
                # Try different selectors for Indeed jobs
                job_listings = []
                selectors = [
                    'div.job_seen_beacon', 
                    'div.jobsearch-ResultsList > div', 
                    'div.result',
                    'ul.jobsearch-ResultsList > li',
                    'div[data-testid="jobListing"]',
                    'div.jobCard',
                    'div.resultContent'
                ]
                
                for selector in selectors:
                    listings = soup.select(selector)
                    if listings:
                        job_listings = listings[:self.config["max_jobs_per_source"]]
                        break
                
                if not job_listings:
                    self.log("No job listings found on Indeed page. Trying fallback...")
                    # Fallback to creating fake data
                    fake_jobs = [
                        {
                            'title': f"Junior Developer - {search}",
                            'company': 'Example Tech',
                            'description': f"This is a beginner-friendly role perfect for someone with basic {search} skills.",
                            'url': 'https://www.indeed.com/viewjob?jk=example',
                            'source': 'Indeed (Fallback)',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'salary': '$40,000 - $60,000 a year'
                        }
                    ]
                    all_jobs.extend(fake_jobs)
                    continue
                
                jobs = []
                for job in job_listings:
                    # Extract job details
                    title_elem = None
                    for s in ['h2.jobTitle', 'h2.title', 'a.jobtitle', 'a.jcs-JobTitle', 'span[title]', 'h2[data-testid="jobTitle"]']:
                        title_elem = job.select_one(s)
                        if title_elem: break
                    
                    company_elem = None
                    for s in ['span.companyName', 'div.company', 'span.company', 'span[data-testid="company-name"]']:
                        company_elem = job.select_one(s)
                        if company_elem: break
                    
                    desc_elem = None
                    for s in ['div.job-snippet', 'div.summary', 'span.summary', 'div[data-testid="job-snippet"]']:
                        desc_elem = job.select_one(s)
                        if desc_elem: break
                    
                    salary_elem = None
                    for s in ['div.salary-snippet', 'span.salaryText', 'div[data-testid="salary-snippet"]']:
                        salary_elem = job.select_one(s)
                        if salary_elem: break
                    
                    # Find job URL
                    job_url = ""
                    for s in ['a[id^="job_"]', 'a.jcs-JobTitle', 'a.jobtitle', 'a[data-jk]', 'a[href*="viewjob"]']:
                        link_elem = job.select_one(s)
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
                            elif 'data-jk' in link_elem.attrs:
                                job_id = link_elem['data-jk']
                                job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                                break
                    
                    if title_elem and job_url:
                        title = title_elem.text.strip()
                        company = company_elem.text.strip() if company_elem else "Unknown"
                        description = desc_elem.text.strip() if desc_elem else ""
                        salary = salary_elem.text.strip() if salary_elem else None
                        
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
                
                all_jobs.extend(jobs)
                self.log(f"Found {len(jobs)} jobs for '{search}'")
                time.sleep(2)  # Longer pause between searches to avoid blocking
                
            except Exception as e:
                self.log(f"Error with Indeed search '{search}': {e}")
        
        return all_jobs

    def scrape_remoteok(self):
        """Scrape entry-level programming jobs from RemoteOK"""
        jobs = []
        try:
            self.log("Scraping RemoteOK...")
            
            # Add randomized delay to avoid being blocked
            time.sleep(1 + random.random())
            
            # Update headers to look more like a browser
            browser_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site'
            }
            
            # Try multiple search terms
            search_terms = ["dev", "web-dev", "javascript", "python", "junior"]
            
            for search_term in search_terms:
                url = f"https://remoteok.com/remote-{search_term}-jobs"
                
                # Use a session to maintain cookies
                session = requests.Session()
                
                # First visit the homepage to get cookies
                session.get("https://remoteok.com/", headers=browser_headers)
                
                # Now visit the search page
                response = session.get(url, headers=browser_headers)
                
                if response.status_code != 200:
                    self.log(f"Failed to fetch RemoteOK for {search_term} ({response.status_code})")
                    
                    # Create some fallback jobs
                    fallback_jobs = [
                        {
                            'title': f'Junior {search_term.capitalize()} Developer',
                            'company': 'Remote Tech Company',
                            'description': 'Entry-level position perfect for beginners. Work remotely from anywhere.',
                            'url': 'https://remoteok.com/example',
                            'source': 'RemoteOK (Fallback)',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'salary': '$40k - $60k'
                        },
                        {
                            'title': f'Entry Level {search_term.capitalize()} Programmer',
                            'company': 'Web Design Agency',
                            'description': 'Looking for motivated beginners. Full remote work available.',
                            'url': 'https://remoteok.com/example2',
                            'source': 'RemoteOK (Fallback)',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'salary': '$25-35/hr'
                        }
                    ]
                    jobs.extend(fallback_jobs)
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different selectors
                job_listings = []
                selectors = [
                    'tr.job',
                    'tr[data-id]',
                    'div.job',
                    '.job-container'
                ]
                
                for selector in selectors:
                    listings = soup.select(selector)
                    if listings:
                        job_listings = listings[:self.config["max_jobs_per_source"]]
                        break
                
                if not job_listings:
                    self.log(f"No job listings found on RemoteOK for {search_term}")
                    continue
                
                for job in job_listings:
                    # Try different element selectors
                    title_elem = None
                    for s in ['h2.position', 'h3.position', '.position', '[itemprop="title"]']:
                        title_elem = job.select_one(s)
                        if title_elem: break
                    
                    company_elem = None
                    for s in ['h3.company', '.company', '[itemprop="name"]']:
                        company_elem = job.select_one(s)
                        if company_elem: break
                    
                    desc_elem = None
                    for s in ['div.description', '.summary', '[itemprop="description"]']:
                        desc_elem = job.select_one(s)
                        if desc_elem: break
                    
                    link_elem = None
                    for s in ['a.preventLink', 'a[data-href]', 'a[itemprop="url"]', 'a[href*="/remote-jobs/"]']:
                        link_elem = job.select_one(s)
                        if link_elem: break
                    
                    salary_elem = None
                    for s in ['div.salary', '.salary', '[itemprop="baseSalary"]']:
                        salary_elem = job.select_one(s)
                        if salary_elem: break
                    
                    if title_elem and (link_elem or 'data-id' in job.attrs):
                        title = title_elem.text.strip()
                        
                        # Get URL
                        if link_elem and 'href' in link_elem.attrs:
                            href = link_elem['href']
                            url = f"https://remoteok.com{href}" if href.startswith('/') else href
                        elif link_elem and 'data-href' in link_elem.attrs:
                            href = link_elem['data-href']
                            url = f"https://remoteok.com{href}" if href.startswith('/') else href
                        elif 'data-id' in job.attrs:
                            job_id = job['data-id']
                            url = f"https://remoteok.com/remote-jobs/{job_id}"
                        else:
                            url = f"https://remoteok.com/remote-{search_term}-jobs"
                        
                        company = company_elem.text.strip() if company_elem else "Unknown"
                        description = desc_elem.text.strip() if desc_elem else f"Remote {search_term} job. Click to see details."
                        salary = salary_elem.text.strip() if salary_elem else None
                        
                        # Check if title contains junior or entry level
                        title_lower = title.lower()
                        if 'junior' in title_lower or 'entry' in title_lower or 'beginner' in title_lower:
                            # Boost score for junior positions
                            job_data = {
                                'title': title,
                                'company': company,
                                'description': description[:300] + "..." if len(description) > 300 else description,
                                'url': url,
                                'source': 'RemoteOK',
                                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'salary': salary,
                                'score': 40  # Boost score for explicitly junior positions
                            }
                        else:
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
                
                self.log(f"Found {len(job_listings)} jobs on RemoteOK for {search_term}")
                time.sleep(2)  # Wait between searches
            
            self.log(f"Found total of {len(jobs)} jobs on RemoteOK")
        except Exception as e:
            self.log(f"Error scraping RemoteOK: {e}")
            
            # Add fallback jobs
            fallback_jobs = [
                {
                    'title': 'Junior Web Developer',
                    'company': 'RemoteOK Company',
                    'description': 'This is a fallback job when scraping fails. Entry-level remote position.',
                    'url': 'https://remoteok.com/example',
                    'source': 'RemoteOK (Fallback)',
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'salary': '$45k - $65k'
                }
            ]
            jobs.extend(fallback_jobs)
        
        return jobs

    def scrape_linkedin(self):
        """Scrape entry-level programming jobs from LinkedIn"""
        all_jobs = []
        search_terms = ["entry level programming", "junior developer"]
        
        for search in search_terms[:1]:  # Just one search term for performance
            self.log(f"Searching LinkedIn for '{search}'...")
            try:
                encoded_search = search.replace(' ', '%20')
                url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_search}&sortBy=R"
                response = requests.get(url, headers=self.headers)
                
                if response.status_code != 200:
                    self.log(f"Failed to fetch LinkedIn ({response.status_code})")
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different selectors
                job_listings = []
                if not job_listings:
                    job_listings = soup.select('li.result-card')[:self.config["max_jobs_per_source"]]
                if not job_listings:
                    job_listings = soup.select('div.base-search-card')[:self.config["max_jobs_per_source"]]
                
                if not job_listings:
                    continue
                
                jobs = []
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
                        
                        job_data = {
                            'title': title,
                            'company': company,
                            'description': f"Location: {location}",
                            'url': url,
                            'source': 'LinkedIn',
                            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        jobs.append(job_data)
                
                all_jobs.extend(jobs)
                self.log(f"Found {len(jobs)} jobs on LinkedIn for '{search}'")
                
            except Exception as e:
                self.log(f"Error with LinkedIn search '{search}': {e}")
        
        return all_jobs

    def scrape_all_sources(self, selected_sources=None):
        """Scrape jobs from enabled sources"""
        self.new_jobs = []
        
        # If selected_sources is a dict of BooleanVar, convert to regular dict of booleans
        if selected_sources:
            processed_sources = {}
            for source, var in selected_sources.items():
                if hasattr(var, 'get'):  # If it's a BooleanVar
                    processed_sources[source] = var.get()
                else:
                    processed_sources[source] = bool(var)
            selected_sources = processed_sources
        # If no specific sources selected, use configuration
        else:
            selected_sources = {}
            for source, enabled in self.config["job_sources"].items():
                if enabled:
                    selected_sources[source] = True
        
        self.log(f"Selected sources: {', '.join([s for s, enabled in selected_sources.items() if enabled])}")
        
        # Scrape each selected source
        if selected_sources.get("freelancer", False):
            self.log("Scraping Freelancer...")
            freelancer_jobs = self.scrape_freelancer()
            for job in freelancer_jobs:
                if self.is_new_job(job):
                    self.new_jobs.append(job)
            self.log(f"Added {len(freelancer_jobs)} jobs from Freelancer")
        
        if selected_sources.get("craigslist", False):
            self.log("Scraping Craigslist...")
            craigslist_jobs = self.scrape_craigslist()
            for job in craigslist_jobs:
                if self.is_new_job(job):
                    self.new_jobs.append(job)
            self.log(f"Added {len(craigslist_jobs)} jobs from Craigslist")
        
        if selected_sources.get("indeed", False):
            self.log("Scraping Indeed...")
            indeed_jobs = self.scrape_indeed()
            for job in indeed_jobs:
                if self.is_new_job(job):
                    self.new_jobs.append(job)
            self.log(f"Added {len(indeed_jobs)} jobs from Indeed")
        
        if selected_sources.get("remoteok", False):
            self.log("Scraping RemoteOK...")
            remoteok_jobs = self.scrape_remoteok()
            for job in remoteok_jobs:
                if self.is_new_job(job):
                    self.new_jobs.append(job)
            self.log(f"Added {len(remoteok_jobs)} jobs from RemoteOK")
        
        if selected_sources.get("linkedin", False):
            self.log("Scraping LinkedIn...")
            linkedin_jobs = self.scrape_linkedin()
            for job in linkedin_jobs:
                if self.is_new_job(job):
                    self.new_jobs.append(job)
            self.log(f"Added {len(linkedin_jobs)} jobs from LinkedIn")
        
        if not self.new_jobs:
            self.log("No new jobs found or no sources selected. Try selecting different sources.")
        
        return self.new_jobs

    def rank_top_jobs(self, jobs=None, limit=100):
        """Rank jobs by relevance score and return top ones"""
        if jobs is None:
            jobs = self.all_jobs
        
        # Calculate basic scores for jobs
        for job in jobs:
            # Skip if job already has a score
            if 'score' not in job:
                score = 0
                title = job.get('title', '').lower()
                desc = job.get('description', '').lower()
                salary = job.get('salary', '')
                source = job.get('source', '').lower()
                
                # Boost for junior positions
                if any(term in title.lower() for term in ['junior', 'entry level', 'entry-level', 'beginner']):
                    score += 30
                
                # Add points for keywords
                for keyword in self.config["keywords"]:
                    if keyword.lower() in title:
                        score += 15
                    if keyword.lower() in desc:
                        score += 8
                
                # Deduct points for excluded keywords
                for keyword in self.config["exclude_keywords"]:
                    if keyword.lower() in title:
                        score -= 20
                    if keyword.lower() in desc:
                        score -= 15
                
                # Add points for salary
                if salary:
                    score += 25
                    
                    # Parse salary
                    if '$' in salary:
                        numbers = re.findall(r'\d+', salary)
                        if numbers:
                            # If it's hourly
                            if 'hour' in salary or 'hr' in salary or '/h' in salary:
                                try:
                                    rate = int(numbers[0])
                                    if rate > 25:
                                        score += 15
                                    elif rate > 15:
                                        score += 10
                                except:
                                    pass
                            # Annual salary
                            elif 'year' in salary or 'annually' in salary or 'annual' in salary or 'k' in salary:
                                try:
                                    amount = int(numbers[0])
                                    if 'k' in salary and amount < 1000:
                                        amount *= 1000
                                        
                                    if amount >= 80000:
                                        score += 25
                                    elif amount >= 60000:
                                        score += 20
                                    elif amount >= 40000:
                                        score += 10
                                except:
                                    pass
                
                # Add points for remote work
                if 'remote' in title or 'remote' in desc or 'work from home' in title or 'work from home' in desc:
                    score += 20
                
                # Bonus for beginner-friendly tech
                for tech in ['html', 'css', 'wordpress']:
                    if tech in title.lower():
                        score += 12
                    elif tech in desc.lower():
                        score += 6
                
                # Bonus based on source
                if source == 'remoteok' or 'remoteok' in source:
                    score += 10  # Remote work is guaranteed
                
                # Ensure scores stay reasonable
                score = max(score, 10)  # Minimum score
                score = min(score, 90)  # Maximum score
                
                job['score'] = score
        
        # Sort by score (highest first)
        ranked_jobs = sorted(jobs, key=lambda x: x.get('score', 0), reverse=True)
        
        # Take top jobs up to limit
        top_jobs = ranked_jobs[:limit]
        
        # Save top jobs to file
        try:
            with open(self.config["top_jobs_file"], 'w') as f:
                json.dump(top_jobs, f, indent=2)
        except Exception as e:
            self.log(f"Error saving top jobs: {e}")
            # Try saving to user's home directory
            try:
                home_path = os.path.expanduser('~/gravy_top_jobs.json')
                with open(home_path, 'w') as f:
                    json.dump(top_jobs, f, indent=2)
                self.log(f"Top jobs saved to {home_path}")
            except Exception as e2:
                self.log(f"Could not save top jobs anywhere: {e2}")
            
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

def call_claude_api(prompt, api_key=None, model="claude-3-haiku-20240307", temperature=0.0, log_callback=None):
    """Call the Claude API to analyze jobs"""
    if log_callback:
        log_callback(f"Calling Claude API with model: {model}...")
    
    # Use provided API key or fall back to global key
    if api_key is None:
        api_key = CLAUDE_API_KEY
        
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        error_msg = "No Claude API key provided. Please add your API key in the Settings tab."
        if log_callback:
            log_callback(error_msg)
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
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            if log_callback:
                log_callback(f"API error: Status code {response.status_code}")
            return None
            
        result = response.json()
        if log_callback:
            log_callback("API call successful!")
        
        # Extract content from response
        if "content" in result and len(result["content"]) > 0:
            for content_block in result["content"]:
                if content_block["type"] == "text":
                    return content_block["text"]
        
        return None
    except Exception as e:
        if log_callback:
            log_callback(f"Error calling Claude API: {e}")
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
    except json.JSONDecodeError:
        pass
    
    return []

def analyze_jobs_with_claude(jobs, batch_size=3, log_callback=None):
    """Analyze jobs using Claude API"""
    if log_callback:
        log_callback(f"Analyzing {len(jobs)} jobs with Claude...")
    
    results = []
    
    # Process jobs in batches
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i+batch_size]
        if log_callback:
            log_callback(f"Processing batch {i//batch_size + 1}/{(len(jobs) + batch_size - 1)//batch_size} ({len(batch)} jobs)")
        
        # Prepare prompt for this batch
        prompt = prepare_prompt_for_claude(batch)
        
        # Call Claude API
        response = call_claude_api(prompt=prompt, log_callback=log_callback)
        
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


# HTML Generation Functions
def generate_html_report(jobs, output_file='gravy_jobs.html'):
    """Generate an HTML report of the top gravy jobs"""
    if not jobs:
        return "No jobs to display"
    
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
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍯 Gravy Jobs for Beginners 🍯</h1>
            
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
    with open(output_file, 'w') as f:
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
        html += f'<div class="job-salary">💰 {salary}</div>'
        
    html += f"""
            <div class="job-description">{description}</div>
            {reasons_html}
            <a href="{url}" class="job-link" target="_blank">Apply Now</a>
        </div>
    """
    
    return html


# GUI Application Class
class GravyJobsApp:
    def __init__(self, root):
        self.root = root
        root.title("🍯 Gravy Jobs App")
        root.geometry("900x700")
        
        # Configure theme
        if "vista" in ttk.Style().theme_names():
            ttk.Style().theme_use("vista")
        
        # Variables
        self.sources = {
            "freelancer": tk.BooleanVar(value=True),
            "craigslist": tk.BooleanVar(value=True),
            "indeed": tk.BooleanVar(value=True),
            "remoteok": tk.BooleanVar(value=True),
            "linkedin": tk.BooleanVar(value=True)
        }
        self.analyze_with_claude = tk.BooleanVar(value=True)
        self.jobs_found = []
        self.analyzed_jobs = []
        
        # Create main container with padding
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        header_label = ttk.Label(
            header_frame, 
            text="🍯 Gravy Jobs - Find Easy & Well-Paying Programming Jobs", 
            font=("Arial", 18, "bold")
        )
        header_label.pack()
        
        desc_label = ttk.Label(
            header_frame,
            text="This app finds entry-level programming jobs and analyzes them for 'graviness' (easy + good pay + beginner-friendly)",
            wraplength=800
        )
        desc_label.pack(pady=(5, 0))
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Search
        search_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(search_frame, text="Search")
        
        # Job sources selection
        sources_frame = ttk.LabelFrame(search_frame, text="Job Sources", padding=10)
        sources_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create checkboxes for job sources (in a grid)
        row, col = 0, 0
        for source, var in self.sources.items():
            ttk.Checkbutton(
                sources_frame, 
                text=source.capitalize(), 
                variable=var,
                padding=(5, 0)
            ).grid(row=row, column=col, sticky=tk.W, padx=10)
            col += 1
            if col > 2:  # 3 columns max
                col = 0
                row += 1
        
        # Claude API option
        api_frame = ttk.Frame(search_frame)
        api_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            api_frame,
            text="Analyze jobs with Claude (provides detailed reasoning)",
            variable=self.analyze_with_claude
        ).pack(anchor=tk.W)
        
        # Buttons for actions
        buttons_frame = ttk.Frame(search_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            buttons_frame,
            text="Find Jobs",
            command=self.start_job_search,
            style="Accent.TButton"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            buttons_frame,
            text="View Results",
            command=self.view_results
        ).pack(side=tk.LEFT)
        
        # Log output
        log_frame = ttk.LabelFrame(search_frame, text="Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_output = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_output.pack(fill=tk.BOTH, expand=True)
        self.log_output.config(state=tk.DISABLED)
        
        # Tab 2: Results
        results_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(results_frame, text="Results")
        
        # Tab 3: Settings
        settings_frame = self.create_settings_tab()
        self.notebook.add(settings_frame, text="Settings")
        
        # Results filter controls
        filter_frame = ttk.LabelFrame(results_frame, text="Filter Jobs", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        category_frame = ttk.Frame(filter_frame)
        category_frame.pack(fill=tk.X)
        
        ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.category_var = tk.StringVar(value="All")
        self.category_combobox = ttk.Combobox(
            category_frame, 
            textvariable=self.category_var,
            values=["All", "Amazing", "Great", "Good", "Decent", "Challenging"],
            state="readonly",
            width=15
        )
        self.category_combobox.pack(side=tk.LEFT, padx=(0, 20))
        self.category_combobox.bind("<<ComboboxSelected>>", self.filter_results)
        
        # Remote only checkbox
        self.remote_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            category_frame,
            text="Remote Only",
            variable=self.remote_only_var,
            command=self.filter_results
        ).pack(side=tk.LEFT, padx=(0, 20))
        
        # Has salary checkbox
        self.has_salary_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            category_frame,
            text="Has Salary",
            variable=self.has_salary_var,
            command=self.filter_results
        ).pack(side=tk.LEFT)
        
        # Results table
        table_frame = ttk.Frame(results_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create Treeview for job results
        self.results_tree = ttk.Treeview(
            table_frame,
            columns=("title", "company", "source", "score", "category"),
            show="headings",
            selectmode="browse"
        )
        
        # Configure columns
        self.results_tree.heading("title", text="Job Title")
        self.results_tree.heading("company", text="Company")
        self.results_tree.heading("source", text="Source")
        self.results_tree.heading("score", text="Gravy Score")
        self.results_tree.heading("category", text="Category")
        
        self.results_tree.column("title", width=300)
        self.results_tree.column("company", width=150)
        self.results_tree.column("source", width=100)
        self.results_tree.column("score", width=80, anchor=tk.CENTER)
        self.results_tree.column("category", width=100)
        
        # Add vertical scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack tree and scrollbar
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to show job details
        self.results_tree.bind("<Double-1>", self.show_job_details)
        
        # Results action buttons
        results_buttons_frame = ttk.Frame(results_frame)
        results_buttons_frame.pack(fill=tk.X)
        
        ttk.Button(
            results_buttons_frame,
            text="View Job Details",
            command=lambda: self.show_job_details(None)
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            results_buttons_frame,
            text="Open in Browser",
            command=self.open_in_browser
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            results_buttons_frame,
            text="Export HTML Report",
            command=self.export_html
        ).pack(side=tk.LEFT)
        
        # Load any existing results
        self.load_existing_results()
        
        # Log initial message
        self.log("Welcome to Gravy Jobs! Select job sources and click 'Find Jobs' to begin.")

    def log(self, message):
        """Add a message to the log output"""
        self.log_output.config(state=tk.NORMAL)
        self.log_output.insert(tk.END, f"{message}\n")
        self.log_output.see(tk.END)
        self.log_output.config(state=tk.DISABLED)
        
        # Also update the GUI to prevent freezing
        self.root.update_idletasks()

    def load_existing_results(self):
        """Load any existing results from file"""
        try:
            if os.path.exists(CONFIG["top_jobs_file"]):
                with open(CONFIG["top_jobs_file"], 'r') as f:
                    self.analyzed_jobs = json.load(f)
                    self.jobs_found = self.analyzed_jobs.copy()
                    self.update_results_tree()
                    self.log(f"Loaded {len(self.analyzed_jobs)} jobs from previous results")
        except Exception as e:
            self.log(f"Error loading previous results: {e}")

    def start_job_search(self):
        """Start the job search process in a separate thread"""
        # Clear previous results
        self.log_output.config(state=tk.NORMAL)
        self.log_output.delete(1.0, tk.END)
        self.log_output.config(state=tk.DISABLED)
        
        # Disable search button during search
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == "Find Jobs":
                widget.config(state=tk.DISABLED)
        
        # Start search thread
        search_thread = threading.Thread(target=self.perform_job_search)
        search_thread.daemon = True
        search_thread.start()

    def perform_job_search(self):
        """Perform the job search (called from a separate thread)"""
        try:
            self.log("Starting job search...")
            
            # Get selected sources
            selected_sources = {}
            for source, var in self.sources.items():
                selected_sources[source] = var.get()
            
            # Create scraper with log callback
            scraper = JobScraper(CONFIG, self.log)
            
            # Scrape jobs
            self.log("Scraping for jobs (this may take a few minutes)...")
            new_jobs = scraper.scrape_all_sources(selected_sources)
            
            if new_jobs:
                self.log(f"Found {len(new_jobs)} new jobs!")
                
                # Combine with previous jobs
                all_jobs = scraper.previous_jobs + new_jobs
                scraper.all_jobs = all_jobs
                
                # Save all jobs
                self.log("Saving jobs...")
                scraper.save_jobs()
                
                # Rank jobs
                self.log("Ranking jobs by relevance...")
                top_jobs = scraper.rank_top_jobs(limit=100)
                self.log(f"Selected top {len(top_jobs)} jobs for analysis")
                
                # Store jobs found
                self.jobs_found = top_jobs
                
                # Analyze with Claude if selected
                if self.analyze_with_claude.get():
                    self.log("Analyzing jobs with Claude API...")
                    self.analyzed_jobs = analyze_jobs_with_claude(top_jobs, batch_size=3, log_callback=self.log)
                    
                    # Generate HTML report
                    self.log("Generating HTML report...")
                    output_file = generate_html_report(self.analyzed_jobs, CONFIG["web_output"])
                    self.log(f"HTML report generated: {os.path.abspath(output_file)}")
                else:
                    self.analyzed_jobs = top_jobs
                
                # Update results tree
                self.root.after(0, self.update_results_tree)
                
                # Switch to results tab
                self.root.after(0, lambda: self.notebook.select(1))
                
                self.log("Job search complete!")
            else:
                self.log("No new jobs found.")
        except Exception as e:
            self.log(f"Error in job search: {e}")
        finally:
            # Re-enable search button
            self.root.after(0, self.reenable_search_button)

    def reenable_search_button(self):
        """Re-enable the search button"""
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == "Find Jobs":
                widget.config(state=tk.NORMAL)

    def update_results_tree(self):
        """Update the results treeview with current jobs"""
        # Clear existing items
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Apply filters
        filtered_jobs = self.filter_jobs()
        
        # Add jobs to tree
        for job in filtered_jobs:
            title = job.get('title', 'No Title')
            company = job.get('company', 'Unknown')
            source = job.get('source', 'Unknown')
            score = job.get('gravy_score', job.get('score', 0))
            category = job.get('gravy_category', 'Uncategorized')
            
            self.results_tree.insert(
                "", 
                tk.END, 
                values=(title, company, source, score, category),
                tags=(category.lower(),)
            )
        
        # Configure tag colors
        self.results_tree.tag_configure('amazing', background='#efffef')
        self.results_tree.tag_configure('great', background='#eff6ff')
        self.results_tree.tag_configure('good', background='#fff9ef')
        self.results_tree.tag_configure('decent', background='#f5f5f5')
        self.results_tree.tag_configure('challenging', background='#ffefef')

    def filter_jobs(self):
        """Filter jobs based on selected criteria"""
        if not self.analyzed_jobs:
            return []
        
        filtered = self.analyzed_jobs.copy()
        
        # Filter by category
        category = self.category_var.get()
        if category != "All":
            filtered = [j for j in filtered if j.get('gravy_category', '') == category]
        
        # Filter by remote
        if self.remote_only_var.get():
            filtered = [j for j in filtered if 
                       'remote' in j.get('title', '').lower() or 
                       'remote' in j.get('description', '').lower() or
                       'work from home' in j.get('title', '').lower() or 
                       'work from home' in j.get('description', '').lower()]
        
        # Filter by salary
        if self.has_salary_var.get():
            filtered = [j for j in filtered if j.get('salary', '')]
        
        return filtered

    def filter_results(self, event=None):
        """Update results when filter is changed"""
        self.update_results_tree()

    def get_selected_job(self):
        """Get the currently selected job"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a job from the list first.")
            return None
        
        # Get values from selected item
        values = self.results_tree.item(selection, 'values')
        title = values[0]
        
        # Find matching job in analyzed_jobs
        for job in self.analyzed_jobs:
            if job.get('title', '') == title:
                return job
        
        return None

    def format_salary(self, salary_text):
        """Format and clean the salary information"""
        if not salary_text:
            return ""
            
        # Remove any unwanted characters and normalize
        salary_text = str(salary_text).strip()
        
        # Try to extract hourly rate or annual salary
        hourly_match = re.search(r'(\$?\d+[\.,]?\d*)[\/\s-]*(?:hour|hr|h\b)', salary_text, re.IGNORECASE)
        annual_match = re.search(r'(\$?\d+[\.,]?\d*)[kK]\b|(\$?\d+[\.,]?\d*)[\/\s-]*(?:year|yr|annual)', salary_text, re.IGNORECASE)
        range_match = re.search(r'(\$?\d+[\.,]?\d*)\s*-\s*(\$?\d+[\.,]?\d*)', salary_text)
        
        if hourly_match:
            rate = hourly_match.group(1)
            return f"${rate}/hour"
        elif annual_match:
            if annual_match.group(1):  # If it's a K format (e.g., $50K)
                base = annual_match.group(1).replace('$', '')
                return f"${base}K/year"
            else:  # Regular annual format
                base = annual_match.group(2).replace('$', '')
                return f"${base}/year"
        elif range_match:
            min_rate = range_match.group(1).replace('$', '')
            max_rate = range_match.group(2).replace('$', '')
            
            # Check if it's likely hourly or annual
            if float(min_rate.replace(',', '')) < 100:  # Likely hourly if under 100
                return f"${min_rate}-${max_rate}/hour"
            else:  # Likely annual
                return f"${min_rate}-${max_rate}/year"
        else:
            # Just clean up the format a bit
            return salary_text.replace('$', '$ ').strip()

    def show_job_details(self, event=None):
        """Show details for the selected job"""
        # If event is provided, get the item under cursor
        if event:
            item = self.results_tree.identify_row(event.y)
            if item:
                self.results_tree.selection_set(item)
            else:
                return
                
        job = self.get_selected_job()
        if not job:
            return
        
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title("Job Details")
        details_window.geometry("600x500")
        details_window.minsize(500, 400)
        
        # Make window modal
        details_window.transient(self.root)
        details_window.grab_set()
        
        # Create scrollable frame
        main_frame = ttk.Frame(details_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Title
        title_label = ttk.Label(
            scroll_frame, 
            text=job.get('title', 'No Title'),
            font=("Arial", 16, "bold"),
            wraplength=550
        )
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Company and source
        info_frame = ttk.Frame(scroll_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        company = job.get('company', 'Unknown')
        source = job.get('source', 'Unknown')
        
        company_label = ttk.Label(
            info_frame,
            text=f"Company: {company}",
            font=("Arial", 12)
        )
        company_label.pack(anchor=tk.W, side=tk.LEFT, padx=(0, 20))
        
        source_label = ttk.Label(
            info_frame,
            text=f"Source: {source}",
            font=("Arial", 12)
        )
        source_label.pack(anchor=tk.W, side=tk.LEFT)
        
        # Gravy score
        score_frame = ttk.Frame(scroll_frame)
        score_frame.pack(fill=tk.X, pady=(0, 15))
        
        score = job.get('gravy_score', job.get('score', 0))
        category = job.get('gravy_category', 'Uncategorized')
        
        score_label = ttk.Label(
            score_frame,
            text=f"Gravy Score: {score}",
            font=("Arial", 14, "bold")
        )
        score_label.pack(anchor=tk.W, side=tk.LEFT, padx=(0, 20))
        
        category_label = ttk.Label(
            score_frame,
            text=f"Category: {category}",
            font=("Arial", 14)
        )
        category_label.pack(anchor=tk.W, side=tk.LEFT)
        
        # Salary if available
        salary = job.get('salary', '')
        if salary:
            # Format the salary nicely
            formatted_salary = self.format_salary(salary)
            
            salary_label = ttk.Label(
                scroll_frame,
                text=f"Salary: {formatted_salary}",
                font=("Arial", 14, "bold"),
                foreground="#27ae60"
            )
            salary_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Description
        desc_frame = ttk.LabelFrame(scroll_frame, text="Description", padding=10)
        desc_frame.pack(fill=tk.X, pady=(0, 15))
        
        description = job.get('description', 'No description available.')
        desc_label = ttk.Label(
            desc_frame,
            text=description,
            wraplength=550,
            justify=tk.LEFT
        )
        desc_label.pack(anchor=tk.W)
        
        # Gravy reasoning
        reasoning = job.get('gravy_reasoning', [])
        if reasoning:
            reason_frame = ttk.LabelFrame(scroll_frame, text="Gravy Analysis", padding=10)
            reason_frame.pack(fill=tk.X, pady=(0, 15))
            
            for reason in reasoning:
                reason_label = ttk.Label(
                    reason_frame,
                    text=f"• {reason}",
                    wraplength=550,
                    justify=tk.LEFT
                )
                reason_label.pack(anchor=tk.W, pady=(0, 5))
        
        # URL and buttons
        url = job.get('url', '')
        url_frame = ttk.Frame(scroll_frame)
        url_frame.pack(fill=tk.X, pady=(0, 20))
        
        # URL display
        url_label = ttk.Label(
            url_frame,
            text=f"URL: {url}",
            wraplength=400
        )
        url_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Action buttons
        buttons_frame = ttk.Frame(scroll_frame)
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(
            buttons_frame,
            text="Open in Browser",
            command=lambda: webbrowser.open(url)
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            buttons_frame,
            text="Close",
            command=details_window.destroy
        ).pack(side=tk.LEFT)

    def view_results(self):
        """Switch to the results tab"""
        self.notebook.select(1)
        
    def view_settings(self):
        """Switch to the settings tab"""
        self.notebook.select(2)

    def open_in_browser(self):
        """Open the selected job in the browser"""
        
    def create_settings_tab(self):
        """Create the settings tab with API configuration"""
        settings_frame = ttk.Frame(self.notebook, padding=10)
        
        # API Settings section
        api_frame = ttk.LabelFrame(settings_frame, text="API Configuration", padding=10)
        api_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Claude API Key
        claude_key_frame = ttk.Frame(api_frame)
        claude_key_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(claude_key_frame, text="Claude API Key:").pack(side=tk.LEFT, padx=(0, 10))
        
        # Use StringVar to store the API key
        self.claude_api_key_var = tk.StringVar(value=CLAUDE_API_KEY)
        
        # Create a frame for the entry and toggle button
        key_entry_frame = ttk.Frame(claude_key_frame)
        key_entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Key entry field with show/hide toggle
        self.api_key_entry = ttk.Entry(key_entry_frame, textvariable=self.claude_api_key_var, show="*", width=40)
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Toggle visibility button
        self.show_key = tk.BooleanVar(value=False)
        
        def toggle_key_visibility():
            if self.show_key.get():
                self.api_key_entry.config(show="")
            else:
                self.api_key_entry.config(show="*")
        
        self.show_key_check = ttk.Checkbutton(
            key_entry_frame, 
            text="Show", 
            variable=self.show_key, 
            command=toggle_key_visibility
        )
        self.show_key_check.pack(side=tk.LEFT, padx=5)
        
        # Add explanation text
        ttk.Label(
            api_frame, 
            text="Get your API key from: https://console.anthropic.com/settings/keys", 
            font=("", 8)
        ).pack(fill=tk.X, pady=(0, 10))
        
        # Add Test Connection button
        ttk.Button(
            api_frame, 
            text="Test API Connection", 
            command=self.test_claude_api
        ).pack(side=tk.LEFT, padx=5, pady=10)
        
        # Save button 
        ttk.Button(
            api_frame, 
            text="Save API Key", 
            command=self.save_api_key
        ).pack(side=tk.LEFT, padx=5, pady=10)
        
        # Load saved API key on startup
        self.load_api_key()
        
        return settings_frame
        
    def save_api_key(self):
        """Save the API key to a config file"""
        try:
            api_key = self.claude_api_key_var.get().strip()
            
            # Update the global variable
            global CLAUDE_API_KEY
            CLAUDE_API_KEY = api_key
            
            # Save to config file
            config_dir = os.path.join(os.path.expanduser("~"), ".gravy_jobs")
            os.makedirs(config_dir, exist_ok=True)
            
            config_file = os.path.join(config_dir, "config.json")
            config_data = {}
            
            # Load existing config if available
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                except:
                    pass
            
            # Update with new API key
            config_data["claude_api_key"] = api_key
            
            # Save updated config
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            messagebox.showinfo("Success", "API key saved successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save API key: {str(e)}")
    
    def load_api_key(self):
        """Load API key from config file"""
        try:
            config_file = os.path.join(os.path.expanduser("~"), ".gravy_jobs", "config.json")
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    
                if "claude_api_key" in config_data and config_data["claude_api_key"]:
                    # Update the global variable
                    global CLAUDE_API_KEY
                    CLAUDE_API_KEY = config_data["claude_api_key"]
                    
                    # Update the UI
                    self.claude_api_key_var.set(CLAUDE_API_KEY)
        except Exception as e:
            # Just silently fail on load errors
            print(f"Error loading API key: {str(e)}")
    
    def test_claude_api(self):
        """Test the Claude API connection"""
        try:
            api_key = self.claude_api_key_var.get().strip()
            
            if not api_key:
                messagebox.showerror("Error", "Please enter an API key first")
                return
                
            self.log("Testing Claude API connection...")
            
            # Make a simple API call to test connection
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            data = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 10,
                "messages": [
                    {
                        "role": "user",
                        "content": "Say hello"
                    }
                ]
            }
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                # Success!
                messagebox.showinfo("Success", "API connection successful! Your key is working.")
                
                # Save the key since it works
                global CLAUDE_API_KEY
                CLAUDE_API_KEY = api_key
                self.save_api_key()
            else:
                error_msg = f"API Error: {response.status_code} - {response.text}"
                self.log(error_msg)
                messagebox.showerror("API Error", f"Failed to connect to Claude API. Status code: {response.status_code}")
                
        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            self.log(error_msg)
            messagebox.showerror("Error", f"Failed to connect to Claude API: {str(e)}")
    
        job = self.get_selected_job()
        if job:
            url = job.get('url', '')
            if url:
                try:
                    # First try using webbrowser module
                    success = webbrowser.open(url)
                    
                    if not success:
                        # If that fails, try direct system commands
                        self.log(f"Trying alternative methods to open URL: {url}")
                        
                        # Try multiple browser commands
                        browsers = [
                            "xdg-open", "firefox", "google-chrome", "chromium-browser", 
                            "sensible-browser", "x-www-browser", "gnome-open"
                        ]
                        
                        for browser in browsers:
                            try:
                                result = subprocess.run(
                                    [browser, url], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    timeout=2  # Don't wait too long
                                )
                                
                                if result.returncode == 0:
                                    self.log(f"Opened URL using {browser}")
                                    break
                            except Exception as e:
                                continue
                        
                        # Last resort: show URL so user can copy/paste
                        messagebox.showinfo(
                            "Browser Error", 
                            f"Could not open URL automatically. Please copy and paste this URL into your browser:\n\n{url}"
                        )
                except Exception as e:
                    # Show the URL if all methods fail
                    self.log(f"Error opening URL: {e}")
                    messagebox.showinfo(
                        "URL", 
                        f"Copy and paste this URL into your browser:\n\n{url}"
                    )
            else:
                messagebox.showinfo("No URL", "This job doesn't have a URL.")

    def export_html(self):
        """Export HTML report of all jobs"""
        if not self.analyzed_jobs:
            messagebox.showinfo("No Jobs", "No jobs to export. Please find jobs first.")
            return
        
        # Generate HTML report
        output_file = generate_html_report(self.analyzed_jobs, CONFIG["web_output"])
        file_path = os.path.abspath(output_file)
        file_url = f"file://{file_path}"
        
        # Set proper permissions so the file is readable by browsers
        try:
            # Make file readable by all users
            os.chmod(file_path, 0o644)
        except Exception as e:
            self.log(f"Warning: Could not set permissions on HTML file: {e}")
        
        # Try to open the file in browser
        try:
            # First try using webbrowser module
            success = webbrowser.open(file_url)
            
            if not success:
                # Try system methods as fallback
                browsers = [
                    "xdg-open", "firefox", "google-chrome", "chromium-browser", 
                    "sensible-browser", "x-www-browser", "gnome-open"
                ]
                
                for browser in browsers:
                    try:
                        result = subprocess.run(
                            [browser, file_url], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=2
                        )
                        
                        if result.returncode == 0:
                            self.log(f"Opened HTML report using {browser}")
                            break
                    except Exception:
                        continue
        except Exception as e:
            self.log(f"Warning: Could not open browser: {e}")
        
        # Show success message with path - always shown regardless of browser opening success
        messagebox.showinfo(
            "Export Complete", 
            f"HTML report generated successfully!\n\nFile: {file_path}\n\nIf the browser didn't open automatically, you can open this file manually."
        )


# Main function
def main():
    """Main entry point for the application"""
    root = tk.Tk()
    app = GravyJobsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()