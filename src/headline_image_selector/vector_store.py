"""
ChromaDB vector store for storing and querying image embeddings
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import numpy as np
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ImageVectorStore:
    """
    Vector database for storing and searching image embeddings using ChromaDB
    """

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "brand_images",
        distance_metric: str = "cosine",
    ):
        """
        Initialize ChromaDB vector store

        Args:
            persist_directory: Directory to persist the database
            collection_name: Name of the collection
            distance_metric: Distance metric (cosine, l2, ip)
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name

        # Ensure directory exists
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Map distance metric names
        metric_map = {"cosine": "cosine", "l2": "l2", "ip": "ip"}
        self.distance_metric = metric_map.get(distance_metric, "cosine")

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": self.distance_metric},
        )

        logger.info(
            f"Initialized ChromaDB: {persist_directory}, "
            f"collection={collection_name}, metric={self.distance_metric}"
        )

    def add_image(
        self,
        image_id: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add single image embedding to the store

        Args:
            image_id: Unique identifier for the image (e.g., Drive file ID)
            embedding: Image embedding vector
            metadata: Optional metadata dict
        """
        self.collection.add(
            ids=[image_id],
            embeddings=[embedding.tolist()],
            metadatas=[metadata] if metadata else None,
        )

    def add_images_batch(
        self,
        image_ids: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Add multiple image embeddings in batch

        Args:
            image_ids: List of unique identifiers
            embeddings: Array of embeddings (n_images x embedding_dim)
            metadatas: Optional list of metadata dicts
        """
        self.collection.add(
            ids=image_ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search for similar images

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional metadata filters (ChromaDB where clause)

        Returns:
            Dict with keys: ids, distances, metadatas
        """
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=filters,
        )

        # Convert distances to similarities for cosine metric
        # ChromaDB returns distances, we convert to similarity scores
        distances = results["distances"][0]
        if self.distance_metric == "cosine":
            # Cosine distance is 1 - cosine_similarity
            # So similarity = 1 - distance
            similarities = [1.0 - d for d in distances]
        else:
            # For other metrics, return raw distances
            similarities = distances

        return {
            "ids": results["ids"][0],
            "similarities": similarities,
            "metadatas": results["metadatas"][0] if results["metadatas"] else None,
        }

    def get_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Get image embedding and metadata by ID

        Args:
            image_id: Image identifier

        Returns:
            Dict with embedding and metadata, or None if not found
        """
        try:
            results = self.collection.get(
                ids=[image_id],
                include=["embeddings", "metadatas"],
            )

            if results["ids"]:
                return {
                    "id": results["ids"][0],
                    "embedding": np.array(results["embeddings"][0]),
                    "metadata": results["metadatas"][0] if results["metadatas"] else None,
                }
        except Exception as e:
            logger.error(f"Error getting image {image_id}: {e}")

        return None

    def delete_image(self, image_id: str):
        """
        Delete image from the store

        Args:
            image_id: Image identifier to delete
        """
        self.collection.delete(ids=[image_id])

    def image_exists(self, image_id: str) -> bool:
        """
        Check if image exists in the store

        Args:
            image_id: Image identifier

        Returns:
            True if image exists, False otherwise
        """
        try:
            results = self.collection.get(ids=[image_id])
            return len(results["ids"]) > 0
        except Exception:
            return False

    def count(self) -> int:
        """Get total number of images in the store"""
        return self.collection.count()

    def list_all(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        List all images in the store

        Args:
            limit: Maximum number of results to return

        Returns:
            Dict with ids and metadatas
        """
        results = self.collection.get(
            include=["metadatas"],
            limit=limit,
        )

        return {
            "ids": results["ids"],
            "metadatas": results["metadatas"] if results["metadatas"] else None,
        }

    def reset(self):
        """Delete all data from the collection (use with caution!)"""
        logger.warning(f"Resetting collection: {self.collection_name}")
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": self.distance_metric},
        )

    def __repr__(self) -> str:
        return (
            f"ImageVectorStore(collection={self.collection_name}, "
            f"count={self.count()}, metric={self.distance_metric})"
        )
