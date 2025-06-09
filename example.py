#!/usr/bin/env python3
"""
Example script showing how to use the AdobeStockScraper programmatically.
"""

from adobe_stock_scraper import AdobeStockScraper

def main():
    # Create scraper instance
    scraper = AdobeStockScraper(
        download_dir="example_downloads",
        delay=1.5  # 1.5 second delay between requests
    )
    
    # Example 1: Download nature videos
    print("Example 1: Downloading nature videos...")
    nature_count = scraper.scrape_and_download("beautiful nature landscape", count=3)
    print(f"Downloaded {nature_count} nature videos\n")
    
    # Example 2: Download business videos
    print("Example 2: Downloading business videos...")
    business_count = scraper.scrape_and_download("business people meeting", count=2)
    print(f"Downloaded {business_count} business videos\n")
    
    # Example 3: Search only (without downloading)
    print("Example 3: Searching for technology videos...")
    tech_videos = scraper.search_videos("artificial intelligence technology", limit=5)
    
    print(f"Found {len(tech_videos)} technology videos:")
    for i, video in enumerate(tech_videos, 1):
        print(f"  {i}. {video['title']} (ID: {video['id']})")
    
    # Example 4: Download specific videos
    print("\nExample 4: Downloading first technology video...")
    if tech_videos:
        if scraper.download_video(tech_videos[0]):
            print("Successfully downloaded technology video")
        else:
            print("Failed to download technology video")
    
    total_downloaded = nature_count + business_count + (1 if tech_videos else 0)
    print(f"\nTotal videos downloaded: {total_downloaded}")

if __name__ == "__main__":
    main() 