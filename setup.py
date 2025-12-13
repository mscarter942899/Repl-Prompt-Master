#!/usr/bin/env python3
"""
Setup script for the Roblox Trading Discord Bot.
Run this to verify all dependencies and configurations.
"""

import sys
import os

def check_python_version():
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 10):
        print("ERROR: Python 3.10+ is required!")
        return False
    print("✓ Python version OK")
    return True

def check_dependencies():
    required = [
        'discord',
        'aiohttp',
        'aiosqlite',
        'flask',
        'dotenv',
        'Levenshtein'
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✓ {pkg} installed")
        except ImportError:
            print(f"✗ {pkg} NOT installed")
            missing.append(pkg)
    
    return len(missing) == 0

def check_env():
    token = os.getenv('DISCORD_TOKEN')
    if token:
        print("✓ DISCORD_TOKEN is set")
        return True
    else:
        print("⚠ DISCORD_TOKEN not set - add it to Secrets")
        return False

def check_directories():
    dirs = ['cogs', 'api', 'ui', 'utils', 'data', 'locales']
    all_ok = True
    for d in dirs:
        if os.path.isdir(d):
            print(f"✓ {d}/ exists")
        else:
            print(f"✗ {d}/ missing")
            all_ok = False
    return all_ok

def main():
    print("=" * 50)
    print("Roblox Trading Bot Setup Check")
    print("=" * 50)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment", check_env),
        ("Directories", check_directories)
    ]
    
    results = []
    for name, check in checks:
        print(f"\n[{name}]")
        results.append(check())
    
    print("\n" + "=" * 50)
    if all(results):
        print("All checks passed! Run 'python main.py' to start.")
    else:
        print("Some checks failed. Please fix the issues above.")
    print("=" * 50)

if __name__ == "__main__":
    main()
