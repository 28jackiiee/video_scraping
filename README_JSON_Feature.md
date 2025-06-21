# Adobe Stock Scraper - JSON Output Feature

## Overview

The Adobe Stock scraper now supports creating JSON metadata dictionaries instead of downloading videos directly. This feature is useful for:

- Creating datasets for machine learning projects
- Cataloging video content without storage overhead
- Building content databases with structured metadata
- Quick content analysis and filtering

## Usage

### Basic JSON Output

```bash
python adobe_stock_scraper.py --query "ocean waves" --count 5 --json-output --intended-label "Nature Videos"
```

### JSON Output without Authentication

```bash
python adobe_stock_scraper.py --query "mountain landscape" --count 10 --json-output --intended-label "Landscape Videos" --no-login
```

### JSON Output with Filtering

```bash
python adobe_stock_scraper.py --query "urban city" --count 8 --json-output --intended-label "Urban Scenes" --max-duration 30 --exclude-titles "logo" "text" "watermark"
```

## Required Parameters for JSON Mode

- `--json-output`: Enables JSON output mode
- `--intended-label`: Required label for organizing the JSON structure

## JSON Output Structure

The generated JSON follows this structure:

```json
{
  "Intended Label": {
    "Query Used": [
      {
        "id": "123456789",
        "caption": "Beautiful ocean waves at sunset",
        "url": "https://stock.adobe.com/Download/Watermarked/123456789"
      }
    ]
  }
}
```

## Key Features

### 1. Simple Structured Output
- Clean JSON structure with only essential fields (ID, caption, URL)
- Minimal data for fast processing and analysis
- Easy to parse and integrate with other systems

### 2. Organized by Query
- Videos are organized by intended label and query
- Easy to merge multiple JSON files
- Consistent structure for processing

### 3. Ready-to-Use URLs
- Automatic watermarked download URL generation
- Preserves original preview URLs when available
- Ready-to-use download links

### 4. Filtering Support
- All existing filtering options work with JSON mode
- Duration limits (`--max-duration`)
- Title exclusion patterns (`--exclude-titles`)

## Output Files

JSON files are saved with timestamps to prevent conflicts:
```
{query}_videos_{timestamp}.json
```

Example: `ocean_waves_videos_20231215_143022.json`

## Example Usage in Python

```python
from adobe_stock_scraper import AdobeStockScraper

# Create scraper in JSON mode
scraper = AdobeStockScraper(
    download_dir="json_outputs",
    json_output=True,
    intended_label="Nature Collection",
    use_auth=False
)

# Generate JSON for a query
count = scraper.scrape_and_download("forest landscape", 10)
print(f"Processed {count} videos")
```

## Processing Generated JSON

```python
import json

# Load and process the JSON
with open('forest_landscape_videos_20231215_143022.json', 'r') as f:
    data = json.load(f)

# Extract video information
for label, queries in data.items():
    for query, videos in queries.items():
        print(f"Query '{query}' found {len(videos)} videos")
        for video in videos:
            print(f"- {video['id']}: {video['caption']}")
```

## Benefits Over Download Mode

1. **Speed**: No actual video downloads, just metadata extraction
2. **Storage**: Minimal disk space usage
3. **Scalability**: Process thousands of videos quickly
4. **Flexibility**: Easy to filter and analyze results programmatically
5. **Reusability**: URLs remain valid for future downloads if needed

## Combining with Download Mode

You can use JSON mode to preview and filter content, then use regular download mode for selected videos:

```bash
# First, generate JSON to see what's available
python adobe_stock_scraper.py --query "nature" --count 50 --json-output --intended-label "Nature Preview"

# Then download specific content with filters
python adobe_stock_scraper.py --query "nature forest" --count 10 --max-duration 20
```

print("\n" + "=" * 60)
print("💡 USAGE TIPS:")
print("1. Use --json-output flag to enable JSON mode")
print("2. Always provide --intended-label when using JSON mode")
print("3. JSON files are saved with timestamps to avoid conflicts")
print("4. Output contains only essential fields: id, caption, and url")
print("5. Use filtering options to refine your results")
print("\n📝 Command line example:")
print("python adobe_stock_scraper.py --query 'ocean waves' --count 5 --json-output --intended-label 'Nature Videos'") 