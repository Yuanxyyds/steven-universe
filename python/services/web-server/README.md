# Web Server - API Gateway

Lightweight FastAPI gateway that routes requests to specialized microservices.

**Path**: `python/services/web-server/`

## Overview

This service acts as the **central API gateway** for all backend functionality. It doesn't contain ML models or heavy processing - instead, it routes requests to dedicated microservices for each feature.

### Architecture

```
┌──────────────────────────────┐
│          Frontend            │
│  (Next.js / React)           │
└──────────────┬───────────────┘
               │ HTTPS
               ▼
       ┌───────────────────┐
       │   API Gateway     │
       │   (This Service)  │
       └───────┬───────────┘
               │ Internal calls
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
               │
        ┌──────┴───────┬──────────┬──────────┐
        ▼              ▼          ▼          ▼
  ┌─────────┐    ┌─────────┐  ┌─────────┐  ┌─────────┐
  │StevenAI │    │ Food101 │  │LandSink │  │  File   │
  │ Service │    │ Service │  │ Service │  │ Service │
  └─────────┘    └─────────┘  └─────────┘  └─────────┘
   (Phase 2)      (Phase 3)    (Phase 4)    (Existing)
```

## Features

### Currently Implemented (Phase 1)

✅ **Health Checks**
- `/health` - Service status
- `/health/services` - Downstream service health

✅ **Server Stats** (Proxmox Monitoring)
- `/stats/servers` - CPU, memory, temperature for all nodes
- Real-time monitoring via Proxmox API

### Stub Endpoints (Future Phases)

⏳ **AI Chatbot** (Phase 2 - stevenai-service)
- `/chat/query` - RAG-powered chatbot about Steven
- Supports GPT-4o and LLaMA models
- Returns 501 Not Implemented (will route to stevenai-service)

⏳ **Food Classification** (Phase 3 - food101-service)
- `/classifications/food` - Image classification with CNN models
- Returns 501 Not Implemented (will route to food101-service)

⏳ **Climate Prediction** (Phase 4 - landsink-service)
- `/predictions/landsink?year=YYYY` - Land sink prediction
- Returns 501 Not Implemented (will route to landsink-service)

## API Endpoints

### Health & Status

```bash
# Basic health check
GET /health

# Check all downstream services
GET /health/services
```

### Server Statistics

```bash
# Get Proxmox server stats
GET /stats/servers

# Response:
{
  "success": true,
  "nodes": [
    {
      "name": "local",
      "status": "online",
      "memory_used_gb": 45.23,
      "memory_total_gb": 128.0,
      "memory_usage_percent": 35.34,
      "cpu_usage_percent": 12.5,
      "cpu_cores": 16,
      "cpu_temp_celsius": 45.2
    }
  ]
}
```

### AI Chatbot (Phase 2)

```bash
# Query chatbot
GET /chat/query?q=Tell+me+about+Steven&model=gpt4o&context=qa-docs

# Query parameters:
# - q: User question (required)
# - model: gpt4o or llama (default: gpt4o)
# - context: qa, docs, or qa-docs (default: qa-docs)
# - last_q: Previous question for follow-up (optional)
# - last_a: Previous answer for follow-up (optional)
```

### Food Classification (Phase 3)

```bash
# Upload food image for classification
POST /classifications/food
Content-Type: multipart/form-data

# Form data:
# - file: Image file (JPG/PNG)
```

### Climate Prediction (Phase 4)

```bash
# Predict land sink for specific year
GET /predictions/landsink?year=2050

# Default year (2023)
GET /predictions/landsink
```

## Development Setup

### Local Development

```bash
# Install dependencies (includes shared-schemas in editable mode)
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env

# Run locally
uvicorn app.main:app --reload

# Or use Python directly
python -m app.main
```

**Note:** Use `requirements-dev.txt` for local development. It includes `requirements.txt` plus the editable shared-schemas package.

### Environment Variables

```bash
# Application
APP_NAME="Web Server API Gateway"
APP_VERSION="1.0.0"
LOG_LEVEL=INFO

# CORS (comma-separated)
CORS_ORIGINS=https://liustev6.ca,http://localhost:3000

# Proxmox API
PROXMOX_API_URL=https://proxmox.liustev6.ca/api2/json
PROXMOX_API_TOKEN=PVEAPIToken=root@pam!webserver=your-token
PROXMOX_VERIFY_SSL=false

# Downstream Services (for future phases)
STEVENAI_SERVICE_URL=http://localhost:8001
FOOD101_SERVICE_URL=http://localhost:8002
LANDSINK_SERVICE_URL=http://localhost:8003

# File Service (existing)
FILE_SERVICE_URL=https://file-server.liustev6.ca
FILE_SERVICE_API_KEY=your-api-key
```

## Deployment

### Prerequisites
- LXC container with Docker installed (see `docs/lxc-setup.md`)
- SSH key authentication configured to LXC
- rsync installed on local machine
- Local `.env` file with all configuration

### Deploy to LXC Container

**1. Configure environment variables in `.env`:**
```bash
# Copy template and edit with your values
cp .env.example .env
nano .env

# Important: All configuration comes from local .env
# The deployment script will transfer these to the LXC
```

