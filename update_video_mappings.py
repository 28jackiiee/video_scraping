#!/usr/bin/env python3
"""
Utility script to update video ID to filename mappings for existing video files.

This script helps when you have existing video files but the metadata doesn't include
the video ID to filename mappings. It can:
1. Try to extract video IDs from filenames if they contain IDs
2. Allow manual mapping entry
3. Use existing JSON files to create mappings

Usage:
    python update_video_mappings.py [directory_path]
"""

import json
import os
import sys
import re
from pathlib import Path

def extract_video_id_from_filename(filename):
    """Try to extract video ID from filename if it contains one."""
    # Look for patterns like _123456789.mp4 or 123456789_ in filename
    patterns = [
        r'_(\d{8,})\.mp4$',  # Filename ending with _ID.mp4
        r'_(\d{8,})_',       # ID surrounded by underscores
        r'(\d{8,})\.mp4$',   # Filename ending with just ID.mp4
        r'^(\d{8,})_',       # Filename starting with ID_
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    
    return None

def load_json_mappings(directory_path):
    """Load video ID mappings from JSON files in the directory and parent directory."""
    json_mappings = {}
    
    # Search in current directory and parent directory
    search_paths = [directory_path, directory_path.parent]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
            
        json_files = list(search_path.glob("*.json"))
        
        for json_file in json_files:
            if json_file.name == "query_metadata.json":
                continue
                
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Handle the structure: {"label": {"query": [{"id": "...", "caption": "..."}]}}
                for label_data in data.values():
                    if isinstance(label_data, dict):
                        for query_data in label_data.values():
                            if isinstance(query_data, list):
                                for video_data in query_data:
                                    if isinstance(video_data, dict) and 'id' in video_data:
                                        video_id = video_data['id']
                                        title = video_data.get('caption', video_data.get('title', ''))
                                        json_mappings[video_id] = {
                                            'title': title,
                                            'source_file': json_file.name,
                                            'source_path': str(json_file.relative_to(directory_path.parent))
                                        }
            except Exception as e:
                print(f"Warning: Could not parse {json_file.name}: {e}")
    
    return json_mappings

def find_matching_videos(video_files, json_mappings):
    """Try to match video files with JSON data based on titles."""
    matches = {}
    
    for video_file in video_files:
        filename_no_ext = video_file.stem
        
        # Clean filename for comparison (remove underscores, make lowercase)
        clean_filename = re.sub(r'[_-]', ' ', filename_no_ext).lower()
        
        best_match = None
        best_score = 0
        
        for video_id, mapping in json_mappings.items():
            title = mapping['title']
            clean_title = re.sub(r'[^\w\s]', '', title).lower()
            
            # Simple similarity check - count matching words
            filename_words = set(clean_filename.split())
            title_words = set(clean_title.split())
            
            if len(title_words) > 0:
                common_words = filename_words.intersection(title_words)
                score = len(common_words) / len(title_words)
                
                if score > best_score and score > 0.3:  # At least 30% word match
                    best_match = video_id
                    best_score = score
        
        if best_match:
            matches[video_file.name] = {
                'video_id': best_match,
                'title': json_mappings[best_match]['title'],
                'match_score': best_score,
                'source': json_mappings[best_match]['source_file']
            }
    
    return matches

def update_metadata_mappings(directory_path, new_mappings):
    """Update the query_metadata.json file with new video mappings."""
    metadata_file = directory_path / "query_metadata.json"
    
    if not metadata_file.exists():
        print("No query_metadata.json file found. Creating new one.")
        metadata = {
            "original_query": "unknown",
            "clean_query": directory_path.name,
            "created_at": "unknown",
            "last_updated": "unknown"
        }
    else:
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"Error reading metadata file: {e}")
            return False
    
    # Add or update video file mappings
    if "video_file_mappings" not in metadata:
        metadata["video_file_mappings"] = {}
    
    # Add new mappings
    for filename, mapping_data in new_mappings.items():
        metadata["video_file_mappings"][mapping_data['video_id']] = {
            'filename': filename,
            'title': mapping_data['title'],
            'url': f'https://stock.adobe.com/Download/Watermarked/{mapping_data["video_id"]}',
            'download_timestamp': 'unknown - mapped retroactively',
            'mapping_source': mapping_data.get('source', 'manual')
        }
    
    # Save updated metadata
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"✅ Updated metadata file with {len(new_mappings)} new mappings")
        return True
    except Exception as e:
        print(f"❌ Error saving metadata file: {e}")
        return False

