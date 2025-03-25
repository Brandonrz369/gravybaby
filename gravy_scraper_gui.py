#!/usr/bin/env python3

"""
Gravy Scraper GUI - Advanced scraping interface with Claude AI integration
Supports both job scraping and general website scraping with premium features
"""

import os
import sys
import json
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import datetime
import subprocess
import webbrowser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gravy_gui.log'
)
logger = logging.getLogger('gravy_gui')

# Import VPN Manager if available
try:
    from vpn_manager import VPNManager
    VPN_AVAILABLE = True
except ImportError:
    VPN_AVAILABLE = False
    logger.warning("VPN Manager not available. Some features will be disabled.")

# Check for the job scraper
try:
    from job_scraper import JobScraper, CONFIG as JOB_CONFIG
    JOB_SCRAPER_AVAILABLE = True
except ImportError:
    JOB_SCRAPER_AVAILABLE = False
    logger.warning("Job scraper not available. Job search features will be disabled.")

# Check for the general scraper
try:
    from general_scraper import GeneralScraper
    GENERAL_SCRAPER_AVAILABLE = True
except ImportError:
    GENERAL_SCRAPER_AVAILABLE = False
    logger.warning("General scraper not available. General scraping features will be disabled.")

class GravyScraperGUI:
    """Main GUI for Gravy Scraper"""
    
    def __init__(self, root):
        """Initialize the GUI"""
        self.root = root
        self.root.title("Gravy Scraper")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Set app icon if available
        try:
            if os.path.exists("icon.ico"):
                self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Initialize license status
        self.license_status = {
            "valid": False,
            "enabled_features": ["basic_scraping"]
        }
        
        # Create VPN Manager if available
        self.vpn_manager = None
        if VPN_AVAILABLE:
            try:
                self.vpn_manager = VPNManager()
                self.license_status = self.vpn_manager.get_license_status()
                logger.info(f"VPN Manager initialized, license valid: {self.license_status.get('valid', False)}")
            except Exception as e:
                logger.error(f"Error initializing VPN Manager: {e}")
        
        # Set up UI elements
        self.setup_ui()
        
        # Check premium features
        self.update_premium_features()
    
    def setup_ui(self):
        """Set up the user interface"""
        # Create a notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.job_tab = ttk.Frame(self.notebook)
        self.general_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.job_tab, text="Job Scraper")
        self.notebook.add(self.general_tab, text="General Scraper")
        self.notebook.add(self.settings_tab, text="Settings")
        
        # Set up each tab
        self.setup_job_tab()
        self.setup_general_tab()
        self.setup_settings_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # License status in corner
        self.license_frame = ttk.Frame(self.root)
        self.license_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        
        self.license_label = ttk.Label(self.license_frame, text="License Status:")
        self.license_label.pack(side=tk.LEFT, padx=5)
        
        license_status_text = "✓ Premium" if self.license_status.get("valid", False) else "○ Basic"
        self.license_status_label = ttk.Label(
            self.license_frame, 
            text=license_status_text,
            foreground="green" if self.license_status.get("valid", False) else "red"
        )
        self.license_status_label.pack(side=tk.LEFT)
    
    def setup_job_tab(self):
        """Set up the Job Scraper tab"""
        # Main frame for job scraper
        job_frame = ttk.Frame(self.job_tab, padding="10 10 10 10")
        job_frame.pack(fill=tk.BOTH, expand=True)
        
        # Claude query section
        ttk.Label(job_frame, text="Custom Job Search Query", font=("", 12, "bold")).grid(
            column=0, row=0, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(job_frame, text="Describe the job you're looking for in plain language:").grid(
            column=0, row=1, sticky=tk.W)
        
        self.job_query_entry = scrolledtext.ScrolledText(job_frame, height=4, width=70, wrap=tk.WORD)
        self.job_query_entry.grid(column=0, row=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.job_query_entry.insert(tk.END, "Find entry-level remote software developer jobs that require minimal experience")
        
        # Template selection
        template_frame = ttk.Frame(job_frame)
        template_frame.grid(column=0, row=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(template_frame, text="Or select a template:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.job_template_var = tk.StringVar()
        templates = ["Entry-level programming", "Remote only", "Data science", "DevOps", "MSP Provider"]
        self.job_template_combo = ttk.Combobox(template_frame, values=templates, textvariable=self.job_template_var)
        self.job_template_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.job_template_combo.current(0)
        
        ttk.Button(template_frame, text="Use Template", command=self.use_job_template).pack(side=tk.LEFT, padx=(10, 0))
        
        # Location section
        location_frame = ttk.Frame(job_frame)
        location_frame.grid(column=0, row=4, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(location_frame, text="Location:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.job_location_var = tk.StringVar()
        self.job_location_var.set("Remote")
        self.job_location_entry = ttk.Entry(location_frame, textvariable=self.job_location_var, width=30)
        self.job_location_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Options section
        options_frame = ttk.LabelFrame(job_frame, text="Options")
        options_frame.grid(column=0, row=5, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Job sources checkboxes
        sources_frame = ttk.Frame(options_frame)
        sources_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(sources_frame, text="Job Sources:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.source_vars = {}
        sources = ["Indeed", "RemoteOK", "LinkedIn", "Freelancer", "Craigslist"]
        
        for i, source in enumerate(sources):
            var = tk.BooleanVar(value=True)
            self.source_vars[source.lower()] = var
            ttk.Checkbutton(sources_frame, text=source, variable=var).pack(side=tk.LEFT, padx=5)
        
        # Run options
        run_options_frame = ttk.Frame(options_frame)
        run_options_frame.pack(fill=tk.X, pady=5)
        
        self.job_headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(run_options_frame, text="Run in background (headless)", 
                        variable=self.job_headless_var).pack(side=tk.LEFT, padx=(0, 10))
        
        self.job_test_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(run_options_frame, text="Test mode (no actual scraping)", 
                        variable=self.job_test_var).pack(side=tk.LEFT, padx=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(job_frame)
        button_frame.grid(column=0, row=6, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_job_button = ttk.Button(button_frame, text="Start Job Search", 
                                          command=self.start_job_scraper)
        self.start_job_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.view_jobs_button = ttk.Button(button_frame, text="View Latest Jobs", 
                                         command=self.view_jobs)
        self.view_jobs_button.pack(side=tk.LEFT)
        
        # Output console
        ttk.Label(job_frame, text="Output:").grid(column=0, row=7, sticky=tk.W)
        
        self.job_output = scrolledtext.ScrolledText(job_frame, height=10, width=70, wrap=tk.WORD)
        self.job_output.grid(column=0, row=8, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.job_output.config(state=tk.DISABLED)
        
        # Configure grid
        job_frame.columnconfigure(0, weight=1)
        job_frame.rowconfigure(8, weight=1)
    
    def setup_general_tab(self):
        """Set up the General Scraper tab"""
        # Main frame for general scraper
        general_frame = ttk.Frame(self.general_tab, padding="10 10 10 10")
        general_frame.pack(fill=tk.BOTH, expand=True)
        
        # Premium feature indicator
        self.premium_indicator = ttk.Label(
            general_frame, 
            text="✨ Premium Feature", 
            font=("", 10, "italic"),
            foreground="purple"
        )
        self.premium_indicator.grid(column=0, row=0, sticky=tk.E)
        
        # Claude query section
        ttk.Label(general_frame, text="Website Scraping Query", font=("", 12, "bold")).grid(
            column=0, row=1, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(general_frame, text="What information are you looking for?").grid(
            column=0, row=2, sticky=tk.W)
        
        self.general_query_entry = scrolledtext.ScrolledText(general_frame, height=4, width=70, wrap=tk.WORD)
        self.general_query_entry.grid(column=0, row=3, sticky=(tk.W, tk.E), pady=(0, 10))
        self.general_query_entry.insert(tk.END, "Find information about electric vehicle charging stations in Seattle")
        
        # Website type section
        site_frame = ttk.Frame(general_frame)
        site_frame.grid(column=0, row=4, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(site_frame, text="Type of websites to search:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.site_type_var = tk.StringVar()
        site_types = ["Any", "News", "Blogs", "Government", "Corporate", "Forums", "E-commerce"]
        self.site_type_combo = ttk.Combobox(site_frame, values=site_types, textvariable=self.site_type_var)
        self.site_type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.site_type_combo.current(0)
        
        # Output format section
        format_frame = ttk.Frame(general_frame)
        format_frame.grid(column=0, row=5, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(format_frame, text="Output format:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.output_format_var = tk.StringVar()
        formats = ["JSON", "CSV", "HTML"]
        self.output_format_combo = ttk.Combobox(format_frame, values=formats, textvariable=self.output_format_var)
        self.output_format_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.output_format_combo.current(0)
        
        # Options section
        options_frame = ttk.LabelFrame(general_frame, text="Scraping Options")
        options_frame.grid(column=0, row=6, sticky=(tk.W, tk.E), pady=(0, 10))
        
        depth_frame = ttk.Frame(options_frame)
        depth_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(depth_frame, text="Maximum pages per site:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.max_pages_var = tk.StringVar()
        self.max_pages_var.set("10")
        self.max_pages_spin = ttk.Spinbox(depth_frame, from_=1, to=50, textvariable=self.max_pages_var, width=5)
        self.max_pages_spin.pack(side=tk.LEFT)
        
        # Buttons
        button_frame = ttk.Frame(general_frame)
        button_frame.grid(column=0, row=7, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_general_button = ttk.Button(button_frame, text="Start Scraping", 
                                             command=self.start_general_scraper)
        self.start_general_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.view_results_button = ttk.Button(button_frame, text="View Latest Results", 
                                            command=self.view_scrape_results)
        self.view_results_button.pack(side=tk.LEFT)
        
        # Output console
        ttk.Label(general_frame, text="Output:").grid(column=0, row=8, sticky=tk.W)
        
        self.general_output = scrolledtext.ScrolledText(general_frame, height=10, width=70, wrap=tk.WORD)
        self.general_output.grid(column=0, row=9, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.general_output.config(state=tk.DISABLED)
        
        # Configure grid
        general_frame.columnconfigure(0, weight=1)
        general_frame.rowconfigure(9, weight=1)
    
    def setup_settings_tab(self):
        """Set up the Settings tab"""
        # Main frame for settings
        settings_frame = ttk.Frame(self.settings_tab, padding="10 10 10 10")
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # License section
        license_frame = ttk.LabelFrame(settings_frame, text="License Management")
        license_frame.pack(fill=tk.X, pady=(0, 10))
        
        license_input_frame = ttk.Frame(license_frame)
        license_input_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(license_input_frame, text="License Key:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.license_key_var = tk.StringVar()
        self.license_key_entry = ttk.Entry(license_input_frame, textvariable=self.license_key_var, width=40)
        self.license_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(license_input_frame, text="Activate License", 
                  command=self.activate_license).pack(side=tk.LEFT, padx=(10, 0))
        
        # License status
        license_status_frame = ttk.Frame(license_frame)
        license_status_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(license_status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 10))
        
        status_text = "Valid" if self.license_status.get("valid", False) else "Invalid or Missing"
        self.license_detail_label = ttk.Label(
            license_status_frame, 
            text=status_text,
            foreground="green" if self.license_status.get("valid", False) else "red"
        )
        self.license_detail_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Show expiration date if available
        if self.license_status.get("valid_until"):
            ttk.Label(license_status_frame, text=f"Valid until: {self.license_status['valid_until']}").pack(
                side=tk.LEFT)
        
        # Enabled features
        features_frame = ttk.Frame(license_frame)
        features_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(features_frame, text="Enabled Features:").pack(side=tk.LEFT, padx=(0, 10))
        
        features = self.license_status.get("enabled_features", ["basic_scraping"])
        features_text = ", ".join(features)
        ttk.Label(features_frame, text=features_text).pack(side=tk.LEFT)
        
        # Claude API section
        claude_frame = ttk.LabelFrame(settings_frame, text="Claude API Configuration")
        claude_frame.pack(fill=tk.X, pady=(0, 10))
        
        claude_input_frame = ttk.Frame(claude_frame)
        claude_input_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(claude_input_frame, text="API Key:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.claude_key_var = tk.StringVar()
        self.claude_key_entry = ttk.Entry(claude_input_frame, textvariable=self.claude_key_var, width=40)
        self.claude_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(claude_input_frame, text="Configure API", 
                  command=self.configure_claude).pack(side=tk.LEFT, padx=(10, 0))
        
        # Model selection
        claude_model_frame = ttk.Frame(claude_frame)
        claude_model_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(claude_model_frame, text="Model:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.claude_model_var = tk.StringVar()
        models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        self.claude_model_combo = ttk.Combobox(claude_model_frame, values=models, textvariable=self.claude_model_var)
        self.claude_model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.claude_model_combo.current(0)
        
        # Pre-fill API key if it exists in config
        if self.vpn_manager and self.vpn_manager.config.get("claude_integration", {}).get("api_key"):
            self.claude_key_var.set("*" * 20)  # Don't show actual key for security
        
        # VPN & Proxy section
        proxy_frame = ttk.LabelFrame(settings_frame, text="VPN & Proxy Configuration")
        proxy_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Commercial proxy services
        proxy_service_frame = ttk.Frame(proxy_frame)
        proxy_service_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(proxy_service_frame, text="Configure Proxy Service:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.proxy_service_var = tk.StringVar()
        services = ["BrightData", "Oxylabs", "SmartProxy", "ProxyMesh", "ZenRows", "ScraperAPI"]
        self.proxy_service_combo = ttk.Combobox(proxy_service_frame, values=services, textvariable=self.proxy_service_var)
        self.proxy_service_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.proxy_service_combo.current(0)
        
        ttk.Button(proxy_service_frame, text="Setup Proxy", 
                  command=self.setup_proxy).pack(side=tk.LEFT, padx=(10, 0))
        
        # Browser fingerprinting
        fingerprint_frame = ttk.Frame(proxy_frame)
        fingerprint_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(fingerprint_frame, text="Browser Fingerprinting:").pack(side=tk.LEFT, padx=(0, 10))
        
        fingerprint_enabled = False
        if self.vpn_manager and self.vpn_manager.config.get("browser_fingerprints", {}).get("enabled", False):
            fingerprint_enabled = True
        
        self.fingerprint_var = tk.BooleanVar(value=fingerprint_enabled)
        ttk.Checkbutton(fingerprint_frame, text="Enable", 
                        variable=self.fingerprint_var, 
                        command=self.toggle_fingerprinting).pack(side=tk.LEFT)
        
        # Buttons section
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Test Features", 
                  command=self.test_features).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="View Logs", 
                  command=self.view_logs).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="About", 
                  command=self.show_about).pack(side=tk.LEFT)
    
    def update_premium_features(self):
        """Update UI based on premium features availability"""
        # Check if licensed for premium features
        premium_available = False
        if self.license_status.get("valid", False):
            premium_features = self.license_status.get("enabled_features", [])
            if "general_scraping" in premium_features:
                premium_available = True
        
        # Update general scraper tab
        if hasattr(self, 'premium_indicator'):
            if premium_available:
                self.premium_indicator.config(text="✓ Premium Feature Enabled", foreground="green")
                self.start_general_button.config(state=tk.NORMAL)
            else:
                self.premium_indicator.config(text="⚠️ Premium License Required", foreground="red")
                if not GENERAL_SCRAPER_AVAILABLE:
                    self.start_general_button.config(state=tk.DISABLED)
    
    def use_job_template(self):
        """Use the selected job template"""
        template = self.job_template_var.get().lower()
        
        if self.vpn_manager:
            templates = self.vpn_manager.get_custom_search_templates()
            if template in templates:
                self.job_query_entry.delete(1.0, tk.END)
                self.job_query_entry.insert(tk.END, templates[template])
                self.status_var.set(f"Template '{template}' loaded")
            else:
                # Fallback templates
                if template == "entry-level programming":
                    self.job_query_entry.delete(1.0, tk.END)
                    self.job_query_entry.insert(tk.END, "Find entry-level programming jobs for beginners with HTML, CSS, and JavaScript skills")
                elif template == "remote only":
                    self.job_query_entry.delete(1.0, tk.END)
                    self.job_query_entry.insert(tk.END, "Find fully remote software development jobs with flexible hours")
                elif template == "data science":
                    self.job_query_entry.delete(1.0, tk.END)
                    self.job_query_entry.insert(tk.END, "Find data science jobs that work with Python, pandas, and machine learning")
                elif template == "devops":
                    self.job_query_entry.delete(1.0, tk.END)
                    self.job_query_entry.insert(tk.END, "Find DevOps engineer positions working with AWS, Docker, and Kubernetes")
                elif template == "msp provider":
                    self.job_query_entry.delete(1.0, tk.END)
                    self.job_query_entry.insert(tk.END, "Find jobs with Managed Service Providers (MSPs) for IT support and services")
    
    def start_job_scraper(self):
        """Start the job scraper in a separate thread"""
        if not JOB_SCRAPER_AVAILABLE:
            messagebox.showerror("Error", "Job scraper module not available")
            return
        
        query = self.job_query_entry.get(1.0, tk.END).strip()
        if not query:
            messagebox.showerror("Error", "Please enter a job search query")
            return
        
        # Collect job sources
        for source, var in self.source_vars.items():
            if source in JOB_CONFIG["job_sources"]:
                JOB_CONFIG["job_sources"][source] = var.get()
        
        # Update status
        self.status_var.set("Starting job scraper...")
        self.start_job_button.config(state=tk.DISABLED)
        
        # Clear output
        self.job_output.config(state=tk.NORMAL)
        self.job_output.delete(1.0, tk.END)
        self.job_output.config(state=tk.DISABLED)
        
        # Start thread
        threading.Thread(target=self._run_job_scraper, args=(query,), daemon=True).start()
    
    def _run_job_scraper(self, query):
        """Run the job scraper (in thread)"""
        try:
            # Update output
            self._update_job_output(f"Starting job search for: {query}\n")
            self._update_job_output(f"Using location: {self.job_location_var.get()}\n")
            
            # Build command
            cmd = ["python", "job_scraper.py", "--query", query]
            
            if self.job_location_var.get():
                cmd.extend(["--location", self.job_location_var.get()])
            
            if self.job_headless_var.get():
                cmd.append("--headless")
            
            if self.job_test_var.get():
                cmd.append("--test")
            
            # Run the process
            self._update_job_output("Executing command: " + " ".join(cmd) + "\n")
            self._update_job_output("This may take a few minutes...\n")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output and error streams
            for line in process.stdout:
                self._update_job_output(line)
            
            # Wait for process to complete
            process.wait()
            
            # Check for errors
            if process.returncode != 0:
                stderr = process.stderr.read()
                self._update_job_output(f"Error: {stderr}\n")
                self.status_var.set("Job scraper failed")
            else:
                self._update_job_output("\nJob search completed!\n")
                self._update_job_output("Check the \"View Latest Jobs\" button to see results.\n")
                self.status_var.set("Job scraper completed")
            
        except Exception as e:
            self._update_job_output(f"Error: {e}\n")
            logger.error(f"Error running job scraper: {e}")
            self.status_var.set("Job scraper failed")
        
        finally:
            # Re-enable button
            self.root.after(0, lambda: self.start_job_button.config(state=tk.NORMAL))
    
    def _update_job_output(self, text):
        """Update the job output text (thread-safe)"""
        self.root.after(0, lambda: self._update_output_widget(self.job_output, text))
    
    def _update_output_widget(self, widget, text):
        """Update text widget (called in main thread)"""
        widget.config(state=tk.NORMAL)
        widget.insert(tk.END, text)
        widget.see(tk.END)
        widget.config(state=tk.DISABLED)
    
    def view_jobs(self):
        """View the latest scraped jobs"""
        # Check for jobs HTML file
        jobs_html = None
        for file in ["jobs.html", "gravy_jobs.html"]:
            if os.path.exists(file):
                jobs_html = file
                break
        
        if not jobs_html:
            messagebox.showerror("Error", "No job results found. Run a job search first.")
            return
        
        # Open in browser
        try:
            # Convert to absolute path
            abs_path = os.path.abspath(jobs_html)
            webbrowser.open('file://' + abs_path)
            self.status_var.set(f"Opened {jobs_html} in browser")
        except Exception as e:
            logger.error(f"Error opening jobs HTML: {e}")
            messagebox.showerror("Error", f"Could not open jobs file: {e}")
    
    def start_general_scraper(self):
        """Start the general scraper in a separate thread"""
        # Check premium license for general scraping
        is_premium = False
        if self.license_status.get("valid", False):
            if "general_scraping" in self.license_status.get("enabled_features", []):
                is_premium = True
        
        if not is_premium and not GENERAL_SCRAPER_AVAILABLE:
            messagebox.showerror("Error", "General scraping requires a premium license")
            return
        
        query = self.general_query_entry.get(1.0, tk.END).strip()
        if not query:
            messagebox.showerror("Error", "Please enter a search query")
            return
        
        # Update status
        self.status_var.set("Starting general scraper...")
        self.start_general_button.config(state=tk.DISABLED)
        
        # Clear output
        self.general_output.config(state=tk.NORMAL)
        self.general_output.delete(1.0, tk.END)
        self.general_output.config(state=tk.DISABLED)
        
        # Start thread
        threading.Thread(target=self._run_general_scraper, args=(query,), daemon=True).start()
    
    def _run_general_scraper(self, query):
        """Run the general scraper (in thread)"""
        try:
            # Update output
            self._update_general_output(f"Starting web scraping for: {query}\n")
            self._update_general_output(f"Site type: {self.site_type_var.get()}\n")
            self._update_general_output(f"Output format: {self.output_format_var.get().lower()}\n")
            
            # Build command
            site_type = None if self.site_type_var.get() == "Any" else self.site_type_var.get().lower()
            
            cmd = [
                "python", "general_scraper.py", 
                "--query", query,
                "--format", self.output_format_var.get().lower(),
                "--max-pages", self.max_pages_var.get()
            ]
            
            if site_type:
                cmd.extend(["--site-type", site_type])
            
            # Run the process
            self._update_general_output("Executing command: " + " ".join(cmd) + "\n")
            self._update_general_output("This may take a few minutes...\n")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output and error streams
            for line in process.stdout:
                self._update_general_output(line)
            
            # Wait for process to complete
            process.wait()
            
            # Check for errors
            if process.returncode != 0:
                stderr = process.stderr.read()
                self._update_general_output(f"Error: {stderr}\n")
                self.status_var.set("General scraper failed")
            else:
                self._update_general_output("\nWeb scraping completed!\n")
                self._update_general_output("Check the \"View Latest Results\" button to see results.\n")
                self.status_var.set("General scraper completed")
            
        except Exception as e:
            self._update_general_output(f"Error: {e}\n")
            logger.error(f"Error running general scraper: {e}")
            self.status_var.set("General scraper failed")
        
        finally:
            # Re-enable button
            self.root.after(0, lambda: self.start_general_button.config(state=tk.NORMAL))
    
    def _update_general_output(self, text):
        """Update the general output text (thread-safe)"""
        self.root.after(0, lambda: self._update_output_widget(self.general_output, text))
    
    def view_scrape_results(self):
        """View the latest scraped results"""
        # Check for scraped data directory
        if not os.path.exists("scraped_data"):
            messagebox.showerror("Error", "No scrape results found. Run a web scrape first.")
            return
        
        # Find the most recent file
        files = [os.path.join("scraped_data", f) for f in os.listdir("scraped_data") 
                if os.path.isfile(os.path.join("scraped_data", f))]
        
        if not files:
            messagebox.showerror("Error", "No scrape result files found in scraped_data directory.")
            return
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        latest_file = files[0]
        
        # Open in browser if HTML, otherwise in default application
        try:
            # Convert to absolute path
            abs_path = os.path.abspath(latest_file)
            if latest_file.endswith('.html'):
                webbrowser.open('file://' + abs_path)
            else:
                # Use the system's default application
                if sys.platform == 'win32':
                    os.startfile(abs_path)
                elif sys.platform == 'darwin':
                    subprocess.call(['open', abs_path])
                else:
                    subprocess.call(['xdg-open', abs_path])
            
            self.status_var.set(f"Opened {os.path.basename(latest_file)}")
        except Exception as e:
            logger.error(f"Error opening result file: {e}")
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def activate_license(self):
        """Activate license key"""
        license_key = self.license_key_var.get().strip()
        if not license_key:
            messagebox.showerror("Error", "Please enter a license key")
            return
        
        if not self.vpn_manager:
            messagebox.showerror("Error", "VPN Manager not available. Cannot activate license.")
            return
        
        # Update status
        self.status_var.set("Activating license...")
        
        try:
            # Set license key
            status = self.vpn_manager.set_license_key(license_key)
            self.license_status = status
            
            # Update UI
            if status.get("valid", False):
                messagebox.showinfo(
                    "License Activated", 
                    f"License activated successfully!\nValid until: {status.get('valid_until', 'Unknown')}\n"
                    f"Enabled features: {', '.join(status.get('enabled_features', []))}"
                )
                self.license_detail_label.config(text="Valid", foreground="green")
                
                # Update license status in corner
                self.license_status_label.config(text="✓ Premium", foreground="green")
                
                # Update premium features availability
                self.update_premium_features()
            else:
                messagebox.showerror(
                    "License Error", 
                    f"Invalid license key: {status.get('message', 'Unknown error')}"
                )
                self.license_detail_label.config(text="Invalid", foreground="red")
            
            self.status_var.set("License activation completed")
        except Exception as e:
            logger.error(f"Error activating license: {e}")
            messagebox.showerror("Error", f"Could not activate license: {e}")
            self.status_var.set("License activation failed")
    
    def configure_claude(self):
        """Configure Claude API"""
        api_key = self.claude_key_var.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Please enter a Claude API key")
            return
        
        if not self.vpn_manager:
            messagebox.showerror("Error", "VPN Manager not available. Cannot configure Claude API.")
            return
        
        model = self.claude_model_var.get()
        
        # Update status
        self.status_var.set("Configuring Claude API...")
        
        try:
            # Configure Claude
            self.vpn_manager.configure_claude_integration(api_key=api_key, model=model)
            
            messagebox.showinfo(
                "Claude API Configured", 
                f"Claude API configured successfully with model: {model}"
            )
            
            self.status_var.set("Claude API configuration completed")
        except Exception as e:
            logger.error(f"Error configuring Claude API: {e}")
            messagebox.showerror("Error", f"Could not configure Claude API: {e}")
            self.status_var.set("Claude API configuration failed")
    
    def toggle_fingerprinting(self):
        """Toggle browser fingerprinting"""
        if not self.vpn_manager:
            messagebox.showerror("Error", "VPN Manager not available. Cannot configure fingerprinting.")
            return
        
        enabled = self.fingerprint_var.get()
        
        # Update status
        self.status_var.set(f"{'Enabling' if enabled else 'Disabling'} browser fingerprinting...")
        
        try:
            # Configure fingerprinting
            self.vpn_manager.config["browser_fingerprints"]["enabled"] = enabled
            save_config = getattr(self.vpn_manager, "save_config", None)
            if save_config:
                save_config(self.vpn_manager.config)
            
            messagebox.showinfo(
                "Fingerprinting Updated", 
                f"Browser fingerprinting {'enabled' if enabled else 'disabled'} successfully"
            )
            
            self.status_var.set("Fingerprinting configuration updated")
        except Exception as e:
            logger.error(f"Error configuring fingerprinting: {e}")
            messagebox.showerror("Error", f"Could not update fingerprinting: {e}")
            self.status_var.set("Fingerprinting configuration failed")
    
    def setup_proxy(self):
        """Set up commercial proxy service"""
        service = self.proxy_service_var.get().lower()
        
        # Check premium license for commercial proxies
        is_premium = False
        if self.license_status.get("valid", False):
            if "commercial_proxies" in self.license_status.get("enabled_features", []):
                is_premium = True
        
        if not is_premium:
            messagebox.showerror("Error", "Commercial proxy services require a premium license")
            return
        
        # Create simple dialog for proxy configuration
        proxy_dialog = tk.Toplevel(self.root)
        proxy_dialog.title(f"Configure {service}")
        proxy_dialog.geometry("400x300")
        proxy_dialog.resizable(False, False)
        proxy_dialog.transient(self.root)
        proxy_dialog.grab_set()
        
        # Configure dialog based on service
        ttk.Label(proxy_dialog, text=f"Configure {service} Proxy", font=("", 12, "bold")).pack(pady=(10, 20))
        
        # Common fields for all services
        entries = {}
        
        if service in ["brightdata", "oxylabs", "smartproxy", "proxymesh"]:
            # Username and password
            username_frame = ttk.Frame(proxy_dialog)
            username_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(username_frame, text="Username:").pack(side=tk.LEFT, padx=(0, 10))
            username_var = tk.StringVar()
            entries["username"] = username_var
            ttk.Entry(username_frame, textvariable=username_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            password_frame = ttk.Frame(proxy_dialog)
            password_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(password_frame, text="Password:").pack(side=tk.LEFT, padx=(0, 10))
            password_var = tk.StringVar()
            entries["password"] = password_var
            ttk.Entry(password_frame, textvariable=password_var, width=30, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Additional fields for BrightData
            if service == "brightdata":
                zone_frame = ttk.Frame(proxy_dialog)
                zone_frame.pack(fill=tk.X, padx=20, pady=5)
                ttk.Label(zone_frame, text="Zone:").pack(side=tk.LEFT, padx=(0, 10))
                zone_var = tk.StringVar()
                entries["zone"] = zone_var
                ttk.Entry(zone_frame, textvariable=zone_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            # API key for ZenRows and ScraperAPI
            api_frame = ttk.Frame(proxy_dialog)
            api_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(api_frame, text="API Key:").pack(side=tk.LEFT, padx=(0, 10))
            api_var = tk.StringVar()
            entries["api_key"] = api_var
            ttk.Entry(api_frame, textvariable=api_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Country selection for services that support it
        if service in ["brightdata", "oxylabs", "smartproxy", "zenrows", "scraperapi"]:
            country_frame = ttk.Frame(proxy_dialog)
            country_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(country_frame, text="Country:").pack(side=tk.LEFT, padx=(0, 10))
            country_var = tk.StringVar()
            entries["country"] = country_var
            countries = ["us", "gb", "ca", "au", "de", "fr", "jp", "sg"]
            ttk.Combobox(country_frame, values=countries, textvariable=country_var, width=5).pack(side=tk.LEFT)
            country_var.set("us")
        
        # Save button
        def save_proxy_config():
            # Collect values
            config = {}
            for key, var in entries.items():
                config[key] = var.get().strip()
            
            # Validate required fields
            required = ["username", "password"] if service in ["brightdata", "oxylabs", "smartproxy", "proxymesh"] else ["api_key"]
            missing = [field for field in required if field in config and not config[field]]
            
            if missing:
                messagebox.showerror("Error", f"Please fill in the required fields: {', '.join(missing)}")
                return
            
            try:
                # Enable the service
                self.vpn_manager.enable_commercial_proxy(service, **config)
                
                messagebox.showinfo(
                    "Proxy Configured", 
                    f"{service} proxy service configured successfully"
                )
                
                proxy_dialog.destroy()
                self.status_var.set(f"{service} proxy configuration completed")
            except Exception as e:
                logger.error(f"Error configuring proxy: {e}")
                messagebox.showerror("Error", f"Could not configure proxy: {e}")
        
        button_frame = ttk.Frame(proxy_dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        ttk.Button(button_frame, text="Save", command=save_proxy_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=proxy_dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def test_features(self):
        """Run the feature test script"""
        # Update status
        self.status_var.set("Testing features...")
        
        # Create dialog for output
        test_dialog = tk.Toplevel(self.root)
        test_dialog.title("Feature Test")
        test_dialog.geometry("600x400")
        test_dialog.transient(self.root)
        
        # Output console
        output = scrolledtext.ScrolledText(test_dialog, height=20, width=70, wrap=tk.WORD)
        output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Button frame
        button_frame = ttk.Frame(test_dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(button_frame, text="Close", command=test_dialog.destroy).pack(side=tk.RIGHT)
        
        # Run test in separate thread
        def run_test():
            try:
                # Build command
                cmd = ["python", "test_features.py", "--all"]
                
                # Run the process
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Read output
                for line in process.stdout:
                    # Update output (thread-safe)
                    test_dialog.after(0, lambda l=line: update_output(l))
                
                # Wait for process to complete
                process.wait()
                
                # Check for errors
                if process.returncode != 0:
                    stderr = process.stderr.read()
                    test_dialog.after(0, lambda: update_output(f"Error: {stderr}\n"))
                    self.status_var.set("Feature test failed")
                else:
                    test_dialog.after(0, lambda: update_output("\nFeature test completed!\n"))
                    self.status_var.set("Feature test completed")
                
            except Exception as e:
                logger.error(f"Error running feature test: {e}")
                test_dialog.after(0, lambda: update_output(f"Error: {e}\n"))
                self.status_var.set("Feature test failed")
        
        def update_output(text):
            output.insert(tk.END, text)
            output.see(tk.END)
        
        threading.Thread(target=run_test, daemon=True).start()
    
    def view_logs(self):
        """View the application logs"""
        log_files = ["gravy_gui.log", "vpn_manager.log", "job_scraper.log", "general_scraper.log"]
        available_logs = [f for f in log_files if os.path.exists(f)]
        
        if not available_logs:
            messagebox.showinfo("Logs", "No log files found")
            return
        
        # Create dialog for viewing logs
        log_dialog = tk.Toplevel(self.root)
        log_dialog.title("Application Logs")
        log_dialog.geometry("700x500")
        log_dialog.transient(self.root)
        
        # Log file selection
        selection_frame = ttk.Frame(log_dialog)
        selection_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(selection_frame, text="Select log file:").pack(side=tk.LEFT, padx=(0, 10))
        
        log_var = tk.StringVar()
        log_combo = ttk.Combobox(selection_frame, values=available_logs, textvariable=log_var)
        log_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        log_combo.current(0)
        
        # Text area for log content
        log_content = scrolledtext.ScrolledText(log_dialog, height=20, width=80, wrap=tk.WORD)
        log_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Button frame
        button_frame = ttk.Frame(log_dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Function to load selected log
        def load_log():
            selected = log_var.get()
            if not selected or not os.path.exists(selected):
                return
            
            try:
                with open(selected, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                log_content.delete(1.0, tk.END)
                log_content.insert(tk.END, content)
                log_content.see(tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read log file: {e}")
        
        # Load log when selection changes
        log_combo.bind("<<ComboboxSelected>>", lambda e: load_log())
        
        # Initial load
        load_log()
        
        # Buttons
        ttk.Button(button_frame, text="Refresh", command=load_log).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=log_dialog.destroy).pack(side=tk.RIGHT)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
Gravy Scraper

Version: 1.0.0
(c) 2025 Gravy Jobs

A powerful web scraper with Claude AI integration for intelligent parameter generation.

Features:
- Job scraping across multiple platforms
- General website scraping with Claude AI assistance
- VPN rotation and browser fingerprinting
- Commercial proxy integration
- License management for premium features

License Information:
"""
        
        # Add license info
        if self.license_status.get("valid", False):
            about_text += f"✓ Premium license active until: {self.license_status.get('valid_until', 'Unknown')}"
        else:
            about_text += "○ Basic license (Premium features disabled)"
        
        messagebox.showinfo("About", about_text)

def main():
    """Main function"""
    root = tk.Tk()
    app = GravyScraperGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()