**2. Run deployment script:**
```bash
./scripts/deploy.sh
```

**What the deployment script does:**
1. 📋 **Loads local `.env`** - Reads all environment variables from your local `.env` file
2. ✅ **Validates required variables** - Ensures all 13 required variables are set
3. 📦 **Syncs files to LXC** - Uses rsync to transfer service code and shared-schemas
4. 📝 **Creates .env on LXC** - Generates `.env` file on LXC from local environment variables
5. 🔨 **Builds Docker image** - Builds the image on the LXC (includes shared-schemas installation)
6. 🛑 **Stops old container** - Removes existing container if present
7. 🚀 **Starts new container** - Runs container with `--env-file .env`
8. 🏥 **Verifies deployment** - Tests health endpoint to confirm service is running

**Important Notes:**
- Configuration is managed in your **local** `.env` file
- Changes to `.env` require redeployment to take effect
- The LXC's `.env` is auto-generated from your local environment on each deployment
- Use `https://` for PROXMOX_API_URL to avoid redirect issues

**Useful commands after deployment:**
```bash
# View logs
ssh your-lxc-host 'docker logs -f web-server'

# Stop service
ssh your-lxc-host 'docker stop web-server'

# Restart service
ssh your-lxc-host 'docker restart web-server'

# SSH into host
ssh your-lxc-host
```

## Shared Schemas

This service uses type-safe Pydantic schemas from `python/libs/shared-schemas/` for all API contracts.

### Defined Schemas

All web-server schemas are in `shared_schemas/web_server.py`:

**Health:**
- `HealthResponse`
- `ServiceStatus`

**Server Stats:**
- `ServerStatsResponse`
- `ServerNode`

**LandSink:**
- `LandsinkPredictionRequest`
- `LandsinkPredictionResponse`

**Food Classification:**
- `FoodClassificationResponse`
- `ModelPredictions`
- `FoodPrediction`

**Chat:**
- `ChatQueryRequest`
- `ChatQueryResponse`
- `ChatContextSource`

### Usage in Code

```python
from shared_schemas.web_server import (
    ServerStatsResponse,
    ServerNode,
    ChatQueryRequest
)

@router.get("/stats/servers", response_model=ServerStatsResponse)
async def get_server_stats():
    # Response is automatically validated
    return ServerStatsResponse(success=True, nodes=[...])
```

## Project Structure

```
python/services/web-server/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app with lifespan, CORS
│   ├── core/
│   │   ├── config.py             # Pydantic Settings (loads .env)
│   │   └── dependencies.py       # Shared dependencies (HTTP client)
│   ├── api/
│   │   ├── health.py             # Health check endpoints
│   │   ├── stats.py              # Server stats (Proxmox)
│   │   ├── landsink.py           # Climate prediction (stub)
│   │   ├── food.py               # Food classification (stub)
│   │   └── chat.py               # AI chatbot (stub)
│   └── clients/
│       ├── proxmox_client.py     # Proxmox API client
│       ├── stevenai_client.py    # StevenAI service client (stub)
│       └── food101_client.py     # Food101 service client (stub)
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── Dockerfile
├── README.md
└── scripts/
    └── deploy.sh
```

## Tech Stack

- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server
- **HTTPX** - Async HTTP client
- **Pydantic Settings** - Configuration management
- **psutil** - System monitoring (CPU temperature)
- **shared-schemas** - Type-safe API contracts

## Future Phases

### Phase 2: StevenAI Service
- Create separate `python/services/stevenai-service/`
- RAG with FAISS, BGE embeddings, OpenAI GPT-4o
- Wire up `/chat/query` endpoint to proxy to this service

### Phase 3: Food101 Service
- Create separate `python/services/food101-service/`
- Load Keras models (Baseline, VGG, Inception, ResNet)
- Wire up `/classifications/food` endpoint to proxy to this service

### Phase 4: LandSink Service
- Create separate `python/services/landsink-service/`
- Linear regression, pandas, pyecharts for visualization
- Wire up `/predictions/landsink` endpoint to proxy to this service

## Migration from Django

This service replaces the old `MyPersonalServerLite/serverlite` Django application with a modern FastAPI architecture:

| Django (Old) | FastAPI (New) | Status |
|--------------|---------------|--------|
| `/serverstats/getServerStats` | `/stats/servers` | ✅ Implemented |
| `/stevenai/*/query` | `/chat/query` | ⏳ Phase 2 |
| `/food101/classify` | `/classifications/food` | ⏳ Phase 3 |
| `/landsink/predict/<year>/` | `/predictions/landsink?year=` | ⏳ Phase 4 |

**Key Improvements:**
- ✅ Modern RESTful API design (resource-based paths)
- ✅ Async HTTP clients for better performance
- ✅ Type-safe with Pydantic schemas
- ✅ Auto-generated OpenAPI docs
- ✅ Microservice architecture (separates concerns)
- ✅ Environment-based configuration
- ✅ Docker deployment with health checks

## License

Part of the `steven-universe` monorepo.
