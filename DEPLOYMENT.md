# Deployment Guide: HeadlineImageSelector on Google Cloud Run

This guide walks you through deploying the HeadlineImageSelector API to Google Cloud Run with both a web UI and programmatic API.

## Prerequisites

- Google Cloud account with billing enabled
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- Docker installed locally (for testing)
- Your indexed ChromaDB database (in `data/chroma/`)
- Google Drive API credentials (`credentials.json` and `token_drive.json`)

## Cost Estimate

**Estimated monthly cost: $5-50/month** depending on usage:

- Container instances: Billed per-second when processing requests
- Cold start: ~5-10 seconds (CLIP model loading)
- Memory: 2GB recommended
- CPU: 1 vCPU sufficient for most workloads
- Free tier: First 2 million requests/month

## Architecture

```
User Request → Cloud Run → FastAPI Server
                              ├── Web UI (GET /)
                              ├── API Endpoint (POST /api/search)
                              ├── CLIP Model (downloads from HuggingFace)
                              ├── ChromaDB (persistent embeddings)
                              └── Google Drive API (image access)
```

## Step 1: Prepare Your Project

### 1.1 Test Locally First

Install API dependencies:

```bash
pip install -e ".[api]"
```

Run the server locally:

```bash
cd ~/Development/Scripts/HeadlineImageSelector
export PYTHONPATH=src:$PYTHONPATH
uvicorn headline_image_selector.api.server:app --host 0.0.0.0 --port 8000
```

Test the endpoints:

```bash
# Web UI
open http://localhost:8000

# API health check
curl http://localhost:8000/health

# API search
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Scientists in a laboratory",
    "style": "professional",
    "top_k": 3
  }'
```

### 1.2 Test Docker Build Locally

```bash
# Build the image
docker build -t headline-image-selector .

# Run the container
docker run -p 8000:8000 headline-image-selector

# Test
curl http://localhost:8000/health
```

## Step 2: Set Up Google Cloud

### 2.1 Create/Select Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com
```

### 2.2 Configure Artifact Registry (Recommended) or Container Registry

```bash
# Option A: Artifact Registry (recommended)
gcloud artifacts repositories create headline-image-selector \
  --repository-format=docker \
  --location=us-central1 \
  --description="HeadlineImageSelector Docker repository"

# Option B: Container Registry (legacy)
# No setup needed, automatically available
```

## Step 3: Build and Push Container

### 3.1 Build with Cloud Build

```bash
# Using Artifact Registry
export REGION="us-central1"
export IMAGE_NAME="$REGION-docker.pkg.dev/$PROJECT_ID/headline-image-selector/api"

gcloud builds submit --tag $IMAGE_NAME

# OR using Container Registry
# export IMAGE_NAME="gcr.io/$PROJECT_ID/headline-image-selector"
# gcloud builds submit --tag $IMAGE_NAME
```

**Note**: Cloud Build will take 10-20 minutes on first run to download PyTorch and other dependencies.

### 3.2 Alternative: Build and Push Manually

```bash
# Build locally
docker build -t $IMAGE_NAME .

# Configure Docker for GCP
gcloud auth configure-docker $REGION-docker.pkg.dev

# Push to registry
docker push $IMAGE_NAME
```

## Step 4: Deploy to Cloud Run

### 4.1 Deploy the Service

```bash
gcloud run deploy headline-image-selector \
  --image $IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --allow-unauthenticated \
  --set-env-vars "PYTHONPATH=/app/src"
```

**Configuration options:**
- `--memory 2Gi`: 2GB RAM (recommended for CLIP model)
- `--cpu 1`: 1 vCPU (sufficient for most workloads)
- `--timeout 300`: 5-minute timeout for long searches
- `--max-instances 10`: Scale up to 10 containers
- `--allow-unauthenticated`: Public access (remove for private API)

### 4.2 Get the Service URL

```bash
gcloud run services describe headline-image-selector \
  --region us-central1 \
  --format 'value(status.url)'
```

Your service will be available at: `https://headline-image-selector-XXXXX-uc.a.run.app`

## Step 5: Secure Your Credentials (Important!)

**⚠️ Warning**: The Dockerfile currently copies credentials directly. For production, use Google Secret Manager.

### 5.1 Store Credentials in Secret Manager

```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create secrets
gcloud secrets create google-drive-credentials \
  --data-file=credentials.json

gcloud secrets create google-drive-token \
  --data-file=token_drive.json

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding google-drive-credentials \
  --member="serviceAccount:$(gcloud run services describe headline-image-selector --region us-central1 --format 'value(spec.template.spec.serviceAccountName)')" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding google-drive-token \
  --member="serviceAccount:$(gcloud run services describe headline-image-selector --region us-central1 --format 'value(spec.template.spec.serviceAccountName)')" \
  --role="roles/secretmanager.secretAccessor"
```

