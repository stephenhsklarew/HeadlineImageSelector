"""
HeadlineImageSelector - AI-powered tool to match brand-approved images with content
"""

__version__ = "0.1.0"

from .embeddings import CLIPEmbedder
from .vector_store import ImageVectorStore
from .drive_indexer import DriveImageIndexer
from .search import ImageSearcher

__all__ = [
    "CLIPEmbedder",
    "ImageVectorStore",
    "DriveImageIndexer",
    "ImageSearcher",
]
