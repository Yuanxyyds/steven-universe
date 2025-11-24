# File Management Service

Centralized file management microservice with three-tier bucket architecture for MinIO/S3 operations.

**Path**: `python/services/file-management/`

## Overview

This service provides a unified API for managing files across three different access patterns:
- **Type 1**: Private + Internal Only (backend services only)
- **Type 2**: Private + Signed URLs (frontend can request time-limited access)
- **Type 3**: Public Buckets (direct URL access, always open)

### Three-Tier Bucket System

| Type | Use Case | Direct Links | Auth Required | Example Buckets |
|------|----------|--------------|---------------|-----------------|
| **Type 1: Internal** | ML models, sensitive data | L No |  Internal token | `models`, `private-data` |
| **Type 2: Signed** | User uploads, private content | L No (signed URLs only) |  Frontend/Internal | `user-uploads`, `private-images` |
| **Type 3: Public** | AI-generated art, public assets |  Yes | L No (reads only) | `ai-generated-photos`, `public-assets` |

### Authentication

- **Internal Token**: Backend services only (full access)
- **Frontend API Key**: Frontend applications (signed + public buckets)
- **No Auth**: Public bucket reads

## API Endpoints

### Type 1: Internal Only (`/internal/*`)

**Auth**: Internal token required

#### Upload to Internal Bucket
```bash
POST /internal/upload
Content-Type: multipart/form-data

# Example
curl -X POST http://localhost:8000/internal/upload \
  -H "Authorization: Bearer <INTERNAL_SECRET_KEY>" \
  -F "bucket=models" \
  -F "key=model_v1.safetensors" \
  -F "file=@model.safetensors"
```

#### Delete from Internal Bucket
```bash
DELETE /internal/delete?bucket=models&key=model_v1.safetensors
Authorization: Bearer <INTERNAL_SECRET_KEY>
```

#### List Internal Bucket Files
```bash
GET /internal/list?bucket=models&prefix=
Authorization: Bearer <INTERNAL_SECRET_KEY>
```

---

### Type 2: Signed URLs (`/signed/*`)

**Auth**: Frontend or Internal token

#### Upload to Signed Bucket
```bash
POST /signed/upload
Content-Type: multipart/form-data
Authorization: Bearer <FRONTEND_API_KEY>

# Example
curl -X POST http://localhost:8000/signed/upload \
  -H "Authorization: Bearer <FRONTEND_API_KEY>" \
  -F "bucket=user-uploads" \
  -F "key=avatar.jpg" \
  -F "file=@avatar.jpg"
```

#### Generate Signed URL
```bash
POST /signed/url
Content-Type: application/json
Authorization: Bearer <FRONTEND_API_KEY>

# Example
curl -X POST http://localhost:8000/signed/url \
  -H "Authorization: Bearer <FRONTEND_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "user-uploads",
    "key": "profiles/user123.jpg",
    "expiration": 3600
  }'

# Response
{
  "success": true,
  "url": "http://192.168.50.26:9000/user-uploads/profiles/user123.jpg?X-Amz-Algorithm=...",
  "url_type": "direct_minio",
  "expires_in": 3600,
  "bucket": "user-uploads",
  "key": "profiles/user123.jpg"
}
```

---

### Type 3: Public Buckets (`/public/*`)

#### Upload to Public Bucket (Auth Required)
```bash
POST /public/upload
Content-Type: multipart/form-data
Authorization: Bearer <FRONTEND_API_KEY>

# Example
curl -X POST http://localhost:8000/public/upload \
  -H "Authorization: Bearer <FRONTEND_API_KEY>" \
  -F "bucket=ai-generated-photos" \
  -F "key=image123.jpg" \
  -F "file=@image.jpg"

# Response includes public URL
{
  "success": true,
  "data": {
    "bucket": "ai-generated-photos",
    "key": "image123.jpg",
    "public_url": "http://minio:9000/ai-generated-photos/image123.jpg"
  }
}
```

#### Get Public URL (No Auth)
```bash
GET /public/url?bucket=ai-generated-photos&key=image123.jpg

# Response
{
  "success": true,
  "url": "http://minio:9000/ai-generated-photos/image123.jpg",
  "bucket": "ai-generated-photos",
  "key": "image123.jpg"
}
```

#### Direct Access (No Auth)
```html
<!-- Direct link always works for public buckets -->
<img src="http://minio-endpoint/ai-generated-photos/image123.jpg" />
```

#### List Public Files (No Auth)
```bash
GET /public/list?bucket=ai-generated-photos&prefix=

# Response
{
  "success": true,
  "bucket": "ai-generated-photos",
  "count": 10,
  "files": [
    {
      "key": "image1.jpg",
      "url": "http://minio:9000/ai-generated-photos/image1.jpg"
    }
  ]
}
```

