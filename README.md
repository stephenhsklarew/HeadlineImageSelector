# HeadlineImageSelector

**AI-powered tool to match brand-approved images with content using CLIP embeddings**

HeadlineImageSelector helps you automatically find the perfect headline image for your blog posts, articles, and marketing content from your brand-approved image library stored in Google Drive. It uses OpenAI's CLIP model to understand both images and text in a shared semantic space, enabling intelligent matching based on content meaning rather than just keywords.

## Features

- 🤖 **AI-Powered Matching**: Uses CLIP (Contrastive Language-Image Pre-training) to understand semantic similarity between content and images
- 🔒 **Privacy-First**: Runs locally on your machine - images never leave your control
- 📁 **Google Drive Integration**: Seamlessly indexes images from your Drive folders
- ⚡ **Fast Search**: ChromaDB vector database for sub-second searches across hundreds of images
- 🎨 **Smart Filtering**: Filter by orientation, colors, folders, and more
- 🖥️ **Apple Silicon Optimized**: Takes full advantage of M1/M2/M3 chips with MPS acceleration
- 🛠️ **CLI Tools**: Easy-to-use command-line interface for indexing and searching
- 📊 **Metadata Extraction**: Automatic color palette and orientation detection

## How It Works

1. **Index Phase**: Scan your Google Drive folders, generate CLIP embeddings for each image, extract metadata (colors, orientation), and store in a local ChromaDB vector database.

2. **Search Phase**: Provide content text (article, headline) + optional style prompt. The tool generates an embedding for your query and finds the most semantically similar images.

3. **Results**: Get ranked results with similarity scores, metadata, and direct Drive links.

## Installation

### Prerequisites

- Python 3.9 or higher
- Google Drive API credentials (instructions below)
- Mac with Apple Silicon (M1/M2/M3) recommended, but works on any system with CPU/CUDA

### Install from Source

```bash
# Clone the repository
git clone https://github.com/stephenhsklarew/HeadlineImageSelector.git
cd HeadlineImageSelector

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers chromadb google-api-python-client google-auth-httplib2 \
    google-auth-oauthlib pyyaml tqdm click rich scikit-learn

# The CLI tools are ready to use from the project directory
# Use ./his-index and ./his-search
```

**Alternative: Python Module Method**

You can also run commands using Python's module syntax:

```bash
export PYTHONPATH=src:$PYTHONPATH
python -m headline_image_selector.cli.index --help
python -m headline_image_selector.cli.search --help
```

### Google Drive Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**
4. Create OAuth 2.0 credentials:
   - Go to "Credentials" → "Create Credentials" → "OAuth client ID"
   - Application type: "Desktop app"
   - Download the credentials JSON file
5. Rename the file to `credentials.json` and place it in the project root or `config/` directory

On first run, you'll be prompted to authorize the application in your browser.

## Configuration

Edit `config/default_config.yaml` to customize your setup:

```yaml
google_drive:
  folder_ids:
    - "YOUR_FOLDER_ID_HERE"  # Get from Drive folder URL

clip:
  model_name: "openai/clip-vit-base-patch32"  # or clip-vit-large-patch14
  device: "mps"  # mps (Apple Silicon), cuda (NVIDIA), cpu

search:
  top_k: 5
  min_similarity: 0.0
  style_weight: 0.3  # 0.0-1.0, higher = style matters more
```

**Finding your Folder ID:**
Open the folder in Google Drive. The URL will look like:
```
https://drive.google.com/drive/folders/1ABC123xyz456
                                         ^^^^^^^^^^^^^^^^^
                                         This is your folder ID
```

## Usage

### 1. Index Your Images

First, scan your Google Drive folders and build the searchable index:

```bash
# Index all configured folders
./his-index

# Reset and rebuild from scratch
./his-index --reset

# Index specific folder(s)
./his-index --folder-id YOUR_FOLDER_ID

# Verbose output
./his-index -v
```

*Note: Use `./his-index` from the project directory, or `python -m headline_image_selector.cli.index` from anywhere.*

This will:
- Authenticate with Google Drive
- Scan for supported images (JPG, PNG, WebP)
- Generate CLIP embeddings
- Extract colors and orientation
- Store in local ChromaDB

### 2. Search for Images

Search for images that match your content:

```bash
# Basic search
./his-search --content "AI transforming healthcare in 2025"

# Add style prompt
./his-search --content "Leadership in remote teams" --style "professional and modern"

# Filter by orientation
./his-search --content "Tech innovation" --orientation landscape

# Limit results
./his-search --content "Startup culture" -k 3

# Pipe content from file or other commands
cat article.txt | ./his-search --style "creative"

# JSON output for programmatic use
./his-search --content "Your content" --json
```

*Note: Use `./his-search` from the project directory, or `python -m headline_image_selector.cli.search` from anywhere.*

### 3. Python API

Use HeadlineImageSelector in your Python code:

