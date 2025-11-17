"""
Image search and matching functionality
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import Config
from .embeddings import CLIPEmbedder
from .vector_store import ImageVectorStore

logger = logging.getLogger(__name__)


class ImageSearcher:
    """
    Search for best matching images given content and style prompts
    """

    def __init__(
        self,
        embedder: CLIPEmbedder,
        vector_store: ImageVectorStore,
        config: Config,
    ):
        """
        Initialize image searcher

        Args:
            embedder: CLIP embedder instance
            vector_store: Vector store instance
            config: Configuration object
        """
        self.embedder = embedder
        self.vector_store = vector_store
        self.config = config

    def search(
        self,
        content: str,
        style_prompt: Optional[str] = None,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for images matching content and style

        Args:
            content: Content text to match (e.g., article, headline)
            style_prompt: Optional style description (e.g., "professional", "creative")
            top_k: Number of results to return (default from config)
            min_similarity: Minimum similarity threshold (default from config)
            filters: Optional metadata filters

        Returns:
            List of dicts with keys: id, similarity, metadata, drive_url
        """
        # Get settings from config if not provided
        if top_k is None:
            top_k = self.config.get("search.top_k", 5)
        if min_similarity is None:
            min_similarity = self.config.get("search.min_similarity", 0.0)

        # Build query text
        query_text = self._build_query(content, style_prompt)
        logger.info(f"Searching with query: {query_text[:100]}...")

        # Generate query embedding
        query_embedding = self.embedder.embed_text(query_text)

        # Build ChromaDB filters
        chroma_filters = self._build_filters(filters)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more results to filter
            filters=chroma_filters,
        )

        # Format and filter results
        formatted_results = []
        for image_id, similarity, metadata in zip(
            results["ids"], results["similarities"], results["metadatas"]
        ):
            # Apply similarity threshold
            if similarity < min_similarity:
                continue

            # Apply custom filters
            if filters and not self._passes_filters(metadata, filters):
                continue

            # Build drive URL
            drive_url = f"https://drive.google.com/file/d/{image_id}/view"

            formatted_results.append(
                {
                    "id": image_id,
                    "similarity": float(similarity),
                    "metadata": metadata,
                    "drive_url": drive_url,
                    "name": metadata.get("name", ""),
                    "orientation": metadata.get("orientation", ""),
                    "colors": metadata.get("colors", []),
                }
            )

            # Stop if we have enough results
            if len(formatted_results) >= top_k:
                break

        logger.info(f"Found {len(formatted_results)} matching images")
        return formatted_results

    def _build_query(self, content: str, style_prompt: Optional[str] = None) -> str:
        """
        Build combined query text from content and style

        Args:
            content: Main content text
            style_prompt: Optional style description

        Returns:
            Combined query text
        """
        # Get style weight from config
        style_weight = self.config.get("search.style_weight", 0.3)

        if style_prompt:
            # Weight the content vs style in the query
            # Higher style_weight = style matters more
            if style_weight >= 0.5:
                # Style-heavy query
                query = f"An image in {style_prompt} style that represents: {content}"
            else:
                # Content-heavy query
                query = f"{content}. Image style: {style_prompt}"
        else:
            query = content

        return query

    def _build_filters(self, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Build ChromaDB where clause from filters

        Args:
            filters: Filter dict with keys like orientation, folder_ids, color_filter

        Returns:
            ChromaDB where clause, or None if no filters
        """
        if not filters:
            return None

        where_clauses = []

        # Orientation filter
        if filters.get("orientation"):
            where_clauses.append({"orientation": filters["orientation"]})

        # Folder ID filter
        if filters.get("folder_ids"):
            folder_ids = filters["folder_ids"]
            if isinstance(folder_ids, str):
                folder_ids = [folder_ids]
            where_clauses.append({"folder_id": {"$in": folder_ids}})

        # Combine clauses with AND
        if not where_clauses:
            return None
        elif len(where_clauses) == 1:
            return where_clauses[0]
        else:
            return {"$and": where_clauses}

    def _passes_filters(
        self, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        """
        Check if image passes custom filters (applied after vector search)

        Args:
            metadata: Image metadata
            filters: Filter dict

        Returns:
            True if passes all filters
        """
        # Color filter (requires custom logic)
        if filters.get("color_filter"):
            target_color = filters["color_filter"]
            tolerance = filters.get("color_tolerance", 50)
            colors = metadata.get("colors", [])

            if not self._has_similar_color(colors, target_color, tolerance):
                return False

        return True

    def _has_similar_color(
        self,
        image_colors: List[List[int]],
        target_color: List[int],
        tolerance: int,
    ) -> bool:
        """
        Check if any image color is similar to target color

        Args:
            image_colors: List of RGB colors from image
            target_color: Target RGB color [R, G, B]
            tolerance: Color distance tolerance (0-255)

        Returns:
            True if a similar color is found
        """
        target = np.array(target_color)

        for color in image_colors:
            color_array = np.array(color)
            distance = np.linalg.norm(color_array - target)

            if distance <= tolerance:
                return True

        return False

    def search_with_feedback(
        self,
        content: str,
        style_prompt: Optional[str] = None,
        positive_examples: Optional[List[str]] = None,
        negative_examples: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Search with relevance feedback from user selections

        Args:
            content: Content text
            style_prompt: Style description
            positive_examples: List of image IDs that user liked
            negative_examples: List of image IDs that user disliked
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        # Get base query embedding
        query_text = self._build_query(content, style_prompt)
        query_embedding = self.embedder.embed_text(query_text)

        # Adjust embedding based on feedback
        if positive_examples or negative_examples:
            query_embedding = self._adjust_with_feedback(
                query_embedding, positive_examples, negative_examples
            )

        # Perform search with adjusted embedding
        # (Simplified version - just returns regular search for now)
        return self.search(content, style_prompt, **kwargs)

    def _adjust_with_feedback(
        self,
        query_embedding: np.ndarray,
        positive_examples: Optional[List[str]] = None,
        negative_examples: Optional[List[str]] = None,
    ) -> np.ndarray:
        """
        Adjust query embedding using Rocchio algorithm

        Args:
            query_embedding: Original query embedding
            positive_examples: Image IDs of positive examples
            negative_examples: Image IDs of negative examples

        Returns:
            Adjusted query embedding
        """
        adjusted = query_embedding.copy()
        alpha, beta, gamma = 1.0, 0.5, 0.25  # Rocchio weights

        # Add positive feedback
        if positive_examples:
            positive_embeddings = []
            for img_id in positive_examples:
                img_data = self.vector_store.get_image(img_id)
                if img_data:
                    positive_embeddings.append(img_data["embedding"])

            if positive_embeddings:
                pos_centroid = np.mean(positive_embeddings, axis=0)
                adjusted = alpha * adjusted + beta * pos_centroid

        # Subtract negative feedback
        if negative_examples:
            negative_embeddings = []
            for img_id in negative_examples:
                img_data = self.vector_store.get_image(img_id)
                if img_data:
                    negative_embeddings.append(img_data["embedding"])

            if negative_embeddings:
                neg_centroid = np.mean(negative_embeddings, axis=0)
                adjusted = adjusted - gamma * neg_centroid

        # Re-normalize
        adjusted = adjusted / np.linalg.norm(adjusted)

        return adjusted
