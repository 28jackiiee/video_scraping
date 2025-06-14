# Adobe Stock Scraper - Authentication Guide

## 🔐 Browser-Based Authentication

The Adobe Stock scraper now supports browser-based authentication to download watermarked videos from Adobe Stock.

## 📋 Prerequisites

Before using authentication, make sure you have:

1. **Chrome Browser** - Required for Selenium automation
2. **ChromeDriver** - Install with: `brew install chromedriver` (macOS)
3. **Adobe Stock Account** - Free or paid account
4. **Selenium** - Install with: `pip install selenium`

## 🚀 Usage Examples

### 1. Basic Authenticated Scraping
```bash
python adobe_stock_scraper.py --query "ocean waves" --count 5 --login
```

### 2. Large Download with Authentication
```bash
python adobe_stock_scraper.py --query "business meeting" --count 20 --login --output my_videos
```

### 3. Custom Rate Limiting
```bash
python adobe_stock_scraper.py --query "nature landscape" --count 10 --login --delay 2.0
```

## 🔄 Authentication Flow

When you use the `--login` flag, here's what happens:

1. **Browser Opens**: Chrome browser opens automatically
2. **Manual Login**: You log in to Adobe Stock manually in the browser
3. **Cookie Extraction**: Script extracts your authentication cookies
4. **Session Save**: Cookies are saved for future use
5. **Automated Downloads**: Script downloads videos using your authenticated session

## 📝 Step-by-Step Instructions

### First Time Setup

1. **Run the command with `--login` flag:**
   ```bash
   python adobe_stock_scraper.py --query "your search" --count 5 --login
   ```

2. **Browser will open automatically** - You'll see this message:
   ```
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
| `--login` | Enable authentication | `--login` |
| `--output` | Output directory | `--output my_videos` |
| `--delay` | Delay between requests | `--delay 2.0` |

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
- Run with `--login` again to re-authenticate
- Make sure your Adobe Stock account has proper permissions

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
✅ Authentication successful! You can now close the browser.
🔐 AUTHENTICATION MODE ENABLED
✅ Scraping completed! Downloaded 5 videos to 'downloads/ocean_waves' directory.
```

**Authentication Failed:**
```
❌ No videos were downloaded. Check authentication or try different search terms.
```

## 🔒 Security Notes

- Cookies are saved locally in `adobe_stock_cookies.json`
- Keep this file secure (contains your session data)
- Add `adobe_stock_cookies.json` to `.gitignore` if using version control
- Cookies expire periodically and will need re-authentication

## 💡 Tips

1. **Test with small counts first** (`--count 2`)
2. **Use specific search terms** for better results
3. **Check Adobe Stock manually first** to verify your account works
4. **Use rate limiting** (`--delay 2.0`) to avoid being blocked
5. **Keep browser window visible** during authentication

## 🆘 Support

If you encounter issues:
1. Check this guide first
2. Verify prerequisites are installed
3. Test Adobe Stock access manually in browser
4. Try deleting cookies and re-authenticating
5. Use smaller `--count` values for testing 