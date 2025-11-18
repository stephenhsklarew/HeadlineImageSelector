# HeadlineImageSelector API Documentation

## Overview

The HeadlineImageSelector API provides both a **web interface** and a **programmatic REST API** for semantic image search powered by CLIP embeddings.

## Features

- 🌐 **Web UI**: Beautiful, user-friendly interface for interactive searching
- 🔌 **REST API**: Programmatic access for integration with other tools
- 🖼️ **Semantic Search**: Find images based on meaning, not just keywords
- 🎨 **Style Matching**: Combine content requirements with stylistic preferences
- 📐 **Filters**: Filter by orientation (landscape/portrait/square)
- ⚡ **Fast**: Pre-indexed embeddings for instant results

## Quick Start

### Local Development

1. Install API dependencies:
```bash
pip install -e ".[api]"
```

2. Start the server:
```bash
cd ~/Development/Scripts/HeadlineImageSelector
export PYTHONPATH=src:$PYTHONPATH
uvicorn headline_image_selector.api.server:app --host 0.0.0.0 --port 8000
```

3. Access the web UI:
```
http://localhost:8000
```

4. View API docs:
```
http://localhost:8000/docs
```

## Web Interface

### Homepage
Visit `http://localhost:8000` (or your deployed URL) to access the web interface.

**Features:**
- Text input for content/article
- Style customization (e.g., "professional", "creative")
- Orientation filter (landscape/portrait/square)
- Number of results (1-10)
- Inline image previews
- Direct links to Google Drive

**Example Usage:**
1. Paste an article or headline in the content box
2. Add a style like "professional" or "modern"
3. Select "landscape" orientation
4. Click "Search Images"
5. View results with similarity scores
6. Click "Download" to get the image from Drive

## REST API

Base URL: `http://localhost:8000` (local) or your Cloud Run URL

### Endpoints

#### 1. Health Check

**GET** `/health`

Check if the service is running and get statistics.

**Response:**
```json
{
  "status": "healthy",
  "total_images": 432,
  "clip_model": "openai/clip-vit-base-patch32",
  "device": "mps"
}
```

---

#### 2. Search Images

**POST** `/api/search`

Search for images matching content and style.

**Request Body:**
```json
{
  "content": "Scientists working in a modern laboratory",
  "style": "professional",
  "top_k": 3,
  "min_similarity": 0.0,
  "orientation": "landscape"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Content text to search for (article, headline, description) |
| `style` | string | No | Style description (e.g., "professional", "creative", "modern") |
| `top_k` | integer | No | Number of results (1-20, default: 3) |
| `min_similarity` | float | No | Minimum similarity threshold (0.0-1.0, default: 0.0) |
| `orientation` | string | No | Filter by orientation: "landscape", "portrait", or "square" |

**Response:**
```json
{
  "results": [
    {
      "id": "1Gd0_r8Ka6yBhH7Fsbn7oHPQOcK4NHGns",
      "name": "AdobeStock_313425715.jpeg",
      "similarity": 0.3067,
      "drive_url": "https://drive.google.com/uc?export=download&id=1Gd0_r8Ka6yBhH7Fsbn7oHPQOcK4NHGns",
      "drive_view_url": "https://drive.google.com/file/d/1Gd0_r8Ka6yBhH7Fsbn7oHPQOcK4NHGns/view",
      "orientation": "landscape",
      "colors": [[207, 214, 225], [97, 108, 123], [137, 147, 159]],
      "metadata": {
        "folder_id": "...",
        "mime_type": "image/jpeg",
        "size": "4944880",
        "name": "AdobeStock_313425715.jpeg",
        "orientation": "landscape"
      }
    }
  ],
  "query": "Scientists working in a modern laboratory. Image style: professional",
  "total_indexed": 432
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Google Drive file ID |
| `name` | string | Image filename |
| `similarity` | float | Similarity score (0.0-1.0, higher = better match) |
| `drive_url` | string | Direct download URL |
| `drive_view_url` | string | Google Drive preview URL |
| `orientation` | string | Image orientation (landscape/portrait/square) |
| `colors` | array | Dominant RGB colors [[R,G,B], ...] |
| `metadata` | object | Additional metadata |

---

#### 3. Get Statistics

**GET** `/api/stats`

Get statistics about indexed images.

**Response:**
```json
{
  "total": 432,
  "by_orientation": {
    "landscape": 325,
    "portrait": 89,
    "square": 18
  },
  "clip_model": "openai/clip-vit-base-patch32",
  "device": "mps"
}
```

## Usage Examples

### cURL

**Search for images:**
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Scientists working in a modern laboratory",
    "style": "professional",
    "top_k": 3,
    "orientation": "landscape"
  }'
```

**Check health:**
```bash
curl http://localhost:8000/health
```

---

### Python

**Using requests library:**

```python
import requests

# Search for images
response = requests.post(
    "http://localhost:8000/api/search",
    json={
        "content": "Scientists working in a modern laboratory",
        "style": "professional",
        "top_k": 3,
        "orientation": "landscape"
    }
)

