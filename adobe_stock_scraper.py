import os
import re
import time
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from tqdm import tqdm
from pathvalidate import sanitize_filename
import json


class AdobeStockVideoScraper:
    def __init__(self, download_dir="downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        
        # Essential options for stability
        chrome_options.add_argument('--headless=new')  # Use new headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Additional stability options for macOS
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Speed up loading
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        
        # User agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            print(f"Error setting up Chrome driver: {str(e)}")
            raise
        
    def search_videos_simple(self, query, max_results=20):
        """Simplified search approach using requests for more reliable scraping"""
        print(f"Searching Adobe Stock for: '{query}' (simplified method)")
        
        try:
            # Corrected search URL for videos only - use the working pattern from URL finder
            search_url = f"https://stock.adobe.com/search?k={query.replace(' ', '+')}&filters%5Bcontent_type%3Avideo%5D=1&order=relevance"
            print(f"Fetching: {search_url}")
            
            response = self.session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for video links and information in the HTML
            video_links = soup.find_all('a', href=True)
            video_data = []
            
            for link in video_links:
                href = link.get('href', '')
                # Look for video URLs - they can be in /video/ or /search/ with video content
                if ('/video/' in href or ('/images/' in href and 'video' in href.lower())) and href not in [v.get('detail_url') for v in video_data]:
                    # Extract video ID from different patterns
                    video_id = None
                    
                    # Pattern 1: /video/something/id
                    match = re.search(r'/video/[^/]+/(\d+)', href)
                    if match:
                        video_id = match.group(1)
                    
                    # Pattern 2: /images/something/id (for videos that show as images)
                    if not video_id:
                        match = re.search(r'/images/[^/]+/(\d+)', href)
                        if match:
                            video_id = match.group(1)
                    
                    if video_id:
                        # Get title from surrounding elements
                        title = "Video"
                        title_elem = link.find('span') or link.find_parent().find('span')
                        if title_elem:
                            title = title_elem.get_text(strip=True)[:100]
                        
                        # Alternative way to find title from alt attribute
                        img_elem = link.find('img')
                        if img_elem and img_elem.get('alt') and not title_elem:
                            title = img_elem.get('alt')[:100]
                        
                        video_info = {
                            'id': video_id,
                            'title': title or f"Video_{video_id}",
                            'detail_url': f"https://stock.adobe.com{href}" if href.startswith('/') else href
                        }
                        
                        video_data.append(video_info)
                        print(f"Found video: {video_info['title']}")
                        
                        if len(video_data) >= max_results:
                            break
            
            print(f"Successfully found {len(video_data)} videos using simple method")
            return video_data
            
        except Exception as e:
            print(f"Error in simplified search: {str(e)}")
            return []
        
    def search_videos(self, query, max_results=20):
        """Search for videos on Adobe Stock with fallback methods"""
        print(f"Searching Adobe Stock for: '{query}'")
        
        # Try simple method first
        video_data = self.search_videos_simple(query, max_results)
        if video_data:
            return video_data
        
        # Fallback to Selenium if simple method fails
        print("Falling back to Selenium method...")
        driver = None
        
        try:
            driver = self.setup_driver()
            
            # Correct search URL for videos
            search_url = f"https://stock.adobe.com/search?k={query}&filters%5Bcontent_type%3Avideo%5D=1&order=relevance"
            
            print(f"Navigating to: {search_url}")
            driver.get(search_url)
            
            # Wait a bit for page to load
            time.sleep(5)
            
            # Parse the page source
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Find video containers using the discovered structure
            video_containers = soup.find_all('div', class_='js-search-result-cell')
            
            print(f"Found {len(video_containers)} video containers")
            
            for i, container in enumerate(video_containers[:max_results]):
                try:
                    video_info = self._extract_video_info(container)
                    if video_info and '/video/' in video_info.get('detail_url', ''):
                        video_data.append(video_info)
                        print(f"Extracted info for video {i+1}: {video_info['title'][:50]}...")
                except Exception as e:
                    print(f"Error extracting video {i+1}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error during Selenium search: {str(e)}")
        finally:
            if driver:
                driver.quit()
            
        print(f"Successfully extracted {len(video_data)} videos")
        return video_data
    
    def _scroll_page(self, driver, max_results):
        """Scroll the page to load more results"""
        last_height = driver.execute_script("return document.body.scrollHeight")
        results_loaded = 0
        
        while results_loaded < max_results:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Check if new content loaded
            new_height = driver.execute_script("return document.body.scrollHeight")
            current_results = len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='asset-grid-item']"))
            
            if new_height == last_height or current_results >= max_results:
                break
                
            last_height = new_height
            results_loaded = current_results
    
    def _extract_video_info(self, container):
        """Extract video information from container element"""
        video_info = {}
        
        # Extract content ID from data attribute
        content_id = container.get('data-content-id')
        if content_id:
            video_info['id'] = content_id
        
        # Extract title from meta tag or img alt attribute
        title = "Untitled Video"
        meta_title = container.find('meta', {'itemprop': 'name'})
        if meta_title:
            title = meta_title.get('content', title)
        else:
            # Try img alt
            img_elem = container.find('img')
            if img_elem and img_elem.get('alt'):
                title = img_elem.get('alt')
        
        video_info['title'] = title
        
        # Extract video URL from link
        link_elem = container.find('a', class_='js-search-result-thumbnail')
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            video_info['detail_url'] = f"https://stock.adobe.com{href}" if href.startswith('/') else href
        
        # Extract preview image
        img_elem = container.find('img')
        if img_elem and img_elem.get('src'):
            video_info['preview_image'] = img_elem['src']
        
        return video_info if video_info.get('id') else None
    
    def get_video_download_info(self, video_id):
        """Get detailed video information and download URLs using requests first"""
        
        # For Adobe Stock, we need to construct the correct video detail URL
        # Try different possible URL patterns
        possible_urls = [
            f"https://stock.adobe.com/video/detail/{video_id}",
            f"https://stock.adobe.com/video/{video_id}",
        ]
        
        for detail_url in possible_urls:
            try:
                print(f"Getting video details from: {detail_url}")
                response = self.session.get(detail_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                download_info = {}
                
                # Look for video elements in the HTML
                video_elements = soup.find_all('video')
                for video_elem in video_elements:
                    src = video_elem.get('src')
                    if src:
                        download_info['preview_url'] = src
                        break
                        
                    # Check for source elements
                    sources = video_elem.find_all('source')
                    for source in sources:
                        src = source.get('src')
                        if src:
                            download_info['preview_url'] = src
                            break
                
                # Look for title
                title_elem = soup.find('h1') or soup.find('title')
                if title_elem:
                    download_info['title'] = title_elem.get_text(strip=True)
                
                # If we found something, return it
                if download_info:
                    return download_info
                
            except Exception as e:
                print(f"Error getting video details from {detail_url}: {str(e)}")
                continue
        
        # If no video found with requests, try Selenium as fallback
        print("No video URL found with requests, trying Selenium...")
        return self._get_video_details_selenium(video_id)
    
    def _get_video_details_selenium(self, video_id):
        """Fallback method using Selenium to get video details"""
        possible_urls = [
            f"https://stock.adobe.com/video/detail/{video_id}",
            f"https://stock.adobe.com/video/{video_id}",
        ]
        
        driver = None
        download_info = {}
        
        try:
            driver = self.setup_driver()
            
            for detail_url in possible_urls:
                try:
                    driver.get(detail_url)
                    time.sleep(3)
                    
                    # Look for preview video elements
                    video_elements = driver.find_elements(By.TAG_NAME, 'video')
                    
                    for video_elem in video_elements:
                        src = video_elem.get_attribute('src')
                        if src:
                            download_info['preview_url'] = src
                            break
                            
                        # Check for source elements within video
                        sources = video_elem.find_elements(By.TAG_NAME, 'source')
                        for source in sources:
                            src = source.get_attribute('src')
                            if src:
                                download_info['preview_url'] = src
                                break
                    
                    if download_info:
                        break
                        
                except Exception as e:
                    print(f"Error getting video details with Selenium from {detail_url}: {str(e)}")
                    continue
            
        except Exception as e:
            print(f"Error with Selenium video details: {str(e)}")
        finally:
            if driver:
                driver.quit()
                
        return download_info
    
    def download_video(self, video_info, filename=None):
        """Download a video file"""
        if not filename:
            safe_title = sanitize_filename(video_info.get('title', 'video'))
            filename = f"{safe_title}_{video_info.get('id', 'unknown')}.mp4"
        
        filepath = self.download_dir / filename
        
        # Try preview video first, then preview image as fallback
        download_url = video_info.get('preview_video') or video_info.get('preview_url') or video_info.get('preview_image')
        
        if not download_url:
            print(f"No download URL found for {video_info.get('title', 'video')}")
            return None
        
        # Determine file extension based on URL
        if download_url.endswith('.jpg') or download_url.endswith('.jpeg') or download_url.endswith('.png'):
            filename = filename.replace('.mp4', '.jpg')
            filepath = self.download_dir / filename
        
        try:
            print(f"Downloading: {filename}")
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    with tqdm(total=total_size, unit='iB', unit_scale=True, desc=filename) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
            
            print(f"Successfully downloaded: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error downloading {filename}: {str(e)}")
            if filepath.exists():
                filepath.unlink()
            return None
    
    def scrape_and_download(self, query, max_videos=5):
        """Complete pipeline: search, extract, and download videos"""
        print(f"Starting Adobe Stock video scraping pipeline for: '{query}'")
        
        # Create query-specific directory
        query_dir = self.download_dir / sanitize_filename(query)
        query_dir.mkdir(exist_ok=True)
        
        # Update download directory
        original_dir = self.download_dir
        self.download_dir = query_dir
        
        try:
            # Search for videos
            videos = self.search_videos(query, max_videos * 2)  # Get more to account for failures
            
            if not videos:
                print("No videos found!")
                return []
            
            downloaded_files = []
            successful_downloads = 0
            
            for i, video in enumerate(videos):
                if successful_downloads >= max_videos:
                    break
                    
                print(f"\nProcessing video {i+1}/{len(videos)}")
                
                # Get detailed video info
                if video.get('id'):
                    detailed_info = self.get_video_download_info(video['id'])
                    video.update(detailed_info)
                
                # Download the video
                downloaded_file = self.download_video(video)
                if downloaded_file:
                    downloaded_files.append(downloaded_file)
                    successful_downloads += 1
                
                # Add delay between downloads
                time.sleep(1)
            
            # Save metadata
            metadata_file = query_dir / 'metadata.json'
            with open(metadata_file, 'w') as f:
                json.dump({
                    'query': query,
                    'total_found': len(videos),
                    'downloaded': len(downloaded_files),
                    'videos': videos[:len(downloaded_files)]
                }, f, indent=2)
            
            print(f"\n✅ Pipeline completed!")
            print(f"📁 Downloaded {len(downloaded_files)} videos to: {query_dir}")
            print(f"📄 Metadata saved to: {metadata_file}")
            
            return downloaded_files
            
        finally:
            self.download_dir = original_dir


if __name__ == "__main__":
    # Example usage
    scraper = AdobeStockVideoScraper()
    query = input("Enter search query: ")
    max_videos = int(input("Max videos to download (default 5): ") or 5)
    
    downloaded = scraper.scrape_and_download(query, max_videos)
    print(f"\nDownloaded {len(downloaded)} videos:")
    for file in downloaded:
        print(f"  - {file}") 