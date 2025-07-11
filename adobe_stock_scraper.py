#!/usr/bin/env python3
"""
Adobe Stock Video Thumbnail Scraper

This script scrapes and downloads thumbnail videos from Adobe Stock
based on a search query. Authentication is required by default.

Can also create JSON metadata dictionaries instead of downloading videos.

ENHANCED DUPLICATE CHECKING:
This script now includes comprehensive duplicate checking mechanisms:

1. Cross-Session Duplicate Prevention:
   - Loads existing video IDs from metadata files and filenames
   - Prevents re-downloading videos from previous sessions
   - Tracks video IDs across multiple script runs

2. Intra-Session Duplicate Prevention:
   - Global video ID tracking across all search attempts
   - Prevents processing the same video ID multiple times in one session
   - Enhanced search result deduplication

3. Multi-Level ID Extraction:
   - Extracts video IDs from existing filenames using multiple patterns
   - Reads video mappings from metadata JSON files
   - Handles different filename formats consistently

4. JSON Mode Duplicate Prevention:
   - Checks existing JSON files for duplicate video IDs
   - Prevents including the same videos in multiple JSON outputs
   - Cross-references with previous JSON generations

5. Download-Level Duplicate Checking:
   - Video ID-based duplicate checking (not just filename-based)
   - Checks for existing files with same video ID but different names
   - Robust file existence validation

Usage:
    # Download videos (default mode)
    python adobe_stock_scraper.py --query "nature landscape" --count 10
    python adobe_stock_scraper.py --query "ocean waves" --count 5 --no-login
    
    # Random video scraping - get completely random videos from various categories
    python adobe_stock_scraper.py --random --count 20
    python adobe_stock_scraper.py --random --count 15 --json-output --intended-label "Random Videos"
    python adobe_stock_scraper.py --random --count 10 --max-duration 45 --exclude-titles "watermark"
    
    # Random sampling - search more videos and randomly select from them
    python adobe_stock_scraper.py --query "nature landscape" --count 10 --sample-from 50
    python adobe_stock_scraper.py --query "city skyline" --count 15 --sample-from 100 --json-output --intended-label "Urban Scenes"
    
    # Create JSON metadata instead of downloading
    python adobe_stock_scraper.py --query "nature landscape" --count 10 --json-output --intended-label "Nature Videos"
    python adobe_stock_scraper.py --query "ocean waves" --count 5 --json-output --intended-label "Water Scenes" --no-login
    
    # With filtering options:
    python adobe_stock_scraper.py --query "nature" --count 10 --max-duration 30 --exclude-titles "advertisement" "promo"
    python adobe_stock_scraper.py --query "city" --count 20 --exclude-titles "logo" "text" "watermark" --json-output --intended-label "Urban Scenes"
    python adobe_stock_scraper.py --query "animals" --count 15 --max-size 50M --max-duration 60 --exclude-titles "watermark"
    python adobe_stock_scraper.py --query "technology" --count 10 --max-size 100MB --json-output --intended-label "Tech Videos"
    
    # Random sampling with filtering:
    python adobe_stock_scraper.py --query "wildlife" --count 10 --sample-from 80 --max-duration 45 --exclude-titles "watermark" "stock"
    python adobe_stock_scraper.py --query "business" --count 20 --sample-from 150 --json-output --intended-label "Business Videos" --max-size 75M

JSON Output Format:
    {
      "Intended Label": {
        "Query Used": [
          {
            "id": "stock_video_id",
            "caption": "Adobe stock caption",
            "url": "download URL or preview URL"
          }
        ]
      }
    }
"""

import requests
import json
import os
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
from typing import List, Dict, Optional, Tuple
import logging
from bs4 import BeautifulSoup
import random  # Added for random sampling

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

# Import ignore list functionality
try:
    from add_to_ignore_list import IgnoreListManager
    IGNORE_LIST_AVAILABLE = True
except ImportError:
    IGNORE_LIST_AVAILABLE = False

