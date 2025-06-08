#!/usr/bin/env python3
"""
Script to find the correct Adobe Stock video search URL
"""

import requests
from urllib.parse import urlencode


def test_adobe_stock_urls():
    """Test different URL patterns for Adobe Stock video search"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    query = "ocean waves"
    
    # Different URL patterns to test
    url_patterns = [
        # Original working pattern but filtered for videos
        f"https://stock.adobe.com/search?k={query.replace(' ', '+')}&content_type%3Avideo=1&order=relevance",
        
        # Try the video subdirectory
        f"https://stock.adobe.com/video?k={query.replace(' ', '+')}&order=relevance",
        
        # Try video with search parameter
        f"https://stock.adobe.com/video/search?k={query.replace(' ', '+')}&order=relevance",
        
        # Try different video filter approach
        f"https://stock.adobe.com/search?k={query.replace(' ', '+')}&filters%5Bcontent_type%3Avideo%5D=1&order=relevance",
        
        # Try the videos landing page with search
        f"https://stock.adobe.com/video?k={query.replace(' ', '+')}",
        
        # Try videos with different syntax
        f"https://stock.adobe.com/search?k={query.replace(' ', '+')}&asset_type=Videos",
        
        # Try with category filter
        f"https://stock.adobe.com/search?k={query.replace(' ', '+')}&category=1&content_type%3Avideo=1",
        
        # Direct approach to videos section
        f"https://stock.adobe.com/video?search_text={query.replace(' ', '+')}",
    ]
    
    print("Testing Adobe Stock video search URLs:")
    print("=" * 60)
    
    for i, url in enumerate(url_patterns, 1):
        try:
            print(f"\n{i}. Testing: {url}")
            response = session.get(url)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   Content Length: {len(response.content)}")
                
                # Check if it's likely a video search page
                content = response.text.lower()
                
                video_indicators = ['video', 'mp4', 'footage', 'clip']
                video_score = sum(content.count(indicator) for indicator in video_indicators)
                
                photo_indicators = ['photo', 'image', 'jpg', 'jpeg', 'png']
                photo_score = sum(content.count(indicator) for indicator in photo_indicators)
                
                print(f"   Video indicators: {video_score}")
                print(f"   Photo indicators: {photo_score}")
                
                if video_score > photo_score:
                    print("   ✅ Likely a VIDEO search page!")
                elif photo_score > video_score:
                    print("   📷 Likely a PHOTO search page")
                else:
                    print("   ❓ Mixed content")
                    
                # Check title
                title_start = content.find('<title>')
                title_end = content.find('</title>')
                if title_start != -1 and title_end != -1:
                    title = content[title_start+7:title_end]
                    print(f"   Title: {title[:100]}...")
                    
            elif response.status_code == 404:
                print("   ❌ Not Found")
            else:
                print(f"   ⚠️ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("Summary: Look for URLs marked with ✅ for video content")


if __name__ == "__main__":
    test_adobe_stock_urls() 