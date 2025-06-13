#!/usr/bin/env python3
"""
ChromeDriver Setup Script

This script automatically downloads and installs ChromeDriver for authentication
functionality in the Adobe Stock scraper.
"""

import requests
import zipfile
import os
import platform
import shutil
from pathlib import Path
import subprocess
import json


def get_chrome_version():
    """Get the installed Chrome version."""
    try:
        if platform.system() == "Darwin":  # macOS
            result = subprocess.run([
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"
            ], capture_output=True, text=True)
        elif platform.system() == "Windows":
            result = subprocess.run([
                "reg", "query", "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon", 
                "/v", "version"
            ], capture_output=True, text=True)
        else:  # Linux
            result = subprocess.run([
                "google-chrome", "--version"
            ], capture_output=True, text=True)
        
        if result.returncode == 0:
            version = result.stdout.strip().split()[-1]
            return version.split('.')[0]  # Return major version
        
    except Exception as e:
        print(f"Error getting Chrome version: {e}")
    
    return None


def download_chromedriver(version):
    """Download ChromeDriver for the specified Chrome version."""
    
    # Determine platform
    system = platform.system().lower()
    if system == "darwin":
        if platform.machine() == "arm64":
            platform_name = "mac-arm64"
        else:
            platform_name = "mac-x64"
    elif system == "windows":
        platform_name = "win64" if platform.machine().endswith('64') else "win32"
    else:
        platform_name = "linux64"
    
    # ChromeDriver download URL
    base_url = "https://chromedriver.storage.googleapis.com"
    
    try:
        # Get the latest version for the Chrome major version
        version_url = f"{base_url}/LATEST_RELEASE_{version}"
        response = requests.get(version_url)
        response.raise_for_status()
        driver_version = response.text.strip()
        
        print(f"Downloading ChromeDriver {driver_version} for {platform_name}...")
        
        # Download ChromeDriver
        download_url = f"{base_url}/{driver_version}/chromedriver_{platform_name}.zip"
        response = requests.get(download_url)
        response.raise_for_status()
        
        # Save and extract
        zip_path = Path("chromedriver.zip")
        with open(zip_path, "wb") as f:
            f.write(response.content)
        
        # Extract ChromeDriver
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(".")
        
        # Make executable on Unix systems
        if system != "windows":
            chromedriver_path = Path("chromedriver")
            if chromedriver_path.exists():
                chromedriver_path.chmod(0o755)
        
        # Clean up
        zip_path.unlink()
        
        print("ChromeDriver downloaded and installed successfully!")
        return True
        
    except Exception as e:
        print(f"Error downloading ChromeDriver: {e}")
        return False


def check_chromedriver_installed():
    """Check if ChromeDriver is already installed and accessible."""
    try:
        result = subprocess.run(["chromedriver", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"ChromeDriver already installed: {result.stdout.strip()}")
            return True
    except:
        pass
    
    # Check local directory
    local_chromedriver = Path("chromedriver")
    if platform.system() == "Windows":
        local_chromedriver = Path("chromedriver.exe")
    
    if local_chromedriver.exists():
        print(f"ChromeDriver found in local directory: {local_chromedriver}")
        return True
    
    return False


def main():
    """Main setup function."""
    print("Adobe Stock Scraper - ChromeDriver Setup")
    print("=" * 45)
    
    # Check if ChromeDriver is already installed
    if check_chromedriver_installed():
        print("ChromeDriver is already available. No action needed.")
        return
    
    # Get Chrome version
    chrome_version = get_chrome_version()
    if not chrome_version:
        print("Could not detect Chrome version. Please ensure Google Chrome is installed.")
        print("You can download Chrome from: https://www.google.com/chrome/")
        return
    
    print(f"Detected Chrome version: {chrome_version}")
    
    # Download ChromeDriver
    if download_chromedriver(chrome_version):
        print("\nSetup completed successfully!")
        print("You can now use the Adobe Stock scraper with authentication:")
        print("python adobe_stock_scraper.py --query 'your search' --login")
    else:
        print("\nSetup failed. You may need to manually download ChromeDriver from:")
        print("https://chromedriver.chromium.org/downloads")


if __name__ == "__main__":
    main() 