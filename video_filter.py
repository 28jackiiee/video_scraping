#!/usr/bin/env python3
"""
Video Filter using CLIP embeddings.

This script filters downloaded videos by comparing their visual content with text prompts
using CLIP embeddings and cosine similarity. The most relevant videos are copied to a
filtered directory.

Usage:
    python video_filter.py [--source_dir downloads] [--top_k 5] [--query "your query"]
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np

# Import CLIP and related libraries
try:
    import torch
    import clip
    from PIL import Image
    import cv2
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError as e:
    print(f"Error: Missing required dependencies. Please install:")
    print("pip install torch torchvision clip-by-openai pillow opencv-python scikit-learn")
    sys.exit(1)


class VideoFilter:
    def __init__(self, device=None):
        """Initialize the video filter with CLIP model."""
        if device:
            self.device = device
        else:
            # Auto-detect best available device
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self.device = "mps"  # Apple Silicon GPU acceleration
            else:
                self.device = "cpu"
        
        print(f"Using device: {self.device}")
        if self.device == "mps":
            print("🍎 Apple Silicon GPU acceleration enabled")
        elif self.device == "cuda":
            print("🚀 NVIDIA GPU acceleration enabled")
        else:
            print("💻 Using CPU (consider upgrading for faster processing)")
        
        # Load CLIP model
        try:
            self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)
            print("✅ CLIP model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading CLIP model: {e}")
            print("💡 Try installing PyTorch with proper device support:")
            if self.device == "mps":
                print("   For Apple Silicon: pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu")
            elif self.device == "cuda":
                print("   For NVIDIA GPU: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
            sys.exit(1)
    
    def extract_video_frames(self, video_path: Path, num_frames: int = 8) -> List[np.ndarray]:
        """Extract evenly spaced frames from a video."""
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            print(f"⚠️  Warning: Could not open video {video_path}")
            return []
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            print(f"⚠️  Warning: Video {video_path} has no frames")
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
        return frames
    
    def encode_video(self, video_path: Path) -> np.ndarray:
        """Encode a video into a CLIP embedding by averaging frame embeddings."""
        frames = self.extract_video_frames(video_path)
        
        if not frames:
            return np.zeros(512)  # Return zero embedding for failed videos
        
        frame_embeddings = []
        
        for frame in frames:
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
    
    def find_video_files(self, directory: Path) -> List[Path]:
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
    
    def filter_videos(self, source_dir: Path, query: str = None, top_k: int = 5) -> List[Tuple[Path, float]]:
        """Filter videos by similarity to query text."""
        print(f"\n🔍 Filtering videos in: {source_dir}")
        
        # Find all subdirectories with videos
        video_results = []
        
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
            
            # Find video files
            video_files = self.find_video_files(subdir)
            
            if not video_files:
                print(f"⚠️  No video files found in {subdir.name}")
                continue
            
            print(f"🎥 Found {len(video_files)} video files")
            
            # Process each video
            for video_file in video_files:
                print(f"  Processing: {video_file.name}...")
                
                # Encode video
                video_embedding = self.encode_video(video_file)
                
                # Calculate similarity
                similarity = self.calculate_similarity(video_embedding, text_embedding)
                
                video_results.append((video_file, similarity))
                print(f"    Similarity: {similarity:.4f}")
        
        # Sort by similarity (highest first)
        video_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k results
        return video_results[:top_k]
    
    def copy_filtered_videos(self, filtered_videos: List[Tuple[Path, float]], output_dir: Path):
        """Copy filtered videos to output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📋 Copying {len(filtered_videos)} videos to: {output_dir}")
        
        # Create a results file with similarity scores
        results_data = {
            "filtering_timestamp": str(Path().absolute()),
            "total_videos_filtered": len(filtered_videos),
            "videos": []
        }
        
        for i, (video_path, similarity) in enumerate(filtered_videos, 1):
            # Create new filename with rank and similarity
            original_name = video_path.stem
            extension = video_path.suffix
            new_name = f"rank_{i:02d}_sim_{similarity:.4f}_{original_name}{extension}"
            
            output_path = output_dir / new_name
            
            try:
                shutil.copy2(video_path, output_path)
                print(f"  ✅ Copied: {new_name}")
                
                results_data["videos"].append({
                    "rank": i,
                    "original_path": str(video_path),
                    "output_filename": new_name,
                    "similarity_score": similarity,
                    "source_directory": video_path.parent.name
                })
                
            except Exception as e:
                print(f"  ❌ Failed to copy {video_path.name}: {e}")
        
        # Save results metadata
        results_file = output_dir / "filtering_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Results saved to: {results_file}")


def main():
    parser = argparse.ArgumentParser(description="Filter videos using CLIP embeddings")
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
        help="Device to use for processing: auto (default), cpu, cuda (NVIDIA), or mps (Apple Silicon)"
    )
    
    args = parser.parse_args()
    
    # Validate source directory
    source_path = Path(args.source_dir)
    if not source_path.exists():
        print(f"❌ Error: Source directory '{args.source_dir}' does not exist.")
        sys.exit(1)
    
    # Initialize filter
    print("🚀 Initializing Video Filter with CLIP...")
    device = None if args.device == "auto" else args.device
    video_filter = VideoFilter(device=device)
    
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
    
    # Display summary
    print("\n📊 Top Results:")
    for i, (video_path, similarity) in enumerate(filtered_videos, 1):
        print(f"  {i}. {video_path.name} (similarity: {similarity:.4f})")


if __name__ == "__main__":
    main() 