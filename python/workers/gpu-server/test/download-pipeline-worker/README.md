# Download Pipeline Worker

Session-based test worker that demonstrates the complete model download pipeline.

## Features

- **HTTP Server**: FastAPI-based server (not docker log following)
- **Model Enumeration**: Lists all files in model directory
- **SSE Streaming**: Streams responses as Server-Sent Events
- **Session-based**: Long-lived container that can process multiple tasks

## Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "worker": "download-pipeline-worker",
  "model_path": "/data/models"
}
```

### `GET /status`
Worker status with file count.

**Response:**
```json
{
  "status": "ready",
  "worker": "download-pipeline-worker",
  "model_path": "/data/models/Qwen2.5-Coder-3B-Instruct",
  "model_path_exists": true,
  "total_files": 42
}
```

### `POST /task`
Submit task for processing with SSE streaming.

**Request:**
```json
{
  "task_id": "task-123",
  "model_id": "Qwen2.5-Coder-3B-Instruct",
  "task_preset": "download-pipeline-test",
  "metadata": {}
}
```

**Response:** SSE stream with events:
- `logs`: Status messages
- `text_delta`: Streaming text output
- `completed`: Task completion

## Building

```bash
./build.sh
```

This builds the Docker image: `download-pipeline-worker:latest`

## Running Locally

```bash
docker run -p 8000:8000 \
  -v /path/to/models:/data/models \
  download-pipeline-worker:latest
```

## Testing

```bash
# Health check
curl http://localhost:8000/health

# Status
curl http://localhost:8000/status

# Submit task (SSE stream)
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-123",
    "model_id": "Qwen2.5-Coder-3B-Instruct",
    "task_preset": "download-pipeline-test",
    "metadata": {}
  }'
```

## Environment Variables

- `SERVER_PORT`: HTTP server port (default: 8000)
- `MODEL_PATH`: Base path for models (default: /data/models)

## SSE Event Format

Events use the standard SSE format:

```
event: logs
data: {"log": "Task received", "level": "info"}

event: text_delta
data: {"delta": "Task Received!\n"}

event: completed
data: {"status": "completed", "files_found": 42}
```

## Integration with GPU Service

The GPU service will:
1. Download model tar.gz from file-service if not cached
2. Extract to `/data/models/{model_id}/`
3. Create session container with model mounted
4. Send HTTP POST to `http://container-name:8000/task`
5. Stream SSE responses back to client
