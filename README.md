# Gravy Jobs

Gravy Jobs is an automated job scraper designed to help you find suitable job opportunities with minimal effort. It searches various job platforms for listings that match your specified criteria, aggregates the results, and presents them in an easily digestible format.

## Features

### Job Scraping
- **Multi-platform Scraping**: Searches Indeed, RemoteOK, LinkedIn, Craigslist, and Freelancer
- **Intelligent Filtering**: Filter jobs based on your specified keywords and exclude unwanted ones
- **Job Ranking**: Scores and ranks jobs based on relevance to your interests
- **Email Notifications**: Sends email notifications for new job matches

### General Website Scraping (Premium)
- **Intelligent Scraping**: Scrape any website with Claude-powered parameter generation
- **Multiple Output Formats**: Save results as JSON, CSV, or HTML reports
- **Content Extraction**: Automatically extracts titles, content, dates, and more
- **Custom Crawling**: Set crawl depth and configure selectors for precise data extraction

### Advanced Technologies
- **VPN Rotation**: Automatically rotates proxies/VPNs to avoid getting blocked
- **Browser Fingerprinting**: Mimics real browser behavior with consistent fingerprints
- **Claude AI Integration**: Customizes search parameters based on your plain language queries
- **Commercial Proxy Support**: Integrates with premium proxy services for reliable scraping
- **License Management**: Unlocks premium features with license keys

### User Interfaces
- **Command Line**: Powerful CLI with extensive options
- **Graphical Interface**: Easy-to-use GUI for all features
- **Windows Support**: Seamless operation on Windows systems

## VPN Auto-Switching

Gravy Jobs includes advanced VPN and proxy rotation capabilities to avoid being blocked by job sites:

- Rotates browser fingerprints with IP addresses to appear as different users
- Integrates with premium proxy services (Bright Data, Oxylabs, SmartProxy, etc.)
- Automatically detects and handles 403/429 rate-limit errors
- Falls back to cached data when necessary

## Claude AI Integration

The Claude AI integration allows you to customize job searches using natural language:

```bash
./run_scraper.sh --query "Find DevOps jobs in Seattle that require Kubernetes experience"
```

Claude will analyze your query and generate appropriate search parameters including:
- Keywords to include
- Terms to exclude
- Locations to search in
- Technology requirements

## Setup & Usage

### Basic Setup

1. Install required packages:
   ```
   pip install requests beautifulsoup4 requests[socks]
   ```

2. Configure email (optional):
   ```
   export EMAIL_PASSWORD='your-email-app-password'
   ```

3. Run the scraper (choose one method):
   ```
   # Option 1: Shell script (recommended for most users)
   chmod +x run_scraper.sh
   ./run_scraper.sh --query "Find remote developer jobs"
   
   # Option 2: Job scraper directly
   python job_scraper.py --query "Find remote developer jobs"
   
   # Option 3: Graphical interface (most user-friendly)
   python gravy_scraper_gui.py
   
   # Option 4: General website scraper (any website)
   python general_scraper.py --query "Electric vehicle charging stations" --format html
   
   # Option 5: Test all features first
   python test_features.py --all
   ```

### Graphical Interface

For easier usage, you can run the graphical interface:

```
python gravy_scraper_gui.py
```

The GUI provides access to all features with an intuitive interface:
- Job scraping with Claude-powered search customization
- General website scraping with custom parameters
- Settings management for proxies, licenses, and more
- Integrated results viewer

### Job Scraping

Run the job scraper with a custom query:

```
./run_scraper.sh --query "Find entry level data science jobs in remote companies"
```

Or use the Python script directly:

```
python job_scraper.py --query "DevOps engineer positions with Kubernetes experience" --location "Seattle, WA"
```

### General Website Scraping (Premium)

Use the general scraper to extract data from any website:

```
python general_scraper.py --query "Electric vehicle charging stations in Seattle" --format html
```

Options include:
- `--site-type`: Focus on specific types of websites (news, blogs, government, etc.)
- `--format`: Output format (json, csv, html)
- `--max-pages`: Maximum pages to scrape per site

### Premium Features

To enable premium features like commercial proxies and Claude integration:

1. Set your license key:
   ```
   ./run_scraper.sh --license-key YOUR_LICENSE_KEY
   ```

2. Configure Claude API:
   ```
   ./run_scraper.sh --configure-claude YOUR_CLAUDE_API_KEY
   ```

3. Set up a commercial proxy service:
   ```
   ./run_scraper.sh --setup-proxy brightdata
   ```

### Advanced Options

- Enable browser fingerprinting:
  ```
  ./run_scraper.sh --fingerprint-on
  ```

- Run in test mode (no actual scraping):
  ```
  ./run_scraper.sh --test
  ```

- Run headless (no visible console):
  ```
  ./run_scraper.sh --headless
  ```
  
- Test all features:
  ```
  python test_features.py --all
  ```

## Configuration

Edit the CONFIG dictionary in `job_scraper.py` to customize:

- Keywords to search for
- Terms to exclude
- Job sources to scrape
- Email settings
- Check interval

For advanced proxy and fingerprinting settings, edit `vpn_config.json`.

## License & Premium Features

Gravy Jobs offers a tiered licensing model:

### Free License
- Basic job scraping
- Local proxy support
- Email notifications
- Command-line interface

### Premium License
- All free features plus:
- Commercial proxy integration (6 premium services)
- Advanced browser fingerprinting
- Claude AI integration for intelligent parameters
- General website scraping with AI assistance
- Multiple output formats (JSON, CSV, HTML)
- Graphical user interface
- Priority support

### Enterprise License
- All premium features plus:
- Custom integrations
- Unlimited scraping volume
- Advanced analytics
- Dedicated support

To purchase a license, contact us at licensing@gravyjobs.com or visit our website.

### Test License

For testing purposes, you can use the following test license key:
```
TEST-GRAVY-JOBS-12345
```

This will enable all premium features for a 30-day trial period.