#!/usr/bin/env python3
"""
Debug script to inspect Adobe Stock HTML structure
"""

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time


def debug_requests_method():
    """Debug what we get with requests"""
    print("=== DEBUGGING WITH REQUESTS ===")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    search_url = 'https://stock.adobe.com/search?k=ocean+waves&content_type%3Avideo=1&order=relevance'
    print(f"Fetching: {search_url}")
    
    try:
        response = session.get(search_url)
        print(f"Status Code: {response.status_code}")
        print(f"Response Length: {len(response.content)}")
        
        # Save the HTML for inspection
        with open('debug_requests.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("HTML saved to debug_requests.html")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for common elements
        print("\n--- Looking for links ---")
        links = soup.find_all('a', href=True)
        detail_links = [link for link in links if '/detail/' in link.get('href', '')]
        print(f"Found {len(detail_links)} detail links")
        
        for i, link in enumerate(detail_links[:5]):
            print(f"  {i+1}. {link.get('href')}")
        
        # Look for video-related elements
        print("\n--- Looking for video elements ---")
        videos = soup.find_all('video')
        print(f"Found {len(videos)} video elements")
        
        # Look for image elements (might be video thumbnails)
        print("\n--- Looking for images ---")
        images = soup.find_all('img')
        print(f"Found {len(images)} image elements")
        
        # Look for common class names
        print("\n--- Looking for common classes ---")
        all_elements = soup.find_all(class_=True)
        classes = set()
        for elem in all_elements:
            if isinstance(elem.get('class'), list):
                classes.update(elem.get('class'))
        
        video_related_classes = [cls for cls in classes if any(word in cls.lower() for word in ['video', 'asset', 'item', 'result', 'grid'])]
        print("Video-related classes found:")
        for cls in sorted(video_related_classes)[:10]:
            print(f"  .{cls}")
            
    except Exception as e:
        print(f"Error with requests: {e}")


def debug_selenium_method():
    """Debug what we get with Selenium"""
    print("\n=== DEBUGGING WITH SELENIUM ===")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        search_url = 'https://stock.adobe.com/search?k=ocean+waves&content_type%3Avideo=1&order=relevance'
        print(f"Navigating to: {search_url}")
        
        driver.get(search_url)
        print("Page loaded, waiting...")
        time.sleep(5)
        
        # Save the HTML for inspection
        with open('debug_selenium.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("HTML saved to debug_selenium.html")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Check page title
        print(f"Page title: {driver.title}")
        
        # Look for detail links
        print("\n--- Looking for links ---")
        links = soup.find_all('a', href=True)
        detail_links = [link for link in links if '/detail/' in link.get('href', '')]
        print(f"Found {len(detail_links)} detail links")
        
        for i, link in enumerate(detail_links[:5]):
            print(f"  {i+1}. {link.get('href')}")
            
        # Try different selectors
        selectors_to_test = [
            "[data-testid='search-asset-grid']",
            "[data-testid='asset-grid-item']", 
            ".search-result-item",
            ".asset-item",
            "a[href*='/detail/']",
            "[data-automation-id*='asset']",
            ".js-result-item"
        ]
        
        print("\n--- Testing selectors ---")
        for selector in selectors_to_test:
            try:
                elements = soup.select(selector)
                print(f"  {selector}: {len(elements)} elements found")
            except Exception as e:
                print(f"  {selector}: Error - {e}")
                
    except Exception as e:
        print(f"Error with Selenium: {e}")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    debug_requests_method()
    debug_selenium_method()
    
    print("\n=== SUMMARY ===")
    print("Check the generated HTML files:")
    print("- debug_requests.html (what requests sees)")
    print("- debug_selenium.html (what Selenium sees)")
    print("\nLook for video containers and update the scraper selectors accordingly.") 