#!/usr/bin/env python3
"""
Video Filter for M4 MacBook with MPS acceleration.
Simplified version that avoids problematic imports.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np

# Import required libraries
try:
    import torch
    import clip
    from PIL import Image
    import cv2
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError as e:
    print(f"Error: Missing required dependencies: {e}")
    print("Run: pip install torch clip-by-openai pillow opencv-python-headless scikit-learn")
    sys.exit(1)


class M4VideoFilter:
    def __init__(self, device=None):
        """Initialize the video filter with CLIP model optimized for M4 MacBook."""
        # Auto-detect best available device, prioritizing MPS for M4 MacBook
        if device:
            self.device = device
        elif torch.backends.mps.is_available():
            self.device = "mps"  # Apple Silicon M4 GPU acceleration
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        
        print(f"🚀 M4 Video Filter starting...")
        print(f"Device: {self.device}")
        if self.device == "mps":
            print("🍎 Apple M4 GPU acceleration enabled")
        elif self.device == "cuda":
            print("🚀 NVIDIA GPU acceleration enabled")
        else:
            print("💻 Using CPU (slower processing)")
        
        # Load CLIP model
        try:
            print("Loading CLIP model...")
            self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)
            print("✅ CLIP model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading CLIP model: {e}")
            sys.exit(1)
    
    def extract_frames(self, video_path: Path, num_frames: int = 8) -> List[np.ndarray]:
        """Extract evenly spaced frames from a video."""
        print(f"  📹 Extracting frames from: {video_path.name}")
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            print(f"  ⚠️  Could not open video {video_path}")
            return []
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            print(f"  ⚠️  Video {video_path} has no frames")
            cap.release()
            return []
        
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        frames = []
        
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
        
        cap.release()
        print(f"  ✅ Extracted {len(frames)} frames")
        return frames
    
    def encode_video(self, video_path: Path) -> np.ndarray:
        """Encode a video into a CLIP embedding by averaging frame embeddings."""
        frames = self.extract_frames(video_path)
        
        if not frames:
            return np.zeros(512)  # Return zero embedding for failed videos
        
        frame_embeddings = []
        
        print(f"  🧠 Processing {len(frames)} frames with CLIP...")
        for i, frame in enumerate(frames):
            # Convert numpy array to PIL Image
            pil_image = Image.fromarray(frame)
            
            # Preprocess and encode the frame
            image_input = self.preprocess(pil_image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                frame_embeddings.append(image_features.cpu().numpy())
        
        if frame_embeddings:
            # Average all frame embeddings
            video_embedding = np.mean(frame_embeddings, axis=0)
            print(f"  ✅ Video encoded successfully")
            return video_embedding.flatten()
        else:
            return np.zeros(512)
    
    def encode_text(self, text: str) -> np.ndarray:
        """Encode text into a CLIP embedding."""
        text_input = clip.tokenize([text]).to(self.device)
        
        with torch.no_grad():
            text_features = self.model.encode_text(text_input)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            return text_features.cpu().numpy().flatten()
    
    def calculate_similarity(self, video_embedding: np.ndarray, text_embedding: np.ndarray) -> float:
        """Calculate cosine similarity between video and text embeddings."""
        if video_embedding.shape[0] == 0 or text_embedding.shape[0] == 0:
            return 0.0
        
        video_embedding = video_embedding.reshape(1, -1)
        text_embedding = text_embedding.reshape(1, -1)
        
        similarity = cosine_similarity(video_embedding, text_embedding)[0][0]
        return float(similarity)
    
    def find_videos(self, directory: Path) -> List[Path]:
        """Find all video files in a directory."""
        video_extensions = {'.mp4', '.mov', '.webm', '.avi', '.mkv'}
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(directory.glob(f"*{ext}"))
        
        return sorted(video_files)
    
    def load_metadata(self, directory: Path) -> Dict:
        """Load metadata from a directory."""
        metadata_file = directory / "query_metadata.json"
        
        if not metadata_file.exists():
            return {}
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Warning: Could not load metadata from {metadata_file}: {e}")
            return {}
    
    def filter_videos(self, source_dir: Path, query: str = None, top_k: int = 5) -> List[Tuple[Path, float, str]]:
        """Filter videos by similarity to query text."""
        print(f"\n🔍 Filtering videos in: {source_dir}")
        
        video_results = []
        
        # Process each subdirectory
        for subdir in source_dir.iterdir():
            if not subdir.is_dir():
                continue
            
            print(f"\n📁 Processing directory: {subdir.name}")
            
            # Load metadata to get the original query
            metadata = self.load_metadata(subdir)
            
            # Use provided query or fall back to metadata query
            search_query = query
            if not search_query and metadata:
                search_query = metadata.get('original_query', metadata.get('clean_query', ''))
            
            if not search_query:
                print(f"⚠️  No query found for {subdir.name}, skipping...")
                continue
            
            print(f"🎯 Query: '{search_query}'")
            
            # Encode the text query
            text_embedding = self.encode_text(search_query)
            print(f"✅ Text query encoded")
            
            # Find video files
            video_files = self.find_videos(subdir)
            
            if not video_files:
                print(f"⚠️  No video files found in {subdir.name}")
                continue
            
            print(f"🎥 Found {len(video_files)} video files")
            
            # Process each video
            for video_file in video_files:
                print(f"\n📹 Processing: {video_file.name}")
                
                # Encode video
                video_embedding = self.encode_video(video_file)
                
                # Calculate similarity
                similarity = self.calculate_similarity(video_embedding, text_embedding)
                
                video_results.append((video_file, similarity, search_query))
                print(f"📊 Similarity score: {similarity:.4f}")
        
        # Sort by similarity (highest first)
        video_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k results
        return video_results[:top_k]
    
    def clean_query_for_folder(self, query: str) -> str:
        """Clean query text to make it safe for folder names."""
        import re
        
        # Remove or replace problematic characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', query)  # Replace filesystem-unsafe chars
        cleaned = re.sub(r'\s+', '_', cleaned)  # Replace spaces with underscores
        cleaned = re.sub(r'_+', '_', cleaned)  # Replace multiple underscores with single
        cleaned = cleaned.strip('_')  # Remove leading/trailing underscores
        
        # Limit length to avoid filesystem issues
        if len(cleaned) > 50:
            cleaned = cleaned[:50].rstrip('_')
        
        return cleaned or "unknown_query"
    
    def copy_filtered_videos(self, filtered_videos: List[Tuple[Path, float, str]], output_dir: Path):
        """Copy filtered videos to output directory organized by query."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📋 Copying {len(filtered_videos)} videos to: {output_dir}")
        
        # Group videos by query
        query_groups = {}
        for video_path, similarity, query in filtered_videos:
            if query not in query_groups:
                query_groups[query] = []
            query_groups[query].append((video_path, similarity))
        
        # Create a summary results file for the main directory
        summary_data = {
            "filtering_timestamp": str(Path().absolute()),
            "total_videos_filtered": len(filtered_videos),
            "device_used": self.device,
            "total_queries": len(query_groups),
            "query_summary": []
        }
        
        # Process each query group
        for query, videos in query_groups.items():
            # Create query-specific subdirectory
            query_folder_name = self.clean_query_for_folder(query)
            query_output_dir = output_dir / query_folder_name
            query_output_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"\n📁 Creating folder for query: '{query}' -> {query_folder_name}")
            
            # Create query-specific results data
            query_results = {
                "filtering_timestamp": str(Path().absolute()),
                "original_query": query,
                "folder_name": query_folder_name,
                "device_used": self.device,
                "total_videos_in_query": len(videos),
                "videos": []
            }
            
            # Sort videos in this query group by similarity
            videos.sort(key=lambda x: x[1], reverse=True)
            
            for i, (video_path, similarity) in enumerate(videos, 1):
                # Create new filename with rank and similarity
                original_name = video_path.stem
                extension = video_path.suffix
                new_name = f"rank_{i:02d}_sim_{similarity:.4f}_{original_name}{extension}"
                
                output_path = query_output_dir / new_name
                
                try:
                    shutil.copy2(video_path, output_path)
                    print(f"  ✅ Copied: {new_name}")
                    
                    query_results["videos"].append({
                        "rank": i,
                        "original_path": str(video_path),
                        "output_filename": new_name,
                        "similarity_score": similarity,
                        "source_directory": video_path.parent.name
                    })
                    
                except Exception as e:
                    print(f"  ❌ Failed to copy {video_path.name}: {e}")
            
            # Save query-specific results file in the query folder
            query_results_file = query_output_dir / "filtering_results.json"
            with open(query_results_file, 'w', encoding='utf-8') as f:
                json.dump(query_results, f, indent=2, ensure_ascii=False)
            
            print(f"  📊 Query results saved to: {query_results_file}")
            
            # Add to summary
            summary_data["query_summary"].append({
                "query": query,
                "folder_name": query_folder_name,
                "video_count": len(videos),
                "top_similarity": max(similarity for _, similarity in videos) if videos else 0.0,
                "avg_similarity": sum(similarity for _, similarity in videos) / len(videos) if videos else 0.0
            })
        
        # Save summary results file in the main filtered directory
        summary_file = output_dir / "filtering_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Summary saved to: {summary_file}")
        print(f"📁 Videos organized into {len(query_groups)} query-based folders")
        print(f"📋 Each folder contains its own filtering_results.json file")


