"""
Google Drive indexer for scanning and processing brand-approved images
"""

import io
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from PIL import Image
from sklearn.cluster import KMeans
from tqdm import tqdm

logger = logging.getLogger(__name__)

# Google Drive API scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]


class DriveImageIndexer:
    """
    Scans Google Drive folders for images and extracts metadata
    """

    def __init__(
        self,
        credentials_path: str,
        token_path: str,
        folder_ids: List[str],
        supported_formats: Optional[List[str]] = None,
        recursive: bool = True,
    ):
        """
        Initialize Drive indexer

        Args:
            credentials_path: Path to credentials.json
            token_path: Path to token storage file
            folder_ids: List of Drive folder IDs to scan
            supported_formats: List of file extensions to include
            recursive: Whether to scan subfolders
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.folder_ids = folder_ids
        self.supported_formats = supported_formats or ["jpg", "jpeg", "png", "webp"]
        self.recursive = recursive

        # Normalize formats (lowercase, no dots)
        self.supported_formats = [
            fmt.lower().lstrip(".") for fmt in self.supported_formats
        ]

        # Authenticate
        self.service = self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Drive API"""
        creds = None

        # Load existing token
        if Path(self.token_path).exists():
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Google Drive credentials")
                creds.refresh(Request())
            else:
                if not Path(self.credentials_path).exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please download credentials.json from Google Cloud Console"
                    )
                logger.info("Initiating OAuth flow for Google Drive")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return build("drive", "v3", credentials=creds)

    def list_images(self, show_progress: bool = True) -> List[Dict[str, Any]]:
        """
        List all images in configured Drive folders

        Args:
            show_progress: Show progress bar

        Returns:
            List of image metadata dicts with keys: id, name, mimeType, size, folder_id
        """
        all_images = []

        # Validate folder IDs first
        for folder_id in self.folder_ids:
            if folder_id == "YOUR_FOLDER_ID_HERE":
                raise ValueError(
                    "Please replace 'YOUR_FOLDER_ID_HERE' in config with your actual Google Drive folder ID.\n"
                    "To find your folder ID:\n"
                    "  1. Open the folder in Google Drive\n"
                    "  2. Look at the URL: https://drive.google.com/drive/folders/FOLDER_ID_HERE\n"
                    "  3. Copy the FOLDER_ID_HERE part to your config file"
                )
            try:
                # Verify folder exists and is accessible (support Shared Drives)
                folder = self.service.files().get(
                    fileId=folder_id,
                    fields="id, name",
                    supportsAllDrives=True
                ).execute()
                logger.info(f"Scanning folder: {folder['name']} ({folder_id})")
            except Exception as e:
                raise ValueError(
                    f"Cannot access folder {folder_id}: {e}\n"
                    "Please check:\n"
                    "  1. The folder ID is correct\n"
                    "  2. The Google account has access to this folder\n"
                    "  3. The folder is not in the trash"
                )

        folders_to_scan = self.folder_ids.copy()
        scanned_folders = set()

        with tqdm(desc="Scanning folders", disable=not show_progress) as pbar:
            while folders_to_scan:
                folder_id = folders_to_scan.pop(0)

                if folder_id in scanned_folders:
                    continue
                scanned_folders.add(folder_id)

                # Query for files in this folder
                query = f"'{folder_id}' in parents and trashed=false"
                page_token = None

                while True:
                    results = (
                        self.service.files()
                        .list(
                            q=query,
                            pageSize=100,
                            fields="nextPageToken, files(id, name, mimeType, size, parents)",
                            pageToken=page_token,
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True
                        )
                        .execute()
                    )

                    items = results.get("files", [])

                    logger.debug(f"Folder {folder_id}: found {len(items)} items")

                    for item in items:
                        # Check if it's a folder
                        if item["mimeType"] == "application/vnd.google-apps.folder":
                            if self.recursive:
                                logger.debug(f"Found subfolder: {item['name']} ({item['id']})")
                                folders_to_scan.append(item["id"])
                        # Check if it's a supported image
                        elif item["mimeType"].startswith("image/"):
                            # Extract file extension
                            ext = item["name"].rsplit(".", 1)[-1].lower()
                            logger.debug(f"Found image: {item['name']} (type: {item['mimeType']}, ext: {ext})")
                            if ext in self.supported_formats:
                                item["folder_id"] = folder_id
                                all_images.append(item)
                                pbar.set_postfix(images=len(all_images))
                            else:
                                logger.debug(f"  Skipped: extension '{ext}' not in {self.supported_formats}")

                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break

                pbar.update(1)

        logger.info(f"Found {len(all_images)} images in {len(scanned_folders)} folders")
        return all_images

    def download_image(self, file_id: str, temp_dir: Optional[str] = None) -> Path:
        """
        Download image from Drive to temporary location

        Args:
            file_id: Google Drive file ID
            temp_dir: Directory for temporary files (uses system temp if None)

        Returns:
            Path to downloaded image file
        """
        # Get file metadata
        file_metadata = self.service.files().get(fileId=file_id, fields="name").execute()
        filename = file_metadata["name"]

        # Download file (support Shared Drives)
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        # Save to temp file
        if temp_dir:
            temp_path = Path(temp_dir) / filename
            temp_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp_path = Path(tempfile.gettempdir()) / filename

        with open(temp_path, "wb") as f:
            f.write(file_content.getvalue())

        return temp_path

    def get_image_stream(self, file_id: str) -> io.BytesIO:
        """
        Get image as BytesIO stream without saving to disk

        Args:
            file_id: Google Drive file ID

        Returns:
            BytesIO object with image data
        """
        request = self.service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_content.seek(0)
        return file_content

    def extract_colors(self, image: Image.Image, num_colors: int = 5) -> List[List[int]]:
        """
        Extract dominant colors from image using K-means clustering

        Args:
            image: PIL Image object
            num_colors: Number of dominant colors to extract

        Returns:
            List of RGB color values [[R, G, B], ...]
        """
        # Resize image for faster processing
        img_small = image.copy()
        img_small.thumbnail((150, 150))

        # Convert to RGB if needed
        if img_small.mode != "RGB":
            img_small = img_small.convert("RGB")

        # Get pixel data
        pixels = list(img_small.getdata())

        # Use K-means to find dominant colors
        kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)

        # Get cluster centers (dominant colors)
        colors = kmeans.cluster_centers_.astype(int).tolist()

        return colors

    def get_image_orientation(self, image: Image.Image) -> str:
        """
        Determine image orientation

        Args:
            image: PIL Image object

        Returns:
            "landscape", "portrait", or "square"
        """
        width, height = image.size

        if width > height * 1.1:  # 10% threshold
            return "landscape"
        elif height > width * 1.1:
            return "portrait"
        else:
            return "square"
