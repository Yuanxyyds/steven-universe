#!/bin/bash
# Deployment script - deploys to LXC container via SSH

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Deployment to LXC${NC}"

# Get script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Load .env file
if [ -f .env ]; then
    echo -e "${YELLOW}📋 Loading environment from .env${NC}"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo -e "${YELLOW}Please create .env from .env.example${NC}"
    exit 1
fi

# Check required environment variables
REQUIRED_VARS=(
    "LXC_HOST"
    "APP_NAME"
    "APP_VERSION"
    "LOG_LEVEL"
    "CORS_ORIGINS"
    "PROXMOX_API_URL"
    "PROXMOX_API_TOKEN"
    "PROXMOX_VERIFY_SSL"
    "STEVENAI_SERVICE_URL"
    "FOOD101_SERVICE_URL"
    "LANDSINK_SERVICE_URL"
    "FILE_SERVICE_URL"
    "FILE_SERVICE_API_KEY"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Error: Required variable $var is not set${NC}"
        echo -e "${YELLOW}Please set all required variables in .env or export them${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Environment variables validated${NC}"

# Sync files to LXC
echo -e "${YELLOW}📦 Syncing files to LXC...${NC}"
DEPLOY_PATH="${LXC_DEPLOY_PATH:-~/web-server}"

# Sync service directory
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'venv' \
  --exclude '.pytest_cache' \
  --exclude 'scripts' \
  ./ "$LXC_HOST:$DEPLOY_PATH/"

# Sync shared-schemas package (required dependency)
echo -e "${YELLOW}📦 Syncing shared-schemas...${NC}"
rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  ../../libs/shared-schemas/ "$LXC_HOST:$DEPLOY_PATH/shared-schemas/"

echo -e "${GREEN}✅ Files synced successfully${NC}"

# Deploy on LXC
echo -e "${YELLOW}🚀 Deploying on LXC...${NC}"
ssh "$LXC_HOST" bash <<ENDSSH
set -e
cd $DEPLOY_PATH

# Create .env file from environment variables
cat > .env << 'EOF'
APP_NAME=$APP_NAME
APP_VERSION=$APP_VERSION
LOG_LEVEL=${LOG_LEVEL:-INFO}
CORS_ORIGINS=$CORS_ORIGINS
PROXMOX_API_URL=$PROXMOX_API_URL
PROXMOX_API_TOKEN=$PROXMOX_API_TOKEN
PROXMOX_VERIFY_SSL=${PROXMOX_VERIFY_SSL:-false}
STEVENAI_SERVICE_URL=${STEVENAI_SERVICE_URL:-http://localhost:8001}
FOOD101_SERVICE_URL=${FOOD101_SERVICE_URL:-http://localhost:8002}
LANDSINK_SERVICE_URL=${LANDSINK_SERVICE_URL:-http://localhost:8003}
FILE_SERVICE_URL=$FILE_SERVICE_URL
FILE_SERVICE_API_KEY=$FILE_SERVICE_API_KEY
EOF

echo "✅ Environment file created"

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t web-server:latest .

# Stop and remove old container
echo "🛑 Stopping old container..."
docker stop web-server 2>/dev/null || true
docker rm web-server 2>/dev/null || true

# Run new container
echo "🚀 Starting new container..."
docker run -d \
  --name web-server \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  web-server:latest

# Wait for healthcheck
echo "⏳ Waiting for service to be healthy..."
sleep 10

# Check container status
if docker ps | grep -q web-server; then
  echo "✅ Service deployed successfully!"
  docker logs --tail 20 web-server
else
  echo "❌ Service failed to start"
  docker logs web-server
  exit 1
fi
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Deployment on LXC successful${NC}"
else
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

# Verify deployment
echo -e "${YELLOW}🏥 Verifying deployment...${NC}"
sleep 5

ssh "$LXC_HOST" bash <<ENDSSH
# Test health endpoint
curl -f http://localhost:8000/health || exit 1
echo "✅ Health check passed!"
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  View logs:    ssh $LXC_HOST 'docker logs -f web-server'"
echo -e "  Stop service: ssh $LXC_HOST 'docker stop web-server'"
echo -e "  SSH to host:  ssh $LXC_HOST"
