#!/bin/bash
set -e

echo "Building download-pipeline-worker Docker image..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Find shared-schemas directory
# Check multiple possible locations
if [ -d "$HOME/gpu-server/build/libs/shared-schemas/shared_schemas" ]; then
    # GPU server deployment location
    SHARED_SCHEMAS_SOURCE="$HOME/gpu-server/build/libs/shared-schemas/shared_schemas"
elif [ -d "$SCRIPT_DIR/../../../../../libs/shared-schemas/shared_schemas" ]; then
    # Local development location (python root)
    SHARED_SCHEMAS_SOURCE="$SCRIPT_DIR/../../../../../libs/shared-schemas/shared_schemas"
else
    echo "❌ Error: Cannot find shared-schemas"
    echo "Tried:"
    echo "  - $HOME/gpu-server/build/libs/shared-schemas/shared_schemas"
    echo "  - $SCRIPT_DIR/../../../../../libs/shared-schemas/shared_schemas"
    exit 1
fi

# Copy shared_schemas into worker directory temporarily
echo "Copying shared_schemas from: $SHARED_SCHEMAS_SOURCE"
cp -r "$SHARED_SCHEMAS_SOURCE" "$SCRIPT_DIR/shared_schemas"

# Verify copy succeeded
if [ ! -d "$SCRIPT_DIR/shared_schemas" ]; then
    echo "❌ Error: Failed to copy shared_schemas"
    exit 1
fi

echo "✓ Copied shared_schemas"

# Build the image
echo "Building Docker image..."
docker build -t download-pipeline-worker:latest .

# Clean up copied shared_schemas
echo "Cleaning up..."
rm -rf "$SCRIPT_DIR/shared_schemas"

echo "✓ download-pipeline-worker:latest built successfully"
echo ""
echo "Test the worker:"
echo "  docker run -p 8000:8000 -v /path/to/models:/models download-pipeline-worker:latest"
echo ""
echo "Test health:"
echo "  curl http://localhost:8000/health"
