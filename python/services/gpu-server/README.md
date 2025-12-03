# GPU Service

Session-based GPU task execution service with SSE streaming support.

## Architecture

This service manages GPU resources using a **session-based architecture** that keeps models loaded in memory between requests for improved performance.

### Key Features

- **Session-based execution**: Long-lived containers that reuse loaded models
- **One-off tasks**: Ephemeral containers for single-use tasks
- **Task difficulty routing**: Route tasks to appropriate GPUs (low/high difficulty)
- **SSE streaming**: Real-time event streaming with structured events
- **Auto model fetching**: Automatically downloads models from file-service
- **FIFO queue per session**: 3-5 requests per session with fair queuing
- **Automatic timeouts**: Idle timeout (5 min) and max lifetime (1 hour)
- **Docker-outside-of-Docker**: Manages Docker containers from within Docker

## Architecture Documentation

See [SERVER_DESIGN.md](./SERVER_DESIGN.md) for comprehensive architecture documentation including:
- Session-based architecture deep dive
- Component diagrams and state machines
- Request flow decision trees
- Event streaming protocol
- Model management system
- Security boundaries

## Quick Start

### 1. Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key configuration:

```env
# GPU Configuration
GPU_DEVICE_IDS=0,1
GPU_DEVICE_DIFFICULTY=0:low,1:high

# Session Configuration
SESSION_IDLE_TIMEOUT_SECONDS=300
SESSION_MAX_LIFETIME_SECONDS=3600
SESSION_QUEUE_MAX_SIZE=5

# File Service Integration
FILE_SERVICE_URL=http://192.168.2.98:8000
FILE_SERVICE_INTERNAL_KEY=your-internal-secret-key-here

# Authentication
INTERNAL_API_KEY=your-internal-api-key-here
```

### 2. Task Configuration

The service uses three YAML files to configure tasks:

#### `app/config/task_definitions.yaml`
Defines task metadata and defaults:

```yaml
loading-test:
  description: "Test worker that simulates GPU loading"
  task_type: "oneoff"
  task_difficulty: "low"
  timeout_seconds: 60
  metadata:
    test_mode: true
  model_id: "test-loading"
```

#### `app/config/task_actions.yaml`
Maps model IDs to Docker configurations:

```yaml
test-loading:
  source_path: ~/gpu-workers/test/loading-worker
  dockerfile: Dockerfile
  docker_image: loading-worker:latest
  command: ["python", "/app/worker.py"]
  env_vars:
    MODEL_NAME: test-loading
    WORKER_TYPE: test
  build_args: {}
```

#### `app/config/model_paths.yaml`
Specifies model file locations (optional, for tasks requiring model files):

```yaml
llama-7b:
  path: /data/models/llama-7b
  description: "LLaMA 7B model weights"
  size_gb: 13.5
```

This three-file structure separates task metadata, Docker execution configuration, and model file paths for better organization and maintainability.

### 3. Local Development

Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run the service:

```bash
python app/main.py
```

Service will be available at `http://localhost:8001`

### 4. Deployment to GPU VM

Deploy using the deployment script:

```bash
# Build and deploy
./scripts/deploy.sh

# Build only (no deploy)
./scripts/deploy.sh --build-only

# Deploy without rebuilding
./scripts/deploy.sh --no-build
```

## API Endpoints

**Note**: All task and session endpoints use the `/api` prefix.

### Health Check

```bash
GET /health
```

Returns service status, GPU devices, active sessions, and active tasks.

```bash
GET /health/resources
```

Returns detailed resource allocation including GPU status, running tasks, and session details.

### Task Submission

#### Pre-defined Tasks (Recommended)

```bash
POST /api/tasks/predefined
Content-Type: application/json
X-API-Key: your-internal-api-key-here

{
  "task_name": "loading-test",
  "task_difficulty": "low",
  "timeout_seconds": 300,
  "metadata": {
    "custom_param": "value"
  }
}
```

Executes a pre-defined task from `task_definitions.yaml` configuration. The `task_name` field is required and maps to a configured task.

#### Custom Tasks

```bash
POST /api/tasks/custom
```

