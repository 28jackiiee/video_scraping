#!/usr/bin/env python3
"""
Adobe Stock Video Thumbnail Scraper

This script scrapes and downloads thumbnail videos from Adobe Stock
based on a search query.

Usage:
    python adobe_stock_scraper.py --query "nature landscape" --count 10
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

class AdobeStockScraper:
    def __init__(self, download_dir: str = "downloads", delay: float = 1.0):
        """
        Initialize the Adobe Stock scraper.
        
        Args:
            download_dir: Directory to save downloaded videos
            delay: Delay between requests in seconds
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        
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
            
            # Try different Adobe Stock URL patterns
            search_urls = [
                "https://stock.adobe.com/search/videos",
                "https://stock.adobe.com/search",
            ]
            
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
        
        # Method 1: Look for various JSON data patterns
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
        
        # Method 2: Use BeautifulSoup for HTML parsing
        if not videos:
            videos = self._extract_video_data_soup(html_content)
        
        # Method 3: Regex fallback for direct video URLs
        if not videos:
            videos = self._extract_video_data_regex(html_content)
        
        return videos

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
        
        # Extract URLs
        preview_urls = []
        comp_urls = []
        
        # Look for various URL patterns
        url_fields = [
            'video_preview_url', 'preview_url', 'comp_url', 'thumbnail_url',
            'video_small_preview_url', 'video_preview_url_https',
            'thumbnail_500_url', 'thumbnail_1000_url'
        ]
        
        for field in url_fields:
            url = item_data.get(field)
            if url and isinstance(url, str):
                if any(ext in url.lower() for ext in ['.mp4', '.mov', '.webm']):
                    if 'preview' in field.lower():
                        preview_urls.append(url)
                    else:
                        comp_urls.append(url)
        
        # If no video URLs found, skip
        if not preview_urls and not comp_urls:
            return None
        
        video_info = {
            'id': item_id,
            'title': item_data.get('title', item_data.get('name', f'Video_{item_id}')),
            'thumbnail_url': item_data.get('thumbnail_500_url', item_data.get('thumbnail_url')),
            'preview_url': preview_urls[0] if preview_urls else None,
            'comp_url': comp_urls[0] if comp_urls else None,
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
        
        # Look for video URLs
        preview_url = None
        comp_url = None
        
        url_attrs = [
            'data-video-preview-url', 'data-comp-url', 'data-preview-url',
            'data-video-url', 'src', 'data-src'
        ]
        
        for attr in url_attrs:
            url = attrs.get(attr)
            if url and any(ext in url.lower() for ext in ['.mp4', '.mov', '.webm']):
                if 'preview' in attr.lower():
                    preview_url = url
                else:
                    comp_url = url
                break
        
        if not preview_url and not comp_url:
            return None
        
        # Extract title
        title = (attrs.get('data-title') or 
                attrs.get('alt') or 
                attrs.get('title') or 
                element.get_text(strip=True) or 
                f"Video_{element_id}")
        
        return {
            'id': element_id,
            'title': title[:100],  # Limit title length
            'thumbnail_url': attrs.get('data-thumbnail-url'),
            'preview_url': preview_url,
            'comp_url': comp_url,
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
        
        # Look for video URLs in various formats
        video_patterns = [
            r'https://[^"\s]*adobe[^"\s]*\.mp4',
            r'https://[^"\s]*stock\.adobe\.com[^"\s]*\.(mp4|mov|webm)',
            r'data-video-preview-url="([^"]+)"',
            r'data-comp-url="([^"]+)"',
            r'"video_preview_url":\s*"([^"]+)"',
            r'"comp_url":\s*"([^"]+)"',
        ]
        
        for i, pattern in enumerate(video_patterns):
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for j, match in enumerate(matches):
                url = match if isinstance(match, str) else match[0]
                if url and any(ext in url.lower() for ext in ['.mp4', '.mov', '.webm']):
                    video_info = {
                        'id': f'regex_{i}_{j}',
                        'title': f'Video_regex_{i}_{j}',
                        'thumbnail_url': None,
                        'preview_url': url if 'preview' in url.lower() else None,
                        'comp_url': url if 'preview' not in url.lower() else None,
                        'description': '',
                        'tags': []
                    }
                    videos.append(video_info)
        
        if videos:
            self.logger.info(f"Regex extraction found {len(videos)} videos")
        
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
        # Determine the best URL to download
        download_url = video_data.get('comp_url') or video_data.get('preview_url')
        
        if not download_url:
            self.logger.warning(f"No download URL found for video {video_data['id']}")
            return False
        
        # Create filename
        if not filename:
            if query_prefix is not None and index is not None:
                # Use query-based naming: query_0.mp4, query_1.mp4, etc.
                extension = '.mp4'
                if download_url:
                    if '.mov' in download_url.lower():
                        extension = '.mov'
                    elif '.webm' in download_url.lower():
                        extension = '.webm'
                filename = f"{query_prefix}_{index}{extension}"
            else:
                # Fall back to original naming scheme
                safe_title = re.sub(r'[^\w\s-]', '', video_data['title'])
                safe_title = re.sub(r'[-\s]+', '_', safe_title)
                extension = '.mp4'
                if download_url:
                    if '.mov' in download_url.lower():
                        extension = '.mov'
                    elif '.webm' in download_url.lower():
                        extension = '.webm'
                filename = f"{video_data['id']}_{safe_title}{extension}"
        
        filepath = self.download_dir / filename
        
        # Skip if file already exists
        if filepath.exists():
            self.logger.info(f"File {filename} already exists, skipping...")
            return True
        
        try:
            self.logger.info(f"Downloading {filename} from {download_url}")
            
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info(f"Successfully downloaded {filename}")
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
    
    args = parser.parse_args()
    
    # Create scraper instance
    scraper = AdobeStockScraper(download_dir=args.output, delay=args.delay)
    
    # Create clean query name for the subdirectory
    clean_query = re.sub(r'[^\w\s-]', '', args.query)
    clean_query = re.sub(r'[-\s]+', '_', clean_query)
    clean_query = clean_query.lower().strip('_')
    
    # Run scraping
    try:
        downloaded_count = scraper.scrape_and_download(args.query, args.count)
        query_dir = f"{args.output}/{clean_query}"
        print(f"\nScraping completed! Downloaded {downloaded_count} videos to '{query_dir}' directory.")
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main() 