```python
from headline_image_selector import CLIPEmbedder, ImageVectorStore, ImageSearcher
from headline_image_selector.config import Config

# Load configuration
config = Config()

# Initialize components
embedder = CLIPEmbedder(
    model_name=config.clip_model_name,
    device=config.clip_device
)

vector_store = ImageVectorStore(
    persist_directory=config.chroma_persist_dir,
    collection_name=config.chroma_collection_name
)

searcher = ImageSearcher(embedder, vector_store, config)

# Search for matching images
results = searcher.search(
    content="Your article or headline text",
    style_prompt="professional, modern",
    top_k=5
)

for result in results:
    print(f"{result['name']}: {result['similarity']:.2%}")
    print(f"  {result['drive_url']}")
```

## Examples

### Example 1: Blog Post Header

```bash
his-search --content "The future of artificial intelligence in healthcare: \
how machine learning is revolutionizing patient diagnosis and treatment" \
--style "professional medical technology" \
--orientation landscape -k 3
```

### Example 2: Social Media Post

```bash
echo "5 tips for effective remote team leadership" | \
his-search --style "modern corporate" --orientation square
```

### Example 3: Newsletter Header

```bash
his-search --content "Weekly tech innovation roundup" \
--style "minimalist and clean" \
--orientation landscape \
--min-similarity 0.7
```

## Advanced Features

### Color Filtering

Search for images with specific color palettes:

```python
results = searcher.search(
    content="Your content",
    filters={
        "color_filter": [50, 100, 200],  # RGB values
        "color_tolerance": 50  # Distance tolerance
    }
)
```

### Relevance Feedback

Improve results by providing examples of good/bad matches:

```python
results = searcher.search_with_feedback(
    content="Your content",
    positive_examples=["image_id_1", "image_id_2"],  # IDs of images you liked
    negative_examples=["image_id_3"],  # IDs of images you didn't like
)
```

### Batch Processing

Process multiple content pieces at once:

```python
contents = [
    "Article 1 headline...",
    "Article 2 headline...",
    "Article 3 headline..."
]

for content in contents:
    results = searcher.search(content, top_k=1)
    best_match = results[0]
    print(f"Best image for '{content[:30]}...': {best_match['name']}")
```

## Architecture

```
┌──────────────────┐
│  Google Drive    │
│  (Your Images)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│  Drive Indexer           │
│  • Lists images          │
│  • Downloads temporarily │
│  • Extracts metadata     │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  CLIP Embedder           │
│  • openai/clip-vit-*     │
│  • Runs locally (MPS)    │
│  • 512-dim embeddings    │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  ChromaDB                │
│  • Vector database       │
│  • Cosine similarity     │
│  • Metadata storage      │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Image Searcher          │
│  • Semantic matching     │
│  • Filtering & ranking   │
│  • Relevance feedback    │
└──────────────────────────┘
```

## Performance

On an M1 Max Mac Studio with 64GB RAM:
- **Indexing**: ~2-3 seconds per image (includes embedding generation and color extraction)
- **Search**: <100ms for databases with hundreds of images
- **Model Loading**: ~3 seconds (one-time at startup)

## CLIP Models

Two models are supported:

| Model | Size | Quality | Speed |
|-------|------|---------|-------|
| `openai/clip-vit-base-patch32` | ~350MB | Good | Fast |
| `openai/clip-vit-large-patch14` | ~900MB | Better | Slower |

For most use cases, the base model provides excellent results.

## Troubleshooting

### "No images in index"
Run `his-index` first to build the index.

### "Credentials not found"
Ensure `credentials.json` is in the project root or `config/` directory.

### "MPS not available"
Change `device: "mps"` to `device: "cpu"` in the config file.

### Slow indexing
- Use the base model instead of large
- Reduce batch size in config
- Check your internet connection (downloads from Drive)

### Poor search results
- Try adjusting `style_weight` in config
- Increase `top_k` to see more options
- Use more descriptive content text
- Try different style prompts

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black src/

# Lint
ruff src/

# Type checking
mypy src/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OpenAI CLIP](https://github.com/openai/CLIP) for the powerful multimodal embeddings
- [ChromaDB](https://www.trychroma.com/) for the vector database
- [HuggingFace Transformers](https://huggingface.co/transformers/) for model inference

## Roadmap

- [ ] Support for additional cloud storage (Dropbox, OneDrive)
- [ ] Web UI for visual search and feedback
- [ ] Fine-tuning on user selections
- [ ] Image quality scoring
- [ ] Duplicate image detection
- [ ] API server mode
- [ ] Pre-built Docker container

## Support

- **Issues**: [GitHub Issues](https://github.com/stephenhsklarew/HeadlineImageSelector/issues)
- **Discussions**: [GitHub Discussions](https://github.com/stephenhsklarew/HeadlineImageSelector/discussions)

---

Built with ❤️ for content creators who value brand consistency
