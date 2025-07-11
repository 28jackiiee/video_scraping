# Adobe Stock Video Scraper and Management Tools

This repository contains a suite of Python scripts designed to scrape, download, filter, and manage video thumbnails from Adobe Stock. It includes functionalities for enhanced duplicate checking, creating JSON metadata, and filtering videos based on content similarity using CLIP embeddings.

## 🚀 Features

### Adobe Stock Scraper (adobe_stock_scraper.py)

- Scrape and download video thumbnails based on a search query
- Option for completely random video scraping from various categories
- Random sampling: search a larger set of videos and randomly select a subset
- Create JSON metadata dictionaries instead of downloading videos
- **Comprehensive Duplicate Checking**: Prevents re-downloading videos from previous sessions and avoids processing the same video ID multiple times in one session. It extracts video IDs from existing filenames, reads mappings from metadata JSON files, and checks existing JSON outputs
- **Filtering Options**: Filter videos by maximum/minimum duration, maximum file size, and exclusion of titles matching specific patterns
- Browser-based authentication (Selenium) for logged-in access (optional)
- Integrates with query-specific ignore lists to skip unwanted videos

### Metadata Reader (read_metadata.py)

- Read and display detailed metadata from downloaded video directories, including original query, download counts, and video ID to filename mappings
- List all download directories and their summaries

### Ignore List Manager (add_to_ignore_list.py)

- Add video IDs from metadata files to query-specific ignore lists
- Manage the ignore list (add, remove, clear, check status) to prevent re-downloading specific videos

### CLIP-based Video Filter (clipscore/video_filter.py & clipscore/video_filter_m4.py)

- Filter downloaded videos by comparing their visual content with text prompts using CLIP embeddings and cosine similarity
- Extracts evenly spaced frames from videos for encoding
- Optimized version (video_filter_m4.py) specifically for Apple Silicon (M4, M3, M2, M1) Macs leveraging MPS acceleration
- Copies the most relevant videos to a filtered directory, organized by query

## 🛠️ Setup and Installation

### 1. Clone the Repository (or download files)

```bash
git clone https://github.com/28jackiiee/video_scraping.git
cd scraping
```

### 2. Create a Virtual Environment (Recommended)

```bash
conda create --name scraping python=3.10
conda activate scraping
```

### 3. Install Dependencies

The requirements.txt file lists the necessary Python packages.

```bash
pip install -r requirements.txt
conda install -c conda-forge ffmpeg
```

### 4. Install chrome driver (for selenium)

**macOS (Homebrew):**
```bash
brew install chromedriver
```

**Linux (apt):**
```bash
python linux_webdriver_install.py
```

### 5. Install PyTorch and CLIP (for video filtering) (optional)

The video_filter.py and video_filter_m4.py scripts require specific installations for PyTorch and CLIP.

**Apple Silicon (M1/M2/M3/M4 with MPS):**
```bash
pip install --pre torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/nightly/cpu
pip install clip-by-openai pillow opencv-python-headless scikit-learn
```