### 5.2 Update Dockerfile to Use Secrets

Replace these lines in Dockerfile:

```dockerfile
# Remove these lines:
# COPY credentials.json ./credentials.json
# COPY token_drive.json ./token_drive.json

# Add this at the end before CMD:
# Secrets will be mounted at runtime by Cloud Run
```

### 5.3 Redeploy with Secret Mounting

```bash
gcloud run deploy headline-image-selector \
  --image $IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --allow-unauthenticated \
  --set-env-vars "PYTHONPATH=/app/src" \
  --update-secrets=/app/credentials.json=google-drive-credentials:latest \
  --update-secrets=/app/token_drive.json=google-drive-token:latest
```

## Step 6: Test Your Deployment

### 6.1 Test Web UI

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe headline-image-selector \
  --region us-central1 \
  --format 'value(status.url)')

# Open in browser
open $SERVICE_URL
```

### 6.2 Test API Endpoint

```bash
curl -X POST "$SERVICE_URL/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Scientists working in a modern laboratory",
    "style": "professional",
    "top_k": 3,
    "orientation": "landscape"
  }' | jq .
```

### 6.3 Check API Documentation

Visit: `https://your-service-url/docs` for interactive Swagger UI

## Step 7: Update and Redeploy

When you make changes:

```bash
# Rebuild and push
gcloud builds submit --tag $IMAGE_NAME

# Redeploy (Cloud Run will automatically use new image)
gcloud run deploy headline-image-selector \
  --image $IMAGE_NAME \
  --region us-central1
```

## Monitoring and Logging

### View Logs

```bash
# Stream logs
gcloud run services logs tail headline-image-selector --region us-central1

# View logs in Cloud Console
# https://console.cloud.google.com/run
```

### Monitor Performance

```bash
# Get service metrics
gcloud run services describe headline-image-selector \
  --region us-central1 \
  --format json | jq .status.traffic
```

## Cost Optimization

### 1. Reduce Memory (if possible)

```bash
gcloud run deploy headline-image-selector \
  --memory 1Gi \
  --region us-central1
```

### 2. Set Minimum Instances (reduce cold starts)

```bash
gcloud run deploy headline-image-selector \
  --min-instances 1 \
  --region us-central1
```

**Note**: This keeps 1 instance always running (~$15/month) but eliminates cold starts.

### 3. Use Smaller CLIP Model

Edit `config/default_config.yaml`:

```yaml
clip:
  model_name: "openai/clip-vit-base-patch16"  # Smaller than patch32
  device: "cpu"  # Cloud Run uses CPU
```

## Troubleshooting

### Container Won't Start

Check logs:
```bash
gcloud run services logs read headline-image-selector --region us-central1 --limit 50
```

Common issues:
- **ChromaDB not found**: Ensure `data/` directory was copied in Docker build
- **Credentials missing**: Check secret mounting
- **Out of memory**: Increase `--memory` to 4Gi

### Cold Starts Too Slow

The CLIP model takes 5-10 seconds to load. Options:

1. **Keep warm with min-instances**: `--min-instances 1`
2. **Use startup probe**: Allow more time for health checks
3. **Lazy load model**: Only load CLIP on first request (requires code changes)

### API Returns 503

- Service is scaling up (wait 10-15 seconds)
- Check health endpoint: `curl $SERVICE_URL/health`
- Check logs for initialization errors

## Custom Domain (Optional)

Map a custom domain to your service:

```bash
gcloud run domain-mappings create \
  --service headline-image-selector \
  --domain images.yourdomain.com \
  --region us-central1
```

Follow the instructions to add DNS records.

## API Authentication (Optional)

To require authentication:

```bash
# Redeploy without --allow-unauthenticated
gcloud run deploy headline-image-selector \
  --image $IMAGE_NAME \
  --region us-central1

# Generate auth token
gcloud auth print-identity-token

# Use in requests
curl -X POST "$SERVICE_URL/api/search" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"content": "lab images", "top_k": 3}'
```

## Next Steps

- Set up CI/CD with GitHub Actions for automatic deployments
- Add rate limiting with Cloud Armor
- Set up monitoring alerts with Cloud Monitoring
- Consider Cloud CDN for static assets
- Implement API key authentication for public APIs

## Support

For issues:
- Check logs: `gcloud run services logs read headline-image-selector`
- Cloud Run docs: https://cloud.google.com/run/docs
- Project issues: https://github.com/stephenhsklarew/HeadlineImageSelector/issues
