#!/usr/bin/env python3
"""
Script to add video IDs from metadata files to query-specific ignore lists.

This script reads metadata files (like query_metadata.json) and extracts
video IDs from the video_file_mappings section, then adds them to a 
query-specific ignore list file that adobe_stock_scraper.py can use to 
avoid downloading these videos in future sessions.

When processing a metadata file, the script automatically creates a 
query-specific ignore list named "{query}_ignore_list.json" based on 
the "query" field in the metadata file.

Usage:
    python add_to_ignore_list.py <metadata_file_path>
    python add_to_ignore_list.py '/Users/jackieli/Downloads/prof_code/scraping_vis/downloads/testing/Dolly Zoom/dolly_zoom/query_metadata.json'
    
    # This will create "ignore_list/dolly_zoom_ignore_list.json" for the above example

Examples:
    # Add videos from metadata file (creates query-specific ignore list)
    python add_to_ignore_list.py downloads/nature/query_metadata.json
    → Creates: ignore_list/nature_ignore_list.json
    
    # Add videos from metadata file (creates query-specific ignore list)  
    python add_to_ignore_list.py downloads/city_skyline/query_metadata.json
    → Creates: ignore_list/city_skyline_ignore_list.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Set, List, Tuple
import time
import re


class IgnoreListManager:
    """Manages the persistent ignore list for Adobe Stock video IDs."""
    
    def __init__(self, ignore_list_path: str = "ignore_list/adobe_stock_ignore_list.json"):
        """
        Initialize the ignore list manager.
        
        Args:
            ignore_list_path: Path to the ignore list file
        """
        self.ignore_list_path = Path(ignore_list_path)
        # Ensure parent directory exists
        self.ignore_list_path.parent.mkdir(exist_ok=True)
        self.ignore_list = self.load_ignore_list()
    
    def load_ignore_list(self) -> Set[str]:
        """
        Load the existing ignore list from file.
        
        Returns:
            Set of video IDs to ignore
        """
        if not self.ignore_list_path.exists():
            return set()
        
        try:
            with open(self.ignore_list_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('ignored_video_ids', []))
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            print(f"Warning: Could not load ignore list from {self.ignore_list_path}: {e}")
            return set()
    
    def save_ignore_list(self) -> bool:
        """
        Save the ignore list to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                'ignored_video_ids': sorted(list(self.ignore_list)),
                'last_updated': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                'total_ignored': len(self.ignore_list),
                'description': 'List of Adobe Stock video IDs to ignore during scraping'
            }
            
            with open(self.ignore_list_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error: Could not save ignore list to {self.ignore_list_path}: {e}")
            return False
    
    def add_video_ids(self, video_ids: List[str]) -> int:
        """
        Add video IDs to the ignore list.
        
        Args:
            video_ids: List of video IDs to add
            
        Returns:
            Number of new video IDs added
        """
        initial_count = len(self.ignore_list)
        
        # Convert to strings and add to set
        for video_id in video_ids:
            if video_id and str(video_id).strip():
                self.ignore_list.add(str(video_id).strip())
        
        new_count = len(self.ignore_list) - initial_count
        return new_count
    
    def remove_video_ids(self, video_ids: List[str]) -> int:
        """
        Remove video IDs from the ignore list.
        
        Args:
            video_ids: List of video IDs to remove
            
        Returns:
            Number of video IDs removed
        """
        initial_count = len(self.ignore_list)
        
        for video_id in video_ids:
            if video_id and str(video_id).strip():
                self.ignore_list.discard(str(video_id).strip())
        
        removed_count = initial_count - len(self.ignore_list)
        return removed_count
    
    def is_ignored(self, video_id: str) -> bool:
        """
        Check if a video ID is in the ignore list.
        
        Args:
            video_id: Video ID to check
            
        Returns:
            True if the video ID should be ignored
        """
        return str(video_id).strip() in self.ignore_list
    
    def get_ignore_count(self) -> int:
        """Get the total number of ignored video IDs."""
        return len(self.ignore_list)


def extract_and_clean_query_from_metadata(metadata_file_path: Path) -> str:
    """
    Extract the query from a metadata file and clean it for use as a filename.
    
    Args:
        metadata_file_path: Path to the metadata JSON file
        
    Returns:
        Cleaned query string suitable for filenames
    """
    if not metadata_file_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file_path}")
    
    try:
        with open(metadata_file_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in metadata file: {e}")
    
    # Extract query from metadata
    query = metadata.get('query', '')
    
    if not query:
        raise ValueError("No 'query' field found in metadata file")
    
    # Clean the query using the same logic as adobe_stock_scraper.py
    clean_query = re.sub(r'[^\w\s-]', '', query)  # Remove special characters except spaces and hyphens
    clean_query = re.sub(r'[-\s]+', '_', clean_query)  # Replace spaces and hyphens with underscores
    clean_query = clean_query.lower().strip('_')  # Lowercase and remove leading/trailing underscores
    
    if not clean_query:
        clean_query = 'unknown_query'
    
    return clean_query


def get_ignore_list_directory() -> Path:
    """
    Get the ignore list directory path, creating it if it doesn't exist.
    
    Returns:
        Path to the ignore list directory
    """
    ignore_list_dir = Path("ignore_list")
    ignore_list_dir.mkdir(exist_ok=True)
    return ignore_list_dir


def get_query_specific_ignore_list_path(query_name: str) -> Path:
    """
    Generate a query-specific ignore list path in the ignore_list directory.
    
    Args:
        query_name: Clean query name
        
    Returns:
        Path to the query-specific ignore list file
    """
    ignore_list_dir = get_ignore_list_directory()
    return ignore_list_dir / f"{query_name}_ignore_list.json"


def extract_video_ids_from_metadata(metadata_file_path: Path) -> List[str]:
    """
    Extract video IDs from a metadata file.
    
    Args:
        metadata_file_path: Path to the metadata JSON file
        
    Returns:
        List of video IDs found in the file
    """
    if not metadata_file_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file_path}")
    
    try:
        with open(metadata_file_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in metadata file: {e}")
    
    # Extract video IDs from video_file_mappings
    video_file_mappings = metadata.get('video_file_mappings', {})
    
    if not video_file_mappings:
        print("Warning: No video_file_mappings found in metadata file")
        return []
    
    # The keys in video_file_mappings are the video IDs
    video_ids = list(video_file_mappings.keys())
    
    print(f"Found {len(video_ids)} video IDs in metadata file")
    return video_ids


def main():
    """Main function to handle command line arguments and process metadata files."""
    parser = argparse.ArgumentParser(
        description="Add video IDs from metadata files to query-specific Adobe Stock ignore lists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Add videos from a metadata file to query-specific ignore list
    python add_to_ignore_list.py downloads/dolly_zoom/query_metadata.json
    → Creates: ignore_list/dolly_zoom_ignore_list.json
    
    # Add videos from a metadata file to query-specific ignore list
    python add_to_ignore_list.py downloads/nature_scenes/query_metadata.json
    → Creates: ignore_list/nature_scenes_ignore_list.json
    
    # Use custom ignore list file location for general operations
    python add_to_ignore_list.py --status --ignore-list my_ignore_list.json
    
    # Show current ignore list status (uses default ignore list)
    python add_to_ignore_list.py --status
    
    # Remove specific video IDs from default ignore list
    python add_to_ignore_list.py --remove 537301017 571470338
        """
    )
    
    parser.add_argument('metadata_file', nargs='?', type=str,
                        help='Path to the metadata JSON file. When provided, creates a query-specific ignore list based on the query name in the metadata.')
    parser.add_argument('--ignore-list', '-i', default=str(get_ignore_list_directory() / "adobe_stock_ignore_list.json"),
                        help='Path to the ignore list file for --status, --remove, and --clear operations (default: ignore_list/adobe_stock_ignore_list.json). Note: When processing metadata files, query-specific ignore lists are created automatically.')
    parser.add_argument('--status', '-s', action='store_true',
                        help='Show current ignore list status')
    parser.add_argument('--remove', '-r', nargs='+', metavar='VIDEO_ID',
                        help='Remove specific video IDs from ignore list')
    parser.add_argument('--clear', '-c', action='store_true',
                        help='Clear all video IDs from ignore list')
    parser.add_argument('--dry-run', '-d', action='store_true',
                        help='Show what would be added without actually modifying the ignore list')
    
    args = parser.parse_args()
    
    # Initialize ignore list manager
    ignore_manager = IgnoreListManager(args.ignore_list)
    
    # Handle status command
    if args.status:
        print(f"📋 Ignore List Status")
        print(f"   File: {ignore_manager.ignore_list_path}")
        print(f"   Total ignored video IDs: {ignore_manager.get_ignore_count()}")
        if ignore_manager.get_ignore_count() > 0:
            print(f"   Sample IDs: {list(ignore_manager.ignore_list)[:5]}")
            if ignore_manager.get_ignore_count() > 5:
                print(f"   ... and {ignore_manager.get_ignore_count() - 5} more")
        return
    
    # Handle remove command
    if args.remove:
        removed_count = ignore_manager.remove_video_ids(args.remove)
        if ignore_manager.save_ignore_list():
            print(f"✅ Removed {removed_count} video IDs from ignore list")
            print(f"   Remaining ignored IDs: {ignore_manager.get_ignore_count()}")
        else:
            print("❌ Failed to save ignore list")
            sys.exit(1)
        return
    
    # Handle clear command
    if args.clear:
        old_count = ignore_manager.get_ignore_count()
        ignore_manager.ignore_list.clear()
        if ignore_manager.save_ignore_list():
            print(f"✅ Cleared ignore list (removed {old_count} video IDs)")
        else:
            print("❌ Failed to save ignore list")
            sys.exit(1)
        return
    
    # Handle metadata file processing
    if not args.metadata_file:
        parser.error("Metadata file path is required (or use --status, --remove, or --clear)")
    
    metadata_file_path = Path(args.metadata_file)
    
    try:
        # Extract query from metadata file
        query_name = extract_and_clean_query_from_metadata(metadata_file_path)
        
        # Also load the original query for display purposes
        with open(metadata_file_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        original_query = metadata.get('query', 'unknown')
        
        # Construct the specific ignore list filename
        specific_ignore_list_path = get_query_specific_ignore_list_path(query_name)
        
        # Initialize specific ignore list manager
        specific_ignore_manager = IgnoreListManager(specific_ignore_list_path)
        
        print(f"📹 Processing metadata file for query: '{original_query}'")
        print(f"🎯 Using query-specific ignore list: {specific_ignore_list_path}")
        
        # Extract video IDs from metadata file
        video_ids = extract_video_ids_from_metadata(metadata_file_path)
        
        if not video_ids:
            print("No video IDs found to add to ignore list")
            return
        
        print(f"📹 Found {len(video_ids)} video IDs in {metadata_file_path}")
        
        # Show sample of video IDs that will be added
        print(f"   Sample IDs: {video_ids[:5]}")
        if len(video_ids) > 5:
            print(f"   ... and {len(video_ids) - 5} more")
        
        if args.dry_run:
            print(f"🔍 Dry run: Would add {len(video_ids)} video IDs to query-specific ignore list '{query_name}_ignore_list.json'")
            already_ignored = sum(1 for vid in video_ids if specific_ignore_manager.is_ignored(vid))
            new_additions = len(video_ids) - already_ignored
            print(f"   {already_ignored} already in query-specific ignore list")
            print(f"   {new_additions} would be newly added")
            return
        
        # Add video IDs to specific ignore list
        new_count = specific_ignore_manager.add_video_ids(video_ids)
        
        # Save the updated specific ignore list
        if specific_ignore_manager.save_ignore_list():
            print(f"✅ Successfully added {new_count} new video IDs to query-specific ignore list for '{query_name}'")
            print(f"   Total video IDs in '{query_name}' ignore list: {specific_ignore_manager.get_ignore_count()}")
            print(f"   Query-specific ignore list saved to: {specific_ignore_manager.ignore_list_path}")
            
            if new_count == 0:
                print("   (All video IDs were already in the query-specific ignore list)")
        else:
            print("❌ Failed to save query-specific ignore list")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 