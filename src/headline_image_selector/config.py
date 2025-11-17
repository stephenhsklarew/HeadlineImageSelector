"""
Configuration loader and validator
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Config:
    """Configuration manager for HeadlineImageSelector"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Load configuration from YAML file

        Args:
            config_path: Path to config file. If None, uses default_config.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            self._config: Dict[str, Any] = yaml.safe_load(f)

        # Resolve paths relative to project root
        self.project_root = Path(__file__).parent.parent.parent
        self._resolve_paths()

    def _resolve_paths(self):
        """Resolve relative paths to absolute paths"""
        # ChromaDB persist directory
        persist_dir = self._config["chromadb"]["persist_directory"]
        if not Path(persist_dir).is_absolute():
            self._config["chromadb"]["persist_directory"] = str(
                self.project_root / persist_dir
            )

        # Temp directory
        temp_dir = self._config["indexing"]["temp_dir"]
        if not Path(temp_dir).is_absolute():
            self._config["indexing"]["temp_dir"] = str(self.project_root / temp_dir)

        # Credentials paths
        creds_path = self._config["google_drive"]["credentials_path"]
        if not Path(creds_path).is_absolute():
            # Try project root first, then config dir
            if (self.project_root / creds_path).exists():
                self._config["google_drive"]["credentials_path"] = str(
                    self.project_root / creds_path
                )
            elif (self.project_root / "config" / creds_path).exists():
                self._config["google_drive"]["credentials_path"] = str(
                    self.project_root / "config" / creds_path
                )

        token_path = self._config["google_drive"]["token_path"]
        if not Path(token_path).is_absolute():
            if (self.project_root / token_path).exists():
                self._config["google_drive"]["token_path"] = str(
                    self.project_root / token_path
                )
            elif (self.project_root / "config" / token_path).exists():
                self._config["google_drive"]["token_path"] = str(
                    self.project_root / "config" / token_path
                )

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-separated key (e.g., 'clip.model_name')"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    @property
    def drive_folder_ids(self) -> List[str]:
        """Get list of Google Drive folder IDs to index"""
        return self._config["google_drive"]["folder_ids"]

    @property
    def credentials_path(self) -> str:
        """Get path to Google credentials file"""
        return self._config["google_drive"]["credentials_path"]

    @property
    def token_path(self) -> str:
        """Get path to Google OAuth token file"""
        return self._config["google_drive"]["token_path"]

    @property
    def clip_model_name(self) -> str:
        """Get CLIP model name"""
        return self._config["clip"]["model_name"]

    @property
    def clip_device(self) -> str:
        """Get device for CLIP model (mps, cuda, cpu)"""
        return self._config["clip"]["device"]

    @property
    def chroma_persist_dir(self) -> str:
        """Get ChromaDB persistence directory"""
        return self._config["chromadb"]["persist_directory"]

    @property
    def chroma_collection_name(self) -> str:
        """Get ChromaDB collection name"""
        return self._config["chromadb"]["collection_name"]

    def __getitem__(self, key: str) -> Any:
        """Dict-like access to config"""
        return self.get(key)

    def __repr__(self) -> str:
        return f"Config(folders={len(self.drive_folder_ids)}, model={self.clip_model_name})"
