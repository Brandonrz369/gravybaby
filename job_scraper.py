#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
import concurrent.futures
import re
import random
from urllib.parse import quote_plus

# Import the VPN Manager
try:
    from vpn_manager import VPNManager
    VPN_AVAILABLE = True
except ImportError:
    VPN_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='job_scraper.log'
)
logger = logging.getLogger('job_scraper')

# Configuration - modify these settings
CONFIG = {
    "keywords": ["simple", "basic", "beginner", "entry level", "junior", "wordpress", "html", "css", "remote"],
    "exclude_keywords": ["senior", "lead", "expert", "5+ years", "7+ years", "10+ years"],
    "major_cities": [
        "newyork", "losangeles", "chicago", "houston", "phoenix", "philadelphia", 
        "sanantonio", "sandiego", "dallas", "austin", "sanjose", "seattle", "denver",
        "boston", "remote"
    ],
    "email": {
        "sender": "your_email@gmail.com",  # Update with your email
        "receiver": "your_email@gmail.com",  # Update with your email
        "password": "",  # Set this using environment variable for security
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587
    },
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
    "max_jobs_per_source": 50,  # Increased from 15 to 50
    "data_file": "all_jobs.json",
    "top_jobs_file": "top_jobs.json",
    "web_output": "jobs.html"
}

# Load environment variables for sensitive data
CONFIG["email"]["password"] = os.environ.get("EMAIL_PASSWORD", "")

