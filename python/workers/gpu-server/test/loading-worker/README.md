# Loading Worker - Test Worker

A test worker that simulates loading and unloading a model from GPU memory.

## Purpose

This worker helps test the GPU service's ability to:
- Stream events in real-time
- Handle model loading simulation
- Track GPU memory allocation/deallocation
- Parse structured JSON events

## Build

```bash
cd python/workers/gpu-server/test/loading-worker
docker build -t loading-worker:latest .
```

## Run Standalone (for testing)

```bash
docker run --rm loading-worker:latest
```

## Expected Output

The worker emits structured JSON events:

```json
{"event": "connection", "status": "connected", "worker": "loading-worker", "model": "test-model"}
{"event": "worker", "status": "initializing", "message": "Initializing GPU..."}
{"event": "worker", "status": "loading", "message": "Loading model test-model into GPU memory..."}
{"event": "text_delta", "delta": "Loading progress: 20%\n"}
{"event": "text_delta", "delta": "Loading progress: 40%\n"}
{"event": "text_delta", "delta": "Loading progress: 60%\n"}
{"event": "text_delta", "delta": "Loading progress: 80%\n"}
{"event": "text_delta", "delta": "Loading progress: 100%\n"}
{"event": "worker", "status": "ready", "message": "Model loaded successfully"}
{"event": "text_delta", "delta": "\nPerforming GPU computation...\n"}
{"event": "text", "content": "Model test-model computation complete!\nGPU memory allocated: ~2GB\n"}
{"event": "worker", "status": "cleaning_up", "message": "Unloading model from GPU..."}
{"event": "text_delta", "delta": "GPU memory freed.\n"}
{"event": "finish", "status": "completed", "message": "Worker completed successfully"}
```

## Use with GPU Service

Add to `gpu-server/app/config/model_presets.yaml`:

```yaml
models:
  test-loading:
    inference:
      docker_image: "loading-worker:latest"
      command: ["python", "/app/worker.py"]
      env_vars:
        MODEL_NAME: "test-loading"
```

Then submit a task:

```bash
curl -X POST http://192.168.50.49:8001/api/tasks/submit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "task_type": "session",
    "create_session": true,
    "task_difficulty": "low",
    "model_id": "test-loading",
    "task_preset": "inference",
    "metadata": {},
    "timeout_seconds": 60
  }'
```

## Environment Variables

- `MODEL_NAME`: Name of the model (default: "test-model")
- `MODEL_PATH`: Path to model directory (default: "/models")

## Timeline

- **0-0.5s**: Initialize GPU
- **0.5-5.5s**: Load model (with progress updates)
- **5.5-7.5s**: Perform computation
- **7.5-8.5s**: Unload model
- **Total**: ~8-9 seconds