Custom task execution (Not yet implemented - returns 501).

#### Legacy Task Submission

```bash
POST /api/tasks/submit
Content-Type: application/json
X-API-Key: your-internal-api-key-here

{
  "task_type": "session",
  "task_difficulty": "low",
  "model_id": "llama-7b",
  "task_preset": "inference",
  "metadata": {
    "prompt": "Hello, world!",
    "max_tokens": 100
  },
  "timeout_seconds": 300
}
```

Legacy endpoint for backward compatibility.

**SSE Stream Response**:

All task endpoints return an SSE stream with events:

- `CONNECTION`: GPU allocated, session ready
- `WORKER`: Container status (created, working, waiting)
- `TEXT_DELTA`: Streaming text output
- `TEXT`: Complete text output
- `LOGS`: Container logs
- `TASK_FINISH`: Task completed/failed/timeout

### Session Management

```bash
# List all sessions
GET /api/sessions

# Get session details
GET /api/sessions/{session_id}

# Kill session
DELETE /api/sessions/{session_id}

# Keep session alive (reset idle timeout)
POST /api/sessions/{session_id}/keepalive
```

## Request Flow

### Pre-defined Task Pipeline (Recommended)

The service uses a 7-step pipeline for executing pre-defined tasks:

1. **Config Load**: `ConfigLoader` loads task configuration from YAML files
   - `task_definitions.yaml` → Task metadata (type, difficulty, timeout)
   - `task_actions.yaml` → Docker configuration (image, command, env vars)
   - `model_paths.yaml` → Model file paths (if applicable)

2. **Model Prepare**: `ModelDownloader` ensures model availability
   - Checks if model exists on host (`/data/models/{model_id}`)
   - Downloads from file-service if missing and `AUTO_FETCH_MODELS=true`
   - Returns host path for volume mounting

3. **GPU Allocate**: `GPUManager` allocates GPU based on difficulty
   - Routes to low-difficulty GPU (RTX 4060 Ti) or high-difficulty GPU (RTX 5090)
   - Returns device ID or rejects with 503 if all matching GPUs busy

4. **Docker Create**: `DockerManager` creates one-off container
   - Mounts model volume: `-v /host/models:/models:ro`
   - Sets GPU passthrough: `--gpus device={gpu_id}`
   - Applies resource limits (memory, CPU)

5. **Instance Create**: `InstanceManager` tracks worker and streams logs
   - Monitors container stdout/stderr via thread-pooled streaming
   - Parses log output into structured SSE events
   - Enforces task timeout

6. **Task Register**: `TaskManager` tracks running task globally
   - Registers task_id → InstanceManager mapping
   - Enables monitoring and forced shutdown if needed

7. **Stream Execution**: Client receives SSE stream with real-time events
   - CONNECTION, WORKER, TEXT_DELTA, TEXT, LOGS, TASK_FINISH

**Cleanup**: GPU released, task unregistered, container auto-removed

### Session-based Task (Legacy/TODO)

**First Request:**
1. Client submits task with `task_type: "session"`
2. Server allocates GPU and creates long-lived container
3. Server loads model into container memory
4. Server executes task and streams events
5. Container stays alive, session enters WAITING state

**Subsequent Requests:**
1. Client submits task with `session_id` from first request
2. Server enqueues task to existing session (if queue not full)
3. Server executes task in same container (model already loaded)
4. Session idle timer resets on each request

**Session Termination:**
- Idle timeout (300s): No activity for 5 minutes
- Max lifetime (3600s): Session running for 1 hour
- Manual kill: `DELETE /api/sessions/{session_id}`
- Service shutdown: All sessions terminated

## Event Streaming Protocol

The service streams structured events via Server-Sent Events (SSE):

```javascript
// CONNECTION event
event: connection
data: {"status": "session_ready", "gpu_id": 0, "session_id": "abc123"}

// WORKER event
event: worker
data: {"status": "working", "container_id": "def456"}

// TEXT_DELTA event (streaming output)
event: text_delta
data: {"delta": "Hello"}

// TASK_FINISH event
event: task_finish
data: {"status": "completed", "elapsed_seconds": 12}
```

