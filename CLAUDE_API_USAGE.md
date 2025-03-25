# Using Claude API for Real-Time Job Analysis

This guide explains how to use the Claude API to perform real-time analysis of job listings, determining which jobs are the most "gravy" (easy + well-paying + beginner-friendly).

## Prerequisites

1. A Claude API key from Anthropic
   - Sign up at https://console.anthropic.com/
   - Create an API key in your account settings

2. Python 3.6+ with the following packages:
   - requests
   - beautifulsoup4

## Quick Start

1. First, prepare the jobs for analysis:
   ```bash
   python real_claude_analysis.py --prepare-only
   ```
   This will scrape job listings and save them to `jobs_for_claude.json`

2. Run the analysis with your Claude API key:
   ```bash
   python real_claude_analysis.py --analyze --api-key=YOUR_API_KEY --use-existing --input-file=jobs_for_claude.json
   ```

3. View the results:
   ```bash
   python serve_jobs.py --file=claude_gravy_jobs.html
   ```

## How It Works

1. **Job Scraping**: The script first collects jobs from various platforms

2. **Claude Analysis**: Each job is sent to Claude with a carefully crafted prompt asking it to:
   - Determine a "Gravy Score" from 0-100
   - Provide 3-5 bullet points explaining its reasoning
   - Categorize the job (Amazing, Great, Good, Decent, Challenging)

3. **HTML Generation**: Results are compiled into an interactive webpage 

## Command Line Options

- `--prepare-only`: Just scrape jobs and prepare them for Claude analysis
- `--analyze`: Run the analysis with Claude API
- `--api-key=KEY`: Your Claude API key
- `--use-existing`: Use existing job data instead of scraping new jobs
- `--input-file=FILE`: Specify an input JSON file with job data
- `--output-file=FILE`: Specify the output HTML file name

## Debugging

If you encounter issues with the Claude API:

1. Check your API key is valid and has sufficient quota
2. Inspect the `job_scraper.log` file for API error messages
3. Try with a smaller batch of jobs (edit the `max_jobs_per_batch` value)

## Example Output

The script generates an HTML file with jobs organized by category:

- 🔥 **Amazing** (70-100 points): Super easy + great pay
- 💎 **Great** (50-69 points): Very good beginner opportunities
- 👍 **Good** (30-49 points): Solid entry-level jobs
- 🙂 **Decent** (10-29 points): Worth considering
- ⚠️ **Challenging** (0-9 points): May be difficult for beginners

Each job card includes:
- Job title, company and source
- Gravy score and category
- Claude's detailed reasoning (3-5 bullet points)
- Tags (Remote, HTML/CSS, Entry-Level, etc.)
- Direct application link

## API Usage and Costs

- The Claude API is not free - Anthropic charges per token
- Analysis of 100 jobs will typically cost between $0.10-$0.50
- Reduce costs by:
  - Limiting the number of jobs analyzed
  - Using a smaller Claude model (edit the `model` parameter)
  - Removing unnecessary job description text

## Customizing the Analysis

You can customize how Claude analyzes jobs by editing the prompt in the `prepare_prompt_for_claude` function.