data = response.json()

# Print results
for image in data["results"]:
    print(f"{image['name']}: {image['similarity']:.2%} match")
    print(f"  Download: {image['drive_url']}")
    print(f"  View: {image['drive_view_url']}")
    print()
```

**Wrapper class:**

```python
import requests
from typing import List, Dict, Optional

class HeadlineImageSelector:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def search(
        self,
        content: str,
        style: Optional[str] = None,
        top_k: int = 3,
        orientation: Optional[str] = None
    ) -> List[Dict]:
        """Search for matching images"""
        response = requests.post(
            f"{self.base_url}/api/search",
            json={
                "content": content,
                "style": style,
                "top_k": top_k,
                "orientation": orientation
            }
        )
        response.raise_for_status()
        return response.json()["results"]

    def health(self) -> Dict:
        """Check service health"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

# Usage
client = HeadlineImageSelector()
results = client.search(
    content="A group of scientists in a laboratory",
    style="professional",
    orientation="landscape"
)

for img in results:
    print(f"{img['name']}: {img['similarity']:.1%}")
```

---

### JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

async function searchImages(content, style = null, topK = 3, orientation = null) {
  const response = await fetch('http://localhost:8000/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      style,
      top_k: topK,
      orientation
    })
  });

  const data = await response.json();
  return data.results;
}

// Usage
searchImages(
  'Scientists working in a modern laboratory',
  'professional',
  3,
  'landscape'
).then(results => {
  results.forEach(img => {
    console.log(`${img.name}: ${(img.similarity * 100).toFixed(1)}% match`);
    console.log(`  Download: ${img.drive_url}`);
  });
});
```

---

### Shell Script

```bash
#!/bin/bash

# Search function
search_images() {
    local content="$1"
    local style="${2:-professional}"
    local top_k="${3:-3}"

    curl -s -X POST http://localhost:8000/api/search \
        -H "Content-Type: application/json" \
        -d "{
            \"content\": \"$content\",
            \"style\": \"$style\",
            \"top_k\": $top_k
        }" | python3 -m json.tool
}

# Usage
search_images "Scientists in a laboratory" "professional" 5
```

## Integration Examples

### With AgenticContentGenerator

Automatically find images for generated articles:

```python
import requests

def generate_and_find_image(topic: str):
    # 1. Generate article
    article = generate_article(topic)  # Your article generator

    # 2. Find matching image
    response = requests.post(
        "http://localhost:8000/api/search",
        json={
            "content": article,
            "style": "professional",
            "top_k": 1,
            "orientation": "landscape"
        }
    )

    result = response.json()["results"][0]

    return {
        "article": article,
        "image_url": result["drive_url"],
        "image_name": result["name"],
        "similarity": result["similarity"]
    }
```

### With CI/CD Pipeline

```yaml
# .github/workflows/content.yml
name: Generate Content with Images

on:
  schedule:
    - cron: '0 9 * * *'

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - name: Generate article
        run: python generate_article.py > article.md

      - name: Find matching image
        run: |
          curl -X POST https://your-api.run.app/api/search \
            -H "Content-Type: application/json" \
            -d @article.md > image.json

      - name: Download image
        run: |
          IMAGE_URL=$(jq -r '.results[0].drive_url' image.json)
          curl -L "$IMAGE_URL" -o hero-image.jpg
```

## Error Handling

The API returns standard HTTP status codes:

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 500 | Server error |
| 503 | Service unavailable (still initializing) |

**Error Response:**
```json
{
  "detail": "orientation must be 'landscape', 'portrait', or 'square'"
}
```

## Rate Limiting

Currently no rate limiting is implemented. For production use, consider:
- Adding API key authentication
- Implementing rate limiting with Cloud Armor
- Using Cloud Endpoints for API management

## Performance

- **Cold start**: 5-10 seconds (CLIP model loading)
- **Search time**: ~100-300ms (after warm)
- **Concurrent requests**: Supports multiple simultaneous searches

**Tips for better performance:**
- Keep at least 1 instance warm (`--min-instances 1` in Cloud Run)
- Cache frequently used queries
- Use batch operations when possible

## Authentication (Optional)

For production deployments, enable authentication:

```bash
# Deploy without public access
gcloud run deploy headline-image-selector \
  --no-allow-unauthenticated

# Generate auth token
TOKEN=$(gcloud auth print-identity-token)

# Use in requests
curl -H "Authorization: Bearer $TOKEN" \
  http://your-service-url/api/search
```

## Monitoring

View logs and metrics:

```bash
# Stream logs
gcloud run services logs tail headline-image-selector

# View metrics in Cloud Console
https://console.cloud.google.com/run
```

## Support

- **Issues**: https://github.com/stephenhsklarew/HeadlineImageSelector/issues
- **Docs**: See DEPLOYMENT.md for deployment guide
- **Interactive API docs**: Visit `/docs` on your deployment

## License

MIT