## Model Management

Models are automatically fetched from file-service if not found in local cache:

1. Client requests task with `model_id: "llama-7b"`
2. Server checks `MODEL_CACHE_DIR/llama-7b/`
3. If not found and `AUTO_FETCH_MODELS=true`:
   - Fetch from file-service: `POST /api/models/download`
   - Download to `MODEL_CACHE_DIR/llama-7b/`
4. Mount model to container: `-v /host/path:/models:ro`
5. Set environment variable: `MODEL_PATH=/models`

## GPU Workers

GPU workers are Docker containers that execute tasks on GPUs. Worker images are stored in the `python/workers/` directory.

### Worker Structure

```
python/workers/
└── gpu-server/
    └── test/
        └── loading-worker/
            ├── Dockerfile
            ├── worker.py
            └── build.sh
```

### Creating a Worker

1. Create a directory under `python/workers/gpu-server/`
2. Add a `Dockerfile` with your worker image
3. Add a `build.sh` script:

```bash
#!/bin/bash
docker build -t my-worker:latest .
```

4. Reference the image in `task_actions.yaml`:

```yaml
my-task:
  docker_image: my-worker:latest
  command: ["python", "/app/worker.py"]
```

### Worker Event Protocol

Workers communicate with the service by emitting JSON events to stdout:

```python
import json

def emit_event(event_type: str, data: dict):
    event = {"event": event_type, **data}
    print(json.dumps(event), flush=True)

# Connection event
emit_event("connection", {"status": "connected", "worker": "my-worker"})

# Worker status
emit_event("worker", {"status": "ready", "message": "Initialized"})

# Streaming output
emit_event("text_delta", {"delta": "Hello "})
emit_event("text_delta", {"delta": "world!"})

# Completion
emit_event("finish", {"status": "completed"})
```

### Deployment

Worker images are automatically built during deployment:

```bash
./scripts/deploy.sh
```

The deployment script:
1. Syncs `python/workers/` to GPU server (Step 3.5)
2. Finds all `build.sh` scripts
3. Executes each `build.sh` to build worker images
4. Images are available on the GPU server for task execution

## Docker Configuration

### Prerequisites on GPU VM

- Docker with nvidia-docker support
- NVIDIA drivers and CUDA
- Docker socket accessible at `/var/run/docker.sock`

### Container Permissions

The service container needs:
- Docker socket mounted: `-v /var/run/docker.sock:/var/run/docker.sock`
- GPU access: `--gpus all`
- Model cache directory: `-v $MODEL_CACHE_DIR:$MODEL_CACHE_DIR`

### Worker Container Configuration

Worker containers created by the service get:
- Specific GPU: `--gpus device=0`
- Model volume: `-v /host/models:/models:ro`
- Environment variables: `MODEL_PATH=/models`
- Resource limits: `--memory=16g`, `--cpu-quota=100000`

## Monitoring

### View Service Logs

```bash
ssh $VM_HOST 'docker logs -f gpu-service'
```

### Check GPU Status

```bash
curl http://localhost:8001/health | jq '.gpus'
```

### List Active Sessions

```bash
curl -H "X-API-Key: your-key" http://localhost:8001/api/sessions
```

### Container Management

```bash
# List all containers (including workers)
ssh $VM_HOST 'docker ps -a'

# View worker logs
ssh $VM_HOST 'docker logs <container_id>'

# Stop worker manually
ssh $VM_HOST 'docker stop <container_id>'
```

## Development

### Project Structure

