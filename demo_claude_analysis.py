#!/usr/bin/env python3

import sys
import os
import json
import logging
from datetime import datetime
import argparse

# Add the current directory to the path so we can import the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from real analysis script
from real_claude_analysis import generate_gravy_html_report, extract_job_details

def load_sample_analysis():
    """Load sample Claude analysis"""
    sample_jobs = [
        {
            'title': 'Junior Developer - HTML/CSS',
            'company': 'WebCraft Solutions',
            'source': 'Freelancer',
            'description': 'Looking for a junior developer to help with simple website designs. No prior experience necessary, just a good understanding of HTML/CSS and basic JavaScript. Remote work available.',
            'salary': '$25-30/hour',
            'url': 'https://example.com/job1',
            'gravy_score': 85,
            'gravy_category': 'Amazing',
            'gravy_reasoning': [
                'Entry-level position explicitly mentioned in title (Junior Developer)',
                'Remote work available as mentioned in description',
                'Only requires basic HTML/CSS knowledge and some JavaScript',
                'Clearly states "no prior experience necessary"',
                'Good salary range offered ($25-30/hour)'
            ]
        },
        {
            'title': 'WordPress Developer for Small Business',
            'company': 'Creative Agency',
            'source': 'Craigslist (newyork)',
            'description': 'We need a WordPress developer to help with simple designs and updates to our client websites. Flexible hours, partial remote work available.',
            'salary': '$22/hour',
            'url': 'https://example.com/job2',
            'gravy_score': 67,
            'gravy_category': 'Great',
            'gravy_reasoning': [
                'WordPress-focused role which is generally beginner-friendly',
                'Mentions "simple designs" in the description',
                'Offers flexible hours and partial remote work',
                'No advanced frameworks or technologies mentioned',
                'Pays slightly above average for entry-level ($22/hour)'
            ]
        },
        {
            'title': 'Entry-Level Web Developer',
            'company': 'Tech Solutions Inc.',
            'source': 'Indeed',
            'description': 'We are looking for an entry-level web developer to join our team. Knowledge of HTML/CSS required, with some JavaScript experience preferred.',
            'url': 'https://example.com/job3',
            'gravy_score': 42,
            'gravy_category': 'Good',
            'gravy_reasoning': [
                'Position is labeled as entry-level',
                'Requires knowledge of HTML/CSS which is accessible to beginners',
                'Some JavaScript knowledge required which adds complexity',
                'No mention of salary/compensation',
                'Office-based with no remote options mentioned'
            ]
        },
        {
            'title': 'Beginner Friendly Frontend Developer',
            'company': 'StartupXYZ',
            'source': 'LinkedIn',
            'description': 'Looking for a frontend developer with 1-2 years of experience in React. Must be able to work with APIs and implement responsive designs. Some remote work possible.',
            'url': 'https://example.com/job4',
            'gravy_score': 25,
            'gravy_category': 'Decent',
            'gravy_reasoning': [
                'Mentions "beginner friendly" but requires 1-2 years experience',
                'Technology stack includes React which has a steeper learning curve',
                'Salary information not provided',
                'Some complex requirements like API integration',
                'Includes some remote work options'
            ]
        },
        {
            'title': 'Software Developer - React/Node.js',
            'company': 'Enterprise Solutions',
            'source': 'RemoteOK',
            'description': 'Seeking an experienced software developer with 3+ years of experience in React, Node.js, and AWS. Must be able to architect solutions and work in a fast-paced environment.',
            'salary': '$85,000-105,000',
            'url': 'https://example.com/job5',
            'gravy_score': 5,
            'gravy_category': 'Challenging',
            'gravy_reasoning': [
                'Position requires 3+ years of experience',
                'Advanced technologies required (React, Node.js, AWS)',
                'Mentions "fast-paced environment" suggesting high pressure',
                'Responsibilities include system architecture decisions',
                'Does offer good compensation but not suitable for true beginners'
            ]
        }
    ]
    
    return sample_jobs

