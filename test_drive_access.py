#!/usr/bin/env python3
"""Test Drive access and list folder contents"""

import sys
sys.path.insert(0, 'src')

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pathlib import Path

# Load credentials
token_path = "token_drive.json"
if not Path(token_path).exists():
    print(f"Error: {token_path} not found")
    sys.exit(1)

creds = Credentials.from_authorized_user_file(token_path, ["https://www.googleapis.com/auth/drive.readonly"])
service = build("drive", "v3", credentials=creds)

# Test folder ID from config
folder_id = "1xdOPcguZxbzvnsO_8eNa06lmjs3JDnD4"

print(f"Testing access to folder: {folder_id}\n")

# Try to get folder metadata
try:
    folder = service.files().get(fileId=folder_id, fields="id, name, mimeType").execute()
    print(f"✓ Folder found: {folder['name']}")
    print(f"  ID: {folder['id']}")
    print(f"  Type: {folder['mimeType']}\n")
except Exception as e:
    print(f"✗ Error accessing folder: {e}\n")
    sys.exit(1)

# List contents
print("Listing folder contents...")
query = f"'{folder_id}' in parents and trashed=false"

try:
    results = service.files().list(
        q=query,
        pageSize=100,
        fields="files(id, name, mimeType)",
    ).execute()

    items = results.get("files", [])
    print(f"\nFound {len(items)} items:")

    for item in items[:20]:  # Show first 20
        icon = "📁" if item["mimeType"] == "application/vnd.google-apps.folder" else "📄"
        print(f"  {icon} {item['name']} ({item['mimeType']})")

    if len(items) > 20:
        print(f"  ... and {len(items) - 20} more")

except Exception as e:
    print(f"✗ Error listing contents: {e}")
    sys.exit(1)

print(f"\n✓ Drive access is working!")
print(f"If you see 0 items but expect more, check:")
print(f"  1. The folder ID is correct")
print(f"  2. The folder has contents")
print(f"  3. The Google account that authorized the token has access to this folder")
