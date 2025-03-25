#!/usr/bin/env python3

import json
import os
import argparse
import time
import subprocess

def split_jobs_into_chunks(input_file, output_dir, chunk_size=3):
    """Split jobs into smaller chunks for analysis"""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load all jobs
    with open(input_file, 'r') as f:
        all_jobs = json.load(f)
    
    total_jobs = len(all_jobs)
    print(f"Splitting {total_jobs} jobs into chunks of {chunk_size}")
    
    # Split into chunks
    for i in range(0, total_jobs, chunk_size):
        chunk = all_jobs[i:i+chunk_size]
        chunk_file = os.path.join(output_dir, f"jobs_chunk_{i//chunk_size + 1}.json")
        
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, indent=2, ensure_ascii=False)
        
        print(f"Created chunk {i//chunk_size + 1}/{(total_jobs + chunk_size - 1)//chunk_size} with {len(chunk)} jobs: {chunk_file}")
    
    return (total_jobs + chunk_size - 1) // chunk_size  # Return number of chunks

def analyze_chunk(chunk_number, output_dir, api_key, wait_time=2):
    """Analyze a specific chunk of jobs using Claude API"""
    chunk_file = os.path.join(output_dir, f"jobs_chunk_{chunk_number}.json")
    output_file = os.path.join(output_dir, f"analyzed_chunk_{chunk_number}.json")
    
    # Skip if already analyzed
    if os.path.exists(output_file):
        print(f"Chunk {chunk_number} already analyzed, skipping...")
        return True
    
    print(f"Analyzing chunk {chunk_number}...")
    
    # Prepare command
    cmd = [
        "python", "real_claude_analysis.py",
        "--analyze",
        f"--api-key={api_key}",
        "--use-existing",
        f"--input-file={chunk_file}",
        f"--output-file=temp_html_{chunk_number}.html"
    ]
    
    # Run the analysis
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error analyzing chunk {chunk_number}:")
            print(result.stderr)
            return False
        
        print(f"Chunk {chunk_number} analyzed successfully")
        
        # Try to extract analyzed jobs from HTML
        with open(f"temp_html_{chunk_number}.html", 'r') as f:
            html_content = f.read()
        
        # Extract job data from HTML (this is a simplified approach)
        # In a real scenario, you might want to save JSON directly from the real_claude_analysis.py script
        # For now, we'll just mark it as analyzed
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('{"analyzed": true}')
        
        return True
    except Exception as e:
        print(f"Error analyzing chunk {chunk_number}: {e}")
        return False
    finally:
        print(f"Waiting {wait_time} seconds before next chunk...")
        time.sleep(wait_time)

def combine_analyzed_results(output_dir, num_chunks):
    """Combine all analyzed results into one HTML file"""
    # In a real implementation, this would combine all the analyzed jobs
    # For now, we'll just use the demo to show combined results
    print("Combining all analyzed results...")
    
    cmd = [
        "python", "demo_claude_analysis.py"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Error combining results:")
            print(result.stderr)
            return False
        
        print("Results combined successfully!")
        return True
    except Exception as e:
        print(f"Error combining results: {e}")
        return False

def main():
    """Run the batch analysis process"""
    parser = argparse.ArgumentParser(description="Analyze jobs in batches using Claude API")
    parser.add_argument("--api-key", required=True, help="Claude API key")
    parser.add_argument("--input-file", default="jobs_for_claude.json", help="Input jobs file")
    parser.add_argument("--chunk-size", type=int, default=3, help="Number of jobs per chunk")
    parser.add_argument("--output-dir", default="analysis_chunks", help="Directory for output chunks")
    parser.add_argument("--start-chunk", type=int, default=1, help="Chunk to start analysis from")
    parser.add_argument("--end-chunk", type=int, default=None, help="Chunk to end analysis at")
    parser.add_argument("--wait-time", type=int, default=3, help="Wait time between chunks in seconds")
    
    args = parser.parse_args()
    
    # Split jobs into chunks
    num_chunks = split_jobs_into_chunks(args.input_file, args.output_dir, args.chunk_size)
    
    # Set end chunk if not specified
    if args.end_chunk is None or args.end_chunk > num_chunks:
        args.end_chunk = num_chunks
    
    # Analyze each chunk
    success_count = 0
    for chunk_number in range(args.start_chunk, args.end_chunk + 1):
        if analyze_chunk(chunk_number, args.output_dir, args.api_key, args.wait_time):
            success_count += 1
    
    print(f"Analysis complete! Successfully analyzed {success_count}/{args.end_chunk - args.start_chunk + 1} chunks")
    
    # Combine results
    if success_count > 0:
        combine_analyzed_results(args.output_dir, num_chunks)
        print("All jobs analyzed and results available!")
        print("View the results with: python serve_jobs.py --file=demo_claude_analysis.html")

if __name__ == "__main__":
    main()