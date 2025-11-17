#!/usr/bin/env python3
"""
CLI tool for searching images that match content
"""

import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from ..config import Config
from ..embeddings import CLIPEmbedder
from ..search import ImageSearcher
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
    "--content",
    "-t",
    help="Content text to match (or use stdin)",
)
@click.option(
    "--style",
    "-s",
    help="Style prompt (e.g., 'professional', 'creative', 'minimalist')",
)
@click.option(
    "--top-k",
    "-k",
    type=int,
    help="Number of results to return (default from config)",
)
@click.option(
    "--min-similarity",
    type=float,
    help="Minimum similarity threshold 0.0-1.0 (default from config)",
)
@click.option(
    "--orientation",
    type=click.Choice(["landscape", "portrait", "square"]),
    help="Filter by image orientation",
)
@click.option(
    "--folder-id",
    multiple=True,
    help="Filter by specific folder ID(s)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(config, content, style, top_k, min_similarity, orientation, folder_id, output_json, verbose):
    """
    Search for images that match your content

    Provide content via --content or pipe it via stdin:

    Examples:
        his-search --content "AI transforming healthcare" --style "professional"

        echo "The future of work" | his-search --style "modern"

        his-search -t "Blog post about leadership" -k 3 --orientation landscape
    """
    # Set up logging
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not output_json:
        console.print("\n[bold blue]🔍 HeadlineImageSelector - Search[/bold blue]\n")

    # Get content from stdin if not provided
    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read().strip()
        else:
            console.print("[red]✗ No content provided. Use --content or pipe via stdin[/red]")
            console.print("\nExample: his-search --content 'Your text here'")
            console.print("         echo 'Your text' | his-search")
            return

    if not content:
        console.print("[red]✗ Content is empty[/red]")
        return

    # Load configuration
    try:
        cfg = Config(config)
    except Exception as e:
        console.print(f"[red]✗ Error loading config: {e}[/red]")
        return

    # Initialize components
    try:
        if not output_json:
            console.print("[yellow]Loading models...[/yellow]")

        embedder = CLIPEmbedder(
            model_name=cfg.clip_model_name,
            device=cfg.clip_device,
        )

        vector_store = ImageVectorStore(
            persist_directory=cfg.chroma_persist_dir,
            collection_name=cfg.chroma_collection_name,
        )

        if vector_store.count() == 0:
            console.print("[red]✗ No images in index. Run 'his-index' first.[/red]")
            return

        searcher = ImageSearcher(embedder, vector_store, cfg)

        if not output_json:
            console.print(f"✓ Ready to search {vector_store.count()} images\n")

    except Exception as e:
        console.print(f"[red]✗ Initialization error: {e}[/red]")
        logger.exception("Initialization failed")
        return

    # Build filters
    filters = {}
    if orientation:
        filters["orientation"] = orientation
    if folder_id:
        filters["folder_ids"] = list(folder_id)

    # Perform search
    try:
        results = searcher.search(
            content=content,
            style_prompt=style,
            top_k=top_k,
            min_similarity=min_similarity,
            filters=filters if filters else None,
        )

        if not results:
            console.print("[yellow]No matching images found. Try adjusting your query or filters.[/yellow]")
            return

    except Exception as e:
        console.print(f"[red]✗ Search error: {e}[/red]")
        logger.exception("Search failed")
        return

    # Output results
    if output_json:
        import json
        print(json.dumps(results, indent=2))
    else:
        console.print(f"[bold green]Found {len(results)} matching images:[/bold green]\n")

        # Create table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Similarity", justify="right", width=10)
        table.add_column("Image Name", width=40)
        table.add_column("Orientation", width=12)
        table.add_column("Drive URL", width=50)

        for i, result in enumerate(results, 1):
            similarity_pct = f"{result['similarity']*100:.1f}%"

            # Color code similarity
            if result['similarity'] >= 0.8:
                similarity_color = "green"
            elif result['similarity'] >= 0.6:
                similarity_color = "yellow"
            else:
                similarity_color = "red"

            table.add_row(
                str(i),
                f"[{similarity_color}]{similarity_pct}[/{similarity_color}]",
                result['name'][:40],
                result['orientation'],
                result['drive_url'],
            )

        console.print(table)

        # Show top match details
        if results:
            console.print("\n[bold]Top Match Details:[/bold]")
            top = results[0]
            console.print(f"  Name: {top['name']}")
            console.print(f"  Similarity: {top['similarity']*100:.1f}%")
            console.print(f"  Orientation: {top['orientation']}")
            if top.get('colors'):
                console.print(f"  Dominant Colors: {top['colors'][:3]}")
            console.print(f"  URL: [link]{top['drive_url']}[/link]")


if __name__ == "__main__":
    main()
