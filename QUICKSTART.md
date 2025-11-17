# Quick Start Guide

Get HeadlineImageSelector up and running in 5 minutes!

## Step 1: Install

```bash
git clone https://github.com/stephenhsklarew/HeadlineImageSelector.git
cd HeadlineImageSelector
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Step 2: Google Drive Setup

1. Go to https://console.cloud.google.com/
2. Create/select a project
3. Enable "Google Drive API"
4. Create OAuth credentials (Desktop app)
5. Download `credentials.json` to project root

## Step 3: Configure

Edit `config/default_config.yaml`:

```yaml
google_drive:
  folder_ids:
    - "YOUR_FOLDER_ID"  # From Drive folder URL
```

To get your folder ID:
- Open folder in Google Drive
- URL looks like: `https://drive.google.com/drive/folders/1ABC123xyz`
- Copy the `1ABC123xyz` part

## Step 4: Index Your Images

```bash
his-index
```

First run will open browser for OAuth authorization. This creates `token_drive.json`.

## Step 5: Search!

```bash
his-search --content "AI in healthcare" --style "professional"
```

## Example Workflows

### For blog posts:
```bash
cat my_article.md | his-search --style "professional" --orientation landscape
```

### For social media:
```bash
his-search --content "5 tips for remote work" --style "modern" --orientation square -k 3
```

### From Python:
```python
from headline_image_selector import CLIPEmbedder, ImageVectorStore, ImageSearcher
from headline_image_selector.config import Config

config = Config()
embedder = CLIPEmbedder(model_name=config.clip_model_name, device=config.clip_device)
vector_store = ImageVectorStore(config.chroma_persist_dir, config.chroma_collection_name)
searcher = ImageSearcher(embedder, vector_store, config)

results = searcher.search("Your content here", style_prompt="professional")
print(f"Best match: {results[0]['drive_url']}")
```

## Troubleshooting

**"No images in index"** → Run `his-index` first

**"Credentials not found"** → Put `credentials.json` in project root

**"MPS not available"** → Change `device: "mps"` to `device: "cpu"` in config

## Next Steps

- Adjust `style_weight` in config to tune content vs style matching
- Add multiple Drive folders to `folder_ids`
- Try different CLIP models for quality vs speed tradeoffs
- Use filters for orientation, colors, specific folders

Happy matching! 🎨
