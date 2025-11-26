#!/bin/bash

##############################################################################
# GPU Service Deployment Script
#
# Deploys the GPU service to the remote GPU VM with Docker support.
#
# Prerequisites:
# - SSH access to VM_HOST configured in .env
# - Docker and nvidia-docker installed on remote VM
# - NVIDIA drivers and CUDA installed on remote VM
# - Model cache directory exists on remote VM
#
# Usage:
#   ./scripts/deploy.sh [--build-only] [--no-build]
#
# Options:
#   --build-only    Build Docker image only, don't deploy
#   --no-build      Skip Docker build, deploy existing image
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${BLUE}Loading environment from .env${NC}"
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Validate required variables
if [ -z "$VM_HOST" ]; then
    echo -e "${RED}Error: VM_HOST not set in .env${NC}"
    exit 1
fi

if [ -z "$DEPLOY_PATH" ]; then
    echo -e "${RED}Error: DEPLOY_PATH not set in .env${NC}"
    exit 1
fi

# Parse arguments
BUILD_ONLY=false
NO_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Docker image details
IMAGE_NAME="gpu-service"
IMAGE_TAG="${APP_VERSION:-latest}"
FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}GPU Service Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Target: ${BLUE}$VM_HOST${NC}"
echo -e "Deploy Path: ${BLUE}$DEPLOY_PATH${NC}"
echo -e "Image: ${BLUE}$FULL_IMAGE_NAME${NC}"
echo ""

##############################################################################
# Step 1: Build Docker Image
##############################################################################

if [ "$NO_BUILD" = false ]; then
    echo -e "${YELLOW}Step 1: Building Docker image...${NC}"

    cd "$PROJECT_ROOT"

    # Build with shared-schemas
    docker build \
        --build-arg APP_VERSION="$APP_VERSION" \
        -t "$FULL_IMAGE_NAME" \
        -f Dockerfile \
        .

    echo -e "${GREEN}✓ Docker image built successfully${NC}"
    echo ""
else
    echo -e "${YELLOW}Step 1: Skipping Docker build (--no-build)${NC}"
    echo ""
fi

if [ "$BUILD_ONLY" = true ]; then
    echo -e "${GREEN}Build complete (--build-only mode)${NC}"
    exit 0
fi

##############################################################################
# Step 2: Save and Transfer Image
##############################################################################

echo -e "${YELLOW}Step 2: Transferring Docker image to VM...${NC}"

# Save image to tar
IMAGE_TAR="/tmp/${IMAGE_NAME}_${IMAGE_TAG}.tar"
echo "Saving image to $IMAGE_TAR..."
docker save "$FULL_IMAGE_NAME" -o "$IMAGE_TAR"

# Transfer to VM
echo "Transferring to $VM_HOST..."
scp "$IMAGE_TAR" "$VM_HOST:/tmp/"

# Load image on VM
echo "Loading image on VM..."
ssh "$VM_HOST" "docker load -i /tmp/$(basename $IMAGE_TAR) && rm /tmp/$(basename $IMAGE_TAR)"

# Cleanup local tar
rm "$IMAGE_TAR"

echo -e "${GREEN}✓ Image transferred successfully${NC}"
echo ""

##############################################################################
# Step 3: Transfer Configuration Files
##############################################################################

echo -e "${YELLOW}Step 3: Transferring configuration files...${NC}"

# Create deployment directory on VM
ssh "$VM_HOST" "mkdir -p $DEPLOY_PATH"

# Transfer .env file
if [ -f "$PROJECT_ROOT/.env" ]; then
    scp "$PROJECT_ROOT/.env" "$VM_HOST:$DEPLOY_PATH/.env"
    echo -e "${GREEN}✓ Transferred .env${NC}"
else
    echo -e "${RED}Warning: .env file not found${NC}"
fi

# Transfer model_presets.yaml
if [ -f "$PROJECT_ROOT/app/config/model_presets.yaml" ]; then
    ssh "$VM_HOST" "mkdir -p $DEPLOY_PATH/config"
    scp "$PROJECT_ROOT/app/config/model_presets.yaml" "$VM_HOST:$DEPLOY_PATH/config/model_presets.yaml"
    echo -e "${GREEN}✓ Transferred model_presets.yaml${NC}"
else
    echo -e "${RED}Warning: model_presets.yaml not found${NC}"
fi

echo ""

##############################################################################
# Step 4: Create Directories on VM
##############################################################################

echo -e "${YELLOW}Step 4: Setting up directories on VM...${NC}"

ssh "$VM_HOST" << 'EOF'
    # Model cache directory
    if [ -n "$MODEL_CACHE_DIR" ]; then
        mkdir -p "$MODEL_CACHE_DIR"
        echo "Created model cache directory: $MODEL_CACHE_DIR"
    fi
EOF

echo -e "${GREEN}✓ Directories configured${NC}"
echo ""

##############################################################################
# Step 5: Stop Existing Container
##############################################################################

echo -e "${YELLOW}Step 5: Stopping existing container...${NC}"

ssh "$VM_HOST" << EOF
    if docker ps -a --format '{{.Names}}' | grep -q "^gpu-service$"; then
        echo "Stopping and removing existing container..."
        docker stop gpu-service || true
        docker rm gpu-service || true
        echo "✓ Existing container removed"
    else
        echo "No existing container found"
    fi
EOF

echo ""

##############################################################################
# Step 6: Start New Container
##############################################################################

echo -e "${YELLOW}Step 6: Starting new container...${NC}"

ssh "$VM_HOST" << EOF
    cd $DEPLOY_PATH

    # Load environment variables
    export \$(grep -v '^#' .env | xargs)

    # Run container with GPU support
    docker run -d \
        --name gpu-service \
        --restart unless-stopped \
        --gpus all \
        -p 8001:8001 \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v \${MODEL_CACHE_DIR}:\${MODEL_CACHE_DIR} \
        -v $DEPLOY_PATH/config:/app/app/config \
        --env-file .env \
        "$FULL_IMAGE_NAME"

    echo "✓ Container started"
    echo ""
    echo "Container logs:"
    docker logs gpu-service --tail 20
EOF

echo ""
echo -e "${GREEN}✓ Deployment complete${NC}"
echo ""

##############################################################################
# Step 7: Health Check
##############################################################################

echo -e "${YELLOW}Step 7: Running health check...${NC}"
echo "Waiting 5 seconds for service to start..."
sleep 5

ssh "$VM_HOST" << 'EOF'
    HEALTH_CHECK=$(curl -s http://localhost:8001/health || echo "failed")

    if echo "$HEALTH_CHECK" | grep -q "healthy"; then
        echo "✓ Service is healthy"
    else
        echo "⚠ Service health check failed"
        echo "Response: $HEALTH_CHECK"
    fi
EOF

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Service URL: http://$(echo $VM_HOST | cut -d'@' -f2):8001"
echo ""
echo "Useful commands:"
echo "  View logs:    ssh $VM_HOST 'docker logs -f gpu-service'"
echo "  Stop service: ssh $VM_HOST 'docker stop gpu-service'"
echo "  Restart:      ssh $VM_HOST 'docker restart gpu-service'"
echo "  Shell access: ssh $VM_HOST 'docker exec -it gpu-service /bin/bash'"
echo ""
