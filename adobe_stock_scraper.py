#!/usr/bin/env python3
"""
Adobe Stock Video Thumbnail Scraper

This script scrapes and downloads thumbnail videos from Adobe Stock
based on a search query. Authentication is required by default.

Usage:
    python adobe_stock_scraper.py --query "nature landscape" --count 10
    python adobe_stock_scraper.py --query "ocean waves" --count 5 --no-login
    
    # With filtering options:
    python adobe_stock_scraper.py --query "nature" --count 10 --max-duration 30 --exclude-titles "advertisement" "promo"
    python adobe_stock_scraper.py --query "city" --count 20 --exclude-titles "logo" "text" "watermark"
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
    def __init__(self, download_dir: str = "downloads", delay: float = 1.0, use_auth: bool = True, 
                 max_duration_seconds: int = None, exclude_title_patterns: List[str] = None):
        """
        Initialize the Adobe Stock scraper.
        
        Args:
            download_dir: Directory to save downloaded videos
            delay: Delay between requests in seconds
            use_auth: Whether to use browser-based authentication (default: True)
            max_duration_seconds: Maximum video duration in seconds (None for no limit)
            exclude_title_patterns: List of text patterns to exclude from video titles (case-insensitive)
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.delay = delay
        self.use_auth = use_auth
        self.max_duration_seconds = max_duration_seconds
        self.exclude_title_patterns = exclude_title_patterns or []
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
        
        # Log filtering settings
        if self.max_duration_seconds:
            self.logger.info(f"Video duration filter: max {self.max_duration_seconds} seconds")
        if self.exclude_title_patterns:
            self.logger.info(f"Title exclusion patterns: {self.exclude_title_patterns}")
        
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
                # Success - likely authenticated or public access
                self.authenticated = True
                return True
            else:
                # Non-200 status might indicate auth issues
                self.authenticated = False
                return False
                
        except requests.RequestException as e:
            self.logger.error(f"Error checking authentication: {e}")
            return False

    def should_filter_video(self, video_data: Dict) -> bool:
        """
        Check if a video should be filtered out based on title patterns and duration.
        
        Args:
            video_data: Video data dictionary
            
        Returns:
            True if video should be filtered out, False otherwise
        """
        title = video_data.get('title', '').lower()
        
        # Check title exclusion patterns
        for pattern in self.exclude_title_patterns:
            if pattern.lower() in title:
                self.logger.info(f"Filtering out video '{video_data.get('title', '')}' - matches exclusion pattern: '{pattern}'")
                return True
        
        # Check duration if available (Note: Adobe Stock may not provide duration in search results)
        duration = video_data.get('duration_seconds')
        if self.max_duration_seconds and duration:
            if duration > self.max_duration_seconds:
                self.logger.info(f"Filtering out video '{video_data.get('title', '')}' - duration {duration}s exceeds limit of {self.max_duration_seconds}s")
                return True
        
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
        
        # Method 1: Look for video data in embedded JavaScript
        videos_from_js = self._extract_videos_from_javascript(html_content)
        if videos_from_js:
            videos.extend(videos_from_js)
            self.logger.info(f"Extracted {len(videos_from_js)} videos from JavaScript data")
            return videos
        
        # Method 2: Look for various JSON data patterns (fallback)
        json_patterns = [
            (r'window\.__INITIAL_STATE__\s*=\s*({.*?});', 'INITIAL_STATE'),
            (r'window\.INITIAL_STATE\s*=\s*({.*?});', 'INITIAL_STATE_alt'),
            (r'__APOLLO_STATE__["\']?\s*:\s*({.*?})', 'APOLLO_STATE'),
            (r'window\.APOLLO_STATE\s*=\s*({.*?});', 'APOLLO_STATE_alt'),
            (r'"searchResults":\s*({.*?})', 'searchResults'),
            (r'"assets":\s*(\[.*?\])', 'assets'),
            (r'"videos":\s*(\[.*?\])', 'videos'),
            (r'"results":\s*(\[.*?\])', 'results'),
        ]
        
        for pattern, name in json_patterns:
            json_match = re.search(pattern, html_content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    extracted = self._parse_json_data(data)
                    if extracted:
                        videos.extend(extracted)
                        self.logger.info(f"Extracted {len(extracted)} videos from JSON pattern: {name}")
                        break
                except json.JSONDecodeError as e:
                    self.logger.debug(f"Error parsing JSON with pattern {name}: {e}")
                    continue
        
        # Method 4: Use BeautifulSoup for HTML parsing (fallback)
        if not videos:
            videos = self._extract_video_data_soup(html_content)
        
        # Method 5: Regex fallback for direct video URLs (fallback)
        if not videos:
            videos = self._extract_video_data_regex(html_content)
        
        return videos

    def _extract_videos_from_javascript(self, html_content: str) -> List[Dict]:
        """
        Extract video data from embedded JavaScript in Adobe Stock pages.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of video data dictionaries
        """
        videos = []
        
        # Look for the specific video data structure: "video_id":{"content_id":video_id,"title":"title"...}
        # Pattern 1: More specific pattern for the video data
        pattern1 = r'"(\d{8,})":\s*\{\s*"[^"]*":\s*"[^"]*",\s*"content_id":\s*\1[^}]*?"title":\s*"([^"]+)"[^}]*?"comp_file_path":\s*"([^"]+)"[^}]*?\}'
        
        matches = re.findall(pattern1, html_content, re.DOTALL)
        
        for video_id, title, comp_path in matches:
            video_info = {
                'id': video_id,
                'title': title[:150],  # Limit title length
                'thumbnail_url': None,
                'preview_url': comp_path,
                'comp_url': comp_path,
                'description': '',
                'tags': []
            }
            videos.append(video_info)
        
        # Pattern 2: Simpler pattern just looking for title associated with content_id
        if not videos:
            pattern2 = r'"content_id":\s*(\d{8,})[^}]*?"title":\s*"([^"]+)"[^}]*?"comp_file_path":\s*"([^"]+)"'
            
            matches = re.findall(pattern2, html_content, re.DOTALL)
            
            for video_id, title, comp_path in matches:
                video_info = {
                    'id': video_id,
                    'title': title[:150],  # Limit title length
                    'thumbnail_url': None,
                    'preview_url': comp_path,
                    'comp_url': comp_path,
                    'description': '',
                    'tags': []
                }
                videos.append(video_info)
        
        # Pattern 3: Even simpler - just find title near content_id
        if not videos:
            pattern3 = r'"content_id":\s*(\d{8,})[^}]{1,500}?"title":\s*"([^"]+)"'
            
            matches = re.findall(pattern3, html_content, re.DOTALL)
            
            for video_id, title in matches:
                video_info = {
                    'id': video_id,
                    'title': title[:150],  # Limit title length
                    'thumbnail_url': None,
                    'preview_url': f'https://stock.adobe.com/Download/Watermarked/{video_id}',
                    'comp_url': f'https://stock.adobe.com/Download/Watermarked/{video_id}',
                    'description': '',
                    'tags': []
                }
                videos.append(video_info)
        
        # Remove duplicates by video_id
        seen_ids = set()
        unique_videos = []
        for video in videos:
            if video['id'] not in seen_ids:
                seen_ids.add(video['id'])
                unique_videos.append(video)
        
        self.logger.info(f"Found {len(unique_videos)} unique videos from JavaScript parsing")
        return unique_videos

    def _extract_video_ids_and_titles_from_html(self, html_content: str) -> List[Dict]:
        """
        Extract Adobe Stock video IDs and their corresponding titles from HTML content.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of video data dictionaries with IDs and titles
        """
        videos = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for various video container patterns in Adobe Stock
            video_selectors = [
                # Common Adobe Stock video result containers
                '[data-asset-id]',
                '.search-result',
                '.asset-item',
                '.thumbnail-container',
                '.video-thumbnail',
                '.js-glyph-video',
                '[data-id]',
                '.asset-card',
                '.media-item'
            ]
            
            seen_ids = set()
            
            for selector in video_selectors:
                elements = soup.select(selector)
                for element in elements:
                    video_data = self._extract_video_data_from_element(element)
                    if video_data and video_data['id'] not in seen_ids:
                        seen_ids.add(video_data['id'])
                        videos.append(video_data)
            
            # If we didn't find videos with the above selectors, try a more general approach
            if not videos:
                # Look for any elements with video-related data attributes
                all_elements = soup.find_all(attrs={'data-asset-id': True})
                all_elements.extend(soup.find_all(attrs={'data-id': True}))
                
                for element in all_elements:
                    video_data = self._extract_video_data_from_element(element)
                    if video_data and video_data['id'] not in seen_ids:
                        seen_ids.add(video_data['id'])
                        videos.append(video_data)
            
            self.logger.info(f"Found {len(videos)} unique videos with titles from HTML parsing")
            
        except Exception as e:
            self.logger.error(f"Error in HTML parsing for video titles: {e}")
            # Fallback to just IDs if title extraction fails
            video_ids = self._extract_video_ids_from_html(html_content)
            for video_id in video_ids:
                videos.append({
                    'id': video_id,
                    'title': f'Adobe_Stock_Video_{video_id}',
                    'thumbnail_url': None,
                    'preview_url': f'https://stock.adobe.com/Download/Watermarked/{video_id}',
                    'comp_url': f'https://stock.adobe.com/Download/Watermarked/{video_id}',
                    'description': '',
                    'tags': []
                })
        
        return videos
    
    def _extract_video_data_from_element(self, element) -> Optional[Dict]:
        """
        Extract video data (ID, title, etc.) from a single HTML element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Video data dictionary or None
        """
        # Extract video ID
        video_id = None
        id_attrs = ['data-asset-id', 'data-id', 'data-video-id', 'id', 'data-content-id']
        
        for attr in id_attrs:
            potential_id = element.get(attr)
            if potential_id:
                # Clean up the ID (remove prefixes like 'asset-')
                clean_id = re.sub(r'^(asset-|video-)', '', str(potential_id))
                if clean_id.isdigit() and len(clean_id) >= 8:
                    video_id = clean_id
                    break
        
        if not video_id:
            return None
        
        # Extract title from various possible locations
        title = None
        
        # Try multiple strategies to find the title
        title_strategies = [
            # 1. Direct data attributes
            lambda el: el.get('data-title'),
            lambda el: el.get('title'),
            lambda el: el.get('alt'),
            lambda el: el.get('aria-label'),
            
            # 2. Look for title in child elements
            lambda el: self._find_title_in_children(el),
            
            # 3. Look for title in nearby elements (siblings)
            lambda el: self._find_title_in_siblings(el),
            
            # 4. Extract from various text content
            lambda el: el.get_text(strip=True) if el.get_text(strip=True) and len(el.get_text(strip=True)) > 5 else None
        ]
        
        for strategy in title_strategies:
            try:
                title = strategy(element)
                if title and len(title.strip()) > 0 and not title.isdigit():
                    # Clean up the title
                    title = title.strip()
                    # Skip if title is just the video ID or too generic
                    if title != video_id and 'adobe' not in title.lower() and len(title) > 2:
                        break
                    else:
                        title = None
            except:
                continue

        # If no good title found, use fallback
        if not title:
            title = f'Adobe_Stock_Video_{video_id}'
        
        # Extract duration if available
        duration_seconds = None
        duration_attrs = ['data-duration', 'data-length', 'duration', 'data-time']
        for attr in duration_attrs:
            duration_value = element.get(attr)
            if duration_value:
                try:
                    # Try to parse as seconds
                    if isinstance(duration_value, str):
                        duration_str = duration_value.strip().lower()
                        if duration_str.endswith('s'):
                            duration_seconds = int(duration_str[:-1])
                            break
                        elif ':' in duration_str:
                            # Parse MM:SS format
                            parts = duration_str.split(':')
                            if len(parts) == 2:
                                minutes, seconds = parts
                                duration_seconds = int(minutes) * 60 + int(seconds)
                                break
                        elif duration_str.isdigit():
                            duration_seconds = int(duration_str)
                            break
                    elif isinstance(duration_value, (int, float)):
                        duration_seconds = int(duration_value)
                        break
                except (ValueError, TypeError):
                    continue
        
        # Construct video data
        watermarked_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
        
        return {
            'id': video_id,
            'title': title[:150],  # Limit title length
            'thumbnail_url': element.get('data-thumbnail-url') or element.get('src'),
            'preview_url': watermarked_url,
            'comp_url': watermarked_url,
            'description': element.get('data-description', ''),
            'tags': [],
            'duration_seconds': duration_seconds
        }
    
    def _find_title_in_children(self, element) -> Optional[str]:
        """Find title in child elements."""
        title_selectors = [
            '.title', '.name', '.caption', '.description',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            '[class*="title"]', '[class*="name"]', '[class*="caption"]',
            'figcaption', '.video-title', '.asset-title'
        ]
        
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                text = title_elem.get_text(strip=True)
                if text and len(text) > 2:
                    return text
        
        return None
    
    def _find_title_in_siblings(self, element) -> Optional[str]:
        """Find title in sibling elements."""
        # Look at next few siblings for title information
        if element.parent:
            siblings = element.parent.find_all(['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for sibling in siblings[:5]:  # Check first 5 siblings
                text = sibling.get_text(strip=True)
                if text and len(text) > 5 and len(text) < 200:
                    # Skip if it looks like a video ID or generic text
                    if not text.isdigit() and 'adobe' not in text.lower():
                        return text
        
        return None

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
        
        # Handle if data is a list directly
        if isinstance(data, list):
            for i, item_data in enumerate(data):
                video = self._extract_video_info(item_data, str(i))
                if video:
                    videos.append(video)
            return videos
        
        # Try different JSON structures
        search_paths = [
            ['search', 'results'],
            ['searchResults'],
            ['data', 'search', 'results'],
            ['assets'],
            ['items'],
            ['results'],
            ['videos'],
            ['data', 'assets'],
            ['data', 'videos'],
            ['data', 'results'],
            ['response', 'results'],
            ['content', 'results'],
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
        
        # If no videos found with standard paths, try to find any nested video data
        if not videos:
            videos = self._recursive_search_for_videos(data)
        
        return videos
    
    def _recursive_search_for_videos(self, data, max_depth=3, current_depth=0) -> List[Dict]:
        """Recursively search for video data in nested JSON structures."""
        videos = []
        
        if current_depth >= max_depth:
            return videos
        
        if isinstance(data, dict):
            # Look for video-specific keys
            video_keys = ['id', 'asset_id', 'video_id', 'title', 'name']
            has_video_data = any(key in data for key in video_keys)
            
            if has_video_data:
                # Check if this looks like a video item
                asset_type = str(data.get('asset_type', '')).lower()
                content_type = str(data.get('content_type', '')).lower()
                media_type = str(data.get('media_type', '')).lower()
                
                is_video = any(vid_type in [asset_type, content_type, media_type] 
                              for vid_type in ['video', 'videos', 'motion'])
                
                # Also check for video URLs or IDs that suggest it's a video
                has_video_url = any('video' in str(data.get(key, '')).lower() 
                                  for key in ['url', 'preview_url', 'download_url'])
                
                if is_video or has_video_url or 'video' in str(data.get('title', '')).lower():
                    video = self._extract_video_info(data, str(data.get('id', data.get('asset_id', 'unknown'))))
                    if video:
                        videos.append(video)
            
            # Continue searching in nested structures
            for key, value in data.items():
                if isinstance(value, (dict, list)) and key not in ['parent', 'children']:
                    videos.extend(self._recursive_search_for_videos(value, max_depth, current_depth + 1))
        
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    videos.extend(self._recursive_search_for_videos(item, max_depth, current_depth + 1))
        
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
        
        # Extract duration information if available
        duration_seconds = None
        duration_fields = ['duration', 'duration_seconds', 'length', 'length_seconds', 'time']
        for field in duration_fields:
            if field in item_data:
                try:
                    duration_value = item_data[field]
                    if isinstance(duration_value, (int, float)):
                        duration_seconds = int(duration_value)
                        break
                    elif isinstance(duration_value, str):
                        # Try to parse duration string (e.g., "30s", "1:30", "90")
                        duration_str = duration_value.strip().lower()
                        if duration_str.endswith('s'):
                            duration_seconds = int(duration_str[:-1])
                            break
                        elif ':' in duration_str:
                            # Parse MM:SS format
                            parts = duration_str.split(':')
                            if len(parts) == 2:
                                minutes, seconds = parts
                                duration_seconds = int(minutes) * 60 + int(seconds)
                                break
                        elif duration_str.isdigit():
                            duration_seconds = int(duration_str)
                            break
                except (ValueError, TypeError):
                    continue
        
        # Construct the watermarked download URL
        watermarked_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
        
        video_info = {
            'id': video_id,
            'title': item_data.get('title', item_data.get('name', f'Adobe_Stock_Video_{video_id}')),
            'thumbnail_url': item_data.get('thumbnail_500_url', item_data.get('thumbnail_url')),
            'preview_url': watermarked_url,
            'comp_url': watermarked_url,
            'description': item_data.get('description', ''),
            'tags': item_data.get('keywords', item_data.get('tags', [])),
            'duration_seconds': duration_seconds
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
        
        # Extract duration if available
        duration_seconds = None
        duration_attrs = ['data-duration', 'data-length', 'duration', 'data-time']
        for attr in duration_attrs:
            duration_value = attrs.get(attr)
            if duration_value:
                try:
                    # Try to parse as seconds
                    if isinstance(duration_value, str):
                        duration_str = duration_value.strip().lower()
                        if duration_str.endswith('s'):
                            duration_seconds = int(duration_str[:-1])
                            break
                        elif ':' in duration_str:
                            # Parse MM:SS format
                            parts = duration_str.split(':')
                            if len(parts) == 2:
                                minutes, seconds = parts
                                duration_seconds = int(minutes) * 60 + int(seconds)
                                break
                        elif duration_str.isdigit():
                            duration_seconds = int(duration_str)
                            break
                    elif isinstance(duration_value, (int, float)):
                        duration_seconds = int(duration_value)
                        break
                except (ValueError, TypeError):
                    continue
        
        return {
            'id': video_id,
            'title': title[:100],  # Limit title length
            'thumbnail_url': attrs.get('data-thumbnail-url'),
            'preview_url': watermarked_url,
            'comp_url': watermarked_url,
            'description': attrs.get('data-description', ''),
            'tags': [],
            'duration_seconds': duration_seconds
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
                'tags': [],
                'duration_seconds': None
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
            # Extract and clean the Adobe Stock title for use as filename
            adobe_title = video_data.get('title', f'Adobe_Stock_Video_{video_id}')
            
            # Clean the title to make it safe for filesystem
            safe_title = re.sub(r'[^\w\s-]', '', adobe_title)  # Remove special characters except spaces and hyphens
            safe_title = re.sub(r'[-\s]+', '_', safe_title)    # Replace spaces and hyphens with underscores
            safe_title = safe_title.strip('_')                 # Remove leading/trailing underscores
            
            # Limit title length to avoid filesystem issues
            if len(safe_title) > 100:
                safe_title = safe_title[:100].rstrip('_')
            
            # Ensure we have a valid filename
            if not safe_title or safe_title.isspace():
                safe_title = f'Adobe_Stock_Video_{video_id}'
            
            extension = '.mp4'  # Adobe Stock videos are typically mp4
            
            # Use Adobe Stock title as the primary filename
            filename = f"{safe_title}{extension}"
            
            # Check if file with this name already exists, if so, append video ID to make it unique
            base_filepath = self.download_dir / filename
            if base_filepath.exists():
                filename = f"{safe_title}_{video_id}{extension}"
        
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
            "filtering_settings": {
                "max_duration_seconds": self.max_duration_seconds,
                "exclude_title_patterns": self.exclude_title_patterns
            },
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
        
        # Check for existing video files in the directory (any video files, since we now use title-based naming)
        existing_files = list(query_dir.glob("*.mp4")) + \
                        list(query_dir.glob("*.mov")) + \
                        list(query_dir.glob("*.webm")) + \
                        list(query_dir.glob("*.avi")) + \
                        list(query_dir.glob("*.mkv"))
        
        # Filter out metadata files
        existing_files = [f for f in existing_files if f.name != "query_metadata.json"]
        existing_count = len(existing_files)
        
        if existing_count > 0:
            self.logger.info(f"Found {existing_count} existing video files in directory")
        
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
            
            # Apply filtering to videos
            filtered_videos = []
            filtered_count = 0
            
            for video in videos:
                if self.should_filter_video(video):
                    filtered_count += 1
                    continue
                filtered_videos.append(video)
            
            if filtered_count > 0:
                self.logger.info(f"Filtered out {filtered_count} videos based on exclusion criteria")
            
            self.logger.info(f"Processing {len(filtered_videos)} videos after filtering")
            
            # Download videos using title-based naming
            successful_downloads = 0
            
            for video in filtered_videos:
                if successful_downloads >= needed_count:
                    break
                    
                self.logger.info(f"Processing video {successful_downloads + 1}/{needed_count}: {video['title']}")
                
                # Use title-based naming (no longer passing query_prefix and index)
                if self.download_video(video):
                    successful_downloads += 1
                
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
                    "videos_found": len(videos),
                    "videos_filtered_out": filtered_count,
                    "videos_processed": len(filtered_videos),
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
    parser = argparse.ArgumentParser(description='Adobe Stock Video Thumbnail Scraper (Authentication Required)')
    parser.add_argument('--query', '-q', required=True, help='Search query for videos')
    parser.add_argument('--count', '-c', type=int, default=10, help='Number of videos to download (default: 10)')
    parser.add_argument('--output', '-o', default='downloads', help='Output directory (default: downloads)')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--no-login', action='store_true', help='Skip browser-based authentication (may result in 401 errors)')
    parser.add_argument('--max-duration', type=int, help='Maximum video duration in seconds (excludes longer videos)')
    parser.add_argument('--exclude-titles', nargs='*', help='Text patterns to exclude from video titles (case-insensitive)')
    
    args = parser.parse_args()
    
    # Create scraper instance (authentication enabled by default)
    use_auth = not args.no_login  # Reverse the logic - auth is default, --no-login disables it
    scraper = AdobeStockScraper(
        download_dir=args.output, 
        delay=args.delay, 
        use_auth=use_auth,
        max_duration_seconds=args.max_duration,
        exclude_title_patterns=args.exclude_titles or []
    )
    
    # Create clean query name for the subdirectory
    clean_query = re.sub(r'[^\w\s-]', '', args.query)
    clean_query = re.sub(r'[-\s]+', '_', clean_query)
    clean_query = clean_query.lower().strip('_')
    
    # Run scraping
    try:
        if use_auth:
            print("\n🔐 AUTHENTICATION MODE (DEFAULT)")
            print("You will be prompted to log in through your browser.")
            print("Make sure you have Chrome installed and chromedriver available.")
            print("Use --no-login to skip authentication (may result in 401 errors).")
            print("")
        else:
            print("\n⚠️  NO AUTHENTICATION MODE")
            print("Attempting to download without login - this may result in 401 errors.")
            print("Remove --no-login flag to use authentication (recommended).")
            print("")
        
        downloaded_count = scraper.scrape_and_download(args.query, args.count)
        query_dir = f"{args.output}/{clean_query}"
        
        if downloaded_count > 0:
            print(f"\n✅ Scraping completed! Downloaded {downloaded_count} videos to '{query_dir}' directory.")
        else:
            if use_auth:
                print(f"\n❌ No videos were downloaded. Check authentication or try different search terms.")
            else:
                print(f"\n❌ No videos were downloaded. Try using authentication (remove --no-login flag).")
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main() 