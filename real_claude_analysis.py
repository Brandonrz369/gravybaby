#!/usr/bin/env python3

import sys
import os
import json
import logging
from datetime import datetime
import argparse
import time
import requests
from pathlib import Path

# Add the current directory to the path so we can import the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the JobScraper class
from job_scraper import JobScraper, CONFIG, logger

# Configuration for Claude API
CLAUDE_API_CONFIG = {
    "api_key": "",  # Your Claude API key here
    "model": "claude-3-5-sonnet-20240620",  # Claude model to use
    "max_jobs_per_batch": 10,  # Number of jobs to send in each batch to Claude
    "temperature": 0.0  # Keep temperature low for consistent analysis
}

def extract_job_details(job):
    """Extract key details from a job for Claude analysis"""
    details = {
        'title': job.get('title', 'Unknown'),
        'company': job.get('company', 'Unknown') if 'company' in job else 'Unknown',
        'source': job.get('source', 'Unknown'),
        'description': job.get('description', 'No description available'),
        'salary': job.get('salary', None),
        'url': job.get('url', '')
    }
    return details

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
        details = extract_job_details(job)
        prompt += f"""
JOB {i+1}:
Title: {details['title']}
Company: {details['company']}
Source: {details['source']}
{"Salary: " + details['salary'] if details['salary'] else "Salary: Not specified"}
Description: {details['description']}
URL: {details['url']}

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
    # Import the global API key if needed
    if api_key is None:
        from gravy_jobs_gui import CLAUDE_API_KEY
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
        print(f"Calling Claude API with model: {model}...")
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            print(f"API error: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
        result = response.json()
        print("API call successful!")
        
        # Extract content from response
        if "content" in result and len(result["content"]) > 0:
            for content_block in result["content"]:
                if content_block["type"] == "text":
                    text_response = content_block["text"]
                    print(f"Received response from Claude: {text_response[:500]}...")
                    return text_response
        else:
            print(f"Unexpected response format: {result}")
        
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

def analyze_jobs_with_claude(jobs, api_key, config=CLAUDE_API_CONFIG):
    """Analyze jobs using Claude API"""
    if not api_key:
        print("Error: Claude API key not provided")
        return jobs
    
    print(f"Analyzing {len(jobs)} jobs with Claude...")
    results = []
    batch_size = 3  # Limit to 3 jobs per batch to avoid timeout
    
    # Process jobs in batches
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(jobs) + batch_size - 1)//batch_size} ({len(batch)} jobs)")
        
        # Prepare prompt for this batch
        prompt = prepare_prompt_for_claude(batch)
        
        # Call Claude API
        response = call_claude_api(
            prompt=prompt,
            api_key=api_key,
            model=config["model"],
            temperature=config["temperature"]
        )
        
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

def generate_gravy_html_report(jobs, output_file='claude_gravy_jobs.html'):
    """Generate an HTML report of the top gravy jobs"""
    if not jobs:
        return "No jobs to display"
    
    # Group jobs by category
    amazing_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Amazing']
    great_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Great']
    good_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Good']
    decent_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Decent']
    challenging_jobs = [j for j in jobs if j.get('gravy_category', '') == 'Challenging']
    uncategorized = [j for j in jobs if j.get('gravy_category', '') == 'Uncategorized']
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Claude-Analyzed Gravy Jobs</title>
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
            <h1>🍯 Claude-Analyzed Gravy Jobs 🍯</h1>
            
            <div class="explanation">
                <p><strong>What makes a job "gravy"?</strong> Claude has deeply analyzed these jobs based on:</p>
                <ul>
                    <li>How easy/entry-level the job appears to be</li>
                    <li>Salary information (higher pay = more gravy)</li>
                    <li>Remote work options</li>
                    <li>Beginner-friendly technologies (HTML/CSS, WordPress, etc.)</li>
                    <li>Red flags (advanced skills, senior positions)</li>
                </ul>
                <p>Each job has been assigned a "Gravy Score" from 0-100 by Claude. The higher the score, the more this job is considered easy, well-paying, and beginner-friendly.</p>
                <p>The categories are:</p>
                <ul>
                    <li>🔥 <strong>Amazing</strong> (70-100): Super easy + great pay</li>
                    <li>💎 <strong>Great</strong> (50-69): Very good beginner opportunities</li>
                    <li>👍 <strong>Good</strong> (30-49): Solid entry-level jobs</li>
                    <li>🙂 <strong>Decent</strong> (10-29): Worth considering</li>
                    <li>⚠️ <strong>Challenging</strong> (0-9): May be more difficult for beginners</li>
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
    
    # Add uncategorized jobs section if any
    if uncategorized:
        html += f"""
            <h2>Uncategorized Jobs ({len(uncategorized)})</h2>
            <div class="job-list">
        """
        
        for job in uncategorized:
            html += generate_job_card(job, 'decent')  # Use decent styling as default
            
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
    gravy_score = job.get('gravy_score', 0)
    gravy_category = job.get('gravy_category', 'Uncategorized')
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

def save_jobs_for_claude(jobs, output_file='jobs_for_claude.json'):
    """Save jobs in a format ready for Claude API processing"""
    jobs_simplified = []
    
    for job in jobs:
        # Extract only the needed fields to reduce file size
        simplified = {
            'id': jobs.index(job),
            'title': job.get('title', 'No Title'),
            'company': job.get('company', 'Unknown') if 'company' in job else 'Unknown',
            'source': job.get('source', 'Unknown'),
            'description': job.get('description', 'No description available'),
            'salary': job.get('salary', None),
            'url': job.get('url', '#')
        }
        jobs_simplified.append(simplified)
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(jobs_simplified, f, indent=2)
    
    return output_file

def load_analyzed_jobs(input_file):
    """Load jobs that have been analyzed by Claude"""
    try:
        with open(input_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading analyzed jobs: {e}")
        return None

def main():
    """Run the job scraper and prepare for Claude analysis"""
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Analyze jobs with Claude API')
    parser.add_argument('--api-key', type=str, help='Claude API key')
    parser.add_argument('--analyze', action='store_true', help='Run analysis with Claude API')
    parser.add_argument('--use-existing', action='store_true', help='Use existing jobs data')
    parser.add_argument('--input-file', type=str, default='top_jobs.json', help='Input file with jobs data')
    parser.add_argument('--output-file', type=str, default='claude_gravy_jobs.html', help='Output HTML file')
    parser.add_argument('--prepare-only', action='store_true', help='Only prepare jobs for analysis without calling API')
    
    args = parser.parse_args()
    
    print("=== Claude-Powered Job Analysis ===")
    
    jobs = []
    
    # Check if we should use existing data
    if args.use_existing:
        if os.path.exists(args.input_file):
            print(f"Loading existing jobs from {args.input_file}...")
            try:
                with open(args.input_file, 'r') as f:
                    jobs = json.load(f)
                print(f"Loaded {len(jobs)} jobs")
            except json.JSONDecodeError:
                print(f"Error: {args.input_file} is not valid JSON")
                return
        else:
            print(f"Error: Input file {args.input_file} not found")
            return
    else:
        # Create the scraper
        scraper = JobScraper(CONFIG)
        
        # Run the scraping
        print("Scraping for jobs... (this may take a few minutes)")
        new_jobs = scraper.scrape_all_sources()
        
        if new_jobs:
            print(f"\nFound {len(new_jobs)} matching jobs!")
            
            # Combine with previous jobs if any
            all_jobs = scraper.previous_jobs + new_jobs
            scraper.all_jobs = all_jobs
            
            # Save all jobs
            print("Saving all jobs to file...")
            scraper.save_jobs()
            
            # Rank jobs
            print("Ranking jobs by relevance...")
            jobs = scraper.rank_top_jobs(limit=100)  # Limit to 100 for API efficiency
            print(f"Selected top {len(jobs)} jobs for analysis")
        else:
            print("\nNo matching jobs found. Try adjusting your keywords.")
            return
    
    # Check if any jobs to process
    if not jobs:
        print("No jobs to analyze")
        return
    
    # If only preparing for Claude API
    if args.prepare_only:
        output_file = save_jobs_for_claude(jobs)
        print(f"\nJobs prepared for Claude analysis and saved to {output_file}")
        print("\nTo analyze these jobs:")
        print("1. Get a Claude API key from https://console.anthropic.com/")
        print("2. Run this script with the --analyze flag and your API key:")
        print(f"   python {sys.argv[0]} --analyze --api-key=YOUR_API_KEY --use-existing --input-file={output_file}")
        return
    
    # If analyzing with Claude API
    if args.analyze:
        if not args.api_key:
            print("\nError: Claude API key required for analysis")
            print("Get an API key from https://console.anthropic.com/")
            print(f"Then run: python {sys.argv[0]} --analyze --api-key=YOUR_API_KEY")
            return
        
        # Analyze jobs with Claude
        analyzed_jobs = analyze_jobs_with_claude(jobs, args.api_key)
        
        # Generate HTML report
        output_file = generate_gravy_html_report(analyzed_jobs, args.output_file)
        print(f"\nAnalysis complete! HTML report generated at {os.path.abspath(output_file)}")
        print(f"Open it in your browser or run: python serve_jobs.py --file={output_file}")
    else:
        print("\nTo analyze these jobs with Claude API, run with the --analyze flag and your API key")
        print(f"Example: python {sys.argv[0]} --analyze --api-key=YOUR_API_KEY")
        
        # If no API key but we want to generate HTML anyway (for testing)
        output_file = save_jobs_for_claude(jobs)
        print(f"\nJobs prepared for Claude analysis and saved to {output_file}")

if __name__ == "__main__":
    main()