**NVIDIA GPU (CUDA):**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install clip-by-openai pillow opencv-python scikit-learn
```

## 📚 Usage

### 1. Adobe Stock Scraper (adobe_stock_scraper.py)

This script is used for downloading or generating metadata for videos from Adobe Stock.

**Basic Download:**
```bash
python adobe_stock_scraper.py --query "nature landscape" --count 10
```

**Random Sampling (Search many, pick few):**
```bash
python adobe_stock_scraper.py --query "nature landscape" --count 10 --sample-from 50
```

**JSON Metadata Output:**
```bash
python adobe_stock_scraper.py --query "nature landscape" --count 10 --json-output --intended-label "Nature Videos"
```

**With Filtering Options:**
```bash
python adobe_stock_scraper.py --query "shallow focus" --count 100 --max-size 5M --min-duration 5 --max-duration 30 --exclude-titles "shallow focus"
```

**Disabling Authentication or Ignore List:**
```bash
python adobe_stock_scraper.py --query "ocean waves" --count 5 --no-login
python adobe_stock_scraper.py --query "city skyline" --count 10 --no-ignore-list
```

**Combined with Random and JSON output:**
```bash
python adobe_stock_scraper.py --random --json-output --intended-label "deep focus" --sample-from 1000
```

### 2. Metadata Reader (read_metadata.py)

This script helps in reading and displaying the metadata of your downloaded videos.

**Read Metadata for a Specific Directory:**
```bash
python read_metadata.py downloads/your_query_folder
```

**List All Download Directories and Their Metadata:**
```bash
python read_metadata.py
```

### 3. Ignore List Manager (add_to_ignore_list.py)

This utility allows you to manage lists of video IDs that the scraper should ignore in future runs. Query-specific ignore lists are created automatically.

**Add Videos from a Metadata File to a Query-Specific Ignore List:**
```bash
python add_to_ignore_list.py /Users/jackieli/Downloads/prof_code/scraping_vis/downloads/testing/testing/shallow_focus/query_metadata.json
```

This command will create/update ignore_list/shallow_focus_ignore_list.json based on the metadata.

**Show Current Ignore List Status:**
```bash
python add_to_ignore_list.py --status
```

**Remove Specific Video IDs:**
```bash
python add_to_ignore_list.py --remove 123456789 987654321
```

**Clear All Video IDs from the Default Ignore List:**
```bash
python add_to_ignore_list.py --clear
```

### 5. CLIP-based Video Filter (clipscore/video_filter.py or clipscore/video_filter_m4.py)

These scripts filter downloaded videos based on a text query, using CLIP embeddings to find the most relevant videos. video_filter_m4.py is recommended for Apple Silicon Macs.

**Filter Videos with a Query:**
```bash
conda run python scraping/clipscore/video_filter_m4.py --source_dir downloads --query "slow motion" --top_k 5
```

This will copy the top 5 videos most similar to "slow motion" from your downloads directory into a new filtered directory.

## 📄 JSON Output Format

When `--json-output` is enabled, the scraper generates a JSON file with the following structure:

```json
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
```

## 🛡️ Enhanced Duplicate Checking

The adobe_stock_scraper.py script incorporates robust duplicate checking mechanisms to ensure efficiency and avoid redundant downloads:

- **Cross-Session Duplicate Prevention**: Loads existing video IDs from metadata files and filenames to prevent re-downloading videos from previous sessions
- **Intra-Session Duplicate Prevention**: Tracks video IDs globally across all search attempts within a single run, preventing the processing of the same video multiple times
- **Multi-Level ID Extraction**: Extracts video IDs from existing filenames using multiple patterns and reads video mappings from metadata JSON files for consistent handling of different filename formats
- **JSON Mode Duplicate Prevention**: When generating JSON output, it checks existing JSON files for duplicate video IDs, preventing the inclusion of the same videos in multiple JSON outputs
- **Download-Level Duplicate Checking**: Performs video ID-based duplicate checking (not just filename-based) and validates file existence robustly

## 🚫 Ignore List Functionality

The scraper can utilize query-specific ignore lists to skip videos that have been previously downloaded or are undesirable. This is managed through the add_to_ignore_list.py script, which creates `ignore_list/{query}_ignore_list.json` files based on the metadata of your downloaded content. This ensures that future scraping sessions for a particular query will automatically avoid videos already on its respective ignore list.

## 🎥 Video Filtering with CLIP

The video_filter.py and video_filter_m4.py scripts allow you to semantically filter your downloaded videos. By encoding both video frames and a text query into CLIP embeddings, the scripts calculate cosine similarity to find videos that visually match your textual description. This is useful for identifying the most relevant content from large download batches. The _m4 version is specifically optimized for Apple Silicon Macs, leveraging their GPU (MPS) for faster processing.

