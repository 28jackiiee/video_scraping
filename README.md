# Adobe Stock Video Thumbnail Scraper

A Python script that searches and downloads thumbnail videos from Adobe Stock based on text queries.

## ⚠️ Legal Disclaimer

**IMPORTANT**: This tool is for educational purposes only. Please ensure you comply with:
- Adobe Stock's Terms of Service
- Adobe's robots.txt file
- Copyright laws in your jurisdiction
- Rate limiting and respectful scraping practices

Downloaded content may be subject to Adobe Stock's licensing terms. This script downloads preview/comp videos which are typically low-quality watermarked versions intended for preview purposes.

## Features

- Search Adobe Stock videos by text query
- Download thumbnail/preview videos
- Configurable download count
- Rate limiting to be respectful to servers
- Robust error handling and logging
- Clean filename generation
- Resume capability (skips already downloaded files)

## Installation

1. Clone or download this repository
2. Install required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python adobe_stock_scraper.py --query "Fisheye Distortion" --count 5
```

### Advanced Usage

```bash
python adobe_stock_scraper.py \
    --query "business people working" \
    --count 20 \
    --output "my_videos" \
    --delay 2.0
```

### Command Line Arguments

- `--query` / `-q`: **Required** - Search query for videos (e.g., "sunset beach")
- `--count` / `-c`: Number of videos to download (default: 10)
- `--output` / `-o`: Output directory for downloads (default: "downloads")
- `--delay` / `-d`: Delay between requests in seconds (default: 1.0)

### Examples

Download 15 nature videos:
```bash
python adobe_stock_scraper.py -q "nature forest animals" -c 15
```

Download business videos with 3-second delay:
```bash
python adobe_stock_scraper.py -q "business meeting" -c 10 -d 3.0
```

Save to custom directory:
```bash
python adobe_stock_scraper.py -q "technology" -c 8 -o "tech_videos"
```

## How It Works

1. **Search**: Queries Adobe Stock's search API with your text prompt
2. **Parse**: Extracts video metadata and preview URLs from the response
3. **Download**: Downloads the preview/comp videos to your specified directory
4. **Organize**: Creates clean filenames based on video titles and IDs

## Output

Downloaded videos are saved as:
- Format: `{video_id}_{clean_title}.{extension}`
- Extensions: `.mp4` or `.mov` depending on the source
- Directory structure: `downloads/` (or your custom output directory)

## Rate Limiting

The script includes built-in rate limiting:
- Default 1-second delay between requests
- Configurable via `--delay` parameter
- Respects server response times
- Implements proper session management

## Error Handling

- Network timeout handling
- Invalid response recovery
- Partial download cleanup
- Comprehensive logging
- Graceful shutdown on Ctrl+C

## Troubleshooting

### No videos found
- Try different search terms
- Check if Adobe Stock is accessible from your location
- Verify internet connection

### Download failures
- Increase delay with `-d` parameter
- Check available disk space
- Verify write permissions in output directory

### Rate limiting issues
- Increase delay between requests
- Adobe Stock may temporarily block rapid requests

## Technical Details

- Uses `requests` library for HTTP operations
- Parses Adobe Stock's embedded JSON data
- Implements fallback HTML parsing methods
- Maintains session state for efficiency
- Uses streaming downloads for large files

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is for educational purposes. Please respect Adobe Stock's terms of service and copyright laws. 