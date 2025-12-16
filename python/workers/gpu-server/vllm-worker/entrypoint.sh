#!/bin/bash
set -e

echo "========================================="
echo "Starting vLLM Worker Container"
echo "========================================="

# Configuration
MODEL_ID="${MODEL_ID:-Qwen3-4B-Instruct}"
MODEL_PATH="${MODEL_PATH:-/models}"
VLLM_PORT="${VLLM_PORT:-8001}"
SERVER_PORT="${SERVER_PORT:-8000}"
DTYPE="${DTYPE:-auto}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
DISABLE_CUDAGRAPH="${DISABLE_CUDAGRAPH:-false}"

echo "Configuration:"
echo "  MODEL_ID: $MODEL_ID"
echo "  MODEL_PATH: $MODEL_PATH"
echo "  VLLM_PORT: $VLLM_PORT"
echo "  SERVER_PORT: $SERVER_PORT"
echo "  DTYPE: $DTYPE"
echo "  GPU_MEMORY_UTILIZATION: $GPU_MEMORY_UTILIZATION"
echo "  MAX_MODEL_LEN: $MAX_MODEL_LEN"
echo "  DISABLE_CUDAGRAPH: $DISABLE_CUDAGRAPH"
echo ""

# Determine model location
# GPU service mounts model at MODEL_PATH, so try that first
if [ -d "$MODEL_PATH" ] && [ "$(ls -A $MODEL_PATH 2>/dev/null)" ]; then
    # Model is mounted by GPU service at MODEL_PATH
    MODEL_ARG="$MODEL_PATH"
    echo "Using mounted model at: $MODEL_ARG"
else
    # Fallback: Download from HuggingFace (for standalone testing)
    MODEL_ARG="$MODEL_ID"
    echo "No mounted model found, will download from HuggingFace: $MODEL_ARG"
fi

# Start vLLM OpenAI API server in background
echo "========================================="
echo "Starting vLLM Server on port $VLLM_PORT..."
echo "========================================="

# Build vLLM command with optional optimizations
VLLM_CMD="python3 -m vllm.entrypoints.openai.api_server \
    --model $MODEL_ARG \
    --host 0.0.0.0 \
    --port $VLLM_PORT \
    --dtype $DTYPE \
    --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
    --max-model-len $MAX_MODEL_LEN \
    --served-model-name $MODEL_ID \
    --disable-log-requests"

# Disable CUDA graphs for fastest startup (Tier 3 optimization)
if [ "$DISABLE_CUDAGRAPH" = "true" ]; then
    VLLM_CMD="$VLLM_CMD --enforce-eager --max-cudagraph-capture-size 0"
    echo "CUDA graphs disabled for faster startup (slightly lower throughput)"
fi

eval "$VLLM_CMD > /var/log/vllm.log 2>&1 &"

VLLM_PID=$!
echo "vLLM server started (PID: $VLLM_PID)"
echo "Logs: /var/log/vllm.log"

# Note: We don't wait for vLLM here - the worker's /health endpoint will
# handle checking if vLLM is ready. The GPU service polls /health using
# startup_timeout_seconds (configured per task).
echo ""
echo "vLLM is loading model in background..."
echo "Worker wrapper will report healthy once vLLM is ready"

# Start FastAPI worker wrapper (foreground)
echo ""
echo "========================================="
echo "Starting Worker Wrapper on port $SERVER_PORT..."
echo "========================================="

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    echo "Stopping vLLM server (PID: $VLLM_PID)..."
    kill $VLLM_PID 2>/dev/null || true
    wait $VLLM_PID 2>/dev/null || true
    echo "Shutdown complete"
}

trap cleanup EXIT INT TERM

# Run worker in foreground (container lifecycle follows this process)
python3 /app/worker.py
