#!/usr/bin/env python3

import sys
import os
import json
import logging
from datetime import datetime
import re

# Add the current directory to the path so we can import the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the JobScraper class
from job_scraper import JobScraper, CONFIG, logger

def extract_key_details(job):
    """Extract key details from a job for AI analysis"""
    details = {
        'title': job.get('title', 'Unknown'),
        'company': job.get('company', 'Unknown'),
        'source': job.get('source', 'Unknown'),
        'salary': job.get('salary', None),
        'description': job.get('description', ''),
        'url': job.get('url', '#'),
        'score': job.get('score', 0)
    }
    return details

def analyze_job_gravy_factor(job):
    """Analyze how 'gravy' a job is (easy, good-paying, beginner-friendly)"""
    gravy_score = 0
    reasoning = []
    
    # Get job details
    title = job.get('title', '').lower()
    desc = job.get('description', '').lower()
    salary = job.get('salary', None)
    
    # Check if it mentions entry-level, junior, beginner
    entry_terms = ['entry', 'junior', 'beginner', 'intern', 'trainee', 'jr.', 'jr']
    if any(term in title for term in entry_terms):
        gravy_score += 20
        reasoning.append("✓ Entry-level position mentioned in title")
    elif any(term in desc for term in entry_terms):
        gravy_score += 10
        reasoning.append("✓ Entry-level position mentioned in description")
        
    # Check for easy/simple work terms
    easy_terms = ['simple', 'basic', 'easy', 'straightforward']
    if any(term in title for term in easy_terms):
        gravy_score += 25
        reasoning.append("✓ Job explicitly described as simple/easy in title")
    elif any(term in desc for term in easy_terms):
        gravy_score += 15
        reasoning.append("✓ Job explicitly described as simple/easy in description")
    
    # Check for good salary
    if salary:
        try:
            # Extract numeric values from salary
            numbers = re.findall(r'\d+', str(salary))
            if numbers:
                if 'hour' in str(salary).lower() or 'hr' in str(salary).lower():
                    # Hourly rate
                    hourly = int(numbers[0])
                    if hourly >= 30:
                        gravy_score += 35
                        reasoning.append(f"✓ Great hourly pay: ~${hourly}/hr")
                    elif hourly >= 20:
                        gravy_score += 25
                        reasoning.append(f"✓ Good hourly pay: ~${hourly}/hr")
                    elif hourly >= 15:
                        gravy_score += 15
                        reasoning.append(f"✓ Decent hourly pay: ~${hourly}/hr")
                elif 'k' in str(salary).lower():
                    # Annual salary in K format (e.g., 50K)
                    annual = int(numbers[0]) * 1000
                    if annual >= 80000:
                        gravy_score += 35
                        reasoning.append(f"✓ Excellent salary: ~${annual/1000:.0f}K")
                    elif annual >= 60000:
                        gravy_score += 25
                        reasoning.append(f"✓ Great salary: ~${annual/1000:.0f}K")
                    elif annual >= 40000:
                        gravy_score += 15
                        reasoning.append(f"✓ Good salary: ~${annual/1000:.0f}K")
                else:
                    # Try to parse the largest number as the salary
                    max_num = max(int(n) for n in numbers)
                    if max_num >= 80000:
                        gravy_score += 30
                        reasoning.append(f"✓ Excellent potential salary: ~${max_num}")
                    elif max_num >= 60000:
                        gravy_score += 20
                        reasoning.append(f"✓ Great potential salary: ~${max_num}")
                    elif max_num >= 5000:  # Likely monthly or bigger than hourly
                        gravy_score += 15
                        reasoning.append(f"✓ Good potential compensation: ~${max_num}")
        except:
            # Still reward for having salary info
            gravy_score += 10
            reasoning.append("✓ Salary information available")
    
    # Check for remote work
    if 'remote' in title.lower() or 'work from home' in title.lower():
        gravy_score += 20
        reasoning.append("✓ Remote work mentioned in title")
    elif 'remote' in desc.lower() or 'work from home' in desc.lower():
        gravy_score += 15
        reasoning.append("✓ Remote work mentioned in description")
    
    # Check for specific easy job types
    easy_job_types = [
        ('wordpress', 'website', 15, "✓ WordPress/website development (typically straightforward)"),
        ('html', 'css', 15, "✓ HTML/CSS work (generally beginner-friendly)"),
        ('web design', '', 12, "✓ Web design (can be good for beginners)"),
        ('qa', 'test', 15, "✓ QA/Testing role (good entry point)"),
        ('data entry', '', 20, "✓ Data entry (simple, repetitive tasks)"),
        ('support', '', 10, "✓ Support role (good for building experience)")
    ]
    
    for term1, term2, points, reason in easy_job_types:
        if term1 in title.lower() or (term2 and term2 in title.lower()):
            gravy_score += points
            reasoning.append(reason)
        elif term1 in desc.lower() or (term2 and term2 in desc.lower()):
            gravy_score += points // 2  # Half points if only in description
            reasoning.append(reason + " (mentioned in description)")
    
    # Check for red flags (advanced technologies, high requirements)
    red_flags = [
        ('senior', 20, "✗ Senior position"),
        ('lead', 15, "✗ Leadership role"),
        ('expert', 15, "✗ Expert-level position"),
        ('years experience', 10, "✗ Experience requirements"),
        ('advanced', 10, "✗ Advanced skills required"),
        ('machine learning', 10, "✗ Complex technical field"),
        ('deep learning', 10, "✗ Complex technical field"),
        ('architect', 15, "✗ Architect-level position")
    ]
    
    for term, deduction, reason in red_flags:
        if term in title.lower():
            gravy_score -= deduction
            reasoning.append(reason)
        elif term in desc.lower():
            gravy_score -= deduction // 2  # Half deduction if only in description
            reasoning.append(reason + " (mentioned in description)")
    
    # Bonus for very beginner-friendly platforms
    if 'freelancer' in job.get('source', '').lower():
        gravy_score += 10
        reasoning.append("✓ Freelancer platform (good for beginners)")
    
    # Cap the min/max gravy score
    gravy_score = max(-50, min(100, gravy_score))
    
    return {
        'gravy_score': gravy_score,
        'reasoning': reasoning
    }

