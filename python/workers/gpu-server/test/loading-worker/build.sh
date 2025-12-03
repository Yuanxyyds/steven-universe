#!/bin/bash
set -e

echo "Building loading-worker Docker image..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Build the image
docker build -t loading-worker:latest .

echo "✓ loading-worker:latest built successfully"
echo ""
echo "Test the worker:"
echo "  docker run --rm loading-worker:latest"
echo ""
echo "Or deploy to GPU server and test via GPU service"
