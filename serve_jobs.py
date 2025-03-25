#!/usr/bin/env python3

import http.server
import socketserver
import os
import webbrowser
import argparse

def main():
    """Start a simple HTTP server to serve the jobs webpage"""
    parser = argparse.ArgumentParser(description='Serve job listings webpage on localhost')
    parser.add_argument('--port', type=int, default=8000, help='Port to serve on (default: 8000)')
    parser.add_argument('--file', type=str, default="jobs.html", help='HTML file to serve (default: jobs.html)')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()
    
    # Get the directory where this script is located
    directory = os.path.dirname(os.path.abspath(__file__))
    os.chdir(directory)
    
    # Check if the specified HTML file exists
    if not os.path.exists(args.file):
        print(f"{args.file} not found. Run generate_job_webpage.py or ai_curate_jobs.py first to create it.")
        return
    
    # Create the server
    handler = http.server.SimpleHTTPRequestHandler
    
    try:
        with socketserver.TCPServer(("", args.port), handler) as httpd:
            url = f"http://localhost:{args.port}/{args.file}"
            print(f"Server started at {url}")
            
            # Open browser automatically if not disabled
            if not args.no_browser:
                webbrowser.open(url)
            
            # Keep server running until Ctrl+C
            print("Press Ctrl+C to stop the server")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    except OSError as e:
        print(f"Error: {e}")
        print(f"Make sure port {args.port} is available, or specify a different port with --port")

if __name__ == "__main__":
    main()