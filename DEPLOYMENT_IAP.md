# Deployment with IAP (Identity-Aware Proxy) Authentication

This guide shows how to deploy HeadlineImageSelector to Google Cloud Run with **organization-only access** using Identity-Aware Proxy (IAP).

## What You Get

- ✅ **Local Development**: No authentication required when running on your computer
- ✅ **Cloud Deployment**: Automatic Google Workspace authentication
- ✅ **Domain Restriction**: Only `@yourdomain.com` users can access
- ✅ **Zero Code Changes**: Works automatically based on environment
- ✅ **Browser & API**: Works for both web UI and programmatic access

## How It Works

The authentication system automatically detects where it's running:

- **Local** (`localhost`): Authentication **disabled** - anyone can access
- **Cloud Run** (detected via `K_SERVICE` env var): Authentication **enabled** - requires Google login

## Step 1: Deploy to Cloud Run

### 1.1 Build and Push Container

```bash
# Set variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export IMAGE_NAME="$REGION-docker.pkg.dev/$PROJECT_ID/headline-image-selector/api"

# Build and push
gcloud builds submit --tag $IMAGE_NAME
```

### 1.2 Deploy WITHOUT Public Access

**Important**: Use `--no-allow-unauthenticated` to require authentication:

```bash
gcloud run deploy headline-image-selector \
  --image $IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --no-allow-unauthenticated \
  --set-env-vars "PYTHONPATH=/app/src,ALLOWED_DOMAIN=yourdomain.com"
```

**Replace `yourdomain.com`** with your actual Google Workspace domain!

## Step 2: Configure IAP Access

### 2.1 Grant Access to Your Domain

Allow everyone in your organization:

```bash
gcloud run services add-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="domain:yourdomain.com" \
  --role="roles/run.invoker"
```

### 2.2 Grant Access to Specific Users (Optional)

Or grant access to specific users only:

```bash
# Single user
gcloud run services add-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="user:alice@yourdomain.com" \
  --role="roles/run.invoker"

# Multiple users
gcloud run services add-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="user:bob@yourdomain.com" \
  --role="roles/run.invoker"
```

### 2.3 Grant Access to a Google Group (Recommended)

Best practice - manage access via Google Groups:

```bash
gcloud run services add-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="group:image-search-users@yourdomain.com" \
  --role="roles/run.invoker"
```

## Step 3: Get Your Service URL

```bash
gcloud run services describe headline-image-selector \
  --region us-central1 \
  --format 'value(status.url)'
```

Example output: `https://headline-image-selector-abc123-uc.a.run.app`

## Step 4: Test Access

### Browser Access

1. **Visit the URL** in your browser
2. **Sign in** with your `@yourdomain.com` Google account
3. **Redirected** to the app automatically

### API Access (Programmatic)

#### Option A: Using gcloud (Easiest)

```bash
# Get auth token
TOKEN=$(gcloud auth print-identity-token)

# Test API
curl -H "Authorization: Bearer $TOKEN" \
  https://your-service-url/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Scientists in a laboratory",
    "top_k": 3
  }'
```

#### Option B: Python with google-auth

```python
import google.auth
import google.auth.transport.requests
import requests

# Get credentials
credentials, project = google.auth.default()
auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)

# Make authenticated request
response = requests.post(
    "https://your-service-url/api/search",
    headers={"Authorization": f"Bearer {credentials.token}"},
    json={
        "content": "Scientists in a laboratory",
        "style": "professional",
        "top_k": 3
    }
)

print(response.json())
```

#### Option C: Service Account (For Automation)

```bash
# Create service account
gcloud iam service-accounts create image-search-bot \
  --display-name="Image Search Bot"

# Grant it access
gcloud run services add-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="serviceAccount:image-search-bot@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Generate key
gcloud iam service-accounts keys create key.json \
  --iam-account=image-search-bot@PROJECT_ID.iam.gserviceaccount.com

# Use in Python
from google.oauth2 import service_account
import google.auth.transport.requests
import requests

credentials = service_account.Credentials.from_service_account_file(
    'key.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)

auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)

response = requests.post(
    "https://your-service-url/api/search",
    headers={"Authorization": f"Bearer {credentials.token}"},
    json={"content": "lab images", "top_k": 3}
)
```

## Environment Variables

