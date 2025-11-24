# Steven Universe - Monorepo for Steven

My personal monorepo — a unified space that brings together my work across AI, software development, GPU computing, cloud infrastructure, and full-stack applications.

## Project Structure

```
steven-universe/
├── js/
│   └── apps/
│       └── personal-website/     # React-based personal portfolio website
├── python/
│   ├── libs/
│   │   └── shared-schemas/       # Shared Pydantic schemas for API contracts
│   └── services/
│       ├── file-management/      # File management microservice (MinIO/S3)
│       └── web-server/           # Backend API server
└── .github/
    └── workflows/                # CI/CD pipelines
```

## Projects

### Personal Website

Portfolio website showcasing my projects, skills, and experience.

**Main Features:**
- Interactive 3D graphics and animations
- AI-powered chatbot
- Project showcase with video demos
- ML model integrations (food classification, land sink prediction)

**Path:** `js/apps/personal-website/`
**Live:** https://liustev6.ca

---

### File Management Service

Centralized file management microservice with three-tier bucket architecture for MinIO/S3 operations.

**Main Features:**
- Type 1: Private + Internal only (ML models, backend-only data)
- Type 2: Private + Signed URLs (user uploads, time-limited access)
- Type 3: Public buckets (AI-generated photos, direct URL access)
- Dual token authentication (internal + frontend)
- Docker + LXC deployment

**Path:** `python/services/file-management/`

### Web Server (API Gateway)

FastAPI-based API Gateway that routes requests to specialized microservices.

**Main Features:**
- Proxmox server monitoring and statistics
- API gateway routing to downstream microservices
- Health checks for all connected services
- CORS configuration for frontend integration
- Docker + LXC deployment with automated sync

**Current Migration Status:**
- ✅ Phase 1: Proxmox stats API (completed)
- 🚧 Phase 2: StevenAI chatbot service (planned)
- 🚧 Phase 3: Food101 classification service (planned)
- 🚧 Phase 4: Landsink prediction service (planned)

**Architecture:**
```
Frontend → Web Server (Gateway) → Specialized Microservices
                                → File Management Service
                                → Proxmox API
```

**Path:** `python/services/web-server/`