def append_real_jobs_with_mock_analysis(real_jobs, sample_analysis):
    """Append real jobs with mock analysis based on sample patterns"""
    analyzed_jobs = []
    
    # Create a map of sample jobs by category for reference
    sample_by_category = {
        'Amazing': next((j for j in sample_analysis if j['gravy_category'] == 'Amazing'), None),
        'Great': next((j for j in sample_analysis if j['gravy_category'] == 'Great'), None),
        'Good': next((j for j in sample_analysis if j['gravy_category'] == 'Good'), None),
        'Decent': next((j for j in sample_analysis if j['gravy_category'] == 'Decent'), None),
        'Challenging': next((j for j in sample_analysis if j['gravy_category'] == 'Challenging'), None)
    }
    
    for i, job in enumerate(real_jobs):
        # Determine a category based on job properties
        category = 'Decent'  # Default
        score = 25  # Default
        
        title = job.get('title', '').lower()
        desc = job.get('description', '').lower()
        has_salary = bool(job.get('salary', ''))
        
        # Check for entry-level indicators
        if any(term in title for term in ['junior', 'entry', 'beginner']):
            if has_salary and ('remote' in title or 'remote' in desc):
                category = 'Amazing'
                score = 80 + (i % 15)  # Vary score slightly
            else:
                category = 'Great'
                score = 55 + (i % 15)
        
        # Check for WordPress or HTML/CSS
        elif 'wordpress' in title or ('html' in title and 'css' in title):
            if has_salary:
                category = 'Great'
                score = 50 + (i % 15)
            else:
                category = 'Good'
                score = 40 + (i % 10)
        
        # Check for potentially harder jobs
        elif any(term in title for term in ['senior', 'lead', 'architect']):
            category = 'Challenging'
            score = 5 + (i % 5)
        
        # Get reasoning from sample based on assigned category
        sample = sample_by_category.get(category)
        reasoning = sample['gravy_reasoning'] if sample else ["No detailed analysis available"]
        
        # Create analyzed job
        analyzed_job = job.copy()
        analyzed_job['gravy_score'] = score
        analyzed_job['gravy_category'] = category
        analyzed_job['gravy_reasoning'] = reasoning
        
        analyzed_jobs.append(analyzed_job)
    
    return analyzed_jobs

def main():
    """Run a demonstration of Claude analysis"""
    parser = argparse.ArgumentParser(description='Demonstrate Claude job analysis')
    parser.add_argument('--input-file', type=str, default='jobs_for_claude.json', help='Input file with real jobs data')
    parser.add_argument('--output-file', type=str, default='demo_claude_analysis.html', help='Output HTML file')
    parser.add_argument('--sample-only', action='store_true', help='Only use sample jobs (no real data)')
    
    args = parser.parse_args()
    
    print("=== Claude Job Analysis Demo ===")
    print("This demonstration simulates how Claude would analyze jobs for 'graviness'")
    
    # Load sample analysis
    sample_analysis = load_sample_analysis()
    
    if args.sample_only:
        # Use only sample jobs
        print("Using sample jobs only...")
        analyzed_jobs = sample_analysis
    else:
        # Load real jobs and append with mock analysis
        try:
            if os.path.exists(args.input_file):
                print(f"Loading real jobs from {args.input_file}...")
                with open(args.input_file, 'r') as f:
                    real_jobs = json.load(f)
                
                # Add sample jobs at the beginning
                all_jobs = sample_analysis + real_jobs
                
                # Apply mock analysis to combined list
                analyzed_jobs = append_real_jobs_with_mock_analysis(all_jobs, sample_analysis)
                
                print(f"Analyzed {len(analyzed_jobs)} jobs")
            else:
                print(f"Input file {args.input_file} not found, using samples only")
                analyzed_jobs = sample_analysis
        except Exception as e:
            print(f"Error loading real jobs: {e}")
            analyzed_jobs = sample_analysis
    
    # Generate HTML report
    output_file = generate_gravy_html_report(analyzed_jobs, args.output_file)
    print(f"\nDemonstration complete! HTML report generated at {os.path.abspath(output_file)}")
    print(f"View it in your browser: python serve_jobs.py --file={output_file}")
    print("\nNOTE: This is a demonstration only. For actual Claude analysis, use real_claude_analysis.py with an API key")

if __name__ == "__main__":
    main()