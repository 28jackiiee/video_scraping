#!/usr/bin/env python3
"""
Setup script for Adobe Stock Video Scraper

This script helps set up the environment and dependencies.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("\n📦 Installing dependencies...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    except FileNotFoundError:
        print("❌ requirements.txt not found")
        return False

def setup_config():
    """Set up configuration file"""
    print("\n⚙️  Setting up configuration...")
    
    env_file = Path(".env")
    template_file = Path("config_template.env")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if not template_file.exists():
        print("❌ config_template.env not found")
        return False
    
    # Copy template to .env
    try:
        with open(template_file, 'r') as template:
            content = template.read()
        
        with open(env_file, 'w') as env:
            env.write(content)
        
        print("✅ Created .env file from template")
        print("📝 Please edit .env file and add your Adobe Stock API key")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def check_api_key():
    """Check if API key is configured"""
    print("\n🔑 Checking API key configuration...")
    
    # Try to load from .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
            if "ADOBE_STOCK_API_KEY=your_adobe_stock_api_key_here" not in content and "ADOBE_STOCK_API_KEY=" in content:
                print("✅ API key appears to be configured in .env file")
                return True
    
    # Check environment variable
    if os.getenv('ADOBE_STOCK_API_KEY'):
        print("✅ API key found in environment variables")
        return True
    
    print("⚠️  API key not configured")
    print("Please:")
    print("1. Get an API key from https://developer.adobe.com/console/")
    print("2. Edit the .env file and replace 'your_adobe_stock_api_key_here' with your actual key")
    print("   OR set the ADOBE_STOCK_API_KEY environment variable")
    return False

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    
    directories = ["downloads", "downloads/videos", "downloads/thumbnails", "downloads/metadata"]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Created output directories")

def test_imports():
    """Test if all required modules can be imported"""
    print("\n🧪 Testing imports...")
    
    required_modules = [
        "requests", "tqdm", "pathlib", "urllib.parse", 
        "json", "time", "logging", "argparse"
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing modules: {', '.join(missing_modules)}")
        return False
    
    print("✅ All required modules available")
    return True

def main():
    """Main setup function"""
    print("Adobe Stock Video Scraper - Setup")
    print("=" * 40)
    
    success = True
    
    # Check Python version
    if not check_python_version():
        success = False
    
    # Install dependencies
    if success and not install_dependencies():
        success = False
    
    # Test imports
    if success and not test_imports():
        success = False
    
    # Setup configuration
    if success and not setup_config():
        success = False
    
    # Create directories
    if success:
        create_directories()
    
    # Check API key
    api_key_configured = check_api_key()
    
    print("\n" + "=" * 40)
    
    if success:
        print("🎉 Setup completed successfully!")
        
        if api_key_configured:
            print("\n✨ You're ready to start scraping!")
            print("\nTry running:")
            print("  python adobe_stock_scraper.py --search 'nature' --limit 5")
            print("  python example_usage.py")
        else:
            print("\n⚠️  Setup complete, but API key needs configuration")
            print("Please configure your Adobe Stock API key before using the scraper")
    else:
        print("❌ Setup failed. Please check the errors above and try again.")

if __name__ == '__main__':
    main() 