def main():
    parser = argparse.ArgumentParser(description="Filter videos using CLIP embeddings (M4 MacBook optimized)")
    parser.add_argument(
        "--source_dir", 
        type=str, 
        default="downloads",
        help="Source directory containing video subdirectories (default: downloads)"
    )
    parser.add_argument(
        "--top_k", 
        type=int, 
        default=5,
        help="Number of top matching videos to filter (default: 5)"
    )
    parser.add_argument(
        "--query", 
        type=str,
        help="Text query to match against (if not provided, uses metadata queries)"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="filtered",
        help="Output directory for filtered videos (default: filtered)"
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "cuda", "mps"],
        default="auto",
        help="Device to use: auto (default), cpu, cuda (NVIDIA), or mps (Apple Silicon)"
    )
    
    args = parser.parse_args()
    
    # Validate source directory
    source_path = Path(args.source_dir)
    if not source_path.exists():
        print(f"❌ Error: Source directory '{args.source_dir}' does not exist.")
        sys.exit(1)
    
    # Initialize filter
    print("🍎 Initializing M4 Video Filter with CLIP...")
    device = None if args.device == "auto" else args.device
    video_filter = M4VideoFilter(device=device)
    
    # Filter videos
    filtered_videos = video_filter.filter_videos(
        source_dir=source_path,
        query=args.query,
        top_k=args.top_k
    )
    
    if not filtered_videos:
        print("❌ No videos found matching the criteria.")
        sys.exit(0)
    
    # Copy filtered videos
    output_path = Path(args.output_dir)
    video_filter.copy_filtered_videos(filtered_videos, output_path)
    
    print(f"\n🎉 Filtering complete! {len(filtered_videos)} videos saved to '{args.output_dir}'")
    print(f"🍎 M4 MacBook with {'MPS GPU' if video_filter.device == 'mps' else video_filter.device.upper()} acceleration used")
    
    # Display summary
    print("\n📊 Top Results:")
    for i, (video_path, similarity, query) in enumerate(filtered_videos, 1):
        print(f"  {i}. {video_path.name} (similarity: {similarity:.4f})")


if __name__ == "__main__":
    main() 