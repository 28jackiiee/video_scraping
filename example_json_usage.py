#!/usr/bin/env python3
"""
Example script demonstrating the JSON output feature of Adobe Stock scraper.

This script shows how to use the adobe_stock_scraper.py with the new JSON output option
to create metadata dictionaries instead of downloading videos.
"""

import json
from pathlib import Path
from adobe_stock_scraper import AdobeStockScraper

def example_json_output():
    """
    Example of using the scraper in JSON output mode.
    """
    print("🔍 Adobe Stock Scraper - JSON Output Example")
    print("=" * 50)
    
    # Example 1: Basic JSON output
    print("\n📄 Example 1: Basic JSON output")
    scraper = AdobeStockScraper(
        download_dir="json_outputs",
        delay=1.0,
        use_auth=False,  # No authentication for this example
        json_output=True,
        intended_label="Nature Videos"
    )
    
    query = "ocean waves"
    count = 5
    
    print(f"Query: '{query}'")
    print(f"Count: {count}")
    print(f"Intended Label: 'Nature Videos'")
    print("Processing...")
    
    try:
        result_count = scraper.scrape_and_download(query, count)
        print(f"✅ Successfully processed {result_count} videos")
        
        # Find and display the generated JSON file
        json_files = list(Path("json_outputs").glob("*ocean_waves*.json"))
        if json_files:
            latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
            print(f"📁 JSON file created: {latest_file}")
            
            # Load and display the JSON structure
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print("\n📊 JSON Structure Preview:")
            print(json.dumps(data, indent=2)[:500] + "..." if len(json.dumps(data, indent=2)) > 500 else json.dumps(data, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 50)
    
    # Example 2: JSON output with filtering
    print("📄 Example 2: JSON output with filtering")
    scraper_filtered = AdobeStockScraper(
        download_dir="json_outputs",
        delay=1.0,
        use_auth=False,
        max_duration_seconds=30,  # Only videos under 30 seconds
        exclude_title_patterns=["logo", "text", "watermark"],  # Exclude these patterns
        json_output=True,
        intended_label="Short Nature Clips"
    )
    
    query2 = "mountain landscape"
    count2 = 3
    
    print(f"Query: '{query2}'")
    print(f"Count: {count2}")
    print(f"Max Duration: 30 seconds")
    print(f"Exclude Patterns: ['logo', 'text', 'watermark']")
    print(f"Intended Label: 'Short Nature Clips'")
    print("Processing...")
    
    try:
        result_count2 = scraper_filtered.scrape_and_download(query2, count2)
        print(f"✅ Successfully processed {result_count2} videos with filtering")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def load_and_analyze_json(json_file_path):
    """
    Example of how to load and analyze the generated JSON files.
    
    Args:
        json_file_path: Path to the JSON file to analyze
    """
    print(f"\n🔍 Analyzing JSON file: {json_file_path}")
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract video information
        for label, queries in data.items():
            print(f"\n📑 Label: {label}")
            
            for query, videos in queries.items():
                print(f"  🔎 Query: '{query}'")
                print(f"  📊 Videos found: {len(videos)}")
                
                for i, video in enumerate(videos, 1):
                    print(f"    {i}. ID: {video['id']}")
                    print(f"       Caption: {video['caption'][:50]}...")
                    print(f"       URL: {video['url']}")
                    print()
                    
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")

if __name__ == "__main__":
    # Run the examples
    example_json_output()
    
    print("\n" + "=" * 60)
    print("💡 USAGE TIPS:")
    print("1. Use --json-output flag to enable JSON mode")
    print("2. Always provide --intended-label when using JSON mode")
    print("3. JSON files are saved with timestamps to avoid conflicts")
    print("4. Output contains only essential fields: id, caption, and url")
    print("5. Use filtering options to refine your results")
    print("\n📝 Command line example:")
    print("python adobe_stock_scraper.py --query 'ocean waves' --count 5 --json-output --intended-label 'Nature Videos'") 