Configure these when deploying:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALLOWED_DOMAIN` | **Yes** | None | Your Google Workspace domain (e.g., `company.com`) |
| `REQUIRE_AUTH` | No | `auto` | `auto` (detect), `true` (force on), `false` (force off) |
| `IAP_AUDIENCE` | No | None | IAP audience for JWT validation (optional) |

### Example Deployment with All Options:

```bash
gcloud run deploy headline-image-selector \
  --image $IMAGE_NAME \
  --region us-central1 \
  --memory 2Gi \
  --no-allow-unauthenticated \
  --set-env-vars \
"PYTHONPATH=/app/src,\
ALLOWED_DOMAIN=acme.com,\
REQUIRE_AUTH=auto"
```

## Local Development

### Run Without Authentication (Default)

```bash
cd ~/Development/Scripts/HeadlineImageSelector
source venv/bin/activate
export PYTHONPATH=src:$PYTHONPATH
uvicorn headline_image_selector.api.server:app --host 0.0.0.0 --port 8000
```

You'll see: `🔓 IAP Authentication DISABLED (local development mode)`

### Test with Authentication Enabled Locally

```bash
export REQUIRE_AUTH=true
export ALLOWED_DOMAIN=yourdomain.com
uvicorn headline_image_selector.api.server:app --host 0.0.0.0 --port 8000
```

You'll see: `🔒 IAP Authentication ENABLED`

## Troubleshooting

### "Authentication required" error

**Problem**: Getting 401 errors when accessing the service

**Solutions**:
1. Check you're signed in with a `@yourdomain.com` account
2. Verify the user/domain has `roles/run.invoker` permission
3. Check `ALLOWED_DOMAIN` matches your email domain

```bash
# Check current permissions
gcloud run services get-iam-policy headline-image-selector --region=us-central1
```

### "Access restricted to domain" error

**Problem**: Getting 403 errors with wrong domain

**Solution**: Your email domain doesn't match `ALLOWED_DOMAIN`. Either:
1. Sign in with correct domain account, or
2. Update `ALLOWED_DOMAIN` environment variable

```bash
gcloud run services update headline-image-selector \
  --region=us-central1 \
  --set-env-vars "ALLOWED_DOMAIN=correctdomain.com"
```

### Service not detecting Cloud Run

**Problem**: Auth not enabling on Cloud Run

**Solution**: The auth system detects Cloud Run via `K_SERVICE` environment variable (set automatically by Cloud Run). If not working:

```bash
# Force auth on
gcloud run services update headline-image-selector \
  --region=us-central1 \
  --set-env-vars "REQUIRE_AUTH=true"
```

### Can't access from API/script

**Problem**: Programmatic access failing

**Solution**: Get fresh auth token:

```bash
# Check if you're authenticated
gcloud auth list

# Re-authenticate if needed
gcloud auth login

# Get fresh token
TOKEN=$(gcloud auth print-identity-token)

# Test
curl -H "Authorization: Bearer $TOKEN" https://your-service-url/health
```

## Revoking Access

### Remove a user:

```bash
gcloud run services remove-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="user:alice@yourdomain.com" \
  --role="roles/run.invoker"
```

### Remove entire domain:

```bash
gcloud run services remove-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="domain:yourdomain.com" \
  --role="roles/run.invoker"
```

### Make it public (disable auth):

```bash
gcloud run services add-iam-policy-binding headline-image-selector \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"

# Also need to disable domain check
gcloud run services update headline-image-selector \
  --region=us-central1 \
  --update-env-vars "REQUIRE_AUTH=false"
```

## Security Best Practices

1. ✅ **Use Google Groups** for access management instead of individual users
2. ✅ **Set ALLOWED_DOMAIN** to restrict to your organization
3. ✅ **Use Service Accounts** for automated/bot access
4. ✅ **Enable Cloud Audit Logs** to track who accessed what
5. ✅ **Rotate Service Account Keys** regularly
6. ✅ **Use Secret Manager** for credentials (not in container image)

## Cost Impact

IAP/Authentication adds minimal cost:
- **IAP**: Free for Cloud Run
- **Authentication checks**: <1ms per request
- **Total impact**: ~$0-1/month depending on traffic

## Next Steps

- Set up monitoring: See [DEPLOYMENT.md](DEPLOYMENT.md)
- Configure custom domain: `gcloud run domain-mappings create`
- Set up CI/CD: Automate deployments with GitHub Actions

## Support

- Cloud Run IAP docs: https://cloud.google.com/run/docs/authenticating/end-users
- IAM permissions: https://cloud.google.com/run/docs/securing/managing-access
