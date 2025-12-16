# vLLM Worker

Session-based LLM inference worker using vLLM for high-throughput text generation.

## Architecture

This worker runs **two services** in a single container:

1. **Worker Wrapper** (Port 8000): FastAPI server implementing GPUWorkerProtocol
   - Exposes `/health`, `/stop`, `/task` endpoints
   - Translates GPU service requests to vLLM API calls
   - Streams responses as SSE events

2. **vLLM OpenAI Server** (Port 8001): Native vLLM inference engine
   - OpenAI-compatible HTTP API
   - High-throughput inference with PagedAttention
   - Supports streaming and batching

## Features

- OpenAI-compatible chat completions
- Streaming token generation
- Configurable generation parameters (temperature, top_p, max_tokens)
- Automatic model loading from HuggingFace or local path
- Health checks for both services
- Graceful shutdown handling

## Build

```bash
cd python/workers/gpu-server/vllm-worker
./build.sh
```

The build script:
1. Locates shared_schemas library
2. Copies it into worker directory
3. Builds Docker image
4. Cleans up temporary files

## Run Standalone (for testing)

```bash
docker run --gpus all \
  -p 8000:8000 \
  -p 8001:8001 \
  -e MODEL_NAME=Qwen/Qwen2.5-7B-Instruct \
  vllm-worker:latest
```

**Note**: First startup takes 30-120 seconds for model loading.

## Test Endpoints

### Health Check
```bash
# Wait 30-120s for model loading first
curl http://localhost:8000/health
```

Response:
```json
{"status": "healthy"}
```

### Submit Task
```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-123",
    "model_id": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello! How are you?"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

## Use with GPU Service

Submit a task via GPU service API:

```bash
curl -X POST http://192.168.50.49:8001/api/tasks/submit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "task_name": "vllm-chat",
    "create_session": true,
    "metadata": {
      "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing in simple terms."}
      ],
      "temperature": 0.8,
      "max_tokens": 256
    }
  }'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | 8000 | Worker wrapper port |
| `VLLM_PORT` | 8001 | vLLM server port |
| `MODEL_NAME` | Qwen/Qwen2.5-7B-Instruct | Model identifier |
| `MODEL_PATH` | /models | Path to local model cache |
| `DTYPE` | auto | Model precision (auto/float16/bfloat16) |
| `GPU_MEMORY_UTILIZATION` | 0.90 | GPU memory fraction (0.0-1.0) |
| `MAX_MODEL_LEN` | 4096 | Max sequence length |

## Metadata Parameters

When submitting tasks via GPU service, you can customize generation:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `messages` | List[Dict] | Required | Chat messages (OpenAI format) |
| `prompt` | str | Alternative | Raw prompt (alternative to messages) |
| `temperature` | float | 0.7 | Sampling temperature (0.0-2.0) |
| `max_tokens` | int | 512 | Maximum tokens to generate |
| `top_p` | float | 1.0 | Nucleus sampling threshold |
| `top_k` | int | -1 | Top-K sampling (-1 disables) |
| `stop` | List[str] | None | Stop sequences |

## Expected SSE Events

The worker emits these event types:

- `logs`: Status messages (info/error level)
- `text_delta`: Streaming token chunks
- `completed`: Task completion with status

Example stream:
```
event: logs
data: {"log": "Checking vLLM server status...", "level": "info"}

event: logs
data: {"log": "vLLM server ready", "level": "info"}

event: logs
data: {"log": "Starting inference with Qwen/Qwen2.5-7B-Instruct...", "level": "info"}

event: text_delta
data: {"delta": "Hello"}

event: text_delta
data: {"delta": "!"}

event: text_delta
data: {"delta": " How"}

event: logs
data: {"log": "Generated 42 characters", "level": "info"}

event: completed
data: {"status": "completed", "model": "Qwen/Qwen2.5-7B-Instruct"}
```

## Performance Notes

- **First Request**: 30-120 seconds (model loading time)
- **Subsequent Requests**: <1 second to first token
- **GPU Memory**: ~14GB for Qwen2.5-7B with 4K context
- **Throughput**: Depends on GPU (A6000: ~80 tokens/s, 4090: ~100 tokens/s)

## Troubleshooting

### Container starts but health check fails

Check vLLM logs:
```bash
docker exec <container_id> tail -n 100 /var/log/vllm.log
```

Common issues:
- Out of GPU memory: Reduce `GPU_MEMORY_UTILIZATION` or `MAX_MODEL_LEN`
- Model download failed: Check internet connection or use local model path
- CUDA errors: Verify GPU is available and drivers are correct version

### Task timeout

- Increase `timeout_seconds` in task_definitions.yaml (default: 120s)
- Check if model is already loaded (subsequent requests should be fast)
- Verify GPU utilization with `nvidia-smi`

### Slow inference

- Check GPU temperature throttling with `nvidia-smi`
- Reduce `max_tokens` for faster response
- Increase `GPU_MEMORY_UTILIZATION` if memory available
- Use float16 instead of auto: `DTYPE=float16`

## Development

Project structure:
```
vllm-worker/
├── worker.py           # FastAPI wrapper (port 8000)
├── entrypoint.sh       # Multi-service startup script
├── Dockerfile          # Container definition
├── build.sh            # Build script with shared_schemas
└── README.md           # This file
```

Key files in GPU service:
- Worker client: `app/clients/worker/llm/vllm.py`
- Schemas: `shared_schemas/worker/vllm/schemas.py`
- Config: `app/config/task_definitions.yaml`, `task_actions.yaml`

## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [vLLM OpenAI Server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)
- [Qwen2.5 Models](https://huggingface.co/Qwen)