def main():
    if len(sys.argv) > 1:
        directory_path = Path(sys.argv[1])
    else:
        print("Please provide a directory path.")
        print("Usage: python update_video_mappings.py [directory_path]")
        return
    
    if not directory_path.exists():
        print(f"Error: Directory '{directory_path}' does not exist.")
        return
    
    print(f"🔍 Analyzing directory: {directory_path}")
    
    # Find video files
    video_extensions = ['.mp4', '.mov', '.webm', '.avi', '.mkv']
    video_files = []
    for ext in video_extensions:
        video_files.extend(directory_path.glob(f"*{ext}"))
    
    if not video_files:
        print("No video files found in directory.")
        return
    
    print(f"📹 Found {len(video_files)} video files")
    
    # Load existing metadata
    metadata_file = directory_path / "query_metadata.json"
    existing_mappings = {}
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                existing_mappings = metadata.get("video_file_mappings", {})
        except Exception as e:
            print(f"Warning: Could not read existing metadata: {e}")
    
    # Find unmapped files
    mapped_files = {mapping['filename'] for mapping in existing_mappings.values()}
    unmapped_files = [f for f in video_files if f.name not in mapped_files]
    
    if not unmapped_files:
        print("✅ All video files already have mappings!")
        return
    
    print(f"⚠️  Found {len(unmapped_files)} unmapped files")
    
    # Try to extract IDs from filenames
    id_from_filename = {}
    for video_file in unmapped_files:
        video_id = extract_video_id_from_filename(video_file.name)
        if video_id:
            id_from_filename[video_file.name] = video_id
    
    if id_from_filename:
        print(f"📝 Extracted video IDs from {len(id_from_filename)} filenames:")
        for filename, video_id in id_from_filename.items():
            print(f"   {filename} -> ID: {video_id}")
    
    # Load JSON mappings
    json_mappings = load_json_mappings(directory_path)
    if json_mappings:
        print(f"📄 Found {len(json_mappings)} video entries in JSON files")
        
        # Try to match videos with JSON data
        matches = find_matching_videos(unmapped_files, json_mappings)
        if matches:
            print(f"🔗 Found {len(matches)} potential matches based on titles:")
            for filename, match_data in matches.items():
                print(f"   {filename}")
                print(f"      -> ID: {match_data['video_id']} (score: {match_data['match_score']:.2f})")
                print(f"      -> Title: {match_data['title'][:60]}...")
                print()
    
    # Combine all mappings
    new_mappings = {}
    
    # Add filename-based IDs
    for filename, video_id in id_from_filename.items():
        new_mappings[filename] = {
            'video_id': video_id,
            'title': f'Video_{video_id}',
            'source': 'filename_extraction'
        }
    
    # Add JSON-based matches (these override filename-based ones)
    if 'matches' in locals():
        for filename, match_data in matches.items():
            new_mappings[filename] = {
                'video_id': match_data['video_id'],
                'title': match_data['title'],
                'source': f"json_match_{match_data['source']}"
            }
    
    if new_mappings:
        print(f"\n📋 Summary: Will create {len(new_mappings)} new mappings")
        
        # Ask for confirmation
        response = input("Do you want to update the metadata file? (y/N): ").lower().strip()
        if response in ['y', 'yes']:
            if update_metadata_mappings(directory_path, new_mappings):
                print("✅ Mappings updated successfully!")
            else:
                print("❌ Failed to update mappings")
        else:
            print("Operation cancelled.")
    else:
        print("❌ No mappings could be created automatically.")
        print("You may need to create mappings manually by editing the metadata file.")

if __name__ == "__main__":
    main() 