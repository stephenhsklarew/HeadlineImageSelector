#!/usr/bin/env python3
"""
Interactive configuration setup for HeadlineImageSelector
Helps you set up your Google Drive folder ID
"""

import sys
import re
from pathlib import Path

def main():
    print("🖼️  HeadlineImageSelector - Configuration Setup\n")

    config_path = Path("config/default_config.yaml")

    if not config_path.exists():
        print(f"✗ Config file not found: {config_path}")
        sys.exit(1)

    print("To index images from Google Drive, you need to provide your folder ID.")
    print("\nHow to find your Google Drive folder ID:")
    print("  1. Open your image folder in Google Drive (in a web browser)")
    print("  2. Look at the URL in the address bar")
    print("  3. It looks like: https://drive.google.com/drive/folders/FOLDER_ID_HERE")
    print("  4. Copy everything after '/folders/' - that's your folder ID")
    print("\nExample:")
    print("  URL: https://drive.google.com/drive/folders/1ABC123xyz456")
    print("  Folder ID: 1ABC123xyz456")

    print("\n" + "="*70)
    folder_id = input("\nEnter your Google Drive folder ID: ").strip()

    if not folder_id:
        print("✗ No folder ID provided")
        sys.exit(1)

    # Clean up common mistakes
    if "drive.google.com" in folder_id:
        # User pasted URL instead of just the ID
        match = re.search(r'/folders/([a-zA-Z0-9_-]+)', folder_id)
        if match:
            folder_id = match.group(1)
            print(f"\n✓ Extracted folder ID from URL: {folder_id}")
        else:
            print("\n✗ Could not extract folder ID from URL")
            sys.exit(1)

    # Update config
    config_content = config_path.read_text()
    updated_content = config_content.replace(
        '- "YOUR_FOLDER_ID_HERE"',
        f'- "{folder_id}"'
    )

    config_path.write_text(updated_content)

    print(f"\n✓ Configuration updated!")
    print(f"  Folder ID: {folder_id}")
    print(f"  Config file: {config_path}")

    print("\n" + "="*70)
    print("\nNext steps:")
    print("  1. Make sure you have credentials.json in the project root")
    print("     (Download from Google Cloud Console)")
    print("  2. Run: ./his-index")
    print("     (First run will open browser for OAuth authorization)")
    print("  3. Search: ./his-search --content 'Your content here'")

    print("\n✓ Setup complete!")


if __name__ == "__main__":
    main()
