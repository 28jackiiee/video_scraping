# Adobe Stock Scraper - Authentication Guide

## 🔐 Authentication Required by Default

The Adobe Stock scraper now **requires authentication by default** to download watermarked videos from Adobe Stock. This ensures reliable access to videos.

## 📋 Prerequisites

Before using the scraper, make sure you have:

1. **Chrome Browser** - Required for Selenium automation
2. **ChromeDriver** - Install with: `brew install chromedriver` (macOS)
3. **Adobe Stock Account** - Free or paid account
4. **Selenium** - Install with: `pip install selenium`

## 🚀 Usage Examples

### 1. Basic Scraping (Authentication Required)
```bash
python adobe_stock_scraper.py --query "ocean waves" --count 5
```

### 2. Large Download with Custom Directory
```bash
python adobe_stock_scraper.py --query "business meeting" --count 20 --output my_videos
```

### 3. Custom Rate Limiting
```bash
python adobe_stock_scraper.py --query "nature landscape" --count 10 --delay 2.0
```

### 4. Skip Authentication (Not Recommended)
```bash
python adobe_stock_scraper.py --query "test" --count 2 --no-login
```
⚠️ **Warning**: Using `--no-login` will likely result in 401 Unauthorized errors.

## 🔄 Authentication Flow

**By default, every run includes authentication:**

1. **Browser Opens**: Chrome browser opens automatically
2. **Manual Login**: You log in to Adobe Stock manually in the browser
3. **Cookie Extraction**: Script extracts your authentication cookies
4. **Session Save**: Cookies are saved for future use
5. **Automated Downloads**: Script downloads videos using your authenticated session

## 📝 Step-by-Step Instructions

### First Time Setup

1. **Run any command (authentication happens automatically):**
   ```bash
   python adobe_stock_scraper.py --query "your search" --count 5
   ```

2. **Browser opens automatically** - You'll see this message:
   ```
   🔐 AUTHENTICATION MODE (DEFAULT)
   You will be prompted to log in through your browser.
   Make sure you have Chrome installed and chromedriver available.
   Use --no-login to skip authentication (may result in 401 errors).
   
   🌐 BROWSER OPENED FOR ADOBE STOCK LOGIN
   ========================================
   1. Complete your login in the browser window
   2. Navigate to any Adobe Stock page (e.g., search for videos)
   3. Make sure you're fully logged in
   4. Press ENTER here when you're done logging in...
   ```

3. **Log in to Adobe Stock:**
   - Enter your email and password
   - Complete 2FA if required
   - Accept any terms/conditions
   - Make sure you see your profile/account info

4. **Confirm login and continue:**
   - Press ENTER in the terminal
   - The script will extract your cookies
   - Browser will close automatically

5. **Downloads begin:**
   - Script uses your authenticated session
   - Downloads watermarked videos to organized folders

### Subsequent Uses

After the first authentication, cookies are saved to `adobe_stock_cookies.json`. The script will:
- Automatically load saved cookies
- Check if they're still valid
- Re-authenticate only if needed

**Every command runs with authentication by default:**
```bash
python adobe_stock_scraper.py --query "mountains" --count 8
python adobe_stock_scraper.py --query "technology" --count 15
```

## 📁 File Organization

Downloads are organized as follows:
```
downloads/
├── ocean_waves/
│   ├── ocean_waves_0.mp4
│   ├── ocean_waves_1.mp4
│   ├── ocean_waves_2.mp4
│   └── query_metadata.json
└── business_meeting/
    ├── business_meeting_0.mp4
    ├── business_meeting_1.mp4
    └── query_metadata.json
```

## 🔧 Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--query` | Search terms (required) | `--query "nature landscape"` |
| `--count` | Number of videos | `--count 10` |
| `--output` | Output directory | `--output my_videos` |
| `--delay` | Delay between requests | `--delay 2.0` |
| `--no-login` | **Skip authentication** (not recommended) | `--no-login` |

## 🛠️ Troubleshooting

### Common Issues

**1. "chromedriver not found"**
```bash
# Install chromedriver
brew install chromedriver

# Or download manually from:
# https://chromedriver.chromium.org/
```

**2. "Authentication failed"**
- Make sure you're fully logged in to Adobe Stock
- Check that you can access Adobe Stock normally
- Try logging out and back in
- Delete `adobe_stock_cookies.json` and try again

**3. "401 Unauthorized errors"**
- Your session may have expired
- Delete `adobe_stock_cookies.json` and run again to re-authenticate
- Make sure your Adobe Stock account has proper permissions
- **Remove `--no-login` flag** if you were using it

**4. "Browser won't open"**
- Make sure Chrome is installed
- Check chromedriver version matches Chrome version
- Try: `chromedriver --version` and `google-chrome --version`

### Reset Authentication
```bash
# Delete saved cookies to start fresh
rm adobe_stock_cookies.json
```

## 📊 Success Indicators

**Authentication Successful:**
```
🔐 AUTHENTICATION MODE (DEFAULT)
✅ Authentication successful! You can now close the browser.
✅ Scraping completed! Downloaded 5 videos to 'downloads/ocean_waves' directory.
```

**Authentication Failed:**
```
❌ No videos were downloaded. Check authentication or try different search terms.
```

**No Login Mode (Not Recommended):**
```
⚠️  NO AUTHENTICATION MODE
Attempting to download without login - this may result in 401 errors.
Remove --no-login flag to use authentication (recommended).
```

## 🔒 Security Notes

- Cookies are saved locally in `adobe_stock_cookies.json`
- Keep this file secure (contains your session data)
- Add `adobe_stock_cookies.json` to `.gitignore` if using version control
- Cookies expire periodically and will need re-authentication

## 💡 Tips

1. **Authentication is automatic** - no need to add flags
2. **Test with small counts first** (`--count 2`)
3. **Use specific search terms** for better results
4. **Check Adobe Stock manually first** to verify your account works
5. **Use rate limiting** (`--delay 2.0`) to avoid being blocked
6. **Keep browser window visible** during authentication
7. **Avoid `--no-login`** unless testing

## 🆘 Support

If you encounter issues:
1. Check this guide first
2. Verify prerequisites are installed
3. Test Adobe Stock access manually in browser
4. Try deleting cookies and re-authenticating
5. Use smaller `--count` values for testing
6. **Make sure you're not using `--no-login`** flag 