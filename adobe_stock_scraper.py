#!/usr/bin/env python3
"""
Adobe Stock Video Thumbnail Scraper

This script scrapes and downloads thumbnail videos from Adobe Stock
based on a search query. Supports browser-based authentication.

Usage:
    python adobe_stock_scraper.py --query "nature landscape" --count 10 --login
"""

import requests
import json
import os
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
from typing import List, Dict, Optional
import logging
from bs4 import BeautifulSoup

# Selenium imports for browser automation
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: Selenium not installed. Install with: pip install selenium")
    print("Browser authentication will not be available.")

class AdobeStockScraper:
    def __init__(self, download_dir: str = "downloads", delay: float = 1.0, use_auth: bool = False):
        """
        Initialize the Adobe Stock scraper.
        
        Args:
            download_dir: Directory to save downloaded videos
            delay: Delay between requests in seconds
            use_auth: Whether to use browser-based authentication
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.delay = delay
        self.use_auth = use_auth
        self.session = requests.Session()
        self.authenticated = False
        self.cookies_file = Path("adobe_stock_cookies.json")
        
        # Set up headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        })
        
        # Set up logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Try to load existing cookies if authentication is requested
        if self.use_auth:
            self.load_cookies()

    def authenticate_with_browser(self) -> bool:
        """
        Open a browser for user to log in to Adobe Stock manually.
        Extract cookies after successful login.
        
        Returns:
            True if authentication successful, False otherwise
        """
        if not SELENIUM_AVAILABLE:
            self.logger.error("Selenium not available. Install with: pip install selenium")
            return False
        
        self.logger.info("Opening browser for Adobe Stock login...")
        
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Try to start Chrome browser
        try:
            service = Service()  # Will use system chromedriver if available
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
        except WebDriverException as e:
            self.logger.error(f"Failed to start Chrome browser: {e}")
            self.logger.info("Make sure Chrome and chromedriver are installed.")
            self.logger.info("Install chromedriver: brew install chromedriver (macOS) or download from https://chromedriver.chromium.org/")
            return False
        
        try:
            # Navigate to Adobe Stock login page
            login_url = "https://stock.adobe.com/contributor"
            self.logger.info(f"Navigating to {login_url}")
            driver.get(login_url)
            
            # Wait a moment for page to load
            time.sleep(3)
            
            print("\n" + "="*60)
            print("🌐 BROWSER OPENED FOR ADOBE STOCK LOGIN")
            print("="*60)
            print("1. Complete your login in the browser window")
            print("2. Navigate to any Adobe Stock page (e.g., search for videos)")
            print("3. Make sure you're fully logged in")
            print("4. Press ENTER here when you're done logging in...")
            print("="*60)
            
            # Wait for user to complete login
            input("Press ENTER after logging in: ")
            
            # Get current URL to verify login
            current_url = driver.current_url
            self.logger.info(f"Current URL: {current_url}")
            
            # Extract cookies from browser
            selenium_cookies = driver.get_cookies()
            
            if not selenium_cookies:
                self.logger.warning("No cookies found. Make sure you're logged in.")
                return False
            
            # Convert selenium cookies to requests format
            cookies_dict = {}
            for cookie in selenium_cookies:
                if cookie['domain'] in ['.adobe.com', 'stock.adobe.com', '.stock.adobe.com']:
                    cookies_dict[cookie['name']] = cookie['value']
            
            self.logger.info(f"Extracted {len(cookies_dict)} Adobe cookies")
            
            # Save cookies to file
            self.save_cookies(cookies_dict)
            
            # Update session with cookies
            self.session.cookies.update(cookies_dict)
            
            # Test authentication by accessing a protected page
            test_response = self.session.get("https://stock.adobe.com/search")
            if test_response.status_code == 200:
                self.authenticated = True
                self.logger.info("✅ Authentication successful!")
                print("\n✅ Authentication successful! You can now close the browser.")
            else:
                self.logger.warning("Authentication may have failed. Will attempt scraping anyway.")
                self.authenticated = True  # Try anyway
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during browser authentication: {e}")
            return False
            
        finally:
            # Close browser
            try:
                driver.quit()
            except:
                pass

    def load_cookies(self) -> bool:
        """
        Load saved cookies from file.
        
        Returns:
            True if cookies loaded successfully, False otherwise
        """
        if not self.cookies_file.exists():
            return False
        
        try:
            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)
            
            self.session.cookies.update(cookies)
            self.authenticated = True
            self.logger.info(f"Loaded {len(cookies)} cookies from file")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading cookies: {e}")
            return False

    def save_cookies(self, cookies: dict) -> bool:
        """
        Save cookies to file.
        
        Args:
            cookies: Dictionary of cookies to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            
            self.logger.info(f"Saved {len(cookies)} cookies to {self.cookies_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving cookies: {e}")
            return False

    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated by testing access to Adobe Stock.
        
        Returns:
            True if authenticated, False otherwise
        """
        try:
            response = self.session.get("https://stock.adobe.com/search", timeout=10)
            
            # Check for login indicators in the response
            if response.status_code == 200:
                # Look for signs that we're logged in
                content = response.text
                if any(indicator in content.lower() for indicator in ['sign out', 'logout', 'account', 'profile']):
                    self.authenticated = True
                    return True
                elif 'sign in' in content.lower() or 'login' in content.lower():
                    self.authenticated = False
                    return False
                else:
                    # Assume we're authenticated if we can access the page
                    self.authenticated = True
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking authentication: {e}")
            return False

    def search_videos(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for videos on Adobe Stock.
        
        Args:
            query: Search query string
            limit: Number of videos to find
            
        Returns:
            List of video data dictionaries
        """
        videos = []
        seen_video_ids = set()  # Track video IDs to avoid duplicates
        page = 1
        max_pages = 10  # Limit to prevent infinite loops
        consecutive_empty_pages = 0  # Track empty pages to stop early
        
        while len(videos) < limit and page <= max_pages and consecutive_empty_pages < 3:
            self.logger.info(f"Searching page {page} for query: '{query}'")
            
            # Use only the working Adobe Stock URL pattern
            search_urls = [
                "https://stock.adobe.com/search/video",
            ]
            # Every Adobe Stock video uses the pattern: https://stock.adobe.com/Download/Watermarked/video_id
            # The video_id is extracted from the HTML content of the search results page
            
            # Add pagination parameters
            params = {
                'k': query,
                'content_type:video': '1',
                'order': 'relevance',
                'safe_search': '1',
                'search_page': page,  # Add page parameter
                'limit': '200',  # Request more results per page
            }
            
            page_videos = []
            for url in search_urls:
                try:
                    response = self.session.get(url, params=params, timeout=30)
                    response.raise_for_status()
                    
                    self.logger.info(f"Got response from {url}, status: {response.status_code}")
                    
                    # Look for JSON data in the page
                    page_videos = self._extract_video_data(response.text)
                    
                    if page_videos:
                        self.logger.info(f"Found {len(page_videos)} videos using {url}")
                        break
                    else:
                        self.logger.warning(f"No videos found using {url}")
                        
                except requests.RequestException as e:
                    self.logger.error(f"Error with {url}: {e}")
                    continue
            
            if not page_videos:
                self.logger.warning(f"No videos found on page {page}")
                consecutive_empty_pages += 1
            else:
                consecutive_empty_pages = 0
                
                # Filter out duplicates and add new videos
                new_videos = []
                for video in page_videos:
                    video_id = video.get('id')
                    if video_id and video_id not in seen_video_ids:
                        seen_video_ids.add(video_id)
                        new_videos.append(video)
                
                videos.extend(new_videos)
                self.logger.info(f"Found {len(new_videos)} new unique videos on page {page} ({len(page_videos) - len(new_videos)} duplicates filtered)")
                
                # If we got no new videos on this page, it might mean we've seen them all
                if len(new_videos) == 0:
                    consecutive_empty_pages += 1
            
            page += 1
            time.sleep(self.delay)  # Rate limiting
        
        if len(videos) < limit:
            self.logger.warning(f"Only found {len(videos)} unique videos out of requested {limit}. Adobe Stock may not have enough unique results for this query.")
        
        return videos[:limit]

    def _extract_video_data(self, html_content: str) -> List[Dict]:
        """
        Extract video data from Adobe Stock page HTML.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of video data dictionaries
        """
        videos = []
        
        # Method 1: Extract video IDs from HTML to construct watermarked download URLs
        video_ids = self._extract_video_ids_from_html(html_content)
        if video_ids:
            for video_id in video_ids:
                video_data = {
                    'id': video_id,
                    'title': f'Adobe_Stock_Video_{video_id}',
                    'thumbnail_url': None,
                    'preview_url': f'https://stock.adobe.com/Download/Watermarked/{video_id}',
                    'comp_url': f'https://stock.adobe.com/Download/Watermarked/{video_id}',
                    'description': '',
                    'tags': []
                }
                videos.append(video_data)
            self.logger.info(f"Extracted {len(videos)} video IDs from HTML for watermarked downloads")
            return videos
        
        # Method 2: Look for various JSON data patterns (fallback)
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.INITIAL_STATE\s*=\s*({.*?});',
            r'__APOLLO_STATE__["\']?\s*:\s*({.*?})',
            r'window\.APOLLO_STATE\s*=\s*({.*?});',
            r'"searchResults":\s*({.*?})',
        ]
        
        for pattern in json_patterns:
            json_match = re.search(pattern, html_content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    extracted = self._parse_json_data(data)
                    if extracted:
                        videos.extend(extracted)
                        self.logger.info(f"Extracted {len(extracted)} videos from JSON pattern")
                        break
                except json.JSONDecodeError as e:
                    self.logger.debug(f"Error parsing JSON with pattern: {e}")
                    continue
        
        # Method 3: Use BeautifulSoup for HTML parsing (fallback)
        if not videos:
            videos = self._extract_video_data_soup(html_content)
        
        # Method 4: Regex fallback for direct video URLs (fallback)
        if not videos:
            videos = self._extract_video_data_regex(html_content)
        
        return videos

    def _extract_video_ids_from_html(self, html_content: str) -> List[str]:
        """
        Extract Adobe Stock video IDs from HTML content.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of video ID strings
        """
        video_ids = set()  # Use set to avoid duplicates
        
        # Pattern 1: Look for video IDs in data attributes
        patterns = [
            r'data-asset-id="(\d{8,})"',
            r'data-video-id="(\d{8,})"',
            r'data-id="(\d{8,})"',
            r'id="asset-(\d{8,})"',
            r'asset-id-(\d{8,})',
            r'/(\d{8,})/preview',
            r'/(\d{8,})/comp',
            r'asset_id["\']?\s*:\s*["\']?(\d{8,})["\']?',
            r'"id":\s*"?(\d{8,})"?',
            r'"asset_id":\s*"?(\d{8,})"?',
            r'stock\.adobe\.com/.*?/(\d{8,})',
            r'asset/(\d{8,})',
            r'video/(\d{8,})',
            r'Download/Watermarked/(\d{8,})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                # Ensure the ID is at least 8 digits (typical Adobe Stock format)
                if len(match) >= 8 and match.isdigit():
                    video_ids.add(match)
        
        self.logger.info(f"Found {len(video_ids)} unique video IDs in HTML")
        return list(video_ids)

    def _parse_json_data(self, data: dict) -> List[Dict]:
        """Parse JSON data to extract video information."""
        videos = []
        
        # Try different JSON structures
        search_paths = [
            ['search', 'results'],
            ['searchResults'],
            ['data', 'search', 'results'],
            ['assets'],
            ['items'],
        ]
        
        for path in search_paths:
            current = data
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    current = None
                    break
            
            if current:
                if isinstance(current, dict):
                    # Handle dict of items
                    for item_id, item_data in current.items():
                        video = self._extract_video_info(item_data, item_id)
                        if video:
                            videos.append(video)
                elif isinstance(current, list):
                    # Handle list of items
                    for i, item_data in enumerate(current):
                        video = self._extract_video_info(item_data, str(i))
                        if video:
                            videos.append(video)
                
                if videos:
                    break
        
        return videos

    def _extract_video_info(self, item_data: dict, item_id: str) -> Optional[Dict]:
        """Extract video information from item data."""
        if not isinstance(item_data, dict):
            return None
        
        # Check if this is a video
        asset_type = item_data.get('asset_type', '').lower()
        content_type = item_data.get('content_type', '').lower()
        media_type = item_data.get('media_type', '').lower()
        
        if not any(vid_type in [asset_type, content_type, media_type] for vid_type in ['video', 'videos', 'motion']):
            return None
        
        # Extract the actual video ID from the item data
        video_id = None
        id_fields = ['id', 'asset_id', 'video_id', 'content_id']
        
        for field in id_fields:
            potential_id = item_data.get(field)
            if potential_id and (isinstance(potential_id, (str, int))):
                id_str = str(potential_id)
                # Check if it looks like an Adobe Stock video ID (8+ digits)
                if id_str.isdigit() and len(id_str) >= 8:
                    video_id = id_str
                    break
        
        # If no proper video ID found, use the item_id as fallback
        if not video_id:
            video_id = item_id
        
        # Construct the watermarked download URL
        watermarked_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
        
        video_info = {
            'id': video_id,
            'title': item_data.get('title', item_data.get('name', f'Adobe_Stock_Video_{video_id}')),
            'thumbnail_url': item_data.get('thumbnail_500_url', item_data.get('thumbnail_url')),
            'preview_url': watermarked_url,
            'comp_url': watermarked_url,
            'description': item_data.get('description', ''),
            'tags': item_data.get('keywords', item_data.get('tags', []))
        }
        
        return video_info

    def _extract_video_data_soup(self, html_content: str) -> List[Dict]:
        """
        Use BeautifulSoup to extract video data from HTML.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of video data dictionaries
        """
        videos = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for video elements with data attributes
            video_selectors = [
                '[data-video-preview-url]',
                '[data-comp-url]',
                '.js-glyph-video',
                '.video-thumbnail',
                '[data-asset-type="Videos"]',
                'video',
                '.search-result[data-asset-type*="video" i]'
            ]
            
            for selector in video_selectors:
                elements = soup.select(selector)
                for i, element in enumerate(elements):
                    video_data = self._extract_element_data(element, f"soup_{selector}_{i}")
                    if video_data:
                        videos.append(video_data)
            
            if videos:
                self.logger.info(f"BeautifulSoup found {len(videos)} videos")
            
        except Exception as e:
            self.logger.error(f"Error in BeautifulSoup parsing: {e}")
        
        return videos[:20]  # Limit results

    def _extract_element_data(self, element, element_id: str) -> Optional[Dict]:
        """Extract video data from a BeautifulSoup element."""
        # Get all data attributes
        attrs = element.attrs
        
        # Look for video ID in various attributes
        video_id = None
        id_attrs = [
            'data-asset-id', 'data-video-id', 'data-id', 'id', 
            'data-content-id', 'asset-id', 'video-id'
        ]
        
        for attr in id_attrs:
            potential_id = attrs.get(attr)
            if potential_id:
                # Clean up the ID (remove prefixes like 'asset-')
                clean_id = re.sub(r'^(asset-|video-)', '', potential_id)
                if clean_id.isdigit() and len(clean_id) >= 8:
                    video_id = clean_id
                    break
        
        # If no video ID found in attributes, try to extract from URLs or text
        if not video_id:
            # Look for IDs in href or src attributes
            for attr in ['href', 'src', 'data-src']:
                url = attrs.get(attr, '')
                if url:
                    # Extract ID from URLs like /video/123456789 or asset/123456789
                    id_match = re.search(r'/(?:video|asset)/(\d{8,})', url)
                    if id_match:
                        video_id = id_match.group(1)
                        break
        
        # Use element_id as fallback
        if not video_id:
            # Try to extract numeric ID from element_id
            id_match = re.search(r'(\d{8,})', element_id)
            if id_match:
                video_id = id_match.group(1)
            else:
                video_id = element_id
        
        # Construct the watermarked download URL
        watermarked_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
        
        # Extract title
        title = (attrs.get('data-title') or 
                attrs.get('alt') or 
                attrs.get('title') or 
                element.get_text(strip=True) or 
                f"Adobe_Stock_Video_{video_id}")
        
        return {
            'id': video_id,
            'title': title[:100],  # Limit title length
            'thumbnail_url': attrs.get('data-thumbnail-url'),
            'preview_url': watermarked_url,
            'comp_url': watermarked_url,
            'description': attrs.get('data-description', ''),
            'tags': []
        }

    def _extract_video_data_regex(self, html_content: str) -> List[Dict]:
        """
        Fallback method to extract video data using regex patterns.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of video data dictionaries
        """
        videos = []
        video_ids = set()  # Use set to avoid duplicates
        
        # Look for video IDs in various patterns (similar to _extract_video_ids_from_html but broader)
        video_id_patterns = [
            r'data-asset-id="(\d{8,})"',
            r'data-video-id="(\d{8,})"',
            r'data-id="(\d{8,})"',
            r'id="asset-(\d{8,})"',
            r'asset-id-(\d{8,})',
            r'/video/(\d{8,})',
            r'/asset/(\d{8,})',
            r'asset_id["\']?\s*:\s*["\']?(\d{8,})["\']?',
            r'"id":\s*"?(\d{8,})"?',
            r'"asset_id":\s*"?(\d{8,})"?',
            r'stock\.adobe\.com/.*?/(\d{8,})',
            r'Download/Watermarked/(\d{8,})',
            # Additional patterns for Adobe Stock video IDs
            r'video-(\d{8,})',
            r'content-(\d{8,})',
            r'media-(\d{8,})',
        ]
        
        for i, pattern in enumerate(video_id_patterns):
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                # Ensure the ID is at least 8 digits (typical Adobe Stock format)
                if len(match) >= 8 and match.isdigit():
                    video_ids.add(match)
        
        # Convert to list and create video data structures
        for j, video_id in enumerate(video_ids):
            watermarked_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
            video_info = {
                'id': video_id,
                'title': f'Adobe_Stock_Video_{video_id}',
                'thumbnail_url': None,
                'preview_url': watermarked_url,
                'comp_url': watermarked_url,
                'description': '',
                'tags': []
            }
            videos.append(video_info)
        
        if videos:
            self.logger.info(f"Regex extraction found {len(videos)} video IDs")
        
        return videos[:20]  # Limit fallback results

    def download_video(self, video_data: Dict, filename: Optional[str] = None, query_prefix: Optional[str] = None, index: Optional[int] = None) -> bool:
        """
        Download a video thumbnail.
        
        Args:
            video_data: Video data dictionary
            filename: Optional custom filename
            query_prefix: Optional query-based prefix for filename
            index: Optional index for sequential naming
            
        Returns:
            True if download successful, False otherwise
        """
        # Get the video ID and construct the watermarked download URL
        video_id = video_data.get('id')
        if not video_id:
            self.logger.warning("No video ID found in video data")
            return False
        
        # Use watermarked download URL - prioritize comp_url if it exists, otherwise construct it
        download_url = video_data.get('comp_url') or video_data.get('preview_url')
        
        # If no URL is provided or it doesn't match the watermarked pattern, construct it
        if not download_url or 'Download/Watermarked/' not in download_url:
            download_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
            self.logger.info(f"Constructed watermarked download URL: {download_url}")
        
        # Create filename
        if not filename:
            if query_prefix is not None and index is not None:
                # Use query-based naming: query_0.mp4, query_1.mp4, etc.
                extension = '.mp4'  # Adobe Stock videos are typically mp4
                filename = f"{query_prefix}_{index}{extension}"
            else:
                # Fall back to original naming scheme
                safe_title = re.sub(r'[^\w\s-]', '', video_data.get('title', f'Adobe_Stock_Video_{video_id}'))
                safe_title = re.sub(r'[-\s]+', '_', safe_title)
                extension = '.mp4'  # Adobe Stock videos are typically mp4
                filename = f"{video_id}_{safe_title}{extension}"
        
        filepath = self.download_dir / filename
        
        # Skip if file already exists
        if filepath.exists():
            self.logger.info(f"File {filename} already exists, skipping...")
            return True
        
        try:
            self.logger.info(f"Downloading {filename} from {download_url}")
            
            # Use the session with proper headers for Adobe Stock
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Check if we got a valid video file
            content_type = response.headers.get('content-type', '').lower()
            if 'video' not in content_type and 'application/octet-stream' not in content_type:
                self.logger.warning(f"Unexpected content type for {filename}: {content_type}")
                # Continue anyway as Adobe Stock might return different content types
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Check if the downloaded file has a reasonable size
            file_size = filepath.stat().st_size
            if file_size < 1024:  # Less than 1KB might indicate an error
                self.logger.warning(f"Downloaded file {filename} is very small ({file_size} bytes) - might be an error page")
                # Don't delete automatically, let the user decide
            
            self.logger.info(f"Successfully downloaded {filename} ({file_size} bytes)")
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Error downloading {filename}: {e}")
            if filepath.exists():
                filepath.unlink()  # Remove partial file
            return False

    def scrape_and_download(self, query: str, count: int = 10) -> int:
        """
        Search for videos and download them.
        
        Args:
            query: Search query string
            count: Number of videos to download
            
        Returns:
            Number of successfully downloaded videos
        """
        self.logger.info(f"Starting scrape for query: '{query}', count: {count}")
        
        # Check authentication if required
        if self.use_auth:
            if not self.authenticated:
                self.logger.info("Authentication required but not completed. Starting browser login...")
                if not self.authenticate_with_browser():
                    self.logger.error("Authentication failed. Cannot proceed.")
                    return 0
            else:
                # Verify existing authentication is still valid
                if not self.is_authenticated():
                    self.logger.info("Existing authentication expired. Starting browser login...")
                    if not self.authenticate_with_browser():
                        self.logger.error("Re-authentication failed. Cannot proceed.")
                        return 0
        
        # Create a clean directory name from the query
        clean_query = re.sub(r'[^\w\s-]', '', query)  # Remove special characters
        clean_query = re.sub(r'[-\s]+', '_', clean_query)  # Replace spaces/hyphens with underscores
        clean_query = clean_query.lower().strip('_')  # Lowercase and remove leading/trailing underscores
        
        # Create query-specific subdirectory
        query_dir = self.download_dir / clean_query
        query_dir.mkdir(exist_ok=True)
        
        # Create/update metadata file with query information
        metadata_file = query_dir / "query_metadata.json"
        metadata = {
            "original_query": query,
            "clean_query": clean_query,
            "authenticated": self.authenticated,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }
        
        # If metadata file exists, preserve creation time and update last_updated
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    existing_metadata = json.load(f)
                    metadata["created_at"] = existing_metadata.get("created_at", metadata["created_at"])
            except (json.JSONDecodeError, KeyError):
                # If existing file is corrupted, start fresh
                pass
        
        # Write metadata file
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Created/updated metadata file: {metadata_file}")
        except Exception as e:
            self.logger.warning(f"Failed to create metadata file: {e}")
        
        # Temporarily update the download directory for this search
        original_download_dir = self.download_dir
        self.download_dir = query_dir
        
        self.logger.info(f"Downloads will be saved to: {query_dir}")
        
        # Check for existing files to determine starting index
        existing_files = list(query_dir.glob(f"{clean_query}_*.mp4")) + \
                        list(query_dir.glob(f"{clean_query}_*.mov")) + \
                        list(query_dir.glob(f"{clean_query}_*.webm"))
        
        # Extract existing indices
        existing_indices = set()
        for file_path in existing_files:
            filename = file_path.stem  # Get filename without extension
            if filename.startswith(f"{clean_query}_"):
                try:
                    index_str = filename[len(f"{clean_query}_"):]
                    index = int(index_str)
                    existing_indices.add(index)
                except ValueError:
                    continue
        
        start_index = max(existing_indices) + 1 if existing_indices else 0
        existing_count = len(existing_indices)
        
        if existing_count > 0:
            self.logger.info(f"Found {existing_count} existing files. Starting new downloads from index {start_index}")
        
        # Calculate how many new videos we need
        needed_count = count - existing_count if count > existing_count else 0
        
        if needed_count <= 0:
            self.logger.info(f"Already have {existing_count} files, which meets or exceeds requested count of {count}")
            return existing_count
        
        try:
            # Search for videos (get extra to account for potential duplicates)
            search_limit = needed_count * 3  # Get 3x more to account for duplicates
            videos = self.search_videos(query, search_limit)
            
            if not videos:
                self.logger.warning("No videos found for the given query")
                return existing_count
            
            self.logger.info(f"Found {len(videos)} videos to process")
            
            # Download videos with query-based naming, starting from the appropriate index
            successful_downloads = 0
            current_index = start_index
            
            for video in videos:
                if successful_downloads >= needed_count:
                    break
                    
                self.logger.info(f"Processing video {successful_downloads + 1}/{needed_count}: {video['title']}")
                
                # Use query-based naming with current index
                if self.download_video(video, query_prefix=clean_query, index=current_index):
                    successful_downloads += 1
                    current_index += 1
                else:
                    # If download failed, still increment index to avoid conflicts
                    current_index += 1
                
                # Rate limiting between downloads
                if successful_downloads < needed_count:
                    time.sleep(self.delay)
            
            total_files = existing_count + successful_downloads
            self.logger.info(f"Download complete. {successful_downloads} new videos downloaded. Total: {total_files}/{count}")
            
            # Update metadata with download completion info
            try:
                metadata["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                metadata["total_videos_downloaded"] = total_files
                metadata["last_download_session"] = {
                    "requested_count": count,
                    "new_downloads": successful_downloads,
                    "session_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                }
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.warning(f"Failed to update metadata file: {e}")
            
            return total_files
            
        finally:
            # Restore original download directory
            self.download_dir = original_download_dir


def main():
    parser = argparse.ArgumentParser(description='Adobe Stock Video Thumbnail Scraper')
    parser.add_argument('--query', '-q', required=True, help='Search query for videos')
    parser.add_argument('--count', '-c', type=int, default=10, help='Number of videos to download (default: 10)')
    parser.add_argument('--output', '-o', default='downloads', help='Output directory (default: downloads)')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--login', action='store_true', help='Use browser-based authentication')
    
    args = parser.parse_args()
    
    # Create scraper instance
    scraper = AdobeStockScraper(download_dir=args.output, delay=args.delay, use_auth=args.login)
    
    # Create clean query name for the subdirectory
    clean_query = re.sub(r'[^\w\s-]', '', args.query)
    clean_query = re.sub(r'[-\s]+', '_', clean_query)
    clean_query = clean_query.lower().strip('_')
    
    # Run scraping
    try:
        if args.login:
            print("\n🔐 AUTHENTICATION MODE ENABLED")
            print("You will be prompted to log in through your browser.")
            print("Make sure you have Chrome installed and chromedriver available.")
            print("")
        
        downloaded_count = scraper.scrape_and_download(args.query, args.count)
        query_dir = f"{args.output}/{clean_query}"
        
        if downloaded_count > 0:
            print(f"\n✅ Scraping completed! Downloaded {downloaded_count} videos to '{query_dir}' directory.")
        else:
            print(f"\n❌ No videos were downloaded. Check authentication or try different search terms.")
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main() 