---

### Health Check
```bash
GET /health

# Response
{
  "status": "healthy",
  "s3_connection": "ok"
}
```

## Environment Variables

Create a `.env` file (see `.env.example`):

```env
# MinIO Configuration
MINIO_ENDPOINT=192.168.x.x:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# Authentication
INTERNAL_SECRET_KEY=your-internal-secret-key-here
FRONTEND_API_KEY=your-frontend-api-key-here

# Signed URL Configuration
DEFAULT_SIGNED_URL_EXPIRATION=3600
MAX_SIGNED_URL_EXPIRATION=86400

# Application
LOG_LEVEL=INFO
```

## Development Setup

### Local Development

```bash
# Install dependencies (includes shared-schemas in editable mode)
pip install -r requirements-dev.txt

# Run locally
uvicorn app.main:app --reload
```

**Note:** Use `requirements-dev.txt` for local development. It includes `requirements.txt` plus the editable shared-schemas package.

## Deployment

### Prerequisites
- Python 3.11+
- MinIO server running
- Docker

### Deploy to LXC Container

**Generate SSH key pair** (if you don't have one):
   ```bash
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ```

**Copy public key to LXC container**:
   ```bash
   ssh-copy-id your-username@192.168.50.98
   ```

**Configure SSH alias** in `~/.ssh/config`:
   ```bash
   Host lxc-file-service
       HostName 192.168.50.98
       User your-username
       IdentityFile ~/.ssh/id_rsa
   ```

**Configure LXC for Docker** (on Proxmox host):
   ```bash
   # Edit LXC config
   nano /etc/pve/lxc/<container-id>.conf

   # Add these lines:
   lxc.apparmor.profile: unconfined
   lxc.cgroup2.devices.allow: a
   lxc.cap.drop:
   lxc.mount.auto: proc:rw sys:rw

   # Restart container
   pct stop <container-id>
   pct start <container-id>
   ```

**Deploy:**

```bash
# 1. Configure environment variables
cp .env.example .env
# Edit .env with your LXC host, MinIO, and auth credentials

# 2. Run deployment (script loads .env automatically)
./scripts/deploy.sh
```

**Environment variables in `.env`:**
```env
# LXC Configuration (use SSH config alias)
LXC_HOST=lxc-file-service

# MinIO Configuration (internal network)
MINIO_ENDPOINT=192.168.x.x:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_SECURE=false

# Public Service URL (Cloudflare Tunnel)
PUBLIC_SERVICE_URL=https://files.yourdomain.com

# Authentication (generate with: openssl rand -base64 32)
INTERNAL_SECRET_KEY=your-internal-key
FRONTEND_API_KEY=your-frontend-key

# Optional Configuration
DEFAULT_SIGNED_URL_EXPIRATION=3600
MAX_SIGNED_URL_EXPIRATION=86400
LOG_LEVEL=INFO
```

**The deployment script will:**
- 📋 Load environment from `.env`
- ✅ Validate required variables
- 📦 Sync service files to LXC via rsync
- 📦 Sync shared-schemas dependency to LXC
- 🔨 Build Docker image on LXC (installs shared-schemas first)
- 🚀 Deploy and start container
- 🏥 Run health checks

**Useful commands after deployment:**
```bash
# View logs
ssh lxc-file-service 'docker logs -f file-service'

# Stop service
ssh lxc-file-service 'docker stop file-service'

# Restart service
ssh lxc-file-service 'docker restart file-service'

# SSH into container
ssh lxc-file-service
```

## MinIO Setup

### Create Buckets

```bash
# Using MinIO Client (mc)
mc alias set myminio http://192.168.x.x:9000 minioadmin minioadmin

# Create buckets
mc mb myminio/models
mc mb myminio/user-uploads
mc mb myminio/ai-generated-photos
```

### Bucket Policies

The service automatically sets bucket policies on startup:
- **Type 1 & 2 buckets**: Private (no public access)
- **Type 3 buckets**: Public-read (direct URL access)

## Tech Stack

- FastAPI - Web framework
- boto3 - S3 client
- MinIO - S3-compatible storage
- Pydantic - Data validation & schemas
- Uvicorn - ASGI server
- **shared-schemas** - Type-safe API contracts

## Future Enhancements

- [ ] Metadata database for file tracking
- [ ] File versioning
- [ ] User-level permissions (JWT)
- [ ] Rate limiting per token
- [ ] File deduplication
- [ ] Image optimization/thumbnails
- [ ] Virus scanning
- [ ] Metrics and monitoring

## License

Part of the `steven-universe` monorepo.
