#!/usr/bin/env python3
"""
CLI tool for indexing images from Google Drive
"""

import json
import logging
from pathlib import Path

import click
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from tqdm import tqdm

from ..config import Config
from ..drive_indexer import DriveImageIndexer
from ..embeddings import CLIPEmbedder
from ..vector_store import ImageVectorStore

console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to config file (default: config/default_config.yaml)",
)
@click.option(
    "--reset",
    is_flag=True,
    help="Reset the index (delete all existing data)",
)
@click.option(
    "--folder-id",
    multiple=True,
    help="Index only specific folder ID(s), override config",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(config, reset, folder_id, verbose):
    """
    Index images from Google Drive folders

    This will:
    1. Scan configured Drive folders for images
    2. Generate CLIP embeddings for each image
    3. Extract color palettes and metadata
    4. Store in ChromaDB for fast searching

    Example:
        his-index
        his-index --config my_config.yaml
        his-index --reset  # Start fresh
    """
    # Set up logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    console.print("\n[bold blue]🖼️  HeadlineImageSelector - Indexer[/bold blue]\n")

    # Load configuration
    try:
        cfg = Config(config)
        console.print(f"✓ Loaded config: {cfg}")
    except Exception as e:
        console.print(f"[red]✗ Error loading config: {e}[/red]")
        return

    # Override folder IDs if provided
    if folder_id:
        cfg._config["google_drive"]["folder_ids"] = list(folder_id)
        console.print(f"✓ Using folder IDs: {list(folder_id)}")

    # Initialize components
    console.print("\n[yellow]Initializing components...[/yellow]")

    try:
        # Initialize embedder
        with console.status("[bold yellow]Loading CLIP model..."):
            embedder = CLIPEmbedder(
                model_name=cfg.clip_model_name,
                device=cfg.clip_device,
            )
        console.print(f"✓ Loaded CLIP: {cfg.clip_model_name} on {cfg.clip_device}")

        # Initialize vector store
        vector_store = ImageVectorStore(
            persist_directory=cfg.chroma_persist_dir,
            collection_name=cfg.chroma_collection_name,
        )
        console.print(f"✓ Connected to ChromaDB: {vector_store.count()} images indexed")

        # Reset if requested
        if reset:
            if click.confirm("⚠️  Reset will delete all indexed images. Continue?"):
                vector_store.reset()
                console.print("✓ Index reset")
            else:
                console.print("Cancelled")
                return

        # Initialize Drive indexer
        indexer = DriveImageIndexer(
            credentials_path=cfg.credentials_path,
            token_path=cfg.token_path,
            folder_ids=cfg.drive_folder_ids,
            supported_formats=cfg.get("google_drive.supported_formats"),
            recursive=cfg.get("google_drive.recursive", True),
        )
        console.print("✓ Authenticated with Google Drive")

    except Exception as e:
        console.print(f"[red]✗ Initialization error: {e}[/red]")
        logger.exception("Initialization failed")
        return

    # Scan Drive for images
    console.print("\n[yellow]Scanning Google Drive folders...[/yellow]")
    try:
        images = indexer.list_images(show_progress=True)
        console.print(f"✓ Found {len(images)} images")

        if not images:
            console.print("[yellow]No images found. Check your folder IDs and permissions.[/yellow]")
            return

    except Exception as e:
        console.print(f"[red]✗ Error scanning Drive: {e}[/red]")
        logger.exception("Drive scan failed")
        return

    # Process images
    console.print(f"\n[yellow]Processing {len(images)} images...[/yellow]")

    skip_existing = cfg.get("indexing.skip_existing", True)
    extract_colors = cfg.get("indexing.extract_colors", True)
    batch_size = cfg.get("clip.batch_size", 8)

    indexed_count = 0
    skipped_count = 0
    error_count = 0

    with tqdm(images, desc="Indexing images") as pbar:
        for img_meta in pbar:
            image_id = img_meta["id"]

            # Skip if already indexed
            if skip_existing and vector_store.image_exists(image_id):
                skipped_count += 1
                pbar.set_postfix(indexed=indexed_count, skipped=skipped_count, errors=error_count)
                continue

            try:
                # Download image
                image_stream = indexer.get_image_stream(image_id)
                image = Image.open(image_stream).convert("RGB")

                # Generate embedding
                embedding = embedder.embed_image(image)

                # Extract metadata
                metadata = {
                    "name": img_meta["name"],
                    "size": img_meta.get("size"),
                    "mime_type": img_meta["mimeType"],
                    "folder_id": img_meta["folder_id"],
                    "orientation": indexer.get_image_orientation(image),
                }

                # Extract colors
                if extract_colors:
                    num_colors = cfg.get("indexing.num_colors", 5)
                    colors = indexer.extract_colors(image, num_colors)
                    # Convert colors list to JSON string for ChromaDB compatibility
                    metadata["colors"] = json.dumps(colors)

                # Add to vector store
                vector_store.add_image(
                    image_id=image_id,
                    embedding=embedding,
                    metadata=metadata,
                )

                indexed_count += 1
                pbar.set_postfix(indexed=indexed_count, skipped=skipped_count, errors=error_count)

            except Exception as e:
                error_count += 1
                logger.error(f"Error processing {img_meta['name']}: {e}")
                pbar.set_postfix(indexed=indexed_count, skipped=skipped_count, errors=error_count)

    # Summary
    console.print(f"\n[bold green]✓ Indexing complete![/bold green]")
    console.print(f"  • Indexed: {indexed_count}")
    console.print(f"  • Skipped: {skipped_count}")
    console.print(f"  • Errors: {error_count}")
    console.print(f"  • Total in index: {vector_store.count()}")


if __name__ == "__main__":
    main()
