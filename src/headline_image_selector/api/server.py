"""
FastAPI server for HeadlineImageSelector with web UI and programmatic API
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ..config import Config
from ..drive_indexer import DriveImageIndexer
from ..embeddings import CLIPEmbedder
from ..search import ImageSearcher
from ..vector_store import ImageVectorStore
from .auth import get_current_user

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="HeadlineImageSelector API",
    description="Semantic image search using CLIP embeddings",
    version="1.0.0",
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template directory
template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Global instances (initialized on startup)
config: Config = None
embedder: CLIPEmbedder = None
vector_store: ImageVectorStore = None
searcher: ImageSearcher = None
drive_indexer: DriveImageIndexer = None


# Pydantic models for API
class SearchRequest(BaseModel):
    """Request model for image search"""

    content: str = Field(..., description="Content text to search for (e.g., article, headline)")
    style: Optional[str] = Field(None, description="Style description (e.g., 'professional', 'creative')")
    top_k: Optional[int] = Field(3, ge=1, le=20, description="Number of results to return (1-20)")
    min_similarity: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold (0.0-1.0)")
    orientation: Optional[str] = Field(None, description="Filter by orientation: 'landscape', 'portrait', or 'square'")

    class Config:
        schema_extra = {
            "example": {
                "content": "Scientists working in a modern laboratory",
                "style": "professional",
                "top_k": 3,
                "min_similarity": 0.0,
                "orientation": "landscape"
            }
        }


class ImageResult(BaseModel):
    """Response model for a single image result"""

    id: str = Field(..., description="Google Drive file ID")
    name: str = Field(..., description="Image filename")
    similarity: float = Field(..., description="Similarity score (0.0-1.0, higher is better)")
    drive_url: str = Field(..., description="Google Drive download URL")
    drive_view_url: str = Field(..., description="Google Drive view URL")
    orientation: str = Field(..., description="Image orientation (landscape/portrait/square)")
    colors: Optional[List[List[int]]] = Field(None, description="Dominant RGB colors")
    metadata: Dict[str, Any] = Field(..., description="Full metadata")


class SearchResponse(BaseModel):
    """Response model for search results"""

    results: List[ImageResult] = Field(..., description="List of matching images")
    query: str = Field(..., description="Query that was processed")
    total_indexed: int = Field(..., description="Total images in index")


class HealthResponse(BaseModel):
    """Response model for health check"""

    status: str
    total_images: int
    clip_model: str
    device: str


@app.on_event("startup")
async def startup_event():
    """Initialize CLIP model and vector store on startup"""
    global config, embedder, vector_store, searcher, drive_indexer

    logger.info("Initializing HeadlineImageSelector API...")

    # Load configuration
    config = Config()
    logger.info(f"Loaded config from: {config}")

    # Initialize CLIP embedder
    logger.info(f"Loading CLIP model: {config.clip_model_name}")
    embedder = CLIPEmbedder(
        model_name=config.clip_model_name,
        device=config.clip_device,
    )
    logger.info(f"CLIP model loaded on device: {config.clip_device}")

    # Initialize vector store
    vector_store = ImageVectorStore(
        persist_directory=config.chroma_persist_dir,
        collection_name=config.chroma_collection_name,
    )
    logger.info(f"Connected to ChromaDB: {vector_store.count()} images indexed")

    # Initialize searcher
    searcher = ImageSearcher(
        embedder=embedder,
        vector_store=vector_store,
        config=config,
    )
    logger.info("Image searcher initialized")

    # Initialize Drive indexer for image proxy
    drive_indexer = DriveImageIndexer(
        credentials_path=config.credentials_path,
        token_path=config.token_path,
        folder_ids=config.drive_folder_ids,
    )
    logger.info("Drive indexer initialized")

    logger.info("✓ API startup complete!")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Serve the web UI homepage
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "total_images": vector_store.count() if vector_store else 0,
            "clip_model": config.clip_model_name if config else "Not loaded",
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint

    Returns system status and statistics
    """
    if not vector_store or not embedder:
        raise HTTPException(status_code=503, detail="Services not initialized")

    return HealthResponse(
        status="healthy",
        total_images=vector_store.count(),
        clip_model=config.clip_model_name,
        device=str(config.clip_device),
    )


