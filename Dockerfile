# Multi-stage build for HeadlineImageSelector API
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    jinja2==3.1.2 \
    python-multipart==0.0.6

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Copy ChromaDB data (will contain the indexed embeddings)
COPY data/ ./data/

# Copy credentials (should be mounted as secret in Cloud Run)
# In production, use Cloud Secret Manager instead
COPY credentials.json ./credentials.json
COPY token_drive.json ./token_drive.json

# Create directories for ChromaDB
RUN mkdir -p /app/data/chroma

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["uvicorn", "headline_image_selector.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