class JobScraper:
    def __init__(self, config, custom_search_query=None):
        self.config = config
        self.custom_search_query = custom_search_query
        self.custom_search_params = None
        
        # Set up VPN Manager if available
        self.vpn_manager = None
        if VPN_AVAILABLE:
            try:
                self.vpn_manager = VPNManager()
                logger.info("VPN Manager initialized successfully")
                
                # Verify license status
                license_status = self.vpn_manager.get_license_status()
                logger.info(f"License status: {'Valid' if license_status.get('valid', False) else 'Invalid or missing'}")
                
                # Get commercial proxy status
                proxy_status = self.vpn_manager.get_commercial_proxy_status()
                if proxy_status["enabled"] and proxy_status["licensed"]:
                    logger.info(f"Using commercial proxy service: {proxy_status['current_service']}")
                
                # Process custom search query if provided
                if custom_search_query:
                    logger.info(f"Processing custom search query: {custom_search_query}")
                    self.custom_search_params = self.vpn_manager.generate_search_parameters(custom_search_query)
                    logger.info(f"Generated search parameters: {self.custom_search_params}")
                    
                    # Update config with custom parameters
                    if self.custom_search_params:
                        if "keywords" in self.custom_search_params:
                            self.config["keywords"] = self.custom_search_params["keywords"]
                        if "exclude_keywords" in self.custom_search_params:
                            self.config["exclude_keywords"] = self.custom_search_params["exclude_keywords"]
                
            except Exception as e:
                logger.error(f"Error initializing VPN Manager: {e}")
        
        # Fallback headers if VPN Manager is not available
        self.headers = {
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
        
        self.all_jobs = []
        self.previous_jobs = self.load_previous_jobs()
        self.new_jobs = []
        
        # Create fallback data directory if it doesn't exist
        os.makedirs("fallback_data", exist_ok=True)
        
        # If VPN Manager is available, display status
        if self.vpn_manager:
            logger.info("Using VPN Manager for requests")
            
            # If using browser fingerprinting, log it
            if self.vpn_manager.config["browser_fingerprints"]["enabled"]:
                logger.info("Browser fingerprinting is enabled for anti-detection")
                
            # Log proxy configuration
            if self.vpn_manager.config["proxy_services"]["enabled"]:
                service = self.vpn_manager.config["proxy_services"]["current_service"]
                logger.info(f"Using commercial proxy service: {service}")
            else:
                logger.info(f"Using standard proxy: {self.vpn_manager.config['current_proxy_index'] + 1} of {len(self.vpn_manager.config['proxies'])}")
        else:
            logger.info("VPN Manager not available, using standard requests")
            
    def _get_with_vpn(self, url, params=None, allow_fallback=True, retry_count=3):
        """Get URL content using VPN Manager if available, otherwise use standard requests"""
        start_time = time.time()
        
        # Try VPN Manager first if available
        if self.vpn_manager:
            try:
                content = self.vpn_manager.get(url, params=params)
                if content:
                    elapsed = time.time() - start_time
                    logger.info(f"VPN Manager request successful in {elapsed:.2f}s: {url}")
                    return content
                else:
                    logger.warning(f"VPN Manager request failed: {url}")
            except Exception as e:
                logger.error(f"Error using VPN Manager: {e}")
                
            # If VPN Manager failed and we should try again with standard requests
            if not allow_fallback:
                return None
        
        # Fall back to standard requests
        for attempt in range(retry_count):
            try:
                # Add a random delay between retries
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"Retry attempt {attempt+1}, waiting {delay:.2f}s")
                    time.sleep(delay)
                
                # Randomize the User-Agent
                headers = self.headers.copy()
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
                ]
                headers['User-Agent'] = random.choice(user_agents)
                
                response = requests.get(url, params=params, headers=headers, timeout=30)
                
                # Check for blocking or rate limiting
                if response.status_code in [403, 429, 503]:
                    logger.warning(f"Request blocked (status {response.status_code}): {url}")
                    continue
                
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    logger.info(f"Standard request successful in {elapsed:.2f}s: {url}")
                    return response.text
                else:
                    logger.error(f"Request failed with status {response.status_code}: {url}")
            except Exception as e:
                logger.error(f"Request error on attempt {attempt+1}: {e}")
        
        # All attempts failed, check if we have fallback data
        if allow_fallback:
            fallback_data = self._load_fallback_data(url)
            if fallback_data:
                logger.warning(f"Using fallback data for {url}")
                return fallback_data
                
        return None
        
    def _save_fallback_data(self, url, content):
        """Save data as fallback for future use if the site blocks us"""
        if not content:
            return
            
        # Create a safe filename from the URL
        filename = url.replace("://", "_").replace("/", "_").replace("?", "_")
        filename = filename[:200] + ".html"  # Limit length
        filepath = os.path.join("fallback_data", filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Saved fallback data for {url}")
        except Exception as e:
            logger.error(f"Error saving fallback data: {e}")
            
    def _load_fallback_data(self, url):
        """Load fallback data if available"""
        # Create a safe filename from the URL
        filename = url.replace("://", "_").replace("/", "_").replace("?", "_")
        filename = filename[:200] + ".html"  # Limit length
        filepath = os.path.join("fallback_data", filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Loaded fallback data for {url}")
                return content
            except Exception as e:
                logger.error(f"Error loading fallback data: {e}")
                
        return None

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

    def has_salary_info(self, text):
        """Check if text contains salary information"""
        if not text:
            return False
        
        # Common salary patterns
        patterns = [
            r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', # $50,000, $50000, $50.00
            r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|dollars)', # 50,000 USD, 50000 dollars
            r'\d{1,3}(?:,\d{3})*(?:k|K)', # 50k, 50K
            r'\$\d{1,3}(?:,\d{3})*\s*-\s*\$\d{1,3}(?:,\d{3})*', # $50,000 - $70,000
            r'\$\d{1,2}(?:\.\d{2})?\s*(?:per hour|\/hr|\/hour|an hour)', # $15 per hour, $15/hr
            r'\d{2,3}\s*(?:per hour|\/hr|\/hour|an hour)', # 15 per hour, 15/hr
        ]
        
        for pattern in patterns:
            if re.search(pattern, text):
                return True
                
        return False

    def extract_salary(self, text):
        """Extract salary information from text"""
        if not text:
            return None
            
        # Try to find salary patterns
        patterns = [
            r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', # $50,000
            r'\d{1,3}(?:,\d{3})*\s*(?:USD|dollars)', # 50,000 USD
            r'\d{1,3}(?:k|K)', # 50k
            r'\$\d{1,3}(?:,\d{3})*\s*-\s*\$\d{1,3}(?:,\d{3})*', # $50,000 - $70,000
            r'\$\d{2}(?:\.\d{2})?\s*(?:per hour|\/hr|\/hour|an hour)', # $15 per hour
            r'\d{2,3}\s*(?:per hour|\/hr|\/hour|an hour)', # 15 per hour
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
                
        return None

    def is_new_job(self, job):
        """Check if a job is new (not in previous jobs)"""
        for prev_job in self.previous_jobs:
            if prev_job['url'] == job['url']:
                return False
        return True

    def calculate_job_score(self, job):
        """Calculate a relevance score for a job"""
        score = 0
        
        # Add points for keywords in title (weighted higher)
        if 'title' in job:
            for keyword in self.config["keywords"]:
                if keyword.lower() in job['title'].lower():
                    score += 10
        
        # Add points for keywords in description
        if 'description' in job:
            for keyword in self.config["keywords"]:
                if keyword.lower() in job['description'].lower():
                    score += 5
        
        # Deduct points for excluded keywords
        if 'title' in job:
            for keyword in self.config["exclude_keywords"]:
                if keyword.lower() in job['title'].lower():
                    score -= 15
        
        if 'description' in job:
            for keyword in self.config["exclude_keywords"]:
                if keyword.lower() in job['description'].lower():
                    score -= 10
        
        # Add points for salary information
        if 'salary' in job and job['salary']:
            score += 20
            
            # Try to parse the salary amount
            try:
                # Extract numeric part using regex
                salary_text = job['salary']
                numbers = re.findall(r'\d+', salary_text)
                if numbers:
                    # If hourly, convert to approximate annual
                    if 'hour' in salary_text or 'hr' in salary_text:
                        hourly = int(numbers[0])
                        if hourly > 20:  # Good hourly rate
                            score += 10
                        if hourly > 30:  # Great hourly rate
                            score += 15
                    else:
                        # Assume annual salary
                        if 'k' in salary_text or 'K' in salary_text:
                            # Handle format like "50k"
                            annual = int(numbers[0]) * 1000
                        else:
                            # Try to use the largest number found as the salary
                            numbers = [int(n) for n in numbers]
                            annual = max(numbers)
                            
                        if annual > 50000:  # Good salary
                            score += 10
                        if annual > 80000:  # Great salary
                            score += 15
            except:
                # If we can't parse it, still give some points for having salary info
                pass
                
        # Add points for remote work
        if 'title' in job and ('remote' in job['title'].lower() or 'work from home' in job['title'].lower()):
            score += 15
            
        if 'description' in job and ('remote' in job['description'].lower() or 'work from home' in job['description'].lower()):
            score += 10
            
        # Add points for entry-level indicators
        entry_level_terms = ['entry', 'junior', 'beginner', 'intern', 'trainee']
        if 'title' in job:
            for term in entry_level_terms:
                if term.lower() in job['title'].lower():
                    score += 15
                    
        if 'description' in job:
            for term in entry_level_terms:
                if term.lower() in job['description'].lower():
                    score += 8
        
        # Check if appears to be easy/simple job
        easy_terms = ['simple', 'basic', 'easy', 'straightforward']
        if 'title' in job:
            for term in easy_terms:
                if term.lower() in job['title'].lower():
                    score += 12
                    
        if 'description' in job:
            for term in easy_terms:
                if term.lower() in job['description'].lower():
                    score += 6
            
        # Recency bonus
        if 'date' in job:
            try:
                job_date = datetime.strptime(job['date'], "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                days_old = (now - job_date).days
                if days_old < 1:  # Less than a day old
                    score += 15
                elif days_old < 3:  # Less than 3 days old
                    score += 10
                elif days_old < 7:  # Less than a week old
                    score += 5
            except:
                pass
        
        return score

    def rank_top_jobs(self, jobs=None, limit=100):
        """Rank jobs by relevance score and return top ones"""
        if jobs is None:
            jobs = self.all_jobs
            
        # Calculate scores for all jobs
        for job in jobs:
            if 'score' not in job:
                job['score'] = self.calculate_job_score(job)
        
        # Sort by score (highest first)
        ranked_jobs = sorted(jobs, key=lambda x: x.get('score', 0), reverse=True)
        
        # Take top jobs up to limit
        top_jobs = ranked_jobs[:limit]
        
        # Save top jobs to file
        with open(self.config["top_jobs_file"], 'w', encoding='utf-8') as f:
            json.dump(top_jobs, f, indent=2, ensure_ascii=False)
            
        return top_jobs

    def generate_html_report(self, jobs=None):
        """Generate an HTML report of the top jobs"""
        if jobs is None:
            # Load top jobs if available, otherwise use all jobs
            if os.path.exists(self.config["top_jobs_file"]):
                with open(self.config["top_jobs_file"], 'r') as f:
                    jobs = json.load(f)
            else:
                jobs = self.rank_top_jobs()
        
        # Group jobs by source
        jobs_by_source = {}
        for job in jobs:
            source = job.get('source', 'Other')
            if source not in jobs_by_source:
                jobs_by_source[source] = []
            jobs_by_source[source].append(job)
        
        # Generate HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Top Entry-Level Programming Jobs</title>
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
                    margin-bottom: 30px;
                    color: #2c3e50;
                }}
                .job-source {{
                    margin-bottom: 40px;
                }}
                .job-source h2 {{
                    color: #3498db;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #3498db;
                }}
                .job-list {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 20px;
                }}
                .job-card {{
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    padding: 15px;
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }}
                .job-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                }}
                .job-title {{
                    color: #2c3e50;
                    font-size: 18px;
                    margin-top: 0;
                    margin-bottom: 10px;
                }}
                .job-company {{
                    color: #7f8c8d;
                    margin-bottom: 10px;
                    font-weight: bold;
                }}
                .job-salary {{
                    color: #27ae60;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .job-description {{
                    margin-bottom: 15px;
                    font-size: 14px;
                    color: #555;
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
                .job-meta {{
                    font-size: 12px;
                    color: #95a5a6;
                    margin-top: 10px;
                }}
                .job-score {{
                    display: inline-block;
                    background: #f39c12;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    margin-left: 10px;
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
                .job-date {{
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Top Entry-Level Programming Jobs</h1>
                
                <div class="search-filters">
                    <h3 class="filters-title">Quick Filters</h3>
                    <div class="filter-options">
                        <div class="filter-tag" onclick="filterJobs('all')">All Jobs</div>
                        <div class="filter-tag" onclick="filterJobs('remote')">Remote</div>
                        <div class="filter-tag" onclick="filterJobs('salary')">Has Salary</div>
                        <div class="filter-tag" onclick="filterJobs('beginner')">Beginner-Friendly</div>
                        <div class="filter-tag" onclick="filterJobs('newest')">Newest</div>
                        <div class="filter-tag" onclick="filterJobs('highest-score')">Top Rated</div>
                    </div>
                </div>
                
                <p>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        """
        
        # Add jobs by source
        for source, source_jobs in jobs_by_source.items():
            html += f"""
                <div class="job-source">
                    <h2>{source} ({len(source_jobs)})</h2>
                    <div class="job-list">
            """
            
            # Add individual job cards
            for job in source_jobs:
                title = job.get('title', 'No Title')
                company = job.get('company', 'Unknown')
                description = job.get('description', 'No description available.')
                url = job.get('url', '#')
                salary = job.get('salary', '')
                date = job.get('date', '')
                score = job.get('score', 0)
                
                # Add attributes for filtering
                attributes = []
                if 'remote' in title.lower() or 'remote' in description.lower():
                    attributes.append('data-remote="true"')
                if salary:
                    attributes.append('data-salary="true"')
                if any(term in title.lower() or term in description.lower() for term in ['beginner', 'entry', 'junior']):
                    attributes.append('data-beginner="true"')
                    
                attributes_str = ' '.join(attributes)
                
                html += f"""
                    <div class="job-card" {attributes_str} data-score="{score}" data-date="{date}">
                        <h3 class="job-title">{title}</h3>
                        <div class="job-company">{company}</div>
                """
                
                if salary:
                    html += f'<div class="job-salary">$ {salary}</div>'
                    
                html += f"""
                        <div class="job-description">{description}</div>
                        <a href="{url}" class="job-link" target="_blank">Apply Now</a>
                        <div class="job-meta">
                            <span class="job-date">{date}</span>
                            <span class="job-score">Score: {score}</span>
                        </div>
                    </div>
                """
            
            html += """
                    </div>
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
                                if (job.getAttribute('data-remote') !== 'true') {
                                    job.style.display = 'none';
                                }
                            });
                            break;
                        case 'salary':
                            jobs.forEach(job => {
                                if (job.getAttribute('data-salary') !== 'true') {
                                    job.style.display = 'none';
                                }
                            });
                            break;
                        case 'beginner':
                            jobs.forEach(job => {
                                if (job.getAttribute('data-beginner') !== 'true') {
                                    job.style.display = 'none';
                                }
                            });
                            break;
                        case 'newest':
                            // Sort by date (newest first)
                            const sortedByDate = Array.from(jobs).sort((a, b) => {
                                const dateA = new Date(a.getAttribute('data-date'));
                                const dateB = new Date(b.getAttribute('data-date'));
                                return dateB - dateA;
                            });
                            
                            // Reorder in DOM
                            sortedByDate.forEach(job => {
                                job.parentNode.appendChild(job);
                            });
                            break;
                        case 'highest-score':
                            // Sort by score (highest first)
                            const sortedByScore = Array.from(jobs).sort((a, b) => {
                                const scoreA = parseInt(a.getAttribute('data-score'));
                                const scoreB = parseInt(b.getAttribute('data-score'));
                                return scoreB - scoreA;
                            });
                            
                            // Reorder in DOM
                            sortedByScore.forEach(job => {
                                job.parentNode.appendChild(job);
                            });
                            break;
                    }
                }
            </script>
        </body>
        </html>
        """
        
        # Write to file - use UTF-8 encoding explicitly
        with open(self.config["web_output"], 'w', encoding='utf-8') as f:
            f.write(html)
            
        return html

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
                                        if self.has_salary_info(description):
                                            compensation = self.extract_salary(description)
                                    
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
                encoded_search = quote_plus(search)
                url = f"https://www.indeed.com/jobs?q={encoded_search}&sort=date"
                
                # Use VPN-enhanced request method
                response_text = self._get_with_vpn(url)
                
                # If we couldn't get the page, try the next search term
                if not response_text:
                    logger.error(f"Failed to fetch Indeed for '{search}'")
                    continue
                
                # Save fallback data for future use
                self._save_fallback_data(url, response_text)
                
                # Parse the HTML
                soup = BeautifulSoup(response_text, 'html.parser')
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
                    # Try to save HTML for debugging
                    with open(f'indeed_debug_{search.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
                        f.write(soup.prettify())
                    logger.info(f"Saved Indeed HTML to indeed_debug_{search.replace(' ', '_')}.html for debugging")
                    continue
                
                for i, job in enumerate(job_listings):
                    # Print sample HTML for debugging
                    if i == 0:
                        logger.info(f"Sample job HTML: {job.prettify()[:500]}")
                    
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
                        if not salary and self.has_salary_info(description):
                            salary = self.extract_salary(description)
                        
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
                
                # Use variable delay to avoid detection
                delay = random.uniform(1.5, 4)
                logger.info(f"Sleeping for {delay:.2f} seconds to avoid rate limiting")
                time.sleep(delay)
                
                # Occasionally rotate proxy to avoid detection patterns
                if random.random() < 0.25 and self.vpn_manager:  # 25% chance to rotate
                    logger.info("Randomly rotating proxy for Indeed")
                    self.vpn_manager.rotate_proxy()
                
            except Exception as e:
                logger.error(f"Error scraping Indeed for '{search}': {e}")
                
                # If we have the VPN manager, try rotating the proxy when errors occur
                if self.vpn_manager:
                    logger.info("Rotating proxy after error")
                    self.vpn_manager.rotate_proxy()
                    
                # Wait a bit longer after an error
                time.sleep(random.uniform(5, 10))
        
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

    def scrape_stackoverflow(self):
        """Scrape entry-level programming jobs from Stack Overflow"""
        jobs = []
        try:
            url = "https://stackoverflow.com/jobs?sort=i"
            response = requests.get(url, headers=self.headers)
            
            # Stack Overflow Jobs was discontinued, so we'll redirect to Stack Overflow Talent
            url = "https://stackoverflow.com/talent"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Stack Overflow: Status {response.status_code}")
                return jobs
                
            # Since Stack Overflow Jobs is gone, we'll just return an empty list
            logger.info("Stack Overflow Jobs was discontinued, returning empty list")
        except Exception as e:
            logger.error(f"Error scraping Stack Overflow: {e}")
        
        return jobs

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
                encoded_search = quote_plus(search)
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
            if self.config["job_sources"]["stackoverflow"]:
                tasks.append(executor.submit(self.scrape_stackoverflow))
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

    def send_email_notification(self, new_jobs):
        """Send email notification with new jobs"""
        if not new_jobs:
            logger.info("No new jobs to notify about")
            return
        
        if not self.config["email"]["password"]:
            logger.error("Email password not set. Set the EMAIL_PASSWORD environment variable.")
            return
        
        try:
            # Create email
            msg = MIMEMultipart()
            msg['From'] = self.config["email"]["sender"]
            msg['To'] = self.config["email"]["receiver"]
            msg['Subject'] = f"New Entry-Level Programming Jobs - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Email body
            body = "<html><body>"
            body += f"<h2>New Entry-Level Programming Jobs - {len(new_jobs)} found</h2>"
            body += f"<p>View the full list of jobs at: <a href='file://{os.path.abspath(self.config['web_output'])}'>jobs.html</a></p>"
            
            # Group jobs by source
            jobs_by_source = {}
            for job in new_jobs:
                source = job['source']
                if source not in jobs_by_source:
                    jobs_by_source[source] = []
                jobs_by_source[source].append(job)
            
            # Show top 5 jobs per source
            for source, jobs in jobs_by_source.items():
                body += f"<h3>{source} ({len(jobs)})</h3>"
                body += "<ul>"
                for job in jobs[:5]:  # Limit to top 5 per source
                    body += f"<li><strong><a href='{job['url']}'>{job['title']}</a></strong><br>"
                    if 'company' in job:
                        body += f"Company: {job['company']}<br>"
                    if 'salary' in job and job['salary']:
                        body += f"Salary: {job['salary']}<br>"
                    body += f"{job['description']}<br>"
                    body += f"<small>Found: {job['date']}</small></li><br>"
                body += "</ul>"
                
                if len(jobs) > 5:
                    body += f"<p>...and {len(jobs) - 5} more jobs from {source}. See the HTML report for all jobs.</p>"
            
            body += "</body></html>"
            
            msg.attach(MIMEText(body, 'html'))
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
                server.starttls()
                server.login(self.config["email"]["sender"], self.config["email"]["password"])
                server.send_message(msg)
            
            logger.info(f"Email notification sent with {len(new_jobs)} new jobs")
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    def run(self):
        """Run the job scraper"""
        logger.info("Starting job scraper")
        
        while True:
            try:
                logger.info("Scraping for new jobs...")
                new_jobs = self.scrape_all_sources()
                
                if new_jobs:
                    logger.info(f"Found {len(new_jobs)} new jobs")
                    self.all_jobs = self.previous_jobs + new_jobs
                    
                    # Rank and generate report
                    logger.info("Ranking jobs...")
                    top_jobs = self.rank_top_jobs()
                    logger.info(f"Generated top {len(top_jobs)} jobs")
                    
                    logger.info("Generating HTML report...")
                    self.generate_html_report(top_jobs)
                    
                    self.send_email_notification(new_jobs)
                    self.save_jobs()
                else:
                    logger.info("No new jobs found")
                
                # Wait for the next check interval
                logger.info(f"Sleeping for {self.config['check_interval_hours']} hours")
                time.sleep(self.config["check_interval_hours"] * 3600)
            except KeyboardInterrupt:
                logger.info("Job scraper stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # Wait for a shorter time before retrying after an error
                time.sleep(300)  # 5 minutes


if __name__ == "__main__":
    # Check if required packages are installed
    try:
        import requests
        from bs4 import BeautifulSoup
        import argparse
    except ImportError:
        print("Required packages not found. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "requests", "beautifulsoup4"])
        print("Packages installed. Restarting script...")
        import sys
        import os
        os.execv(sys.executable, ['python'] + sys.argv)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Gravy Jobs - Job Scraper with VPN rotation and custom search")
    parser.add_argument("--query", type=str, help="Custom search query for Claude to process")
    parser.add_argument("--test", action="store_true", help="Run in test mode without actual scraping")
    parser.add_argument("--location", type=str, help="Location to search for jobs in (e.g., 'Seattle, WA')")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode without terminal windows")
    args = parser.parse_args()
    
    # Apply command line arguments to config
    if args.test:
        print("Running in test mode - no actual scraping will be performed")
        # Modify config for test mode as needed
        
    if args.location:
        print(f"Focusing search on location: {args.location}")
        if isinstance(CONFIG["keywords"], list):
            CONFIG["keywords"].append(args.location)
            
    if args.headless:
        print("Running in headless mode - no terminal windows will be shown")
        # Setup headless mode (Windows specific)
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.kernel32.FreeConsole()
                print("Detached console for headless operation")
            except:
                print("Failed to detach console, continuing with visible console")
    
    # Create and run the job scraper
    scraper = JobScraper(CONFIG, custom_search_query=args.query)
    
    # In test mode, just generate sample HTML without scraping
    if args.test:
        print("Running in test mode - generating sample HTML report...")
        
        # Create sample test data
        test_jobs = [
            {
                "title": "Python Developer (Remote)",
                "company": "TestCorp Inc.",
                "description": "Entry-level position for Python developers. Work from anywhere!",
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
        
        # Generate HTML report
        scraper.generate_html_report(test_jobs)
        print("Test completed! Check 'jobs.html' to view the sample report.")
        
        # If VPN manager is available, test it too
        if scraper.vpn_manager:
            print("\nTesting VPN manager...")
            print(f"License status: {scraper.vpn_manager.get_license_status()['valid']}")
            if "claude_integration" in scraper.vpn_manager.get_license_status().get("enabled_features", []):
                params = scraper.vpn_manager.generate_search_parameters("Python developer remote job")
                print(f"Generated search parameters for 'Python developer remote job':")
                print(f"- Keywords: {params.get('keywords', [])}")
                print(f"- Exclude: {params.get('exclude_keywords', [])}")
                print(f"- Locations: {params.get('locations', [])}")
    else:
        # Run the full scraper
        scraper.run()