@app.post("/api/search", response_model=SearchResponse)
async def search_images(
    request: SearchRequest,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Search for images matching the provided content and style

    This is the programmatic API endpoint. Returns JSON with image results.

    **Example Request:**
    ```json
    {
        "content": "Scientists working in a modern laboratory",
        "style": "professional",
        "top_k": 3,
        "orientation": "landscape"
    }
    ```

    **Example Response:**
    ```json
    {
        "results": [
            {
                "id": "1abc123",
                "name": "lab-image.jpg",
                "similarity": 0.75,
                "drive_url": "https://drive.google.com/uc?export=download&id=1abc123",
                "drive_view_url": "https://drive.google.com/file/d/1abc123/view",
                "orientation": "landscape",
                "metadata": {...}
            }
        ],
        "query": "Scientists working in a modern laboratory. Image style: professional",
        "total_indexed": 432
    }
    ```
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    try:
        # Build filters
        filters = {}
        if request.orientation:
            if request.orientation not in ["landscape", "portrait", "square"]:
                raise HTTPException(
                    status_code=400,
                    detail="orientation must be 'landscape', 'portrait', or 'square'"
                )
            filters["orientation"] = request.orientation

        # Perform search
        results = searcher.search(
            content=request.content,
            style_prompt=request.style,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            filters=filters if filters else None,
        )

        # Build query text for response
        query_text = searcher._build_query(request.content, request.style)

        # Format results
        image_results = []
        for result in results:
            # Parse colors from JSON string
            colors = None
            if result.get("colors"):
                try:
                    colors = json.loads(result["colors"])
                except:
                    pass

            image_results.append(
                ImageResult(
                    id=result["id"],
                    name=result["name"],
                    similarity=result["similarity"],
                    drive_url=f"https://drive.google.com/uc?export=download&id={result['id']}",
                    drive_view_url=result["drive_url"],
                    orientation=result["orientation"],
                    colors=colors,
                    metadata=result["metadata"],
                )
            )

        return SearchResponse(
            results=image_results,
            query=query_text,
            total_indexed=vector_store.count(),
        )

    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/stats")
async def get_stats():
    """
    Get statistics about the indexed images

    Returns counts by orientation, total images, etc.
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        # Get all metadata to compute stats
        all_images = vector_store._collection.get(include=["metadatas"])
        metadatas = all_images.get("metadatas", [])

        # Count by orientation
        orientations = {"landscape": 0, "portrait": 0, "square": 0}
        for meta in metadatas:
            orientation = meta.get("orientation", "")
            if orientation in orientations:
                orientations[orientation] += 1

        return {
            "total": len(metadatas),
            "by_orientation": orientations,
            "clip_model": config.clip_model_name,
            "device": str(config.clip_device),
        }

    except Exception as e:
        logger.exception("Failed to get stats")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/api/image/{file_id}")
async def proxy_image(
    file_id: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Proxy endpoint to serve Google Drive images with authentication

    Args:
        file_id: Google Drive file ID

    Returns:
        Image file stream
    """
    if not drive_indexer:
        raise HTTPException(status_code=503, detail="Drive indexer not initialized")

    try:
        # Get image stream from Drive
        image_stream = drive_indexer.get_image_stream(file_id)

        # Return as streaming response
        return StreamingResponse(
            image_stream,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"}  # Cache for 24 hours
        )
    except Exception as e:
        logger.exception(f"Failed to fetch image {file_id}")
        raise HTTPException(status_code=404, detail=f"Image not found: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
