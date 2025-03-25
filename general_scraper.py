#!/usr/bin/env python3

"""
General Website Scraper with Claude Integration
This module provides a flexible website scraping capability with
intelligent parameter generation using Claude AI.
"""

import os
import sys
import time
import json
import logging
import argparse
import datetime
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# Import the VPN Manager for proxy rotation
try:
    from vpn_manager import VPNManager, generate_search_params_with_claude
    VPN_AVAILABLE = True
except ImportError:
    VPN_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='general_scraper.log'
)
logger = logging.getLogger('general_scraper')

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class GeneralScraper:
    """
    General purpose website scraper with Claude AI integration for
    intelligent parameter generation and VPN rotation support.
    """
    
    def __init__(self, query=None, site_type=None, output_format="json", max_pages=10):
        """
        Initialize the scraper
        
        Args:
            query: What to look for (processed by Claude)
            site_type: Type of websites to target (e.g. blogs, ecommerce, news)
            output_format: Format for scraped data (json, csv, html)
            max_pages: Maximum number of pages to scrape per site
        """
        self.query = query
        self.site_type = site_type
        self.output_format = output_format.lower()
        self.max_pages = max_pages
        
        # Results storage
        self.results = []
        self.stats = {
            "pages_scraped": 0,
            "successful_sites": 0,
            "failed_sites": 0,
            "total_items": 0,
            "start_time": time.time()
        }
        
        # Set up VPN Manager if available
        self.vpn_manager = None
        if VPN_AVAILABLE:
            try:
                self.vpn_manager = VPNManager()
                logger.info("VPN Manager initialized successfully")
                
                # Verify license status for premium features
                license_status = self.vpn_manager.get_license_status()
                logger.info(f"License status: {'Valid' if license_status.get('valid', False) else 'Invalid or missing'}")
                
                # Check if general scraping is allowed with this license
                if "general_scraping" not in license_status.get("enabled_features", []):
                    logger.warning("General scraping requires a premium license")
                    print("⚠️ General website scraping requires a premium license")
                    print("   Use --license-key to set your license key")
                    
                # Process custom search query if provided
                if query:
                    logger.info(f"Processing custom search query: {query}")
                    self.scrape_params = self._generate_scrape_parameters()
                    if self.scrape_params:
                        logger.info(f"Generated scrape parameters: {self.scrape_params}")
                
            except Exception as e:
                logger.error(f"Error initializing VPN Manager: {e}")
                self.vpn_manager = None
        
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
        
        # Create output directories
        os.makedirs("scraped_data", exist_ok=True)
    
    def _generate_scrape_parameters(self):
        """
        Generate scraping parameters using Claude AI
        
        Returns:
            Dictionary with scraping parameters
        """
        if not self.vpn_manager or not self.query:
            return None
        
        # Check license status for Claude integration
        license_status = self.vpn_manager.get_license_status()
        allowed_features = license_status.get("enabled_features", [])
        
        if "claude_integration" not in allowed_features or "general_scraping" not in allowed_features:
            logger.warning("Claude integration for general scraping requires a premium license")
            return {
                "target_sites": [],
                "data_selectors": {
                    "title": "h1, h2",
                    "content": "p, article, .content",
                    "date": ".date, .published, time",
                    "links": "a[href]"
                },
                "excluded_domains": [
                    "facebook.com", "twitter.com", "instagram.com",
                    "youtube.com", "tiktok.com"
                ],
                "search_terms": [self.query.lower()],
                "max_depth": 2
            }
        
        # Prepare prompt for Claude based on query and site type
        prompt = f"I need to scrape websites to find information about: {self.query}"
        
        if self.site_type:
            prompt += f"\nThe type of websites I should focus on: {self.site_type}"
        
        prompt += "\nPlease provide a well-structured plan for web scraping, including:"
        prompt += "\n1. Specific websites to target"
        prompt += "\n2. CSS selectors for extracting relevant data (title, content, date, links)"
        prompt += "\n3. Domains to exclude"
        prompt += "\n4. Specific search terms related to my query"
        prompt += "\n5. How deep to crawl (max depth 1-3)"
        
        # Get parameters from Claude
        try:
            claude_params = self.vpn_manager.generate_search_parameters(prompt)
            
            # Structure the response
            params = {
                "target_sites": claude_params.get("target_sites", []),
                "data_selectors": claude_params.get("data_selectors", {
                    "title": "h1, h2",
                    "content": "p, article, .content",
                    "date": ".date, .published, time",
                    "links": "a[href]"
                }),
                "excluded_domains": claude_params.get("excluded_domains", [
                    "facebook.com", "twitter.com", "instagram.com"
                ]),
                "search_terms": claude_params.get("search_terms", [self.query.lower()]),
                "max_depth": claude_params.get("max_depth", 2)
            }
            
            return params
            
        except Exception as e:
            logger.error(f"Error generating scrape parameters with Claude: {e}")
            return None
    
    def scrape_website(self, url, max_pages=None, depth=0):
        """
        Scrape a specific website
        
        Args:
            url: Website URL to scrape
            max_pages: Maximum pages to scrape (overrides self.max_pages)
            depth: Current recursion depth
            
        Returns:
            List of scraped items
        """
        if max_pages is None:
            max_pages = self.max_pages
        
        # Parse URL to get domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check if domain is excluded
        if self.scrape_params and "excluded_domains" in self.scrape_params:
            for excluded in self.scrape_params["excluded_domains"]:
                if excluded in domain:
                    logger.info(f"Skipping excluded domain: {domain}")
                    return []
        
        logger.info(f"Scraping website: {url}")
        
        # Check max depth
        max_depth = self.scrape_params.get("max_depth", 2) if self.scrape_params else 2
        if depth > max_depth:
            logger.info(f"Reached maximum depth ({max_depth})")
            return []
        
        # Get page content using VPN rotation if available
        content = None
        if self.vpn_manager:
            try:
                content = self.vpn_manager.get(url)
            except Exception as e:
                logger.error(f"Error fetching {url} with VPN Manager: {e}")
        
        # Fallback to direct request
        if not content:
            try:
                import requests
                response = requests.get(url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    content = response.text
                else:
                    logger.error(f"Failed to fetch {url}: Status {response.status_code}")
                    self.stats["failed_sites"] += 1
                    return []
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                self.stats["failed_sites"] += 1
                return []
        
        # Parse the HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Get selectors from parameters
        selectors = self.scrape_params.get("data_selectors", {}) if self.scrape_params else {}
        title_selector = selectors.get("title", "h1, h2")
        content_selector = selectors.get("content", "p, article, .content")
        date_selector = selectors.get("date", ".date, .published, time")
        links_selector = selectors.get("links", "a[href]")
        
        # Extract data
        scraped_items = []
        
        # Get page title
        page_title = soup.title.text.strip() if soup.title else "Unknown Title"
        
        # Extract main titles
        titles = soup.select(title_selector)
        
        # Extract main content
        content_elements = soup.select(content_selector)
        main_content = "\n".join([el.text.strip() for el in content_elements]) if content_elements else ""
        
        # Extract date if available
        date_element = soup.select_one(date_selector)
        date = date_element.text.strip() if date_element else datetime.datetime.now().isoformat()
        
        # Check if the content matches our search terms
        is_relevant = False
        if self.scrape_params and "search_terms" in self.scrape_params:
            search_terms = self.scrape_params["search_terms"]
            page_text = soup.get_text().lower()
            
            # Check if any search term is in the page text
            for term in search_terms:
                if term.lower() in page_text:
                    is_relevant = True
                    break
        else:
            # If no search terms defined, consider all content relevant
            is_relevant = True
        
        # Only save relevant content
        if is_relevant:
            item = {
                "url": url,
                "title": page_title,
                "date": date,
                "content": main_content[:1000] + "..." if len(main_content) > 1000 else main_content,
                "scraped_at": datetime.datetime.now().isoformat()
            }
            
            # Add individual titles if found
            if titles:
                item["titles"] = [t.text.strip() for t in titles]
            
            scraped_items.append(item)
            self.results.append(item)
            self.stats["total_items"] += 1
        
        # Increment pages scraped
        self.stats["pages_scraped"] += 1
        
        # Extract links for further crawling if under max pages and depth
        if self.stats["pages_scraped"] < max_pages and depth < max_depth:
            links = soup.select(links_selector)
            internal_links = []
            
            for link in links:
                href = link.get('href')
                if href:
                    # Make absolute URL
                    full_url = urljoin(url, href)
                    
                    # Only follow links to the same domain
                    if urlparse(full_url).netloc == domain:
                        internal_links.append(full_url)
            
            # Limit to a reasonable number of links and randomize
            if internal_links:
                random.shuffle(internal_links)
                internal_links = internal_links[:min(5, max_pages - self.stats["pages_scraped"])]
                
                # Crawl internal links
                for link in internal_links:
                    # Add random delay to avoid overloading the server
                    time.sleep(random.uniform(1, 3))
                    sub_items = self.scrape_website(link, max_pages, depth + 1)
                    scraped_items.extend(sub_items)
        
        if depth == 0:
            self.stats["successful_sites"] += 1
            
        return scraped_items
    
    def scrape_from_parameters(self):
        """
        Scrape websites based on generated parameters
        
        Returns:
            Number of items scraped
        """
        if not self.scrape_params:
            logger.error("No scrape parameters available")
            return 0
        
        # Check if target sites are specified
        target_sites = self.scrape_params.get("target_sites", [])
        
        if not target_sites:
            logger.warning("No specific target sites were generated. Using default search.")
            # Generate default sites based on query
            if self.query:
                from urllib.parse import quote_plus
                search_query = quote_plus(self.query)
                target_sites = [
                    f"https://www.google.com/search?q={search_query}",
                    f"https://duckduckgo.com/?q={search_query}",
                    f"https://www.bing.com/search?q={search_query}"
                ]
        
        # License check for premium features
        license_status = self.vpn_manager.get_license_status() if self.vpn_manager else {"enabled_features": []}
        allowed_features = license_status.get("enabled_features", [])
        
        # Limit number of sites for non-premium users
        if "general_scraping" not in allowed_features and len(target_sites) > 1:
            logger.warning("Limited to one site for non-premium license")
            target_sites = target_sites[:1]
        
        # Scrape each target site
        for url in target_sites:
            try:
                # Add random delay between sites
                if target_sites.index(url) > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"Waiting {delay:.2f}s before next site")
                    time.sleep(delay)
                
                # Scrape the website
                items = self.scrape_website(url)
                logger.info(f"Scraped {len(items)} items from {url}")
                
                # Rotate proxy occasionally
                if self.vpn_manager and random.random() < 0.3:  # 30% chance
                    logger.info("Rotating proxy/fingerprint")
                    self.vpn_manager.rotate_proxy()
                    
                    # Also rotate fingerprint sometimes
                    if random.random() < 0.5:  # 50% chance when rotating proxy
                        self.vpn_manager.rotate_fingerprint()
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                self.stats["failed_sites"] += 1
        
        return self.stats["total_items"]
    
    def save_results(self, filename=None):
        """
        Save scraped results to file
        
        Args:
            filename: Custom filename (without extension)
            
        Returns:
            Path to the saved file
        """
        if not self.results:
            logger.warning("No results to save")
            return None
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            query_part = "_".join(self.query.split()[:3]) if self.query else "scrape"
            filename = f"scraped_{query_part}_{timestamp}"
        
        # Ensure filename is safe
        filename = "".join(c if c.isalnum() or c in "-_" else "_" for c in filename)
        
        # Format output based on specified format
        if self.output_format == "json":
            output_file = os.path.join("scraped_data", f"{filename}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": self.query,
                    "stats": {
                        **self.stats,
                        "duration_seconds": time.time() - self.stats["start_time"]
                    },
                    "results": self.results
                }, f, indent=2, ensure_ascii=False)
            
        elif self.output_format == "csv":
            output_file = os.path.join("scraped_data", f"{filename}.csv")
            import csv
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                # Get all possible fields from results
                fieldnames = set()
                for item in self.results:
                    for key in item.keys():
                        fieldnames.add(key)
                
                writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
                writer.writeheader()
                
                for item in self.results:
                    # Handle lists by joining them
                    row = {}
                    for key, value in item.items():
                        if isinstance(value, list):
                            row[key] = ", ".join(str(v) for v in value)
                        else:
                            row[key] = value
                    writer.writerow(row)
                    
        elif self.output_format == "html":
            output_file = os.path.join("scraped_data", f"{filename}.html")
            
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Scraped Results: {self.query}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                    .container {{ max-width: 1200px; margin: 0 auto; }}
                    .header {{ background-color: #333; color: white; padding: 15px; border-radius: 5px; }}
                    .stats {{ background-color: #eee; padding: 10px; border-radius: 5px; margin: 15px 0; }}
                    .item {{ background-color: white; margin: 15px 0; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    .item-title {{ color: #2c3e50; margin-top: 0; }}
                    .item-meta {{ color: #7f8c8d; font-size: 0.9em; }}
                    .item-content {{ margin-top: 10px; }}
                    .item-url {{ word-break: break-all; color: #3498db; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Scraped Results: {self.query}</h1>
                    </div>
                    
                    <div class="stats">
                        <h2>Statistics</h2>
                        <p>Query: {self.query}</p>
                        <p>Pages Scraped: {self.stats['pages_scraped']}</p>
                        <p>Successful Sites: {self.stats['successful_sites']}</p>
                        <p>Failed Sites: {self.stats['failed_sites']}</p>
                        <p>Total Items: {self.stats['total_items']}</p>
                        <p>Duration: {(time.time() - self.stats['start_time']):.2f} seconds</p>
                    </div>
                    
                    <h2>Results ({len(self.results)} items)</h2>
            """
            
            for item in self.results:
                html += f"""
                    <div class="item">
                        <h3 class="item-title">{item.get('title', 'No Title')}</h3>
                        <div class="item-meta">
                            <p>Date: {item.get('date', 'Unknown Date')}</p>
                            <p>Scraped: {item.get('scraped_at', '')}</p>
                            <p>URL: <a href="{item.get('url', '#')}" class="item-url">{item.get('url', 'No URL')}</a></p>
                        </div>
                """
                
                # Add titles if available
                if 'titles' in item and item['titles']:
                    html += "<div class='item-titles'><h4>Extracted Titles:</h4><ul>"
                    for title in item['titles']:
                        html += f"<li>{title}</li>"
                    html += "</ul></div>"
                
                # Add content
                html += f"""
                        <div class="item-content">
                            <h4>Content:</h4>
                            <p>{item.get('content', 'No content')}</p>
                        </div>
                    </div>
                """
            
            html += """
                </div>
            </body>
            </html>
            """
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
        
        else:
            logger.error(f"Unsupported output format: {self.output_format}")
            return None
        
        logger.info(f"Results saved to {output_file}")
        return output_file
    
    def run(self):
        """
        Run the scraper
        
        Returns:
            Path to the saved results file
        """
        logger.info(f"Starting general scraper with query: {self.query}")
        
        # Check for premium license
        if self.vpn_manager:
            license_status = self.vpn_manager.get_license_status()
            if "general_scraping" not in license_status.get("enabled_features", []):
                logger.warning("General scraping requires a premium license. Limited functionality available.")
                print("⚠️ General website scraping requires a premium license for full functionality")
                print("   You can still scrape one site with basic features")
                
                # For non-premium, reduce max pages
                self.max_pages = min(self.max_pages, 3)
        
        # Generate and use parameters
        if not self.scrape_params:
            self.scrape_params = self._generate_scrape_parameters()
        
        # Perform the scraping
        if self.scrape_params:
            logger.info("Scraping with generated parameters")
            item_count = self.scrape_from_parameters()
        else:
            logger.error("Failed to generate scrape parameters")
            return None
        
        # Save the results
        if item_count > 0:
            return self.save_results()
        else:
            logger.warning("No items were scraped")
            return None

def main():
    """Main function to run the scraper from command line"""
    parser = argparse.ArgumentParser(description="General Website Scraper with Claude Integration")
    parser.add_argument("--query", "-q", type=str, help="What to search for (processed by Claude)")
    parser.add_argument("--site-type", "-t", type=str, help="Type of sites to target (blogs, news, ecommerce, etc.)")
    parser.add_argument("--format", "-f", type=str, choices=["json", "csv", "html"], default="json", 
                        help="Output format (default: json)")
    parser.add_argument("--max-pages", "-m", type=int, default=10, 
                        help="Maximum pages to scrape per site (default: 10)")
    parser.add_argument("--license-key", "-l", type=str, help="Set license key for premium features")
    parser.add_argument("--configure-claude", "-c", type=str, help="Configure Claude API key")
    args = parser.parse_args()
    
    # Set license key if provided
    if args.license_key and VPN_AVAILABLE:
        try:
            vpn = VPNManager()
            status = vpn.set_license_key(args.license_key)
            print(f"License status: {'Valid' if status.get('valid', False) else 'Invalid'}")
            print(f"Enabled features: {', '.join(status.get('enabled_features', ['basic_scraping']))}")
        except Exception as e:
            print(f"Error setting license key: {e}")
            return 1
    
    # Configure Claude API if key provided
    if args.configure_claude and VPN_AVAILABLE:
        try:
            vpn = VPNManager()
            vpn.configure_claude_integration(api_key=args.configure_claude)
            print("Claude API key configured successfully")
        except Exception as e:
            print(f"Error configuring Claude API: {e}")
            return 1
    
    # Check if no query provided
    if not args.query:
        parser.print_help()
        return 1
    
    # Create and run the scraper
    scraper = GeneralScraper(
        query=args.query,
        site_type=args.site_type,
        output_format=args.format,
        max_pages=args.max_pages
    )
    
    output_file = scraper.run()
    
    if output_file:
        print(f"\nScraped {scraper.stats['total_items']} items from {scraper.stats['successful_sites']} websites")
        print(f"Results saved to: {output_file}")
        return 0
    else:
        print("\nNo results were found or there was an error during scraping")
        print("Check general_scraper.log for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())