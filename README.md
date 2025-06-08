# Adobe Stock Video Scraper Pipeline

A Python pipeline for scraping and downloading videos from Adobe Stock based on search queries.

## Features

- 🔍 Search Adobe Stock for videos using any query
- 📥 Download preview videos automatically
- 📁 Organize downloads by search query
- 📊 Save metadata for each scraping session
- 🖥️ Headless browser operation
- 🔄 Automatic retry mechanisms
- 📈 Progress bars for downloads

## Installation

### Prerequisites

- Python 3.7+
- Chrome browser (for web scraping)

### Setup

1. **Clone or download the files:**
   ```bash
   # Navigate to your desired directory
   cd /path/to/your/project
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Chrome is installed:**
   - The scraper uses Chrome WebDriver which will be automatically downloaded
   - Make sure Chrome browser is installed on your system

## Usage

### Method 1: Command Line Interface

```bash
# Basic usage
python pipeline.py --query "nature landscape" --max-videos 5

# Specify custom output directory
python pipeline.py --query "business meeting" --output-dir ./my_videos --max-videos 10

# More examples
python pipeline.py --query "technology abstract" --max-videos 3
python pipeline.py --query "cooking food" --max-videos 8
```

### Method 2: Interactive Mode

```bash
# Run without arguments for interactive mode
python pipeline.py
```

### Method 3: Direct Python Usage

```python
from adobe_stock_scraper import AdobeStockVideoScraper

# Initialize scraper
scraper = AdobeStockVideoScraper(download_dir="my_downloads")

# Search and download videos
downloaded_files = scraper.scrape_and_download(
    query="ocean waves",
    max_videos=5
)

print(f"Downloaded {len(downloaded_files)} videos")
```

## Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--query` | `-q` | Search query for videos | Required |
| `--max-videos` | `-n` | Maximum videos to download | 5 |
| `--output-dir` | `-o` | Output directory | "downloads" |
| `--delay` | | Delay between downloads (seconds) | 1.0 |

## Output Structure

```
downloads/
├── nature_landscape/           # Query-specific folder
│   ├── Beautiful_Sunset_123456.mp4
│   ├── Mountain_View_789012.mp4
│   └── metadata.json          # Scraping session info
├── business_meeting/
│   ├── Conference_Room_345678.mp4
│   └── metadata.json
└── ...
```

## How It Works

1. **Search**: Uses Selenium to search Adobe Stock for videos matching your query
2. **Extract**: Parses search results to extract video information and preview URLs
3. **Download**: Downloads available preview videos using HTTP requests
4. **Organize**: Saves files in query-specific folders with metadata

## Important Notes

⚠️ **Legal Considerations:**
- This tool downloads preview videos only (not full-resolution licensed content)
- Preview videos are typically watermarked and low-resolution
- Always respect Adobe Stock's terms of service
- For commercial use, purchase proper licenses from Adobe Stock

🔧 **Technical Limitations:**
- Downloads preview videos only (not full licensed content)
- Requires stable internet connection
- May need updates if Adobe Stock changes their website structure

## Troubleshooting

### Common Issues

1. **Chrome Driver Issues:**
   ```bash
   # Clear Chrome driver cache
   rm -rf ~/.wdm
   ```

2. **Permission Errors:**
   ```bash
   # Make pipeline executable
   chmod +x pipeline.py
   ```

3. **Network Timeouts:**
   - Check your internet connection
   - Try reducing `--max-videos` to a smaller number
   - Increase delay between downloads

### Error Messages

- **"No videos found"**: Try different search terms or check if Adobe Stock is accessible
- **"Chrome driver not found"**: Ensure Chrome browser is installed
- **"Permission denied"**: Check write permissions for output directory

## Examples

### Basic Examples

```bash
# Download 5 nature videos
python pipeline.py --query "nature" --max-videos 5

# Download business videos to specific folder
python pipeline.py --query "business" --output-dir ./business_videos

# Download with custom delay
python pipeline.py --query "technology" --delay 2.0
```

### Advanced Examples

```bash
# Download many videos with custom organization
python pipeline.py --query "abstract background" --max-videos 15 --output-dir ./backgrounds

# Quick test with minimal downloads
python pipeline.py --query "test" --max-videos 1
```

## File Structure

```
├── adobe_stock_scraper.py    # Main scraper class
├── pipeline.py               # CLI interface
├── requirements.txt          # Python dependencies
├── README.md                # This file
└── downloads/               # Output folder (created automatically)
```

## Dependencies

- `requests` - HTTP requests for downloading
- `selenium` - Web browser automation
- `beautifulsoup4` - HTML parsing
- `webdriver-manager` - Automatic Chrome driver management
- `tqdm` - Progress bars
- `pathvalidate` - Safe filename generation

## Contributing

Feel free to submit issues or pull requests to improve the scraper:

1. Add support for different video qualities
2. Implement additional stock photo websites
3. Add batch processing capabilities
4. Improve error handling

## License

This project is for educational purposes. Always respect the terms of service of the websites you're scraping.

---

**Disclaimer**: This tool is for educational and research purposes only. Users are responsible for complying with Adobe Stock's terms of service and applicable laws. 