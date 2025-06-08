#!/usr/bin/env python3
"""
Test script for Adobe Stock Video Scraper
This script performs a dry run to test the scraper functionality
"""

import sys
from adobe_stock_scraper import AdobeStockVideoScraper


def test_scraper():
    """Test the scraper initialization and basic functionality"""
    print("🧪 Testing Adobe Stock Video Scraper")
    print("=" * 40)
    
    try:
        # Test 1: Initialize scraper
        print("1. Initializing scraper...")
        scraper = AdobeStockVideoScraper(download_dir="test_downloads")
        print("   ✅ Scraper initialized successfully")
        
        # Test 2: Test Chrome driver setup
        print("2. Testing Chrome driver setup...")
        driver = scraper.setup_driver()
        print("   ✅ Chrome driver setup successful")
        
        # Quick test navigation
        print("3. Testing website access...")
        driver.get("https://stock.adobe.com")
        title = driver.title
        print(f"   ✅ Successfully accessed Adobe Stock (Title: {title[:50]}...)")
        
        driver.quit()
        
        print("\n🎉 All tests passed! The scraper is ready to use.")
        print("\nYou can now run:")
        print("  python pipeline.py --query 'your search term' --max-videos 3")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Test failed: {str(e)}")
        print("\nTroubleshooting tips:")
        print("- Make sure Chrome browser is installed")
        print("- Check your internet connection")
        print("- Try running: pip install -r requirements.txt")
        return False


if __name__ == "__main__":
    success = test_scraper()
    sys.exit(0 if success else 1) 