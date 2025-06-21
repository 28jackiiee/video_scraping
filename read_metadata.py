#!/usr/bin/env python3
"""
Utility script to read and display metadata from Adobe Stock scraper downloads.

Usage:
    python read_metadata.py [directory_path]
"""

import json
import os
import sys
from pathlib import Path

def read_metadata(directory_path):
    """Read and display metadata from a scraper download directory."""
    dir_path = Path(directory_path)
    
    if not dir_path.exists():
        print(f"Error: Directory '{directory_path}' does not exist.")
        return False
    
    metadata_file = dir_path / "query_metadata.json"
    
    if not metadata_file.exists():
        print(f"Error: No metadata file found in '{directory_path}'.")
        return False
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        print(f"📁 Directory: {dir_path.name}")
        print(f"🔍 Original Query: '{metadata.get('original_query', 'N/A')}'")
        print(f"📂 Clean Query: {metadata.get('clean_query', 'N/A')}")
        print(f"📅 Created: {metadata.get('created_at', 'N/A')}")
        print(f"🕒 Last Updated: {metadata.get('last_updated', 'N/A')}")
        print(f"🎥 Total Videos Downloaded: {metadata.get('total_videos_downloaded', 0)}")
        
        if 'last_download_session' in metadata:
            session = metadata['last_download_session']
            print(f"📊 Last Session:")
            print(f"   - Requested: {session.get('requested_count', 'N/A')}")
            print(f"   - New Downloads: {session.get('new_downloads', 'N/A')}")
            print(f"   - Session Time: {session.get('session_timestamp', 'N/A')}")
        
        # Display video file mappings if available
        if 'video_file_mappings' in metadata:
            video_mappings = metadata['video_file_mappings']
            print(f"🔗 Video ID to Filename Mappings ({len(video_mappings)} videos):")
            for video_id, mapping in video_mappings.items():
                filename = mapping.get('filename', 'N/A')
                title = mapping.get('title', 'N/A')
                download_time = mapping.get('download_timestamp', 'N/A')
                print(f"   📹 ID: {video_id}")
                print(f"      File: {filename}")
                print(f"      Title: {title[:80]}{'...' if len(title) > 80 else ''}")
                print(f"      Downloaded: {download_time}")
                print()
        
        # Count actual video files
        video_extensions = ['.mp4', '.mov', '.webm']
        video_files = []
        for ext in video_extensions:
            video_files.extend(dir_path.glob(f"*{ext}"))
        
        print(f"📹 Actual Video Files Found: {len(video_files)}")
        
        # Check for unmapped files (files that exist but aren't in the mapping)
        if 'video_file_mappings' in metadata:
            mapped_files = {mapping['filename'] for mapping in metadata['video_file_mappings'].values()}
            actual_files = {f.name for f in video_files}
            unmapped_files = actual_files - mapped_files
            
            if unmapped_files:
                print(f"⚠️  Unmapped Files ({len(unmapped_files)} files without video ID mapping):")
                for filename in sorted(unmapped_files):
                    print(f"   - {filename}")
        
        return True
        
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in metadata file '{metadata_file}'.")
        return False
    except Exception as e:
        print(f"Error reading metadata: {e}")
        return False

def list_all_downloads(downloads_dir="downloads"):
    """List all download directories and their metadata."""
    downloads_path = Path(downloads_dir)
    
    if not downloads_path.exists():
        print(f"Error: Downloads directory '{downloads_dir}' does not exist.")
        return
    
    # Find all subdirectories with metadata files
    metadata_dirs = []
    for item in downloads_path.iterdir():
        if item.is_dir() and (item / "query_metadata.json").exists():
            metadata_dirs.append(item)
    
    if not metadata_dirs:
        print(f"No download directories with metadata found in '{downloads_dir}'.")
        return
    
    print(f"Found {len(metadata_dirs)} download directories:\n")
    
    for i, dir_path in enumerate(sorted(metadata_dirs), 1):
        print(f"{i}. {dir_path.name}")
        print("   " + "="*50)
        read_metadata(dir_path)
        print()

def main():
    if len(sys.argv) > 1:
        # Read metadata for specific directory
        directory_path = sys.argv[1]
        read_metadata(directory_path)
    else:
        # List all download directories
        print("Adobe Stock Scraper - Download Metadata\n")
        list_all_downloads()

if __name__ == "__main__":
    main() 