def get_top_gravy_jobs(jobs, limit=100):
    """Analyze and return the top 'gravy' jobs with reasoning"""
    # Process jobs to add gravy score and reasoning
    for job in jobs:
        gravy_analysis = analyze_job_gravy_factor(job)
        job['gravy_score'] = gravy_analysis['gravy_score']
        job['gravy_reasoning'] = gravy_analysis['reasoning']
    
    # Sort by gravy score (highest first)
    sorted_jobs = sorted(jobs, key=lambda x: x.get('gravy_score', 0), reverse=True)
    
    # Return top N jobs
    return sorted_jobs[:limit]

def generate_gravy_html_report(jobs, output_file='gravy_jobs.html'):
    """Generate an HTML report of the top gravy jobs"""
    if not jobs:
        return "No jobs to display"
    
    # Group jobs by gravy level
    amazing_jobs = [j for j in jobs if j.get('gravy_score', 0) >= 70]
    great_jobs = [j for j in jobs if 50 <= j.get('gravy_score', 0) < 70]
    good_jobs = [j for j in jobs if 30 <= j.get('gravy_score', 0) < 50]
    ok_jobs = [j for j in jobs if 10 <= j.get('gravy_score', 0) < 30]
    other_jobs = [j for j in jobs if j.get('gravy_score', 0) < 10]
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gravy Entry-Level Programming Jobs</title>
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
            .ok {{
                border-left: 5px solid #95a5a6;
            }}
            .other {{
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
            .score-ok {{
                background-color: #95a5a6;
            }}
            .score-other {{
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
            <h1>🍯 Gravy Entry-Level Programming Jobs 🍯</h1>
            
            <div class="explanation">
                <p><strong>What makes a job "gravy"?</strong> Claude has analyzed these jobs based on:</p>
                <ul>
                    <li>How easy/entry-level the job appears to be</li>
                    <li>Salary information (higher pay = more gravy)</li>
                    <li>Remote work options</li>
                    <li>Beginner-friendly technologies (HTML/CSS, WordPress, etc.)</li>
                    <li>Red flags (advanced skills, senior positions)</li>
                </ul>
                <p>Each job has been assigned a "Gravy Score" from 0-100. The higher the score, the more this job is considered easy, well-paying, and beginner-friendly.</p>
                <p class="text-warning">⚠️ Note: This analysis is automated and may not be perfect. Always read the full job description before applying.</p>
            </div>
            
            <div class="search-filters">
                <h3 class="filters-title">Quick Filters</h3>
                <div class="filter-options">
                    <div class="filter-tag active" onclick="filterJobs('all')">All Jobs</div>
                    <div class="filter-tag" onclick="filterJobs('remote')">Remote Only</div>
                    <div class="filter-tag" onclick="filterJobs('salary')">Has Salary</div>
                    <div class="filter-tag" onclick="filterJobs('beginner')">Super Beginner-Friendly</div>
                    <div class="filter-tag" onclick="filterJobs('html')">HTML/CSS Jobs</div>
                    <div class="filter-tag" onclick="filterJobs('wordpress')">WordPress Jobs</div>
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
    
    # Add OK jobs section
    if ok_jobs:
        html += f"""
            <h2>🙂 Decent Opportunities ({len(ok_jobs)})</h2>
            <div class="job-list">
        """
        
        for job in ok_jobs:
            html += generate_job_card(job, 'ok')
            
        html += """
            </div>
        """
    
    # Add other jobs section
    if other_jobs:
        html += f"""
            <h2>⚠️ Other Jobs ({len(other_jobs)})</h2>
            <p>These jobs may be more challenging or less suitable for beginners, but are still worth considering.</p>
            <div class="job-list">
        """
        
        for job in other_jobs:
            html += generate_job_card(job, 'other')
            
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
                    case 'beginner':
                        jobs.forEach(job => {
                            if (!job.getAttribute('data-beginner')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                    case 'html':
                        jobs.forEach(job => {
                            if (!job.getAttribute('data-html')) {
                                job.style.display = 'none';
                            }
                        });
                        break;
                    case 'wordpress':
                        jobs.forEach(job => {
                            if (!job.getAttribute('data-wordpress')) {
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
    gravy_score = job.get('gravy_score', 0)
    gravy_reasoning = job.get('gravy_reasoning', [])
    
    # Determine score class
    score_class = 'score-other'
    if gravy_score >= 70:
        score_class = 'score-amazing'
    elif gravy_score >= 50:
        score_class = 'score-great'
    elif gravy_score >= 30:
        score_class = 'score-good'
    elif gravy_score >= 10:
        score_class = 'score-ok'
    
    # Generate data attributes for filtering
    data_attrs = []
    
    # Remote attribute
    if 'remote' in title.lower() or 'work from home' in title.lower() or 'remote' in description.lower() or 'work from home' in description.lower():
        data_attrs.append('data-remote="true"')
    
    # Salary attribute
    if salary:
        data_attrs.append('data-salary="true"')
    
    # Beginner attribute
    beginner_terms = ['entry', 'junior', 'beginner', 'trainee', 'intern']
    if any(term in title.lower() for term in beginner_terms) or any(term in description.lower() for term in beginner_terms):
        data_attrs.append('data-beginner="true"')
    
    # HTML/CSS attribute
    if 'html' in title.lower() or 'css' in title.lower() or 'html' in description.lower() or 'css' in description.lower():
        data_attrs.append('data-html="true"')
    
    # WordPress attribute
    if 'wordpress' in title.lower() or 'wordpress' in description.lower():
        data_attrs.append('data-wordpress="true"')
    
    # Join data attributes
    data_attrs_str = ' '.join(data_attrs)
    
    # Generate job tags
    job_tags = []
    if 'remote' in title.lower() or 'work from home' in title.lower() or 'remote' in description.lower() or 'work from home' in description.lower():
        job_tags.append('<span class="gravy-tag">Remote</span>')
    
    if 'html' in title.lower() or 'css' in title.lower():
        job_tags.append('<span class="gravy-tag">HTML/CSS</span>')
    
    if 'wordpress' in title.lower():
        job_tags.append('<span class="gravy-tag">WordPress</span>')
        
    if any(term in title.lower() for term in beginner_terms):
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

def main():
    """Run the job scraper, have Claude analyze jobs, and generate the webpage"""
    print("=== AI-Curated Job Finder ===")
    print("This will find jobs from multiple sources, have Claude analyze them, and create an interactive webpage")
    
    # Check if we already have jobs data
    if os.path.exists(CONFIG["data_file"]) or os.path.exists(CONFIG["top_jobs_file"]):
        print("\nFound existing job data. Would you like to:")
        print("1. Use existing job data (faster)")
        print("2. Scrape for new jobs (takes longer)")
        
        try:
            choice = input("Enter your choice (1 or 2): ")
        except EOFError:
            # Default to using existing data in non-interactive environments
            choice = "1"
            print("Non-interactive environment detected, defaulting to option 1 (use existing data)")
        
        if choice.strip() == "1":
            # Use existing data
            try:
                if os.path.exists(CONFIG["top_jobs_file"]):
                    print("Using existing top jobs data...")
                    with open(CONFIG["top_jobs_file"], 'r') as f:
                        jobs = json.load(f)
                    print(f"Loaded {len(jobs)} jobs from {CONFIG['top_jobs_file']}")
                    
                    # Have Claude analyze the jobs
                    print("\nAnalyzing jobs for 'graviness'...")
                    gravy_jobs = get_top_gravy_jobs(jobs)
                    
                    # Generate the report
                    print(f"Generating webpage with {len(gravy_jobs)} gravy jobs...")
                    output_file = generate_gravy_html_report(gravy_jobs)
                    
                    print(f"\nDone! Web page created at: {os.path.abspath(output_file)}")
                    print(f"Run 'python serve_jobs.py --file={output_file}' to view it in your browser")
                    return
                elif os.path.exists(CONFIG["data_file"]):
                    print("Using existing all jobs data...")
                    with open(CONFIG["data_file"], 'r') as f:
                        jobs = json.load(f)
                    print(f"Loaded {len(jobs)} jobs from {CONFIG['data_file']}")
                    
                    # Have Claude analyze the jobs
                    print("\nAnalyzing jobs for 'graviness'...")
                    gravy_jobs = get_top_gravy_jobs(jobs)
                    
                    # Generate the report
                    print(f"Generating webpage with {len(gravy_jobs)} gravy jobs...")
                    output_file = generate_gravy_html_report(gravy_jobs)
                    
                    print(f"\nDone! Web page created at: {os.path.abspath(output_file)}")
                    print(f"Run 'python serve_jobs.py --file={output_file}' to view it in your browser")
                    return
            except Exception as e:
                print(f"Error using existing data: {e}")
                print("Proceeding to scrape for new jobs...")
    
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
        top_jobs = scraper.rank_top_jobs(limit=200)  # Get more jobs for AI analysis
        print(f"Selected top {len(top_jobs)} jobs for analysis")
        
        # Have Claude analyze the jobs
        print("\nAnalyzing jobs for 'graviness'...")
        gravy_jobs = get_top_gravy_jobs(top_jobs)
        
        # Generate the report
        print(f"Generating webpage with {len(gravy_jobs)} gravy jobs...")
        output_file = generate_gravy_html_report(gravy_jobs)
        
        print(f"\nDone! Web page created at: {os.path.abspath(output_file)}")
        print(f"Run 'python serve_jobs.py --file={output_file}' to view it in your browser")
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