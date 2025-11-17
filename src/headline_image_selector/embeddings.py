"""
CLIP embeddings module for generating image and text embeddings
"""

import logging
from pathlib import Path
from typing import List, Union

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

logger = logging.getLogger(__name__)


class CLIPEmbedder:
    """
    Wrapper for CLIP model to generate embeddings for images and text
    Uses OpenAI's CLIP via HuggingFace Transformers
    """

    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        device: str = "mps",
    ):
        """
        Initialize CLIP model

        Args:
            model_name: HuggingFace model identifier
            device: Device to run model on (mps, cuda, cpu)
        """
        self.model_name = model_name
        self.device = self._get_device(device)

        logger.info(f"Loading CLIP model: {model_name}")
        logger.info(f"Using device: {self.device}")

        # Load model and processor
        self.model = CLIPModel.from_pretrained(model_name)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # Move model to device
        self.model.to(self.device)
        self.model.eval()

        logger.info("CLIP model loaded successfully")

    def _get_device(self, requested_device: str) -> torch.device:
        """
        Get the actual device to use, with fallbacks

        Args:
            requested_device: Requested device (mps, cuda, cpu)

        Returns:
            torch.device object
        """
        if requested_device == "mps" and torch.backends.mps.is_available():
            return torch.device("mps")
        elif requested_device == "cuda" and torch.cuda.is_available():
            return torch.device("cuda")
        else:
            if requested_device != "cpu":
                logger.warning(
                    f"Requested device '{requested_device}' not available, falling back to CPU"
                )
            return torch.device("cpu")

    def embed_image(self, image: Union[str, Path, Image.Image]) -> np.ndarray:
        """
        Generate embedding for a single image

        Args:
            image: Path to image file or PIL Image object

        Returns:
            Normalized embedding vector as numpy array
        """
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        elif not isinstance(image, Image.Image):
            raise ValueError(f"Invalid image type: {type(image)}")

        # Process image
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate embedding
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

        # Normalize and convert to numpy
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        embedding = image_features.cpu().numpy()[0]

        return embedding

    def embed_images_batch(
        self, images: List[Union[str, Path, Image.Image]], batch_size: int = 8
    ) -> np.ndarray:
        """
        Generate embeddings for multiple images in batches

        Args:
            images: List of image paths or PIL Image objects
            batch_size: Number of images to process at once

        Returns:
            Array of normalized embeddings (n_images x embedding_dim)
        """
        all_embeddings = []

        for i in range(0, len(images), batch_size):
            batch = images[i : i + batch_size]

            # Load images if paths provided
            pil_images = []
            for img in batch:
                if isinstance(img, (str, Path)):
                    pil_images.append(Image.open(img).convert("RGB"))
                elif isinstance(img, Image.Image):
                    pil_images.append(img)
                else:
                    raise ValueError(f"Invalid image type: {type(img)}")

            # Process batch
            inputs = self.processor(images=pil_images, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embeddings
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)

            # Normalize
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            embeddings = image_features.cpu().numpy()
            all_embeddings.append(embeddings)

        # Concatenate all batches
        return np.vstack(all_embeddings)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for text

        Args:
            text: Text to embed

        Returns:
            Normalized embedding vector as numpy array
        """
        # Process text
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate embedding
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)

        # Normalize and convert to numpy
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        embedding = text_features.cpu().numpy()[0]

        return embedding

    def embed_texts_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of text strings to embed

        Returns:
            Array of normalized embeddings (n_texts x embedding_dim)
        """
        # Process all texts
        inputs = self.processor(text=texts, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate embeddings
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)

        # Normalize
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        embeddings = text_features.cpu().numpy()

        return embeddings

    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0 to 1, higher is more similar)
        """
        return float(np.dot(embedding1, embedding2))

    @property
    def embedding_dim(self) -> int:
        """Get the dimensionality of embeddings"""
        return self.model.config.projection_dim
