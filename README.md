# Steven Universe - Monorepo for Steven

My personal monorepo — a unified space that brings together my work across AI, software development, GPU computing, cloud infrastructure, and full-stack applications.

## Project Structure

```
steven-universe/
├── js/
│   └── apps/
│       └── personal-website/     # React-based personal portfolio website
├── python/
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

### Backend Services

Python API server providing ML model endpoints and backend services.

**Main Features:**
- StevenAI chatbot API (GPT-4, Llama with RAG)
- Food image classification
- Land sink prediction
- Server statistics and monitoring

**Path:** `python/services/web-server/`