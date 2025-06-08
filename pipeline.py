#!/usr/bin/env python3
"""
Adobe Stock Video Scraping Pipeline

Usage:
    python pipeline.py --query "nature landscape" --max-videos 10
    python pipeline.py --query "business meeting" --output-dir ./my_videos
    
Examples:
    python pipeline.py --query "technology abstract" --max-videos 5
    python pipeline.py --query "cooking food" --max-videos 8 --output-dir ./cooking_videos
"""

import argparse
import sys
from pathlib import Path
from adobe_stock_scraper import AdobeStockVideoScraper


def main():
    parser = argparse.ArgumentParser(
        description="Download videos from Adobe Stock based on search query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Search query for videos (e.g. 'nature landscape', 'business meeting')"
    )
    
    parser.add_argument(
        "--max-videos", "-n",
        type=int,
        default=5,
        help="Maximum number of videos to download (default: 5)"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="downloads",
        help="Output directory for downloaded videos (default: 'downloads')"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between downloads in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    
    print("🎬 Adobe Stock Video Scraping Pipeline")
    print("=" * 50)
    print(f"Query: {args.query}")
    print(f"Max videos: {args.max_videos}")
    print(f"Output directory: {args.output_dir}")
    print("=" * 50)
    
    try:
        # Initialize scraper
        scraper = AdobeStockVideoScraper(download_dir=args.output_dir)
        
        # Run the pipeline
        downloaded_files = scraper.scrape_and_download(
            query=args.query,
            max_videos=args.max_videos
        )
        
        if downloaded_files:
            print(f"\n🎉 Success! Downloaded {len(downloaded_files)} videos:")
            for i, file in enumerate(downloaded_files, 1):
                print(f"  {i}. {Path(file).name}")
            
            output_path = Path(args.output_dir) / scraper.sanitize_filename(args.query)
            print(f"\n📁 All files saved to: {output_path.absolute()}")
        else:
            print("\n❌ No videos were downloaded. Check your search query or try again later.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {str(e)}")
        sys.exit(1)


def quick_run():
    """Quick interactive mode"""
    print("🎬 Adobe Stock Video Scraper - Quick Mode")
    print("=" * 45)
    
    try:
        query = input("Enter search query: ").strip()
        if not query:
            print("❌ Search query cannot be empty!")
            return
            
        max_videos_input = input("Max videos to download (default 5): ").strip()
        max_videos = int(max_videos_input) if max_videos_input else 5
        
        scraper = AdobeStockVideoScraper()
        downloaded = scraper.scrape_and_download(query, max_videos)
        
        if downloaded:
            print(f"\n🎉 Successfully downloaded {len(downloaded)} videos!")
        else:
            print("\n❌ No videos were downloaded.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments provided, run in interactive mode
        quick_run()
    else:
        # Arguments provided, run with argparse
        main() 