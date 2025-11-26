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

### 2. Model Presets Configuration

Edit `app/config/model_presets.yaml` to define your models:

```yaml
models:
  llama-7b:
    inference:
      docker_image: "llm-runner:latest"
      command: ["python", "inference.py"]
      env_vars:
        MODEL_NAME: "llama-7b"

  stable-diffusion-xl:
    generate:
      docker_image: "diffusion-runner:latest"
      command: ["python", "generate.py"]
      env_vars:
        MODEL_NAME: "stable-diffusion-xl"
```

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

### Health Check

```bash
GET /health
```

Returns service status, GPU devices, active sessions, and active tasks.

### Task Submission

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

Returns SSE stream with events:

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

### One-off Task

1. Client submits task with `task_type: "oneoff"`
2. Server allocates GPU based on `task_difficulty`
3. Server creates ephemeral container with model mounted
4. Server streams execution events via SSE
5. Container exits, GPU is released

### Session-based Task

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
│   │   └── model_presets.yaml
│   ├── core/             # Core managers
│   │   ├── config.py     # Settings
│   │   ├── dependencies.py
│   │   ├── docker_manager.py
│   │   ├── gpu_manager.py
│   │   ├── instance_manager.py
│   │   ├── model_config.py
│   │   └── session_manager.py
│   ├── models/           # Data models
│   │   ├── events.py
│   │   ├── session.py
│   │   └── task.py
│   └── main.py           # FastAPI application
├── scripts/
│   └── deploy.sh         # Deployment script
├── .env.example
├── Dockerfile
├── requirements.txt
├── README.md
└── SERVER_DESIGN.md
```

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