```
gpu-server/
├── app/
│   ├── api/              # API endpoints
│   │   ├── health.py     # Health check
│   │   ├── tasks.py      # Task submission
│   │   └── sessions.py   # Session management
│   ├── config/           # Configuration
│   │   ├── task_definitions.yaml  # Task metadata
│   │   ├── task_actions.yaml      # Docker configs
│   │   └── model_paths.yaml       # Model file paths
│   ├── core/
│   │   ├── manager/      # Singleton managers
│   │   │   ├── docker_manager.py   # Container orchestration
│   │   │   ├── gpu_manager.py      # GPU allocation
│   │   │   ├── session_manager.py  # Session lifecycle
│   │   │   ├── task_manager.py     # Task state tracker
│   │   │   └── model_downloader.py # Model caching
│   │   ├── instance/     # Per-request instances
│   │   │   ├── instance_manager.py   # Log streaming
│   │   │   ├── config_loader.py      # YAML loading
│   │   │   └── task_request_handler.py  # Pipeline executor
│   │   ├── config.py     # Settings
│   │   └── dependencies.py
│   ├── models/           # Data models
│   │   ├── events.py
│   │   ├── session.py
│   │   ├── task.py
│   │   └── gpu.py
│   └── main.py           # FastAPI application
├── scripts/
│   └── deploy.sh         # Deployment script
├── .env.example
├── Dockerfile
├── requirements.txt
├── README.md
└── SERVER_DESIGN.md
```

The core is organized into two subdirectories:
- **`manager/`**: Singleton managers (one per service)
- **`instance/`**: Per-request instances (one per task)

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black app/
isort app/
flake8 app/
```

## Troubleshooting

### Service won't start

Check logs:
```bash
ssh $VM_HOST 'docker logs gpu-service'
```

Common issues:
- Docker socket not mounted
- GPU not accessible (check nvidia-docker)
- Model cache directory doesn't exist
- Invalid configuration in .env

### Task fails with "No available GPU"

- Check GPU allocation: `curl http://localhost:8001/health | jq '.gpus'`
- Verify `task_difficulty` matches GPU difficulty in config
- Check if all GPUs are occupied by sessions

### Session queue full

- Check session queue: `curl http://localhost:8001/api/sessions/{session_id}`
- Increase `SESSION_QUEUE_MAX_SIZE` in .env
- Kill idle sessions manually

### Model not found

- Check `MODEL_CACHE_DIR` exists on host
- Verify `AUTO_FETCH_MODELS=true` in .env
- Check file-service connectivity
- Verify `FILE_SERVICE_INTERNAL_KEY` is correct

### Container creation fails

- Check Docker socket permissions
- Verify allowed images in `ALLOWED_DOCKER_IMAGES`
- Check Docker logs: `ssh $VM_HOST 'journalctl -u docker'`

## Security Considerations

- API key authentication on all endpoints (except health)
- Docker image whitelist: `ALLOWED_DOCKER_IMAGES`
- Resource limits on worker containers (memory, CPU)
- Read-only model volume mounts
- No host network access for workers
- Internal-only file-service communication

## Performance Tuning

### Async I/O Optimization

The service uses thread-pooled log streaming to prevent event loop blocking:

- **Problem**: Docker-py's `container.logs()` is synchronous, blocks the event loop
- **Solution**: `loop.run_in_executor()` runs blocking I/O in thread pool
- **Benefit**: Health checks respond quickly even during active log streaming
- **Implementation**: See `docker_manager.stream_logs()` (line 282-333)

### Concurrency Settings

The service runs as a single Uvicorn worker with high concurrency limits:

- `--workers 1`: Single process (manager state is in-memory, not Redis)
- `--limit-concurrency 1000`: Supports 1000 concurrent connections
- `--backlog 2048`: Queue size for burst traffic

**Why single worker?** GPU Manager, Task Manager, and Session Manager maintain in-memory state. Multiple workers would require Redis for shared state (future enhancement).

### Session Configuration

- `SESSION_IDLE_TIMEOUT_SECONDS`: Lower = less memory usage, higher = better reuse
- `SESSION_MAX_LIFETIME_SECONDS`: Prevent memory leaks from long-lived containers
- `SESSION_QUEUE_MAX_SIZE`: Higher = more concurrent tasks per session

### Task Configuration

- `DEFAULT_TASK_TIMEOUT`: Balance between allowing long tasks and preventing hangs
- `MAX_TASK_TIMEOUT`: Hard limit to prevent abuse

### GPU Configuration

- `GPU_METRICS_REFRESH_INTERVAL`: Lower = more accurate status, higher = less overhead

## License

See main repository license.