class AdobeStockScraper:
    def __init__(self, download_dir: str = "downloads", delay: float = 1.0, use_auth: bool = True, 
                 max_duration_seconds: int = None, min_duration_seconds: int = None, exclude_title_patterns: List[str] = None, 
                 json_output: bool = False, intended_label: str = None, max_size_bytes: int = None, sample_from: int = None,
                 ignore_list_path: str = None, query: str = None, random_mode: bool = False, use_ignore_list: bool = True):
        """
        Initialize the Adobe Stock scraper.
        
        Args:
            download_dir: Directory to save downloaded videos
            delay: Delay between requests in seconds
            use_auth: Whether to use browser-based authentication (default: True)
            max_duration_seconds: Maximum video duration in seconds (None for no limit)
            min_duration_seconds: Minimum video duration in seconds (None for no limit)
            exclude_title_patterns: List of text patterns to exclude from video titles (case-insensitive)
            json_output: Whether to create JSON dictionary instead of downloading videos (default: False)
            intended_label: Label to use in JSON output structure (required if json_output is True)
            max_size_bytes: Maximum video file size in bytes (None for no limit)
            sample_from: If specified, search for this many videos and randomly sample the requested count from them (None for no sampling)
            ignore_list_path: Path to the ignore list file (None for auto-detection based on query)
            query: Search query (used to determine query-specific ignore list if ignore_list_path is None)
            random_mode: Whether to scrape completely random videos from various categories (default: False)
            use_ignore_list: Whether to use ignore list functionality (default: True)
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.delay = delay
        self.use_auth = use_auth
        self.max_duration_seconds = max_duration_seconds
        self.min_duration_seconds = min_duration_seconds
        self.exclude_title_patterns = exclude_title_patterns or []
        self.json_output = json_output
        self.intended_label = intended_label
        self.max_size_bytes = max_size_bytes
        self.sample_from = sample_from
        self.random_mode = random_mode
        self.use_ignore_list = use_ignore_list
        self.session = requests.Session()
        self.authenticated = False
        self.cookies_file = Path("adobe_stock_cookies.json")
        self.current_query = query  # Store current query for ignore list determination
        
        # Define categories for random mode
        self.random_categories = [
            # Nature & Landscapes
            "nature", "landscape", "ocean", "mountain", "forest", "sunset", "sunrise", "beach", "lake", "river",
            "desert", "waterfall", "clouds", "sky", "grass", "flowers", "trees", "wildlife", "birds", "animals",
            
            # Urban & Architecture
            "city", "building", "architecture", "street", "urban", "skyscraper", "bridge", "road", "traffic",
            "downtown", "skyline", "construction", "modern", "historic", "transportation",
            
            # Business & Technology
            "business", "office", "meeting", "technology", "computer", "data", "digital", "innovation",
            "finance", "corporate", "workspace", "teamwork", "presentation", "analytics", "startup",
            
            # Lifestyle & People
            "people", "family", "friends", "lifestyle", "health", "fitness", "cooking", "travel",
            "vacation", "celebration", "sports", "exercise", "meditation", "shopping", "education",
            
            # Abstract & Artistic
            "abstract", "motion", "particles", "light", "colors", "artistic", "creative", "design",
            "pattern", "texture", "minimalist", "geometric", "fluid", "energy", "bokeh",
            
            # Food & Drink
            "food", "cooking", "kitchen", "restaurant", "coffee", "wine", "ingredients", "fresh",
            "organic", "healthy", "delicious", "dining", "chef", "recipe", "meal",
            
            # Industry & Science
            "industry", "factory", "manufacturing", "science", "laboratory", "research", "medical",
            "healthcare", "agriculture", "farming", "machinery", "engineering", "innovation",
            
            # Seasonal & Weather
            "spring", "summer", "autumn", "winter", "snow", "rain", "storm", "weather", "seasons",
            "holiday", "christmas", "halloween", "new year", "celebration", "festival"
        ]
        
        # Set up logging early so it can be used throughout initialization
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Load query-specific ignore list (only if ignore list is enabled)
        if self.use_ignore_list:
            self.current_ignored_video_ids = self._load_query_specific_ignore_list(query, ignore_list_path)
        else:
            self.current_ignored_video_ids = set()
        
        # Enhanced duplicate tracking
        self.global_seen_video_ids = set()  # Track all video IDs seen across all operations
        self.existing_video_ids = set()     # Track video IDs from existing files
        
        # Validate JSON mode requirements
        if self.json_output and not self.intended_label:
            raise ValueError("intended_label is required when json_output is True")
        
        # Validate sampling requirements
        if self.sample_from is not None and self.sample_from <= 0:
            raise ValueError("sample_from must be a positive integer when specified")
        
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
        
        # Only log filtering settings if they're actually set
        if self.max_duration_seconds:
            self.logger.debug(f"Video duration filter: max {self.max_duration_seconds} seconds")
        if self.min_duration_seconds:
            self.logger.debug(f"Video duration filter: min {self.min_duration_seconds} seconds")
        if self.max_size_bytes:
            self.logger.debug(f"Video size filter: max {self.max_size_bytes} bytes")
        if self.exclude_title_patterns:
            self.logger.debug(f"Title exclusion patterns: {self.exclude_title_patterns}")
        if self.sample_from:
            self.logger.debug(f"Random sampling: selecting from {self.sample_from} videos")
        if self.random_mode:
            self.logger.debug(f"Random mode: scraping from {len(self.random_categories)} categories")
        if self.json_output:
            self.logger.debug(f"JSON output mode: creating metadata dictionary with label '{self.intended_label}'")
        if not self.use_ignore_list:
            self.logger.debug(f"Ignore list functionality disabled")
        elif len(self.current_ignored_video_ids) > 0:
            ignore_file_info = f" from query-specific ignore list" if query else " from ignore list"
            self.logger.debug(f"Loaded {len(self.current_ignored_video_ids)} ignored video IDs{ignore_file_info}")
    
        # Try to load existing cookies if authentication is requested
        if self.use_auth:
            cookies_loaded = self.load_cookies()
            
            # If cookies couldn't be loaded, trigger browser authentication
            if not cookies_loaded:
                self.logger.info("No existing cookies found. Browser login required...")
                success = self.authenticate_with_browser()
                if not success:
                    self.logger.warning("Browser authentication failed. Continuing without authentication - may result in 401 errors for downloads.")
                    self.authenticated = False

    def get_random_search_queries(self, count: int) -> List[str]:
        """
        Generate random search queries for random mode.
        
        Args:
            count: Number of queries to generate
            
        Returns:
            List of random search queries
        """
        # Create a mix of single categories and combined categories
        queries = []
        
        # Single category queries (70% of the time)
        single_category_count = int(count * 0.7)
        for _ in range(single_category_count):
            queries.append(random.choice(self.random_categories))
        
        # Combined category queries (30% of the time)
        combined_category_count = count - single_category_count
        for _ in range(combined_category_count):
            # Randomly combine 2-3 categories
            num_categories = random.randint(2, 3)
            selected_categories = random.sample(self.random_categories, num_categories)
            queries.append(" ".join(selected_categories))
        
        return queries

    def scrape_random_videos(self, count: int = 10) -> int:
        """
        Scrape completely random videos from various categories.
        
        Args:
            count: Number of videos to download/process
            
        Returns:
            Number of videos downloaded/processed
        """
        print(f"🎲 Random Mode: Scraping {count} random videos from diverse categories")
        
        # Show ignore list information for random mode
        ignore_list_size = len(self.current_ignored_video_ids) if self.use_ignore_list else 0
        if ignore_list_size > 0:
            print(f"🚫 Ignore list contains {ignore_list_size} video IDs - will search more aggressively to find unique videos")
        
        # Handle JSON output mode for random videos
        if self.json_output:
            return self._handle_random_json_output_mode(count)
        
        # Store original download directory
        original_download_dir = self.download_dir
        
        # Create a subdirectory for random videos
        random_dir = self.download_dir / "random_videos"
        random_dir.mkdir(exist_ok=True)
        
        # Update download directory to the random subdirectory
        self.download_dir = random_dir
        
        # Load existing video IDs to prevent duplicates
        existing_video_ids = self.load_existing_video_ids(random_dir)
        
        # Count existing video files
        video_extensions = ['.mp4', '.mov', '.webm', '.avi', '.mkv']
        existing_files = []
        for ext in video_extensions:
            existing_files.extend(random_dir.glob(f"*{ext}"))
        
        # Filter out metadata files
        existing_files = [f for f in existing_files if f.name != "random_metadata.json"]
        existing_count = len(existing_files)
        
        if existing_count > 0:
            print(f"Found {existing_count} existing random videos")
        
        # Calculate how many new videos we need
        needed_count = count - existing_count if count > existing_count else 0
        
        if needed_count <= 0:
            print(f"Already have {existing_count} random videos, no additional downloads needed")
            return existing_count
        
        print(f"Need to download {needed_count} more random videos")
        if ignore_list_size > 0:
            print(f"📈 Will search across multiple categories to account for {ignore_list_size} ignored video IDs")
        print(f"Downloads will be saved to: {random_dir}")
        
        try:
            # Generate diverse random queries
            search_queries = self.get_random_search_queries(needed_count * 2)  # Generate more queries than needed
            random.shuffle(search_queries)  # Shuffle the queries
            
            # Track successful downloads and metadata
            successful_downloads = 0
            video_filename_mapping = {}
            total_videos_processed = 0
            total_filtered_count = 0
            queries_used = []
            
            # Load existing metadata to preserve video file mappings
            metadata_file = random_dir / "random_metadata.json"
            existing_video_mappings = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        existing_metadata = json.load(f)
                        existing_video_mappings = existing_metadata.get("video_file_mappings", {})
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # Search through different categories until we have enough videos
            for query in search_queries:
                if successful_downloads >= needed_count:
                    break
                
                print(f"🔍 Searching in category: '{query}'")
                queries_used.append(query)
                
                # Search for videos in this category
                videos_per_query = min(10, needed_count - successful_downloads + 5)  # Get a few extra
                videos = self.search_videos(query, videos_per_query)
                
                if not videos:
                    self.logger.debug(f"No videos found for category: {query}")
                    continue
                
                # Filter and process videos
                for video in videos:
                    if successful_downloads >= needed_count:
                        break
                    
                    # Skip if duplicate or in ignore list
                    if self.is_duplicate_video(video):
                        continue
                    
                    # Apply title/pattern filtering
                    if self.should_filter_video(video):
                        total_filtered_count += 1
                        continue
                    
                    total_videos_processed += 1
                    
                    # Add to global tracking
                    self.global_seen_video_ids.add(str(video.get('id', '')))
                    
                    # Try to download the video
                    success, filename = self.download_video(video, index=successful_downloads + 1)
                    if success:
                        successful_downloads += 1
                        # Store the mapping between video ID and filename
                        video_filename_mapping[video['id']] = {
                            'filename': filename,
                            'title': video['title'],
                            'url': video.get('comp_url') or video.get('preview_url') or f'https://stock.adobe.com/Download/Watermarked/{video["id"]}',
                            'download_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                            'category': query,
                            'random_mode': True
                        }
                    
                    # Rate limiting between downloads
                    time.sleep(self.delay)
                
                # Rate limiting between categories
                time.sleep(self.delay)
            
            total_files = existing_count + successful_downloads
            print(f"Random download complete: {successful_downloads} new videos downloaded, {total_files} total")
            
            if successful_downloads < needed_count:
                remaining = needed_count - successful_downloads
                warning_msg = f"Warning: Could not download all requested videos. Missing {remaining} videos."
                if ignore_list_size > 0:
                    warning_msg += f"\n         Large ignore list ({ignore_list_size} IDs) may have limited available unique results."
                print(warning_msg)
            
            # Update metadata for random videos
            metadata = {
                "mode": "random",
                "requested_count": count,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "total_videos_downloaded": total_files,
                "categories_used": queries_used,
                "last_download_session": {
                    "requested_count": count,
                    "new_downloads": successful_downloads,
                    "videos_processed": total_videos_processed,
                    "videos_filtered_out": total_filtered_count,
                    "categories_searched": len(queries_used),
                    "ignore_list_size": ignore_list_size,
                    "session_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                },
                "search_parameters": {
                    "max_duration_seconds": self.max_duration_seconds,
                    "min_duration_seconds": self.min_duration_seconds,
                    "max_size_bytes": self.max_size_bytes,
                    "exclude_title_patterns": self.exclude_title_patterns,
                    "sample_from": self.sample_from,
                    "intended_label": self.intended_label,
                    "random_mode": True,
                    "ignore_list_size": ignore_list_size
                }
            }
            
            # Add or update video ID to filename mappings
            if "video_file_mappings" not in metadata:
                metadata["video_file_mappings"] = {}
            
            metadata["video_file_mappings"] = existing_video_mappings.copy()
            metadata["video_file_mappings"].update(video_filename_mapping)
            
            # Save metadata
            try:
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                self.logger.debug(f"Updated random metadata with {len(video_filename_mapping)} new video file mappings")
            except Exception as e:
                self.logger.warning(f"Failed to update metadata file: {e}")
            
            return total_files
            
        finally:
            # Restore original download directory
            self.download_dir = original_download_dir

    def _handle_random_json_output_mode(self, count: int) -> int:
        """
        Handle JSON output mode for random videos.
        
        Args:
            count: Number of videos to include in JSON
            
        Returns:
            Number of videos processed for JSON output
        """
        print(f"🎲 Random JSON Mode: Creating metadata for {count} random videos")
        
        # Show ignore list information for random JSON mode
        ignore_list_size = len(self.current_ignored_video_ids) if self.use_ignore_list else 0
        if ignore_list_size > 0:
            print(f"🚫 Ignore list contains {ignore_list_size} video IDs - will search more categories to find unique videos")
        
        # Generate diverse random queries
        search_queries = self.get_random_search_queries(count)
        random.shuffle(search_queries)
        
        all_videos = []
        total_filtered_count = 0
        categories_used = []
        
        # Search through different categories
        videos_per_query = max(3, count // len(search_queries) + 1)
        
        for query in search_queries:
            if len(all_videos) >= count * 2:  # Get enough candidates
                break
            
            print(f"🔍 Searching in category: '{query}'")
            categories_used.append(query)
            
            # Search for videos in this category
            videos = self.search_videos(query, videos_per_query)
            
            if not videos:
                continue
            
            # Filter and add videos
            for video in videos:
                if len(all_videos) >= count * 2:
                    break
                
                # Skip if duplicate or in ignore list
                if self.is_duplicate_video(video):
                    continue
                
                # Apply title/pattern filtering
                if self.should_filter_video(video):
                    total_filtered_count += 1
                    continue
                
                # Add category information to video data
                video['category'] = query
                video['random_mode'] = True
                all_videos.append(video)
            
            # Rate limiting between categories
            time.sleep(self.delay)
        
        # Randomly sample from all collected videos
        if len(all_videos) > count:
            videos_to_process = random.sample(all_videos, count)
            print(f"Randomly selected {count} videos from {len(all_videos)} candidates across {len(categories_used)} categories")
        else:
            videos_to_process = all_videos
            if len(videos_to_process) < count:
                warning_msg = f"Warning: Could only find {len(videos_to_process)} videos that pass filters out of {count} requested"
                if ignore_list_size > 0:
                    warning_msg += f" (ignore list: {ignore_list_size} IDs)"
                print(warning_msg)
        
        # Create JSON output
        json_data = self.create_random_json_output(videos_to_process, categories_used)
        
        # Add metadata
        json_data["_metadata"] = {
            "random_mode": True,
            "categories_used": categories_used,
            "total_candidates_found": len(all_videos),
            "videos_filtered_out": total_filtered_count,
            "final_count": len(videos_to_process),
            "ignore_list_size": ignore_list_size,
            "generation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }
        
        # Save JSON to file
        json_filepath = self.save_random_json_output(json_data)
        
        print(f"Random JSON output complete: {len(videos_to_process)} videos saved to {json_filepath}")
        
        return len(videos_to_process)

    def create_random_json_output(self, videos: List[Dict], categories_used: List[str]) -> Dict:
        """
        Create JSON dictionary structure for random video metadata.
        
        Args:
            videos: List of video data dictionaries
            categories_used: List of categories that were searched
            
        Returns:
            JSON dictionary with the requested structure
        """
        # Group videos by category for organized output
        categorized_videos = {}
        uncategorized_videos = []
        
        for video in videos:
            category = video.get('category', 'Mixed')
            
            if category not in categorized_videos:
                categorized_videos[category] = []
            
            # Create video entry
            video_entry = {
                "id": video.get('id', ''),
                "caption": video.get('title', ''),
                "url": video.get('comp_url') or video.get('preview_url') or f'https://stock.adobe.com/Download/Watermarked/{video.get("id", "")}'
            }
            
            categorized_videos[category].append(video_entry)
        
        # Create the final JSON structure
        json_output = {
            self.intended_label: categorized_videos
        }
        
        return json_output

    def save_random_json_output(self, json_data: Dict) -> str:
        """
        Save random JSON data to file.
        
        Args:
            json_data: JSON dictionary to save
            
        Returns:
            Path to saved JSON file
        """
        # Create filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        filename = f"random_videos_{timestamp}.json"
        filepath = self.download_dir / filename
        
        # Save JSON data
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Random JSON output saved to: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Failed to save random JSON output: {e}")
            raise

    def _load_query_specific_ignore_list(self, query: str, ignore_list_path: str = None) -> set:
        """
        Load query-specific ignore list from a file.
        
        Args:
            query: Search query string (used to generate path if ignore_list_path not provided)
            ignore_list_path: Path to the ignore list file (None for auto-detection based on query)
            
        Returns:
            Set of video IDs to ignore
        """
        # If no query is provided (e.g., random mode), return empty set
        if not query and not ignore_list_path:
            return set()
        
        # Determine the ignore list file path
        if ignore_list_path:
            file_path = Path(ignore_list_path)
        else:
            file_path = Path(self._get_query_specific_ignore_list_path(query))
        
        # If file doesn't exist, return empty set
        if not file_path.exists():
            if query:  # Only log if we expected a file to exist
                self.logger.debug(f"No ignore list found for query '{query}' at {file_path}")
            return set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract video IDs from the ignore list format
            video_ids = data.get('ignored_video_ids', [])
            if video_ids:
                ignored_ids = set(str(vid).strip() for vid in video_ids if vid and str(vid).strip())
                self.logger.info(f"📂 Loaded {len(ignored_ids)} video IDs from query-specific ignore list: {file_path}")
                return ignored_ids
            else:
                self.logger.debug(f"Ignore list file is empty: {file_path}")
                return set()
                
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            self.logger.warning(f"Could not load ignore list from {file_path}: {e}")
            return set()
        except Exception as e:
            self.logger.error(f"Error loading ignore list from {file_path}: {e}")
            return set()

    def _get_query_specific_ignore_list_path(self, query: str) -> str:
        """
        Generate a query-specific ignore list path based on the query.
        
        Args:
            query: Search query string
            
        Returns:
            Path to the query-specific ignore list file
        """
        # Clean the query using the same logic as add_to_ignore_list.py
        clean_query = re.sub(r'[^\w\s-]', '', query)  # Remove special characters except spaces and hyphens
        clean_query = re.sub(r'[-\s]+', '_', clean_query)  # Replace spaces and hyphens with underscores
        clean_query = clean_query.lower().strip('_')  # Lowercase and remove leading/trailing underscores
        
        if not clean_query:
            clean_query = 'unknown_query'
        
        # Ensure ignore_list directory exists
        ignore_list_dir = Path("ignore_list")
        ignore_list_dir.mkdir(exist_ok=True)
        
        return str(ignore_list_dir / f"{clean_query}_ignore_list.json")

    def load_existing_video_ids(self, query_dir: Path) -> set:
        """
        Load video IDs from existing files and metadata to prevent duplicates.
        
        Args:
            query_dir: Directory to check for existing videos
            
        Returns:
            Set of existing video IDs
        """
        existing_ids = set()
        
        # Method 1: Load from metadata file if it exists
        metadata_file = query_dir / "query_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    video_mappings = metadata.get("video_file_mappings", {})
                    for video_id in video_mappings.keys():
                        existing_ids.add(str(video_id))
                        
                self.logger.debug(f"Loaded {len(existing_ids)} video IDs from metadata file")
            except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
                self.logger.warning(f"Could not load video IDs from metadata: {e}")
        
        # Method 2: Try to extract video IDs from existing filenames
        if query_dir.exists():
            video_extensions = ['*.mp4', '*.mov', '*.webm', '*.avi', '*.mkv']
            existing_files = []
            for ext in video_extensions:
                existing_files.extend(query_dir.glob(ext))
            
            filename_extracted_ids = set()
            for file_path in existing_files:
                filename = file_path.stem  # Get filename without extension
                
                # Try to extract Adobe Stock video ID from filename
                # Pattern 1: Filename ending with _VIDEOID
                id_match = re.search(r'_(\d{8,})$', filename)
                if id_match:
                    video_id = id_match.group(1)
                    filename_extracted_ids.add(video_id)
                    continue
                
                # Pattern 2: Filename starting with VIDEOID_
                id_match = re.search(r'^(\d{8,})_', filename)
                if id_match:
                    video_id = id_match.group(1)
                    filename_extracted_ids.add(video_id)
                    continue
                
                # Pattern 3: Adobe_Stock_Video_VIDEOID
                id_match = re.search(r'Adobe_Stock_Video_(\d{8,})', filename)
                if id_match:
                    video_id = id_match.group(1)
                    filename_extracted_ids.add(video_id)
                    continue
            
            if filename_extracted_ids:
                self.logger.debug(f"Extracted {len(filename_extracted_ids)} video IDs from existing filenames")
                existing_ids.update(filename_extracted_ids)
        
        # Update global tracking
        self.existing_video_ids.update(existing_ids)
        self.global_seen_video_ids.update(existing_ids)
        
        return existing_ids

    def is_duplicate_video(self, video_data: Dict, add_to_tracking: bool = False) -> bool:
        """
        Check if a video is a duplicate based on ID or if it's in the ignore list.
        
        Args:
            video_data: Video data dictionary
            add_to_tracking: Whether to add the video ID to global tracking if not duplicate
            
        Returns:
            True if video is a duplicate or should be ignored, False otherwise
        """
        video_id = video_data.get('id')
        if not video_id:
            return False
        
        video_id = str(video_id)
        
        # Check against all ignore lists (only if ignore list functionality is enabled)
        if self.use_ignore_list and video_id in self.current_ignored_video_ids:
            self.logger.debug(f"Video {video_id} is in ignore list - skipping (title: {video_data.get('title', 'N/A')})")
            return True
        
        # Check against global seen video IDs
        if video_id in self.global_seen_video_ids:
            self.logger.debug(f"Duplicate video detected: {video_id} (title: {video_data.get('title', 'N/A')})")
            return True
        
        # Add to global tracking only if requested
        if add_to_tracking:
            self.global_seen_video_ids.add(video_id)
        
        return False

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
            self.logger.debug(f"Loaded {len(cookies)} cookies from file")
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
            
            self.logger.debug(f"Saved {len(cookies)} cookies to {self.cookies_file}")
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
                self.logger.debug(f"Filtering out video '{video_data.get('title', '')}' - matches exclusion pattern: '{pattern}'")
                return True
        
        # Check duration if available (Note: Adobe Stock may not provide duration in search results)
        duration = video_data.get('duration_seconds')
        
        # If duration filtering is requested but no duration data is available, warn user
        if (self.max_duration_seconds or self.min_duration_seconds) and duration is None:
            # Only log this warning once per session to avoid spam
            if not hasattr(self, '_duration_warning_logged'):
                self.logger.warning("Duration filtering requested but Adobe Stock search results don't include duration information.")
                self.logger.warning("Videos may exceed your specified duration limits. Consider using a different approach to filter by duration.")
                self._duration_warning_logged = True
            return False  # Don't filter out videos without duration info
        
        if duration:
            # Maximum duration filter
            if self.max_duration_seconds and duration > self.max_duration_seconds:
                self.logger.debug(f"Filtering out video '{video_data.get('title', '')}' - duration {duration}s exceeds limit of {self.max_duration_seconds}s")
                return True
            # Minimum duration filter
            if self.min_duration_seconds and duration < self.min_duration_seconds:
                self.logger.debug(f"Filtering out video '{video_data.get('title', '')}' - duration {duration}s below minimum of {self.min_duration_seconds}s")
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
        seen_video_ids = set()  # Track video IDs to avoid duplicates within this search
        page = 1
        
        # Calculate ignore list impact and adjust search parameters accordingly
        ignore_list_size = len(self.current_ignored_video_ids) if self.use_ignore_list else 0
        
        # Base search parameters
        base_max_pages = 10
        base_consecutive_empty_limit = 3
        
        # Adjust search parameters based on ignore list size
        if ignore_list_size > 0:
            # Calculate expected hit rate (assume 10-20% of videos might be ignored in heavy use)
            ignore_ratio_estimate = min(ignore_list_size / 1000, 0.5)  # Cap at 50% estimated ignore ratio
            search_multiplier = max(1.5, 1 + (ignore_ratio_estimate * 3))  # Scale search effort
            
            max_pages = int(base_max_pages * search_multiplier)
            consecutive_empty_limit = int(base_consecutive_empty_limit * search_multiplier)
            
            self.logger.info(f"🚫 Ignore list contains {ignore_list_size} video IDs")
            self.logger.info(f"📈 Expanding search: max_pages={max_pages}, consecutive_empty_limit={consecutive_empty_limit}")
        else:
            max_pages = base_max_pages
            consecutive_empty_limit = base_consecutive_empty_limit
        
        consecutive_empty_pages = 0  # Track empty pages to stop early
        
        self.logger.debug(f"Starting search with {len(self.global_seen_video_ids)} previously seen video IDs")
        
        while len(videos) < limit and page <= max_pages and consecutive_empty_pages < consecutive_empty_limit:
            self.logger.debug(f"Searching page {page} for query: '{query}' (need {limit - len(videos)} more videos)")
            
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
                    
                    self.logger.debug(f"Got response from {url}, status: {response.status_code}")
                    
                    # Look for JSON data in the page
                    page_videos = self._extract_video_data(response.text)
                    
                    if page_videos:
                        self.logger.debug(f"Found {len(page_videos)} videos using {url}")
                        # Debug: Log the first few video IDs found
                        if page_videos:
                            sample_ids = [v.get('id', 'no-id') for v in page_videos[:3]]
                            self.logger.debug(f"Sample video IDs from extraction: {sample_ids}")
                        break
                    else:
                        self.logger.debug(f"No videos found using {url}")
                        
                except requests.RequestException as e:
                    self.logger.error(f"Error with {url}: {e}")
                    continue
            
            if not page_videos:
                self.logger.debug(f"No videos found on page {page}")
                consecutive_empty_pages += 1
            else:
                consecutive_empty_pages = 0
                
                # Enhanced duplicate filtering with multiple checks
                new_videos = []
                duplicates_filtered = 0
                invalid_videos_filtered = 0
                ignored_videos_filtered = 0
                
                # Debug: Log current tracking state
                self.logger.debug(f"Before processing page {page}: global_seen_video_ids has {len(self.global_seen_video_ids)} IDs")
                if len(self.global_seen_video_ids) <= 10:
                    self.logger.debug(f"Current global_seen_video_ids: {list(self.global_seen_video_ids)}")
                
                for video in page_videos:
                    video_id = video.get('id')
                    
                    # Skip videos without valid IDs
                    if not video_id or not str(video_id).strip():
                        invalid_videos_filtered += 1
                        continue
                    
                    video_id = str(video_id).strip()
                    
                    # Debug: Log checking process for first few videos
                    if len(new_videos) < 3:
                        self.logger.debug(f"Checking video {video_id}: in seen_video_ids={video_id in seen_video_ids}, in global_seen_video_ids={video_id in self.global_seen_video_ids}, in ignore_list={video_id in self.current_ignored_video_ids if self.use_ignore_list else False}")
                    
                    # Check against ignore list first (if enabled)
                    if self.use_ignore_list and video_id in self.current_ignored_video_ids:
                        ignored_videos_filtered += 1
                        if len(new_videos) < 3:  # Debug first few
                            self.logger.debug(f"Video {video_id} is in ignore list - skipping")
                        continue
                    
                    # Check against multiple duplicate sources:
                    # 1. Current search session duplicates
                    # 2. Global seen video IDs (includes existing files)
                    if video_id in seen_video_ids:
                        duplicates_filtered += 1
                        self.logger.debug(f"Duplicate in current search: {video_id}")
                        continue
                    
                    if video_id in self.global_seen_video_ids:
                        duplicates_filtered += 1
                        if len(new_videos) < 3:  # Debug first few
                            self.logger.debug(f"Video {video_id} already in global_seen_video_ids - marking as duplicate")
                        continue
                    
                    # Add to tracking sets - this is the single point where we add to global tracking
                    seen_video_ids.add(video_id)
                    self.global_seen_video_ids.add(video_id)
                    
                    # Add video to results
                    new_videos.append(video)
                
                videos.extend(new_videos)
                
                # Enhanced logging
                total_filtered = duplicates_filtered + invalid_videos_filtered + ignored_videos_filtered
                if total_filtered > 0:
                    filter_details = []
                    if duplicates_filtered > 0:
                        filter_details.append(f"{duplicates_filtered} duplicates")
                    if invalid_videos_filtered > 0:
                        filter_details.append(f"{invalid_videos_filtered} invalid")
                    if ignored_videos_filtered > 0:
                        filter_details.append(f"{ignored_videos_filtered} ignored")
                    
                    self.logger.debug(f"Page {page}: Found {len(new_videos)} new unique videos, filtered {', '.join(filter_details)}")
                else:
                    self.logger.debug(f"Page {page}: Found {len(new_videos)} new unique videos")
                
                # Special handling when ignore list is large
                if ignored_videos_filtered > 0:
                    self.logger.debug(f"🚫 Skipped {ignored_videos_filtered} videos from ignore list on page {page}")
                
                # If we got no new videos on this page, it might mean we've seen them all
                if len(new_videos) == 0:
                    consecutive_empty_pages += 1
                    self.logger.debug(f"No new videos on page {page} - all were duplicates, invalid, or ignored")
            
            page += 1
            time.sleep(self.delay)  # Rate limiting
        
        # Enhanced completion logging
        completion_msg = f"Search complete: {len(videos)} unique videos found"
        if ignore_list_size > 0:
            completion_msg += f" (ignore list: {ignore_list_size} IDs)"
        completion_msg += f", {len(self.global_seen_video_ids)} total video IDs tracked"
        
        if len(videos) < limit:
            if ignore_list_size > 0:
                self.logger.info(f"⚠️  Found {len(videos)}/{limit} videos. Large ignore list ({ignore_list_size} IDs) may have limited available results.")
            else:
                self.logger.debug(f"Only found {len(videos)} unique videos out of requested {limit}. Adobe Stock may not have enough unique results for this query.")
        
        self.logger.debug(completion_msg)
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
        
        # Local duplicate check within this extraction only (don't modify global tracking here)
        unique_videos = []
        seen_ids_in_extraction = set()
        
        for video in videos:
            video_id = video.get('id')
            if video_id and video_id not in seen_ids_in_extraction:
                seen_ids_in_extraction.add(video_id)
                unique_videos.append(video)
        
        self.logger.debug(f"JavaScript extraction: Found {len(unique_videos)} unique videos from {len(videos)} total matches")
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
            
            self.logger.debug(f"Found {len(videos)} unique videos with titles from HTML parsing")
            
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
        
        self.logger.debug(f"Found {len(video_ids)} unique video IDs in HTML")
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
                self.logger.debug(f"BeautifulSoup found {len(videos)} videos")
            
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
            self.logger.debug(f"Regex extraction found {len(videos)} video IDs")
        
        return videos[:20]  # Limit fallback results

    def get_video_duration_with_ffprobe(self, video_url: str) -> Optional[int]:
        """
        Try to get video duration using ffprobe (if available).
        This is more accurate than file size estimation.
        
        Args:
            video_url: URL of the video
            
        Returns:
            Duration in seconds, or None if not available
        """
        try:
            import subprocess
            import json
            
            self.logger.info(f"Using ffprobe to get duration for video URL")
            
            # Try to run ffprobe on the URL directly
            cmd = [
                'ffprobe', 
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                '-user_agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                video_url
            ]
            
            self.logger.debug(f"Running ffprobe command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            
            if result.returncode == 0:
                probe_data = json.loads(result.stdout)
                self.logger.debug(f"ffprobe succeeded, parsing JSON data")
                
                # Look for duration in format info first
                if 'format' in probe_data and 'duration' in probe_data['format']:
                    duration = float(probe_data['format']['duration'])
                    duration_int = int(duration)
                    self.logger.info(f"ffprobe found duration in format: {duration_int} seconds")
                    return duration_int
                
                # If not in format, look in video streams
                if 'streams' in probe_data:
                    for stream in probe_data['streams']:
                        if stream.get('codec_type') == 'video' and 'duration' in stream:
                            duration = float(stream['duration'])
                            duration_int = int(duration)
                            self.logger.info(f"ffprobe found duration in video stream: {duration_int} seconds")
                            return duration_int
                
                self.logger.warning("ffprobe succeeded but no duration found in output")
            else:
                self.logger.warning(f"ffprobe failed with return code {result.returncode}")
                if result.stderr:
                    self.logger.debug(f"ffprobe stderr: {result.stderr}")
                            
        except subprocess.TimeoutExpired:
            self.logger.warning("ffprobe timed out after 45 seconds")
        except (ImportError, subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.warning(f"ffprobe not available or failed: {e}")
        except json.JSONDecodeError as e:
            self.logger.warning(f"ffprobe returned invalid JSON: {e}")
        except Exception as e:
            self.logger.warning(f"Unexpected error with ffprobe: {e}")
        
        return None

    def get_video_duration_from_partial_download(self, video_url: str, video_id: str) -> Optional[int]:
        """
        Download a small portion of the video to check its duration with ffprobe.
        This is more reliable than trying to probe the URL directly.
        
        Args:
            video_url: URL of the video
            video_id: Video ID for temporary file naming
            
        Returns:
            Duration in seconds, or None if not available
        """
        import tempfile
        import subprocess
        import json
        
        # Create a temporary file for the partial download
        temp_file = None
        try:
            # Download first 2MB to get enough metadata
            headers = {'Range': 'bytes=0-2097151'}  # First 2MB
            response = self.session.get(video_url, headers=headers, timeout=30, stream=True)
            
            if response.status_code in [200, 206]:  # Success or partial content
                # Create temporary file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    temp_filename = temp_file.name
                    
                    # Write the partial content
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            temp_file.write(chunk)
                
                self.logger.info(f"Downloaded partial video ({len(response.content) if hasattr(response, 'content') else 'unknown'} bytes) for duration check")
                
                # Use ffprobe on the temporary file
                cmd = [
                    'ffprobe', 
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    temp_filename
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    probe_data = json.loads(result.stdout)
                    
                    if 'format' in probe_data and 'duration' in probe_data['format']:
                        duration = float(probe_data['format']['duration'])
                        duration_int = int(duration)
                        self.logger.info(f"ffprobe found duration from partial download: {duration_int} seconds")
                        return duration_int
                else:
                    self.logger.debug(f"ffprobe failed on partial download: {result.stderr}")
                    
        except Exception as e:
            self.logger.debug(f"Could not get duration from partial download: {e}")
        finally:
            # Clean up temporary file
            if temp_file and hasattr(temp_file, 'name'):
                try:
                    import os
                    os.unlink(temp_filename)
                except:
                    pass
        
        return None

    def get_video_duration_from_url(self, video_url: str, video_id: str = None) -> Optional[int]:
        """
        Try to get video duration from URL metadata without downloading the full video.
        
        Args:
            video_url: URL of the video
            video_id: Video ID for temporary file naming
            
        Returns:
            Duration in seconds, or None if not available
        """
        # First try ffprobe directly on URL (usually won't work for Adobe Stock)
        duration = self.get_video_duration_with_ffprobe(video_url)
        if duration:
            return duration
        
        # If that fails, try partial download + ffprobe (more reliable)
        if video_id:
            duration = self.get_video_duration_from_partial_download(video_url, video_id)
            if duration:
                return duration
        
        # Fallback to file size estimation (improved version)
        try:
            headers = {'Range': 'bytes=0-8192'}  # Get first 8KB to read metadata
            response = self.session.get(video_url, headers=headers, timeout=10, stream=True)
            
            if response.status_code in [200, 206]:  # Success or partial content
                content_length = response.headers.get('content-length')
                if content_length:
                    file_size_mb = int(content_length) / (1024 * 1024)
                    estimated_duration = int(file_size_mb / 0.8)  # ~0.8MB per second for HD video
                    
                    self.logger.info(f"File size: {file_size_mb:.1f}MB, estimated duration: {estimated_duration}s")
                    
                    if 1 <= estimated_duration <= 600:
                        self.logger.info(f"Using file size estimation: {estimated_duration}s (based on {file_size_mb:.1f}MB at ~0.8MB/sec)")
                        return estimated_duration
                    else:
                        self.logger.warning(f"File size estimation seems unrealistic: {estimated_duration}s from {file_size_mb:.1f}MB - skipping estimation")
                    
        except Exception as e:
            self.logger.debug(f"Could not get duration from URL metadata: {e}")
        
        return None

    def download_video(self, video_data: Dict, filename: Optional[str] = None, query_prefix: Optional[str] = None, index: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """
        Download a video thumbnail.
        
        Args:
            video_data: Video data dictionary
            filename: Optional custom filename
            query_prefix: Optional query-based prefix for filename
            index: Optional index for sequential naming
            
        Returns:
            Tuple of (success: bool, filename: str) where filename is the actual filename used
        """
        # Get the video ID and construct the watermarked download URL
        video_id = video_data.get('id')
        if not video_id:
            self.logger.warning("No video ID found in video data")
            return False, None
        
        video_id = str(video_id).strip()
        
        # Check ignore list first - skip early if video should be ignored (only if ignore list functionality is enabled)
        if self.use_ignore_list and video_id in self.current_ignored_video_ids:
            print(f"🚫 Skipping {video_id} (in ignore list)")
            return False, None
        
        # Enhanced duplicate checking - check if video ID already exists
        if video_id in self.existing_video_ids:
            print(f"🔄 Skipping {video_id} (already exists)")
            return False, None
        
        # Check if we've processed this video ID in current session
        if video_id in self.global_seen_video_ids and video_id not in self.existing_video_ids:
            # This means we've seen it in current session but it's not in existing files
            # This could happen if it was filtered out earlier, so we can try again
            self.logger.debug(f"Video {video_id} seen in current session but not in existing files, proceeding...")
        
        # Use watermarked download URL - prioritize comp_url if it exists, otherwise construct it
        download_url = video_data.get('comp_url') or video_data.get('preview_url')
        
        # If no URL is provided or it doesn't match the watermarked pattern, construct it
        if not download_url or 'Download/Watermarked/' not in download_url:
            download_url = f'https://stock.adobe.com/Download/Watermarked/{video_id}'
            self.logger.debug(f"Constructed watermarked download URL: {download_url}")
        
        # Check if duration filtering is enabled
        duration_filtering_enabled = bool(self.max_duration_seconds or self.min_duration_seconds)
        current_duration = video_data.get('duration_seconds')
        
        self.logger.debug(f"Video {video_id}: current_duration = {current_duration}, max_duration_seconds = {self.max_duration_seconds}, min_duration_seconds = {self.min_duration_seconds}")
        
        # If we already have duration info from search results, check it now
        if current_duration is not None and duration_filtering_enabled:
            if self.max_duration_seconds and current_duration > self.max_duration_seconds:
                print(f"🚫 Skipping {video_id} (duration {current_duration}s > {self.max_duration_seconds}s)")
                return False, None
            if self.min_duration_seconds and current_duration < self.min_duration_seconds:
                print(f"🚫 Skipping {video_id} (duration {current_duration}s < {self.min_duration_seconds}s)")
                return False, None
            self.logger.debug(f"✅ Video {video_id} duration {current_duration}s - within acceptable range")
        
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
        
        # Enhanced file existence check - both filename and video ID based
        if filepath.exists():
            self.logger.debug(f"File {filename} already exists, skipping...")
            # Add to existing video IDs if not already there
            self.existing_video_ids.add(video_id)
            return True, filename
        
        # Check if any file with this video ID already exists (different filename)
        video_extensions = ['*.mp4', '*.mov', '*.webm', '*.avi', '*.mkv']
        existing_files = []
        for ext in video_extensions:
            existing_files.extend(self.download_dir.glob(ext))
        
        for existing_file in existing_files:
            existing_filename = existing_file.stem
            # Check if existing file contains this video ID
            if video_id in existing_filename:
                print(f"🔄 Skipping {video_id} (exists as {existing_file.name})")
                self.existing_video_ids.add(video_id)
                return True, existing_file.name

        # Show video processing status
        video_title = video_data.get('title', f'Video_{video_id}')
        if len(video_title) > 80:
            video_title = video_title[:77] + "..."
        print(f"📥 Downloading: {video_title}")

        try:
            # Check file size before downloading if max_size_bytes is set
            if self.max_size_bytes:
                try:
                    # Send HEAD request to get Content-Length without downloading
                    head_response = self.session.head(download_url, timeout=10)
                    content_length = head_response.headers.get('content-length')
                    
                    if content_length:
                        file_size_bytes = int(content_length)
                        if file_size_bytes > self.max_size_bytes:
                            size_mb = file_size_bytes / (1024 * 1024)
                            max_size_mb = self.max_size_bytes / (1024 * 1024)
                            print(f"🚫 Skipping {video_id} (size {size_mb:.1f}MB > {max_size_mb:.1f}MB)")
                            return False, None
                        else:
                            size_mb = file_size_bytes / (1024 * 1024)
                            max_size_mb = self.max_size_bytes / (1024 * 1024)
                            self.logger.debug(f"✅ Video {video_id} file size {size_mb:.1f}MB - within limit of {max_size_mb:.1f}MB")

                except Exception as e:
                    self.logger.debug(f"⚠️ Error checking file size for {video_id}: {e} - proceeding with download")
            
            # Use the session with proper headers for Adobe Stock
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Check if we got a valid video file
            content_type = response.headers.get('content-type', '').lower()
            if 'video' not in content_type and 'application/octet-stream' not in content_type:
                self.logger.debug(f"Unexpected content type for {filename}: {content_type}")
                # Continue anyway as Adobe Stock might return different content types
            
            # Double-check file size during download if we couldn't check it beforehand
            if self.max_size_bytes:
                content_length = response.headers.get('content-length')
                if content_length:
                    file_size_bytes = int(content_length)
                    if file_size_bytes > self.max_size_bytes:
                        size_mb = file_size_bytes / (1024 * 1024)
                        max_size_mb = self.max_size_bytes / (1024 * 1024)
                        print(f"🚫 Skipping {video_id} (size {size_mb:.1f}MB > {max_size_mb:.1f}MB)")
                        return False, None
            
            downloaded_bytes = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        
                        # Check downloaded size if max_size_bytes is set
                        if self.max_size_bytes and downloaded_bytes > self.max_size_bytes:
                            size_mb = downloaded_bytes / (1024 * 1024)
                            max_size_mb = self.max_size_bytes / (1024 * 1024)
                            print(f"🚫 Skipping {video_id} (size {size_mb:.1f}MB > {max_size_mb:.1f}MB)")
                            # Remove the partially downloaded file
                            filepath.unlink()
                            return False, None
            
            # Check if the downloaded file has a reasonable size
            file_size = filepath.stat().st_size
            if file_size < 1024:  # Less than 1KB might indicate an error
                self.logger.warning(f"Downloaded file {filename} is very small ({file_size} bytes) - might be an error page")
                # Don't delete automatically, let the user decide
            
            # Add to existing video IDs tracking
            self.existing_video_ids.add(video_id)
            
            # Now check duration if filtering is enabled and we don't have duration info yet
            if duration_filtering_enabled and current_duration is None:
                self.logger.debug(f"Checking duration of downloaded video {video_id} with ffprobe...")
                actual_duration = self.get_video_duration_from_file(filepath)
                
                if actual_duration:
                    self.logger.debug(f"ffprobe found duration: {actual_duration} seconds")
                    
                    # Check if duration is within limits
                    duration_ok = True
                    if self.max_duration_seconds and actual_duration > self.max_duration_seconds:
                        print(f"🚫 Removed {video_id} (duration {actual_duration}s > {self.max_duration_seconds}s)")
                        duration_ok = False
                    if self.min_duration_seconds and actual_duration < self.min_duration_seconds:
                        print(f"🚫 Removed {video_id} (duration {actual_duration}s < {self.min_duration_seconds}s)")
                        duration_ok = False
                    
                    if not duration_ok:
                        # Delete the file and return failure
                        filepath.unlink()
                        # Remove from existing video IDs since we deleted it
                        self.existing_video_ids.discard(video_id)
                        return False, None
                    else:
                        self.logger.debug(f"✅ Video {video_id} duration {actual_duration}s - within acceptable range")
                        # Update video data for future reference
                        video_data['duration_seconds'] = actual_duration
                else:
                    self.logger.debug(f"⚠️ Could not determine duration for {filename} - keeping file anyway")
            
            # Show success message
            file_size_mb = file_size / (1024 * 1024)
            print(f"✅ Downloaded: {filename} ({file_size_mb:.1f}MB)")
            
            return True, filename
            
        except requests.RequestException as e:
            print(f"❌ Error downloading {video_id}: {e}")
            if filepath.exists():
                filepath.unlink()  # Remove partial file
            return False, None

    def get_video_duration_from_file(self, filepath) -> Optional[int]:
        """
        Get video duration from a downloaded file using ffprobe.
        
        Args:
            filepath: Path to the video file
            
        Returns:
            Duration in seconds, or None if not available
        """
        try:
            import subprocess
            import json
            
            cmd = [
                'ffprobe', 
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(filepath)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                probe_data = json.loads(result.stdout)
                
                if 'format' in probe_data and 'duration' in probe_data['format']:
                    duration = float(probe_data['format']['duration'])
                    return int(duration)
                    
        except Exception as e:
            self.logger.debug(f"Could not get duration from file {filepath}: {e}")
        
        return None

    def scrape_and_download(self, query: str, count: int = 10) -> int:
        """
        Scrape and download videos for a given query.
        
        Args:
            query: Search query string (or None for random mode)
            count: Number of videos to download
            
        Returns:
            Number of videos downloaded
        """
        # Handle random mode
        if self.random_mode:
            return self.scrape_random_videos(count)
        
        # Handle JSON output mode
        if self.json_output:
            search_count = self.sample_from if self.sample_from and self.sample_from > count else count
            return self._handle_json_output_mode(query, count, search_count)
        
        # Store original download directory
        original_download_dir = self.download_dir
        
        # Create a subdirectory for this query
        clean_query = re.sub(r'[^\w\s-]', '', query)
        clean_query = re.sub(r'[-\s]+', '_', clean_query)
        clean_query = clean_query.lower().strip('_')
        
        query_dir = self.download_dir / clean_query
        query_dir.mkdir(exist_ok=True)
        
        # Update download directory to the query subdirectory
        self.download_dir = query_dir
        
        # Prepare metadata
        metadata = {
            "query": query,
            "requested_count": count,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "total_videos_downloaded": 0,
            "search_parameters": {
                "max_duration_seconds": self.max_duration_seconds,
                "min_duration_seconds": self.min_duration_seconds,
                "max_size_bytes": self.max_size_bytes,
                "exclude_title_patterns": self.exclude_title_patterns,
                "sample_from": self.sample_from,
                "intended_label": self.intended_label
            }
        }
        
        # Create metadata files
        metadata_file = query_dir / "query_metadata.json"
        
        # Load existing video IDs to prevent duplicates
        existing_video_ids = self.load_existing_video_ids(query_dir)
        
        # Count existing video files (exclude metadata files)
        video_extensions = ['.mp4', '.mov', '.webm', '.avi', '.mkv']
        
        # Filter out metadata files
        existing_files = list(query_dir.glob("*.mp4")) + \
                        list(query_dir.glob("*.mov")) + \
                        list(query_dir.glob("*.webm")) + \
                        list(query_dir.glob("*.avi")) + \
                        list(query_dir.glob("*.mkv"))
        
        # Filter out metadata files
        existing_files = [f for f in existing_files if f.name != "query_metadata.json"]
        existing_count = len(existing_files)
        
        if existing_count > 0:
            print(f"Found {existing_count} existing videos")
        
        # Load existing metadata to preserve video file mappings
        existing_video_mappings = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    existing_metadata = json.load(f)
                    existing_video_mappings = existing_metadata.get("video_file_mappings", {})
                    metadata["created_at"] = existing_metadata.get("created_at", metadata["created_at"])
            except (json.JSONDecodeError, KeyError):
                # If existing file is corrupted, start fresh
                pass
        
        # Calculate how many new videos we need
        needed_count = count - existing_count if count > existing_count else 0
        
        if needed_count <= 0:
            print(f"Already have {existing_count} videos, no additional downloads needed")
            
            # Still update metadata file
            with open(query_dir / "query_metadata.js", 'w', encoding='utf-8') as f:
                f.write(f'const {clean_query}_metadata = ')
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                f.write(';')
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            return existing_count
        
        print(f"Need to download {needed_count} more videos")
        print(f"Downloads will be saved to: {query_dir}")

        try:
            # MODIFIED LOGIC: Continue searching until target is reached
            successful_downloads = 0
            video_filename_mapping = {}
            total_videos_processed = 0
            total_filtered_count = 0
            search_attempts = 0
            
            # Calculate ignore list impact and adjust search parameters accordingly
            ignore_list_size = len(self.current_ignored_video_ids) if self.use_ignore_list else 0
            
            # Base search parameters
            base_max_attempts = 20
            base_videos_per_attempt_multiplier = 3
            
            # Adjust search parameters based on ignore list size
            if ignore_list_size > 0:
                # For large ignore lists, be more aggressive in searching
                ignore_ratio_estimate = min(ignore_list_size / 1000, 0.7)  # Cap at 70% estimated ignore ratio
                search_multiplier = max(1.5, 1 + (ignore_ratio_estimate * 2))
                
                max_search_attempts = int(base_max_attempts * search_multiplier)
                videos_per_attempt_multiplier = max(base_videos_per_attempt_multiplier, base_videos_per_attempt_multiplier * search_multiplier)
                
                print(f"🚫 Ignore list contains {ignore_list_size} video IDs")
                print(f"📈 Expanding search strategy: max_attempts={max_search_attempts}, search_multiplier={videos_per_attempt_multiplier:.1f}x")
            else:
                max_search_attempts = base_max_attempts
                videos_per_attempt_multiplier = base_videos_per_attempt_multiplier
            
            videos_per_attempt = int(needed_count * videos_per_attempt_multiplier)  # Start with calculated multiplier for better odds
            all_processed_video_ids = set()  # Track all video IDs we've already processed
            
            self.logger.debug(f"Starting search process with {len(self.global_seen_video_ids)} video IDs already tracked (including {len(existing_video_ids)} existing)")
            
            # Continue searching and downloading until we reach the target
            while successful_downloads < needed_count and search_attempts < max_search_attempts:
                search_attempts += 1
                
                # Calculate how many more videos we need
                remaining_needed = needed_count - successful_downloads
                current_search_limit = max(remaining_needed * int(videos_per_attempt_multiplier * 2), videos_per_attempt)  # Search for more than we need
                
                search_msg = f"Search attempt {search_attempts}: Need {remaining_needed} more videos, searching for {current_search_limit} candidates"
                if ignore_list_size > 0:
                    search_msg += f" (accounting for {ignore_list_size} ignored IDs)"
                self.logger.debug(search_msg)
                
                # Search for videos
                videos = self.search_videos(query, current_search_limit)
                
                if not videos:
                    self.logger.warning("No videos found for the given query")
                    break
                
                # Filter out videos we've already processed and existing videos
                new_videos = []
                for video in videos:
                    video_id = video.get('id')
                    if (video_id and 
                        video_id not in self.existing_video_ids and 
                        video_id not in all_processed_video_ids):
                        new_videos.append(video)
                        all_processed_video_ids.add(video_id)  # Mark as processed
                
                if not new_videos:
                    self.logger.debug(f"No new videos found in search attempt {search_attempts} - all were duplicates")
                    videos_per_attempt = int(videos_per_attempt * 1.5)
                    continue
                
                # Apply title/pattern filtering
                candidate_videos = []
                attempt_filtered_count = 0
                for video in new_videos:
                    if self.should_filter_video(video):
                        attempt_filtered_count += 1
                        total_filtered_count += 1
                        continue
                    candidate_videos.append(video)
                
                if attempt_filtered_count > 0:
                    self.logger.debug(f"Filtered out {attempt_filtered_count} videos based on title patterns in search attempt {search_attempts}")
                
                if not candidate_videos:
                    self.logger.debug(f"No valid candidates after filtering in search attempt {search_attempts}")
                    continue
                
                if search_attempts == 1:
                    print(f"Found {len(candidate_videos)} videos to process...")
                
                # Try to download the candidate videos
                attempt_downloads = 0
                for i, video in enumerate(candidate_videos):
                    if successful_downloads >= needed_count:
                        break
                    
                    total_videos_processed += 1
                    
                    # Try to download the video
                    success, filename = self.download_video(video)
                    if success:
                        successful_downloads += 1
                        attempt_downloads += 1
                        # Store the mapping between video ID and filename
                        video_filename_mapping[video['id']] = {
                            'filename': filename,
                            'title': video['title'],
                            'url': video.get('comp_url') or video.get('preview_url') or f'https://stock.adobe.com/Download/Watermarked/{video["id"]}',
                            'download_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                            'search_attempt': search_attempts
                        }
                    
                    # Rate limiting between downloads
                    time.sleep(self.delay)
                
                # If we got no successful downloads from this batch, increase the search multiplier
                if attempt_downloads == 0:
                    videos_per_attempt = int(videos_per_attempt * 2)
                    self.logger.debug(f"No successful downloads in this attempt, increasing search multiplier to {videos_per_attempt}")
                
                # If we still need more videos, continue searching
                if successful_downloads < needed_count:
                    remaining = needed_count - successful_downloads
                    if search_attempts < max_search_attempts:
                        self.logger.debug(f"Still need {remaining} more videos, continuing search...")
                        time.sleep(self.delay)  # Rate limiting between search attempts
            
            total_files = existing_count + successful_downloads
            print(f"Download complete: {successful_downloads} new videos downloaded, {total_files} total")
            
            if successful_downloads < needed_count:
                remaining = needed_count - successful_downloads
                warning_msg = f"Warning: Could not download all requested videos. Missing {remaining} videos."
                if ignore_list_size > 0:
                    warning_msg += f"\n         Large ignore list ({ignore_list_size} IDs) may have limited available unique results."
                print(warning_msg)
                if self.max_size_bytes is not None:
                    print(f"Consider increasing max_size_bytes (currently {self.max_size_bytes / (1024*1024):.1f}MB)")
                if self.max_duration_seconds or self.min_duration_seconds:
                    print(f"Consider adjusting duration filters (currently {self.min_duration_seconds}-{self.max_duration_seconds}s)")
            
            # Update metadata with download completion info and video mappings
            try:
                metadata["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                metadata["total_videos_downloaded"] = total_files
                metadata["last_download_session"] = {
                    "requested_count": count,
                    "new_downloads": successful_downloads,
                    "videos_processed": total_videos_processed,
                    "videos_filtered_out": total_filtered_count,
                    "search_attempts": search_attempts,
                    "existing_videos_at_start": len(existing_video_ids),
                    "ignore_list_size": ignore_list_size,
                    "max_search_attempts_reached": search_attempts >= max_search_attempts,
                    "session_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                }
                
                # Add or update video ID to filename mappings
                if "video_file_mappings" not in metadata:
                    metadata["video_file_mappings"] = {}
                
                # Start with existing mappings and add new ones
                metadata["video_file_mappings"] = existing_video_mappings.copy()
                metadata["video_file_mappings"].update(video_filename_mapping)
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                self.logger.debug(f"Updated metadata with {len(video_filename_mapping)} new video file mappings")
            except Exception as e:
                self.logger.warning(f"Failed to update metadata file: {e}")
            
            return total_files
            
        finally:
            # Restore original download directory
            self.download_dir = original_download_dir

    def _handle_json_output_mode(self, query: str, count: int, search_count: int) -> int:
        """
        Handle JSON output mode - search for videos and create JSON instead of downloading.
        
        Args:
            query: Search query string
            count: Number of videos to include in JSON
            search_count: Number of videos to search for (may be different from count due to sampling)
            
        Returns:
            Number of videos processed for JSON output
        """
        self.logger.debug(f"JSON output mode: searching for {search_count} videos to get {count} for JSON output")
        
        try:
            # Enhanced duplicate checking for JSON mode
            # Create a temporary directory to check for existing JSON output duplicates
            clean_query = re.sub(r'[^\w\s-]', '', query)
            clean_query = re.sub(r'[-\s]+', '_', clean_query)
            clean_query = clean_query.lower().strip('_')
            
            # Check for existing JSON files that might contain duplicates
            existing_json_files = list(self.download_dir.glob(f"{clean_query}*.json"))
            existing_video_ids_in_json = set()
            
            if existing_json_files:
                self.logger.debug(f"Found {len(existing_json_files)} existing JSON files, checking for duplicate video IDs...")
                for json_file in existing_json_files:
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                            # Extract video IDs from existing JSON structure
                            for label_data in json_data.values():
                                if isinstance(label_data, dict):
                                    for query_data in label_data.values():
                                        if isinstance(query_data, list):
                                            for video_entry in query_data:
                                                if isinstance(video_entry, dict) and 'id' in video_entry:
                                                    existing_video_ids_in_json.add(str(video_entry['id']))
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        self.logger.warning(f"Could not parse existing JSON file {json_file}: {e}")
                
                if existing_video_ids_in_json:
                    self.logger.debug(f"Found {len(existing_video_ids_in_json)} video IDs in existing JSON files")
                    # Add these to global tracking to avoid duplicates
                    self.global_seen_video_ids.update(existing_video_ids_in_json)
            
            # Calculate ignore list impact and adjust search parameters accordingly
            ignore_list_size = len(self.current_ignored_video_ids) if self.use_ignore_list else 0
            total_excluded_count = ignore_list_size + len(existing_video_ids_in_json)
            
            # NEW LOGIC: Search iteratively until we have enough videos that pass filters
            all_candidate_videos = []
            total_filtered_count = 0
            search_attempts = 0
            
            # Adjust search parameters based on ignore list and existing JSON size
            base_max_attempts = 5
            base_multiplier = 2
            
            if total_excluded_count > 0:
                # For large exclude lists (ignore + existing JSON), be more aggressive
                exclude_ratio_estimate = min(total_excluded_count / 1000, 0.6)  # Cap at 60% estimated exclude ratio
                search_multiplier = max(1.5, 1 + (exclude_ratio_estimate * 2))
                
                max_search_attempts = int(base_max_attempts * search_multiplier)
                videos_per_attempt_multiplier = max(base_multiplier, base_multiplier * search_multiplier)
                
                if ignore_list_size > 0:
                    print(f"🚫 Ignore list contains {ignore_list_size} video IDs")
                if existing_video_ids_in_json:
                    print(f"📄 Found {len(existing_video_ids_in_json)} video IDs in existing JSON files")
                print(f"📈 Expanding JSON search: max_attempts={max_search_attempts}, search_multiplier={videos_per_attempt_multiplier:.1f}x")
            else:
                max_search_attempts = base_max_attempts
                videos_per_attempt_multiplier = base_multiplier
            
            videos_per_attempt = search_count * videos_per_attempt_multiplier  # Start with calculated multiplier
            
            print(f"Searching for {count} videos for JSON output...")
            
            # Phase 1: Collect candidate videos
            while len(all_candidate_videos) < search_count and search_attempts < max_search_attempts:
                search_attempts += 1
                current_search_limit = int(videos_per_attempt_multiplier * search_attempts * search_count)
                
                search_msg = f"Search attempt {search_attempts}: Looking for {current_search_limit} videos to collect {search_count} candidates"
                if total_excluded_count > 0:
                    search_msg += f" (accounting for {total_excluded_count} excluded IDs)"
                self.logger.debug(search_msg)
                
                # Search for videos
                videos = self.search_videos(query, current_search_limit)
                
                if not videos:
                    self.logger.warning("No videos found for the given query")
                    break
                
                # Filter out duplicates from previous searches and existing JSON files
                new_videos = []
                existing_ids = {v.get('id') for v in all_candidate_videos}
                for video in videos:
                    video_id = video.get('id')
                    # Check against multiple sources of duplicates
                    if video_id and video_id not in existing_ids and video_id not in existing_video_ids_in_json:
                        new_videos.append(video)
                        all_candidate_videos.append(video)
                    elif video_id in existing_video_ids_in_json:
                        self.logger.debug(f"Video {video_id} already exists in JSON files, skipping")
                
                if not new_videos:
                    self.logger.debug(f"No new videos found in search attempt {search_attempts} - all were duplicates")
                    break
                
                self.logger.debug(f"Found {len(new_videos)} new videos in search attempt {search_attempts}")
                
                # Apply filtering to new videos
                attempt_filtered_count = 0
                valid_candidates = []
                for video in new_videos:
                    if self.should_filter_video(video):
                        attempt_filtered_count += 1
                        total_filtered_count += 1
                        # Remove from all_candidate_videos since it was filtered out
                        if video in all_candidate_videos:
                            all_candidate_videos.remove(video)
                        continue
                    else:
                        valid_candidates.append(video)
                
                if attempt_filtered_count > 0:
                    self.logger.debug(f"Filtered out {attempt_filtered_count} videos in search attempt {search_attempts}")
                
                self.logger.debug(f"Now have {len(all_candidate_videos)} valid candidate videos (target: {search_count})")
                
                # If we have enough valid candidates, we can stop searching
                if len(all_candidate_videos) >= search_count:
                    break
                
                # Increase multiplier for next attempt if we're still short
                videos_per_attempt_multiplier = videos_per_attempt_multiplier * 1.5
            
            # Phase 2: Apply sampling if enabled
            videos_to_process = all_candidate_videos[:search_count]  # Limit to search_count
            
            if self.sample_from and self.sample_from > count and len(videos_to_process) >= count:
                # Randomly sample the count from the candidate pool
                videos_to_process = random.sample(videos_to_process, count)
                print(f"Randomly sampled {len(videos_to_process)} videos from {len(all_candidate_videos)} candidates")
                
                # Log some info about the sampling
                sampled_titles = [v.get('title', 'Unknown')[:50] + ('...' if len(v.get('title', '')) > 50 else '') for v in videos_to_process[:3]]
                if len(videos_to_process) > 3:
                    sampled_titles.append(f"... and {len(videos_to_process) - 3} more")
                self.logger.debug(f"JSON sample includes: {sampled_titles}")
            else:
                # Take the first count videos
                videos_to_process = all_candidate_videos[:count]
                if self.sample_from and len(all_candidate_videos) < count:
                    self.logger.debug(f"Not enough candidates for effective sampling, using all {len(videos_to_process)} available videos")
            
            # Final logging
            if total_filtered_count > 0:
                self.logger.debug(f"Total videos filtered out: {total_filtered_count}")
            
            if existing_video_ids_in_json:
                self.logger.debug(f"Total videos skipped as duplicates from existing JSON: {len(existing_video_ids_in_json)}")
            
            if ignore_list_size > 0:
                self.logger.debug(f"Total videos skipped from ignore list: {ignore_list_size}")
            
            if len(videos_to_process) < count:
                warning_msg = f"Warning: Could only find {len(videos_to_process)} videos that pass filters out of {count} requested"
                if total_excluded_count > 0:
                    warning_msg += f" (excluded {total_excluded_count} IDs from ignore list and existing JSON)"
                print(warning_msg)
            
            print(f"Creating JSON output for {len(videos_to_process)} videos...")
            
            # Create JSON output
            json_data = self.create_json_output(videos_to_process, query)
            
            # Add sampling metadata to JSON if applicable
            metadata_info = {
                "generation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "search_attempts": search_attempts,
                "ignore_list_size": ignore_list_size,
                "existing_json_duplicates": len(existing_video_ids_in_json),
                "total_excluded_count": total_excluded_count
            }
            
            if self.sample_from:
                metadata_info["sampling_info"] = {
                    "sample_from": self.sample_from,
                    "requested_count": count,
                    "candidates_found": len(all_candidate_videos),
                    "final_count": len(videos_to_process),
                    "was_sampled": bool(self.sample_from > count and len(all_candidate_videos) >= count)
                }
            
            json_data["_metadata"] = metadata_info
            
            # Save JSON to file
            json_filepath = self.save_json_output(json_data, query)
            
            print(f"JSON output complete: {len(videos_to_process)} videos saved to {json_filepath}")
            
            if self.sample_from and len(all_candidate_videos) > 0:
                self.logger.debug(f"JSON sampling summary: Found {len(all_candidate_videos)} candidates, included {len(videos_to_process)} in final JSON")
            
            return len(videos_to_process)
            
        except Exception as e:
            self.logger.error(f"Error in JSON output mode: {e}")
            return 0

    def create_json_output(self, videos: List[Dict], query: str) -> Dict:
        """
        Create JSON dictionary structure for video metadata.
        
        Args:
            videos: List of video data dictionaries
            query: Search query used
            
        Returns:
            JSON dictionary with the requested structure
        """
        video_entries = []
        
        for video in videos:
            # Get the download URL or preview URL
            url = video.get('comp_url') or video.get('preview_url')
            if not url and video.get('id'):
                # Construct watermarked download URL if no URL is provided
                url = f'https://stock.adobe.com/Download/Watermarked/{video["id"]}'
            
            # Create simplified video entry with only id, caption, and url
            video_entry = {
                "id": video.get('id', ''),
                "caption": video.get('title', ''),
                "url": url or ''
            }
            
            video_entries.append(video_entry)
        
        # Create the final JSON structure
        json_output = {
            self.intended_label: {
                query: video_entries
            }
        }
        
        return json_output

    def save_json_output(self, json_data: Dict, query: str) -> str:
        """
        Save JSON data to file.
        
        Args:
            json_data: JSON dictionary to save
            query: Search query used (for filename)
            
        Returns:
            Path to saved JSON file
        """
        # Create a clean filename from the query
        clean_query = re.sub(r'[^\w\s-]', '', query)  # Remove special characters
        clean_query = re.sub(r'[-\s]+', '_', clean_query)  # Replace spaces/hyphens with underscores
        clean_query = clean_query.lower().strip('_')  # Lowercase and remove leading/trailing underscores
        
        # Create filename with timestamp to avoid conflicts
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        filename = f"{clean_query}.json"
        filepath = self.download_dir / filename
        
        # Save JSON data
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"JSON output saved to: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Failed to save JSON output: {e}")
            raise

    def add_metadata_to_ignore_list(self, metadata_file_path: str) -> bool:
        """
        Add video IDs from a metadata file to the ignore list.
        
        Args:
            metadata_file_path: Path to the metadata JSON file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ignore_manager:
            self.logger.error("Ignore list functionality not available. Make sure add_to_ignore_list.py is in the same directory.")
            return False
        
        try:
            metadata_path = Path(metadata_file_path)
            if not metadata_path.exists():
                self.logger.error(f"Metadata file not found: {metadata_path}")
                return False
            
            # Extract video IDs from metadata file using the same logic as the standalone script
            from add_to_ignore_list import extract_video_ids_from_metadata
            video_ids = extract_video_ids_from_metadata(metadata_path)
            
            if not video_ids:
                self.logger.warning("No video IDs found in metadata file")
                return True
            
            # Add video IDs to ignore list
            new_count = self.ignore_manager.add_video_ids(video_ids)
            
            # Save the updated ignore list
            if self.ignore_manager.save_ignore_list():
                self.logger.info(f"✅ Added {new_count} new video IDs to ignore list from {metadata_path}")
                self.logger.info(f"   Total ignored video IDs: {self.ignore_manager.get_ignore_count()}")
                
                if new_count == 0:
                    self.logger.info("   (All video IDs were already in the ignore list)")
                return True
            else:
                self.logger.error("Failed to save ignore list")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding metadata to ignore list: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Adobe Stock Video Thumbnail Scraper (Authentication Required)')
    parser.add_argument('--query', '-q', help='Search query for videos (required unless --random is used)')
    parser.add_argument('--random', '-r', action='store_true', help='Scrape completely random videos from various categories instead of a specific query')
    parser.add_argument('--count', '-c', type=int, default=10, help='Number of videos to download (default: 10)')
    parser.add_argument('--output', '-o', default='downloads', help='Output directory (default: downloads)')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--no-login', action='store_true', help='Skip browser-based authentication (may result in 401 errors)')
    parser.add_argument('--max-duration', type=int, help='Maximum video duration in seconds (excludes longer videos). Note: Duration filtering will check video metadata before download if not available in search results.')
    parser.add_argument('--min-duration', type=int, help='Minimum video duration in seconds (excludes shorter videos). Note: Duration filtering will check video metadata before download if not available in search results.')
    parser.add_argument('--max-size', type=str, help='Maximum video file size in bytes (excludes larger videos). Supports suffixes: K/KB (kilobytes), M/MB (megabytes), G/GB (gigabytes). Example: --max-size 50M for 50 megabytes.')
    parser.add_argument('--exclude-titles', nargs='*', help='Text patterns to exclude from video titles (case-insensitive)')
    parser.add_argument('--json-output', action='store_true', help='Create JSON dictionary instead of downloading videos')
    parser.add_argument('--intended-label', type=str, help='Label for JSON output structure (required when using --json-output)')
    parser.add_argument('--sample-from', type=int, help='Search for this many videos and randomly sample the requested count from them. Must be greater than --count. Useful for getting diverse/random results instead of just the first N videos found.')
    parser.add_argument('--no-ignore-list', action='store_true', help='Disable ignore list functionality - do not skip videos from the ignore_list directory')
    
    args = parser.parse_args()
    
    # Validate query/random arguments - exactly one must be provided
    if not args.query and not args.random:
        parser.error("Either --query or --random must be specified")
    if args.query and args.random:
        parser.error("--query and --random are mutually exclusive - use only one")
    
    # Validate JSON output arguments
    if args.json_output and not args.intended_label:
        parser.error("--intended-label is required when using --json-output")
    
    # Validate sampling arguments
    if args.sample_from is not None:
        if args.sample_from <= 0:
            parser.error("--sample-from must be a positive integer")
        if args.sample_from <= args.count:
            parser.error("--sample-from must be greater than --count for sampling to be effective")
    
    # Parse max-size argument to handle suffixes
    max_size_bytes = None
    if args.max_size:
        max_size_str = str(args.max_size).upper().strip()
        try:
            if max_size_str.endswith(('K', 'KB')):
                max_size_bytes = int(float(max_size_str.rstrip('KB'))) * 1024
            elif max_size_str.endswith(('M', 'MB')):
                max_size_bytes = int(float(max_size_str.rstrip('MB'))) * 1024 * 1024
            elif max_size_str.endswith(('G', 'GB')):
                max_size_bytes = int(float(max_size_str.rstrip('GB'))) * 1024 * 1024 * 1024
            else:
                max_size_bytes = int(float(max_size_str))
        except ValueError:
            parser.error(f"Invalid max-size value: {args.max_size}. Use a number optionally followed by K/KB, M/MB, or G/GB.")
    
    # Create scraper instance (authentication enabled by default)
    use_auth = not args.no_login  # Reverse the logic - auth is default, --no-login disables it
    use_ignore_list = not args.no_ignore_list  # Reverse the logic - ignore list is default, --no-ignore-list disables it
    scraper = AdobeStockScraper(
        download_dir=args.output, 
        delay=args.delay, 
        use_auth=use_auth,
        max_duration_seconds=args.max_duration,
        min_duration_seconds=args.min_duration,
        max_size_bytes=max_size_bytes,
        exclude_title_patterns=args.exclude_titles or [],
        json_output=args.json_output,
        intended_label=args.intended_label,
        sample_from=args.sample_from,
        query=args.query,  # Pass query to enable query-specific ignore lists
        random_mode=args.random,
        use_ignore_list=use_ignore_list
    )
    
    # Create clean query name for the subdirectory (only for specific queries)
    if args.query:
        clean_query = re.sub(r'[^\w\s-]', '', args.query)
        clean_query = re.sub(r'[-\s]+', '_', clean_query)
        clean_query = clean_query.lower().strip('_')
    else:
        clean_query = "random_videos"
    
    # Run scraping
    try:
        # Print configuration
        print(f"\n{'='*60}")
        print(f"ADOBE STOCK VIDEO {'JSON OUTPUT' if args.json_output else 'DOWNLOADER'}")
        print(f"{'='*60}")
        
        if args.random:
            print(f"🎲 Mode: Random videos from diverse categories")
        else:
            print(f"Query: '{args.query}'")
            
        print(f"Count: {args.count}")
        
        if args.sample_from:
            print(f"🎲 Sampling: {args.sample_from} → {args.count} videos")
        if args.json_output:
            print(f"📄 Mode: JSON Output (label: '{args.intended_label}')")
        else:
            print(f"📥 Mode: Download videos")
        
        # Show filters if any
        filters = []
        if args.max_duration:
            filters.append(f"max {args.max_duration}s")
        if args.min_duration:
            filters.append(f"min {args.min_duration}s")
        if max_size_bytes:
            if max_size_bytes >= 1024 * 1024 * 1024:
                filters.append(f"max {max_size_bytes / (1024*1024*1024):.1f}GB")
            elif max_size_bytes >= 1024 * 1024:
                filters.append(f"max {max_size_bytes / (1024*1024):.1f}MB")
            else:
                filters.append(f"max {max_size_bytes / 1024:.1f}KB")
        if args.exclude_titles:
            filters.append(f"exclude: {args.exclude_titles}")
        
        if filters:
            print(f"🔍 Filters: {', '.join(filters)}")
        
        print(f"📂 Output: {args.output}{('/' + clean_query) if not args.json_output else ''}")
        
        if use_auth:
            print("🔐 Authentication: Enabled")
        else:
            print("⚠️  Authentication: Disabled")
        
        if use_ignore_list:
            print("🚫 Ignore List: Enabled")
        else:
            print("⚠️  Ignore List: Disabled")
        
        print(f"{'='*60}")
        
        # Pass query (which will be None for random mode)
        successful = scraper.scrape_and_download(args.query, args.count)
        
        # Show completion message
        print(f"\n{'='*60}")
        if args.json_output:
            print(f"✅ JSON OUTPUT COMPLETE")
            print(f"Videos processed: {successful}")
            print(f"File saved to: {args.output}/")
        else:
            print(f"✅ DOWNLOAD COMPLETE")
            print(f"Videos downloaded: {successful}")
            if args.random:
                print(f"Files saved to: {args.output}/random_videos/")
            else:
                print(f"Files saved to: {args.output}/{clean_query}/")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print(f"\n\n{'='*60}")
        print("❌ INTERRUPTED BY USER")
        print(f"{'='*60}")
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERROR: {e}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 