# Personal Website

My personal portfolio website showcasing my projects, skills, and experience in AI, software development, and full-stack engineering.

**Live Site**: https://liustev6.ca

## Tech Stack

- **Frontend**: React 19.1.0 with Create React App
- **UI Libraries**: React Bootstrap, Framer Motion, React Icons
- **3D Graphics**: Three.js with React Three Fiber
- **Backend**: Python API server (located in `python/services/web-server`)
- **Deployment**: Vercel with GitHub Actions CI/CD
- **Hosting**: Frontend on Vercel, Backend APIs on AWS

## Features

- Interactive 3D graphics and animations
- AI-powered chatbot (StevenAI) for answering questions about me
- Project showcase with detailed descriptions and video demos
- Food image classification demo
- Land sink prediction visualization
- Responsive design for all devices

## Development

### Prerequisites
- Node.js 20+
- npm or yarn

### Setup

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

The app will open at http://localhost:3000

### Available Scripts

- `npm start` - Runs the app in development mode
- `npm run build` - Builds the app for production
- `npm test` - Runs the test suite

## Deployment

This project is automatically deployed to Vercel when changes are pushed to the `main` branch. The deployment workflow:

1. Triggers on push to `main` or PR creation
2. Installs dependencies and builds the project
3. Deploys to Vercel (production for `main`, preview for PRs)
4. Posts preview URLs as PR comments

See `../../.github/workflows/deploy-personal-website.yml` for workflow configuration.

## Project Structure

```
src/
├── components/         # Reusable React components
│   ├── common/        # Shared components (Navbar, Footer, Chatbot)
│   ├── effects/       # Animation and visual effects
│   ├── home/          # Home page components
│   ├── project/       # Project-specific components
│   └── server/        # 3D server room visualization
├── pages/             # Page-level components
│   ├── home/          # Home page
│   └── project/       # Project pages
└── style/             # CSS files

public/                # Static assets
```

## Backend Integration

The website integrates with backend APIs for:
- **StevenAI**: AI chatbot powered by GPT-4 and Llama with RAG
- **Food Classification**: ML model for food image recognition
- **Land Sink Prediction**: Environmental data visualization

Backend code is located in the monorepo at `../../python/services/web-server/`

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `REACT_APP_API_BASE_URL` | Backend API base URL | `https://server-lite.liustev6.ca` |

## Monorepo Structure

This project is part of the `steven-universe` monorepo:
- Frontend: `js/apps/personal-website/` (this directory)
- Backend: `python/services/web-server/`
- CI/CD: `.github/workflows/`
