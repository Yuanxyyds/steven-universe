# GPU Workers

Worker implementations for the GPU Service. Workers are Docker containers that execute specific tasks (inference, training, etc.) on GPU hardware.

## Directory Structure

```
gpu-server/
├── test/              # Test workers for development
│   └── loading-worker # Simulates model loading/unloading
└── (future)
    ├── llama/         # LLaMA inference worker
    ├── diffusion/     # Stable Diffusion worker
    └── whisper/       # Audio transcription worker
```

## Worker Architecture

Workers are **stateless Docker containers** that:
1. Receive configuration via environment variables
2. Emit structured JSON events to stdout
3. Perform GPU-intensive tasks
4. Exit when complete (one-off) or wait for next task (session)

## Event Protocol

Workers must emit JSON events that the GPU service parses:

### Event Types

```json
// Connection established
{"event": "connection", "status": "connected"}

// Worker status updates
{"event": "worker", "status": "loading", "message": "Loading model..."}

// Streaming text output (incremental)
{"event": "text_delta", "delta": "Hello "}

// Complete text output
{"event": "text", "content": "Hello World!"}

// Task completion
{"event": "finish", "status": "completed"}
```

### Event Flow Example

```
1. CONNECTION → Worker connected to GPU
2. WORKER (initializing) → Starting up
3. WORKER (loading) → Loading model into GPU memory
4. TEXT_DELTA → Streaming output chunks
5. TEXT → Final output
6. WORKER (cleaning_up) → Unloading model
7. FINISH → Task complete
```

## Environment Variables

All workers receive these environment variables:

- `MODEL_NAME`: Model identifier (e.g., "llama-7b")
- `MODEL_PATH`: Path to model files (mounted at `/models`)
- `GPU_DEVICE`: GPU device ID assigned (via Docker `--gpus device=N`)

Additional variables can be specified in `model_presets.yaml`.

## Building Workers

Each worker has its own build script:

```bash
cd test/loading-worker
./build.sh
```

Or build manually:

```bash
docker build -t loading-worker:latest .
```

## Testing Workers Standalone

Test a worker without the GPU service:

```bash
# Run worker locally
docker run --rm loading-worker:latest

# Run with custom environment
docker run --rm \
  -e MODEL_NAME=my-model \
  -e MODEL_PATH=/tmp/models \
  loading-worker:latest
```

## Deploying Workers to GPU Server

### Option 1: Build on GPU Server

```bash
# Copy worker to GPU server
rsync -av test/loading-worker/ user@gpu-server:~/workers/loading-worker/

# SSH to server and build
ssh user@gpu-server
cd ~/workers/loading-worker
docker build -t loading-worker:latest .
```

### Option 2: Export/Import Image

```bash
# Build locally
cd test/loading-worker
docker build -t loading-worker:latest .

# Save to tar
docker save loading-worker:latest -o loading-worker.tar

# Transfer to server
scp loading-worker.tar user@gpu-server:/tmp/

# Load on server
ssh user@gpu-server 'docker load -i /tmp/loading-worker.tar'
```

## Registering Workers

Add workers to `gpu-server/app/config/model_presets.yaml`:

```yaml
models:
  test-loading:
    inference:
      docker_image: "loading-worker:latest"
      command: ["python", "/app/worker.py"]
      env_vars:
        MODEL_NAME: "test-loading"
```

## Creating New Workers

### 1. Create Worker Directory

```bash
mkdir -p {category}/{worker-name}
cd {category}/{worker-name}
```

### 2. Create worker.py

```python
#!/usr/bin/env python3
import json
import sys

def emit_event(event_type: str, data: dict):
    print(json.dumps({"event": event_type, **data}), flush=True)

def main():
    # Your worker logic here
    emit_event("connection", {"status": "connected"})
    emit_event("worker", {"status": "working"})
    # ... do work ...
    emit_event("finish", {"status": "completed"})

if __name__ == "__main__":
    main()
```

### 3. Create Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY worker.py /app/worker.py
RUN chmod +x /app/worker.py
CMD ["python", "/app/worker.py"]
```

### 4. Create build.sh

```bash
#!/bin/bash
set -e
docker build -t my-worker:latest .
```

### 5. Test

```bash
./build.sh
docker run --rm my-worker:latest
```

## Worker Best Practices

1. **Emit events frequently**: Keep the client updated on progress
2. **Flush stdout**: Use `flush=True` to ensure events are sent immediately
3. **Handle errors gracefully**: Emit `finish` event with `status: "failed"`
4. **Clean up resources**: Free GPU memory before exiting
5. **Be stateless**: Don't rely on persistent state between runs
6. **Use structured JSON**: Always emit valid JSON objects
7. **Log to stderr**: Use stderr for debug logs, stdout for events

## GPU Access

Workers receive GPU access via Docker's `--gpus` flag. Inside the container:

```python
import torch
print(torch.cuda.is_available())  # True
print(torch.cuda.device_count())  # 1 (single GPU assigned)
```

## Troubleshooting

**Worker not starting:**
- Check Docker image exists: `docker images | grep worker-name`
- Test worker standalone: `docker run --rm worker-name:latest`
- Check GPU service logs: `docker logs gpu-service`

**Events not streaming:**
- Ensure JSON is valid
- Use `flush=True` on print statements
- Check stdout is not buffered

**GPU not accessible:**
- Verify nvidia-docker is installed on server
- Test: `docker run --rm --gpus all nvidia/cuda:12.1.0-base nvidia-smi`

## Examples

See `test/` directory for working examples:
- `loading-worker`: Simulates model loading/unloading with progress updates
