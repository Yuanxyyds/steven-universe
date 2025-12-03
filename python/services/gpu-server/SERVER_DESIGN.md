# GPU Service - Server Design Document

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Core Principles](#core-principles)
3. [Session-Based Architecture](#session-based-architecture)
4. [Component Architecture](#component-architecture)
5. [Request Flow & Decision Trees](#request-flow--decision-trees)
6. [State Machines](#state-machines)
7. [Event Streaming Protocol](#event-streaming-protocol)
8. [Model Management System](#model-management-system)
9. [Timeout & Lifecycle Management](#timeout--lifecycle-management)
10. [Error Handling & Failure Modes](#error-handling--failure-modes)
11. [Security Boundaries](#security-boundaries)

---

## Architecture Overview

The GPU Service is a **session-based task execution framework** designed to efficiently manage GPU resources for machine learning workloads. It acts as an orchestration layer that creates and manages Docker containers with GPU passthrough, enabling both **long-lived inference sessions** and **one-time tasks**.

### Key Characteristics

- **Session-First Design**: Optimized for interactive workloads where models remain loaded in memory between requests
- **Zero Queue Philosophy**: Reject requests immediately when at capacity (503) rather than building queues
- **Server-Managed Configuration**: Clients specify what (model_id, preset), server controls how (docker image, commands)
- **Docker-outside-of-Docker (DOOD)**: Service creates sibling containers with GPU access via Docker socket
- **Event-Driven Streaming**: Real-time progress updates via Server-Sent Events (SSE)

---

## Core Principles

### 1. Simplicity Over Flexibility
- **No job queues**: Immediate rejection prevents complexity of queue management
- **Server-controlled execution**: Docker images and commands configured server-side for security
- **In-memory state (Phase 1)**: Fast access, simple operations, no database dependencies

### 2. Resource Protection
- **Dual timeout system**: Both idle timeout (inactivity) and max lifetime (absolute limit)
- **Per-session request limits**: Small FIFO queue (3-5 requests) prevents overload
- **GPU difficulty routing**: Match workload intensity to GPU capabilities

### 3. Model Reuse Optimization
- **Session matching**: Find IDLE sessions with same model before allocating new resources
- **Persistent model loading**: Keep models in GPU memory between requests
- **Automatic cache management**: Fetch models from file-service on first use, cache locally

### 4. Observable Execution
- **Streaming events**: Real-time progress via SSE (CONNECTION, WORKER, TEXT_DELTA, LOGS, TASK_FINISH)
- **Status tracking**: Monitor session state (INITIALIZING, WAITING, WORKING, KILLED)
- **GPU metrics**: Continuous monitoring of GPU utilization, memory, temperature

---

## Session-Based Architecture

### Problem Statement

Traditional request-response APIs face a critical challenge with large ML models:

1. **Cold start overhead**: Loading a 7B parameter model takes 20-60 seconds
2. **Memory waste**: Discarding loaded models after each request
3. **Poor UX**: Users wait for model loading on every request

### Solution: Long-Lived Sessions

Sessions are **persistent containers** that keep models loaded in GPU memory across multiple requests.

```
Traditional (One-off):
Request → Load Model (30s) → Inference (2s) → Cleanup → Response
Next Request → Load Model (30s) → Inference (2s) → Cleanup → Response
Total: 64 seconds for 2 requests

Session-Based:
First Request → Load Model (30s) → Inference (2s) → Keep Alive
Next Request → Inference (2s) [Model already loaded!]
Total: 34 seconds for 2 requests (47% faster)
```

### Task Types

**1. Session Tasks**
- Container stays alive after completion
- Model loaded once, reused across requests
- Subject to idle timeout (default: 5 minutes)
- Subject to max lifetime (default: 1 hour)

**2. One-off Tasks**
- Container auto-removed after completion
- No model persistence
- Use for batch processing, training jobs, one-time operations

### Session Lifecycle States

```
INITIALIZING → WAITING → WORKING → WAITING → ... → KILLED
     ↓            ↑         ↓          ↑              ↑
  Starting     Idle      Active     Idle         Timeout
               Ready    Processing  Ready        or Error
```

**INITIALIZING**: Container starting, model loading
**WAITING**: Idle, model loaded, ready for requests
**WORKING**: Processing a request
**KILLED**: Terminated (timeout, error, or explicit kill)

---

## Component Architecture

### Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Client (Web Server)                    │
└────────────────────┬────────────────────────────────────┘
                     │ POST /api/tasks/predefined (SSE)
                     ↓
┌─────────────────────────────────────────────────────────┐
│                   API Layer (FastAPI)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ tasks.py    │  │ sessions.py  │  │ health.py      │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘ │
└─────────┼─────────────────┼──────────────────┼─────────┘
          │                 │                  │
          ↓                 ↓                  ↓
┌─────────────────────────────────────────────────────────┐
│            Singleton Managers (app/core/manager/)        │
│            One instance per service                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │          Task Manager (Central Coordinator)     │    │
│  │  • Holds references to all other managers      │    │
│  │  • Tracks running tasks (task_id → Instance)   │    │
│  │  • Enables monitoring and forced shutdown      │    │
│  └────────────────┬───────────────────────────────┘    │
│                   │                                      │
│  ┌────────────────┼───────────────────────────────┐    │
│  │  GPU Manager   │                                │    │
│  │  • Allocate GPU by difficulty (low/high)       │    │
│  │  • Track availability (is_available flag)      │    │
│  │  • Monitor metrics (memory, temp, utilization) │    │
│  └────────────────┼───────────────────────────────┘    │
│                   │                                      │
│  ┌────────────────┼───────────────────────────────┐    │
│  │ Session Mgr    │                                │    │
│  │  • Track sessions (id → Session mapping)       │    │
│  │  • Match IDLE sessions to new requests         │    │
│  │  • Monitor timeouts (idle + max lifetime)      │    │
│  └────────────────┼───────────────────────────────┘    │
│                   │                                      │
│  ┌────────────────┼───────────────────────────────┐    │
│  │ Docker Mgr     │                                │    │
│  │  • Create containers (session/one-off)         │    │
│  │  • Stream logs via thread pool (non-blocking)  │    │
│  │  • Execute commands via docker exec            │    │
│  └────────────────┼───────────────────────────────┘    │
│                   │                                      │
│  ┌────────────────┼───────────────────────────────┐    │
│  │ Model Download │                                │    │
│  │  • Check local cache (/data/models/{id})       │    │
│  │  • Fetch from file-service if missing          │    │
│  │  • Return host path for volume mount           │    │
│  └────────────────┼───────────────────────────────┘    │
└───────────────────┼─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│       Per-Request Instances (app/core/instance/)         │
│       One instance per task request                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │       Task Request Handler (Pipeline)           │    │
│  │  1. Config Load  → ConfigLoader                │    │
│  │  2. Model Prepare → ModelDownloader             │    │
│  │  3. GPU Allocate → GPUManager                   │    │
│  │  4. Docker Create → DockerManager               │    │
│  │  5. Instance Create → InstanceManager           │    │
│  │  6. Task Register → TaskManager                 │    │
│  │  7. Stream Execution                            │    │
│  └────────────────┬───────────────────────────────┘    │
│                   │                                      │
│  ┌────────────────┼───────────────────────────────┐    │
│  │ Config Loader  │                                │    │
│  │  • Load 3 YAML files (definitions/actions/paths)│   │
│  │  • Merge task definition + action + model path │    │
│  │  • Apply request overrides                     │    │
│  └────────────────┼───────────────────────────────┘    │
│                   │                                      │
│  ┌────────────────┼───────────────────────────────┐    │
│  │  Instance Mgr  │                                │    │
│  │  • Stream docker logs (via thread pool)        │    │
│  │  • Parse stdout/stderr into events             │    │
│  │  • Emit SSE events (CONNECTION, WORKER, etc.)  │    │
│  │  • Enforce task timeout                        │    │
│  └────────────────┬───────────────────────────────┘    │
└───────────────────┼─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│          Worker Container (Docker)                       │
│  • Runs as sibling container (DOOD pattern)             │
│  • Has GPU access via --gpus device=N                   │
│  • Model mounted at /models (volume mount)              │
│  • Receives MODEL_PATH=/models env var                  │
│  • Outputs JSON events to stdout (parsed by Instance)   │
└─────────────────────────────────────────────────────────┘
```

### Data Flow: Task Submission (Pre-defined Tasks)

The service uses a 7-step pipeline orchestrated by `TaskRequestHandler` for pre-defined tasks:

```
1. Client → API: POST /api/tasks/predefined
   {task_name: "loading-test", task_difficulty: "low", metadata: {...}}

2. API → TaskRequestHandler: Create per-request instance

3. Pipeline Execution:

   Step 1: Config Load
   ├─ ConfigLoader.load_task_config(task_name)
   ├─ Reads task_definitions.yaml → TaskDefinition
   ├─ Reads task_actions.yaml → TaskAction (docker_image, command)
   ├─ Reads model_paths.yaml → ModelPath (if applicable)
   └─ Apply request overrides (difficulty, timeout, metadata)

   Step 2: Model Prepare
   ├─ ModelDownloader.prepare_model(model_id)
   ├─ Check: /data/models/{model_id}/ exists?
   ├─ If missing & AUTO_FETCH_MODELS=true: Download from file-service
   └─ Return: host_path or None

   Step 3: GPU Allocate
   ├─ TaskManager.gpu_manager.allocate_gpu(difficulty)
   ├─ Filter GPUs by difficulty (low/high)
   ├─ Find first available GPU in filtered list
   └─ Return: gpu_id or raise ServiceFullError (503)

   Step 4: Emit CONNECTION Event
   └─ SSE: {"event": "connection", "status": "allocated", "gpu_id": X}

   Step 5: Docker Create
   ├─ TaskManager.docker_manager.create_oneoff_container()
   ├─ Mount: -v /host/models:/models:ro
   ├─ GPU: --gpus device={gpu_id}
   ├─ Auto-remove: --rm (cleanup after exit)
   └─ Return: container_id

   Step 6: Instance Create
   ├─ Create InstanceManager(task_id, container_id, timeout)
   └─ TaskManager.register_task(task_id, instance)

   Step 7: Stream Execution
   ├─ InstanceManager.stream_task_execution()
   ├─ Thread-pooled log streaming (loop.run_in_executor)
   ├─ Parse logs → SSE events (WORKER, TEXT_DELTA, LOGS, TASK_FINISH)
   └─ Yield events to client

4. Cleanup:
   ├─ TaskManager.unregister_task(task_id)
   ├─ GPUManager.release_gpu(gpu_id)
   └─ Container auto-removed (--rm flag)
```

### Data Flow: Session-based Tasks (Legacy/TODO)

```
1. Client → API: POST /api/tasks/submit
   {task_type: "session", model_id: "llama-7b", task_preset: "inference"}

2. API → Session Manager: Find or create session
   ├─ Check for IDLE session with same model_id
   │  └─ If found: Reuse (skip container creation)
   └─ If not found: Create new session

3. Session Manager → GPU Manager: Allocate GPU by difficulty
   ← Returns: gpu_device_id or None (503 if full)

4. Session Manager → Model Downloader: Get model path
   ├─ Check local: /data/models/{model_id}
   └─ If missing: Fetch from file-service

5. Session Manager → Docker Manager: Create session container
   {gpu_id, docker_image, command, env_vars, model_path}
   ← Returns: container_id (long-lived, NOT auto-removed)

6. Session Manager → Instance Manager: Stream logs
   ← SSE events: CONNECTION, WORKER, TEXT_DELTA, TEXT, TASK_FINISH

7. Container stays alive in WAITING state for subsequent requests
```

---

## Request Flow & Decision Trees

### Task Submission Decision Tree

```
POST /tasks/submit
│
├─ Has session_id in request?
│  │
│  ├─ YES: Reuse existing session
│  │  │
│  │  ├─ Session exists?
│  │  │  │
│  │  │  ├─ YES: Check status
│  │  │  │  │
│  │  │  │  ├─ WAITING: Add to FIFO queue
│  │  │  │  │  │
│  │  │  │  │  ├─ Queue full? → 503 (queue_full)
│  │  │  │  │  └─ Queue ok → Process
│  │  │  │  │
│  │  │  │  ├─ WORKING: Add to FIFO queue (same as above)
│  │  │  │  └─ KILLED/INITIALIZING → 404 (invalid state)
│  │  │  │
│  │  │  └─ NO: Session not found → 404
│  │  │
│  │  └─ NO session_id provided: Check create_session flag
│     │
│     ├─ create_session=true: Create new session flow
│     │  │
│     │  ├─ Check for IDLE session with same model_id (BONUS)
│     │  │  │
│     │  │  ├─ Found IDLE session → Reuse (goto YES path)
│     │  │  └─ No IDLE session → Allocate new GPU
│     │  │
│     │  ├─ GPU available for difficulty level?
│     │  │  │
│     │  │  ├─ YES: Allocate GPU
│     │  │  │  └─ Fetch model → Create container → Stream
│     │  │  │
│     │  │  └─ NO: All GPUs busy → 503 (full)
│     │  │
│     │  └─ [Continue with session creation...]
│     │
│     └─ create_session=false & task_type=oneoff
│        │
│        ├─ GPU available?
│        │  │
│        │  ├─ YES: Create one-off container
│        │  └─ NO: 503 (full)
│        │
│        └─ [Execute and auto-cleanup]
```

### Session Matching Algorithm (Model Reuse Bonus)

```python
def find_or_create_session(model_id, task_difficulty):
    """
    Optimization: Check for IDLE sessions before allocating new GPU.
    """
    # Step 1: Look for IDLE session with matching model
    for session in sessions.values():
        if (session.status == WAITING and
            session.model_id == model_id):
            # Found match! Reuse session
            return session

    # Step 2: No match found, allocate new GPU
    gpu_id = gpu_manager.allocate_gpu(task_difficulty)
    if gpu_id is None:
        raise ServiceFullError()  # 503

    # Step 3: Create new session
    return create_new_session(gpu_id, model_id)
```

### GPU Allocation Strategy

```
Request arrives with task_difficulty: "low" | "high"
│
├─ GPU_DEVICE_DIFFICULTY config:
│  {0: "low", 1: "high"}
│
├─ Filter GPUs by difficulty:
│  difficulty="low"  → [GPU 0]
│  difficulty="high" → [GPU 1]
│
├─ Find available GPU in filtered list:
│  │
│  ├─ Check GPU 0: is_available=True → Allocate GPU 0
│  ├─ Check GPU 0: is_available=False → Check next
│  └─ No available GPUs → Return None (caller returns 503)
│
└─ Mark GPU as allocated, assign to session
```

---

## State Machines

### Session State Machine

```
                    ┌──────────────┐
                    │              │
              ┌─────┤ INITIALIZING │
              │     │              │
              │     └──────┬───────┘
              │            │
              │    Container started,
              │    model loaded
              │            │
              │            ↓
              │     ┌──────────────┐
Idle timeout  │     │              │
Max lifetime  ├─────┤   WAITING    │◄─────┐
Error occurs  │     │              │      │
Manual kill   │     └──────┬───────┘      │
              │            │              │
              │   Request arrives     Request
              │            │           completed
              │            ↓              │
              │     ┌──────────────┐      │
              │     │              │      │
              └────►│   WORKING    ├──────┘
                    │              │
                    └──────┬───────┘
                           │
                  Timeout or error
                           │
                           ↓
                    ┌──────────────┐
                    │              │
                    │   KILLED     │ (Terminal state)
                    │              │
                    └──────────────┘

State Transitions:
- INITIALIZING → WAITING: Container ready, model loaded
- WAITING → WORKING: Request dequeued from FIFO
- WORKING → WAITING: Request completed successfully
- WORKING → KILLED: Task timeout or error
- WAITING → KILLED: Idle timeout or max lifetime exceeded
- ANY → KILLED: Manual kill or system error
```

### Worker Status State Machine

```
┌──────────────┐
│              │
│ INITIALIZING │  (Container starting, loading model)
│              │
└──────┬───────┘
       │
       ↓
┌──────────────┐     Request      ┌──────────────┐
│              │ ─────arrives────► │              │
│   WAITING    │                   │   WORKING    │
│              │ ◄────completed─── │              │
└──────┬───────┘                   └──────┬───────┘
       │                                  │
       │                                  │
       │         Timeout/Error/Kill       │
       └──────────────┬───────────────────┘
                      │
                      ↓
               ┌──────────────┐
               │              │
               │   KILLED     │
               │              │
               └──────────────┘
```

### Request Processing Flow (Per Session)

```
Request arrives
       │
       ↓
┌────────────────┐
│ Add to Session │
│  FIFO Queue    │
└───────┬────────┘
        │
        ├─ Queue full? → Reject (503)
        └─ Queue ok → Enqueue
              │
              ↓
┌────────────────┐
│ Session Worker │
│ Event Loop     │
└───────┬────────┘
        │
        ↓
Wait for queue.get()
        │
        ↓
┌────────────────┐
│ Process Request│
│ (Sequential)   │
└───────┬────────┘
        │
        ├─ Update session status: WORKING
        ├─ Send command to container
        ├─ Stream logs → Parse events
        ├─ Emit SSE events to client
        └─ Mark completed
              │
              ↓
Update session status: WAITING
Update last_activity timestamp
        │
        ↓
Loop back to wait for next request
```

---

## Event Streaming Protocol

### Event Types

The service emits structured events via Server-Sent Events (SSE) to provide real-time progress updates.

**1. CONNECTION**
- **When**: Immediately after task submission is processed
- **Purpose**: Inform client of GPU allocation status
- **Data**:
  ```json
  {
    "status": "allocated" | "session_found" | "full" | "session_not_found" | "queue_full",
    "gpu_id": 0,
    "session_id": "uuid",
    "message": "Human-readable description"
  }
  ```

**2. WORKER**
- **When**: Container created or encounters error
- **Purpose**: Confirm worker container is running
- **Data**:
  ```json
  {
    "status": "created" | "error",
    "container_id": "docker-container-id",
    "error": "Error message if status=error"
  }
  ```

**3. TEXT_DELTA**
- **When**: Worker outputs incremental text (streaming responses)
- **Purpose**: Real-time token-by-token output for LLM responses
- **Data**:
  ```json
  {
    "delta": "word or token"
  }
  ```

**4. TEXT**
- **When**: Worker outputs final complete text
- **Purpose**: Full response when not streaming
- **Data**:
  ```json
  {
    "content": "Complete response text"
  }
  ```

**5. LOGS**
- **When**: Worker outputs debug/info logs
- **Purpose**: Debugging, progress updates, warnings
- **Data**:
  ```json
  {
    "log": "Log message",
    "level": "info" | "debug" | "warning",
    "timestamp": "ISO 8601"
  }
  ```

**6. TASK_FINISH**
- **When**: Task completes (success or failure)
- **Purpose**: Signal end of task, close SSE stream
- **Data**:
  ```json
  {
    "status": "completed" | "failed" | "timeout",
    "elapsed_seconds": 12,
    "error": "Error message if failed"
  }
  ```

### Log Parsing Strategy

Worker containers output to stdout/stderr. The Instance Manager parses these logs to generate events.

**Parsing Rules:**
```python
# Worker outputs structured JSON to stdout
# Each line is a JSON object with 'type' field

{
  "type": "text_delta",
  "data": {"delta": "Hello"}
}

{
  "type": "log",
  "data": {"log": "Loading model...", "level": "info"}
}

{
  "type": "task_finish",
  "data": {"status": "completed", "elapsed": 5.2}
}

# Instance Manager:
# 1. Read line from docker logs
# 2. Try parse as JSON
# 3. If successful: Extract type and data, emit as SSE event
# 4. If failed: Treat as plain log, emit as LOGS event
```

**Fallback for Non-Structured Output:**
- If worker doesn't output JSON: Treat all stdout as TEXT, stderr as LOGS
- Heuristics: Look for "ERROR:", "WARNING:", "INFO:" prefixes

---

## Model Management System

### Three-Layer Architecture

The model management system uses a three-file configuration approach with separate concerns:

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: YAML Configuration (Three Files)           │
│                                                      │
│ task_definitions.yaml - Task metadata:              │
│   loading-test:                                     │
│     description: "Test worker"                      │
│     task_type: "oneoff"                             │
│     task_difficulty: "low"                          │
│     timeout_seconds: 60                             │
│     model_id: "test-loading"                        │
│                                                      │
│ task_actions.yaml - Docker execution config:        │
│   test-loading:                                     │
│     docker_image: "loading-worker:latest"           │
│     command: ["python", "/app/worker.py"]           │
│     env_vars:                                       │
│       MODEL_NAME: test-loading                      │
│                                                      │
│ model_paths.yaml - Model file locations:            │
│   llama-7b:                                         │
│     path: /data/models/llama-7b                     │
│     description: "LLaMA 7B model weights"           │
│     size_gb: 13.5                                   │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│ Layer 2: Config Loader (Per-Request Instance)       │
│                                                      │
│ Responsibilities:                                   │
│ • Load all three YAML files on demand              │
│ • Merge task definition + action + model path      │
│ • Return complete config tuple                     │
│                                                      │
│ ConfigLoader.load_task_config(task_name):          │
│   1. Read task_definitions.yaml[task_name]         │
│   2. Read task_actions.yaml[model_id]              │
│   3. Read model_paths.yaml[model_id] (optional)    │
│   4. Return (TaskDef, TaskAction, ModelPath)       │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│ Layer 3: Model Downloader (Singleton Manager)       │
│                                                      │
│ Responsibilities:                                   │
│ • Check if model exists: /data/models/{model_id}/   │
│ • If missing: Fetch from file-service               │
│ • Save to host filesystem                           │
│ • Return host path for volume mount                 │
│                                                      │
│ Cache Structure:                                    │
│   /data/models/                                     │
│     ├── llama-7b/                                   │
│     │   ├── model.bin                               │
│     │   ├── config.json                             │
│     │   └── tokenizer.json                          │
│     └── stable-diffusion-xl/                        │
│         ├── model.safetensors                       │
│         └── ...                                     │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│ Layer 4: Docker Volume Mount                        │
│                                                      │
│ docker run \                                        │
│   -v /data/models/llama-7b:/models \                │
│   -e MODEL_PATH=/models \                           │
│   llm-runner:latest                                 │
│                                                      │
│ Worker container:                                   │
│ • Reads MODEL_PATH env var                          │
│ • Loads model from /models directory                │
│ • Model data already on host (fast!)                │
└─────────────────────────────────────────────────────┘
```

### Model Fetch Flow

```
1. Client requests: task_name="loading-test"

2. Config Loader (per-request): load_task_config("loading-test")
   ├─ Read task_definitions.yaml["loading-test"] → model_id="test-loading"
   ├─ Read task_actions.yaml["test-loading"] → docker_image, command
   ├─ Read model_paths.yaml["test-loading"] (optional)
   └─ Return complete config tuple

3. Model Downloader (singleton): prepare_model("test-loading")
   │
   ├─ Check: /data/models/test-loading/ exists?
   │  │
   │  ├─ YES: Return "/data/models/test-loading"
   │  │
   │  └─ NO: Fetch from file-service (if AUTO_FETCH_MODELS=true)
   │     │
   │     ├─ Prevent concurrent fetches (asyncio.Lock)
   │     ├─ Request: POST file-service/api/models/download
   │     ├─ Download to: /data/models/test-loading/
   │     ├─ Register in cache: cache_registry["test-loading"] = path
   │     └─ Return: "/data/models/test-loading"

4. Docker Manager: Create one-off container
   -v /data/models/test-loading:/models:ro
   -e MODEL_PATH=/models
   --rm (auto-remove after exit)

5. Worker Container:
   model_path = os.environ["MODEL_PATH"]  # "/models"
   load_model(model_path)
```

### Three-File Config System Benefits

**Separation of Concerns:**
- `task_definitions.yaml` - What tasks exist and their defaults
- `task_actions.yaml` - How to execute tasks (Docker config)
- `model_paths.yaml` - Where model files are located

**Flexibility:**
- Multiple tasks can share the same Docker image
- Model paths can be updated without touching task definitions
- Easy to add new tasks without complex nested YAML

**Maintainability:**
- Clear boundaries between metadata, execution, and storage
- Easier to validate each config file independently
- Better organization for large numbers of tasks

---

## Timeout & Lifecycle Management

### Dual Timeout System

**Idle Timeout** (Default: 5 minutes)
- **Purpose**: Free GPU when session inactive
- **Trigger**: No requests processed for X seconds
- **Tracked by**: `session.last_activity` timestamp
- **Check**: Background task every 30 seconds
- **Action**: Kill session, release GPU

**Max Lifetime** (Default: 1 hour)
- **Purpose**: Prevent infinite sessions
- **Trigger**: Session existed for X seconds since creation
- **Tracked by**: `session.created_at` timestamp
- **Check**: Background task every 30 seconds
- **Action**: Kill session, release GPU

### Timeout Monitoring Loop

```python
async def monitor_timeouts():
    """Background task that checks timeouts every 30 seconds."""
    while True:
        await asyncio.sleep(settings.SESSION_MONITOR_INTERVAL)

        now = datetime.utcnow()
        sessions_to_kill = []

        for session_id, session in sessions.items():
            # Check max lifetime
            age = (now - session.created_at).total_seconds()
            if age > session.max_lifetime_seconds:
                sessions_to_kill.append((session_id, "max_lifetime"))
                continue

            # Check idle timeout (only for WAITING status)
            if session.status == SessionStatus.WAITING:
                idle_time = (now - session.last_activity).total_seconds()
                if idle_time > session.idle_timeout_seconds:
                    sessions_to_kill.append((session_id, "idle_timeout"))

        # Kill sessions outside the iteration loop
        for session_id, reason in sessions_to_kill:
            await kill_session(session_id, reason=reason)
```

### Activity Tracking

**When to update `last_activity`:**
- Request added to session queue
- Request starts processing
- Request completes successfully
- Keepalive endpoint called

**When NOT to update `last_activity`:**
- Timeout check occurs
- Status query
- Session list endpoint called

---

## Error Handling & Failure Modes

### Error Categories

**1. Client Errors (4xx)**
- Invalid model_id or task_preset → 400 Bad Request
- Session not found → 404 Not Found
- Authentication failed → 401 Unauthorized

**2. Capacity Errors (503)**
- All GPUs allocated → 503 Service Unavailable (status: "full")
- Session queue full → 503 Service Unavailable (status: "queue_full")
- **Always include**: `Retry-After` header

**3. Server Errors (5xx)**
- Container creation failed → 500 Internal Server Error
- Model fetch failed → 500 Internal Server Error
- GPU allocation error → 500 Internal Server Error

### Failure Recovery Strategies

**Container Creation Failure:**
```
1. Attempt to create container
2. If fails:
   ├─ Release allocated GPU immediately
   ├─ Remove session from tracking
   ├─ Send WORKER event with status: "error"
   ├─ Send TASK_FINISH event with status: "failed"
   └─ Log error with full context
```

**Model Fetch Failure:**
```
1. Attempt to fetch model from file-service
2. If fails:
   ├─ Do NOT create container
   ├─ Release allocated GPU
   ├─ Send CONNECTION event with error details
   └─ Return 500 with actionable error message
```

**Container Crash During Execution:**
```
1. Instance Manager detects container stopped unexpectedly
2. Actions:
   ├─ Send TASK_FINISH event with status: "failed"
   ├─ Mark session as KILLED
   ├─ Release GPU
   ├─ Capture container logs for debugging
   └─ Clean up container resources
```

**GPU Allocation Race Condition:**
```
Problem: Two requests try to allocate same GPU simultaneously

Solution: Use asyncio.Lock in GPU Manager
async with self._lock:
    # Check availability and allocate atomically
    # Only one coroutine can enter this section at a time
```

### Partial Failure Handling

**Scenario: Container created but model loading fails inside container**

```
1. Container starts successfully (WORKER event sent)
2. Worker attempts to load model
3. Worker outputs error to stderr
4. Instance Manager captures error from logs
5. Instance Manager sends LOGS event with error
6. Instance Manager sends TASK_FINISH with status: "failed"
7. Session remains INITIALIZING (not WAITING)
8. Timeout monitor will kill session after timeout
```

---

## Security Boundaries

### Trust Boundaries

```
┌────────────────────────────────────────────────┐
│           Untrusted Zone (Client)               │
│  • Web server                                   │
│  • User input                                   │
└─────────────────┬──────────────────────────────┘
                  │
            API Key Check
            (X-API-Key)
                  │
                  ↓
┌─────────────────────────────────────────────────┐
│          Trusted Zone (GPU Service)              │
│                                                  │
│  Validation Layer:                               │
│  ├─ model_id exists in presets?                 │
│  ├─ task_preset exists for model?               │
│  ├─ metadata schema valid?                      │
│  └─ timeout within limits?                      │
│                                                  │
│  Server-Controlled:                              │
│  ├─ docker_image (from YAML config)             │
│  ├─ command (from YAML config)                  │
│  ├─ env_vars (from YAML config)                 │
│  └─ volume_mounts (from model cache)            │
└──────────────────────────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────┐
│        Container Isolation (Docker)              │
│  • GPU access limited to assigned device        │
│  • Memory limits enforced                       │
│  • CPU quota enforced                           │
│  • Network isolated (optional)                  │
│  • Volume mounts read-only where possible       │
└──────────────────────────────────────────────────┘
```

### Security Rules

**1. Client Cannot Specify:**
- ❌ Docker image
- ❌ Container command
- ❌ Environment variables (server-side)
- ❌ Volume mounts
- ❌ GPU device ID
- ❌ Network configuration

**2. Client Can Specify:**
- ✅ model_id (validated against allowlist)
- ✅ task_preset (validated against allowlist)
- ✅ metadata (passed to container, not executed)
- ✅ timeout (capped at MAX_TASK_TIMEOUT)
- ✅ task_difficulty (validated: "low" | "high")

**3. Docker Socket Security (DOOD)**
- **Risk**: Docker socket gives root-equivalent access
- **Mitigations**:
  - Dedicated GPU VM (not shared infrastructure)
  - Firewall rules (no external access)
  - Image allowlist (only approved images)
  - No network mode: host
  - Read-only root filesystem where possible

**4. Model Cache Security**
- Models fetched from internal file-service (not public internet)
- Internal API key required (X-Internal-Key header)
- Models cached locally (prevent tampering via checksums - future)
- Volume mounts: Read-only for inference, read-write only when needed

**5. API Authentication**
- X-API-Key header required for all endpoints
- Key validated against INTERNAL_API_KEY config
- Failed auth: 401 response, no information leakage
- Rate limiting (future: implement per-key limits)

---

## Performance Optimization

### Async I/O and Thread-Pooled Log Streaming

**Problem:**
Docker-py's `container.logs()` is a synchronous, blocking operation. When streaming logs from a container, this blocks the asyncio event loop, making the service unresponsive to other requests (e.g., health checks).

**Solution:**
Use `asyncio.loop.run_in_executor()` to run blocking I/O operations in a thread pool:

```python
# docker_manager.py, lines 282-333
async def stream_logs(container_id: str, follow: bool = True) -> AsyncIterator[str]:
    """Stream logs from container without blocking the event loop."""

    container = self._client.containers.get(container_id)
    log_generator = container.logs(stream=True, follow=follow)

    # Get event loop
    loop = asyncio.get_event_loop()

    def read_next_log():
        """Blocking call to get next log line - runs in thread pool."""
        try:
            return next(log_generator)
        except StopIteration:
            return None

    while True:
        # Run blocking operation in thread pool (non-blocking to event loop)
        log_bytes = await loop.run_in_executor(None, read_next_log)

        if log_bytes is None:
            break

        line = log_bytes.decode('utf-8').rstrip()
        yield line
```

**Benefits:**
- Health checks respond quickly even during active log streaming
- Multiple tasks can stream logs concurrently without blocking each other
- Event loop remains responsive to new incoming requests
- No need to use multiprocessing or additional workers

**Implementation Location:**
- `app/core/manager/docker_manager.py:282-333` - Thread-pooled log streaming
- `app/core/instance/instance_manager.py` - Uses docker_manager.stream_logs()

### Concurrency Settings

The service runs as a single Uvicorn worker with high concurrency limits:

```bash
uvicorn app.main:app \
  --workers 1 \
  --limit-concurrency 1000 \
  --backlog 2048
```

**Why Single Worker?**
- GPU Manager, Task Manager, and Session Manager maintain in-memory state
- Multiple workers would require Redis for shared state (future enhancement)
- Single worker + large thread pool handles concurrent requests efficiently

**Concurrency Limits:**
- `--limit-concurrency 1000`: Supports 1000 concurrent connections
- `--backlog 2048`: Queue size for burst traffic
- Thread pool automatically scales for blocking I/O operations

**Trade-offs:**
- ✅ **Pro**: Simple in-memory state management
- ✅ **Pro**: No Redis dependency
- ✅ **Pro**: Fast state access (no network calls)
- ❌ **Con**: State lost on service restart (sessions killed)
- ❌ **Con**: Cannot scale horizontally without shared state

---

## Design Rationale

### Why Session-Based?

**Problem**: Traditional stateless APIs reload models on every request (30-60s overhead)

**Solution**: Keep containers alive between requests

**Trade-offs**:
- ✅ **Pro**: 10-20x faster subsequent requests
- ✅ **Pro**: Better resource utilization
- ✅ **Pro**: Improved user experience
- ❌ **Con**: More complex lifecycle management
- ❌ **Con**: Memory held even when idle (mitigated by idle timeout)

### Why No Job Queue?

**Alternative Approach**: Queue requests when at capacity

**Our Choice**: Reject immediately with 503

**Rationale**:
- **Simpler logic**: No queue management, priority handling, or queue timeout logic
- **Clear feedback**: Client knows immediately if service is busy
- **No false hope**: Don't accept requests we can't process promptly
- **Exception**: Existing sessions can queue 3-5 requests (bounded, low risk)

### Why Server-Managed Configuration?

**Alternative**: Let clients specify docker_image, command, etc.

**Our Choice**: Server controls execution parameters

**Rationale**:
- **Security**: Client can't run arbitrary containers
- **Consistency**: Same model_id always uses same image/command
- **Maintenance**: Update models without client changes
- **Validation**: Easy to check if combination is valid

### Why YAML for Config?

**Alternatives**: Python dict, JSON, database

**Our Choice**: YAML file

**Rationale**:
- **Human-readable**: Easy to edit, review in pull requests
- **Comments supported**: Document choices inline
- **Version controlled**: Track changes in git
- **No database dependency**: Simple deployment
- **Type-safe loading**: Pydantic validates structure

### Why Split Core into Manager vs Instance?

**Alternative**: Keep all components in flat `app/core/` directory

**Our Choice**: Two subdirectories - `manager/` (singletons) and `instance/` (per-request)

**Rationale**:
- **Clear lifecycle separation**: Singleton vs per-request is explicit in directory structure
- **Prevents shared state bugs**: Impossible to accidentally share per-request state across tasks
- **Easier to understand**: New developers immediately see which components are global vs task-specific
- **Better testing**: Singleton managers mocked once, instances created fresh per test
- **Explicit dependencies**: Per-request instances receive manager references, making data flow clear

**Component Distribution:**

**Singletons** (`app/core/manager/`):
- `gpu_manager.py` - One GPU allocation pool for entire service
- `session_manager.py` - One session registry for all sessions
- `docker_manager.py` - One Docker client for all containers
- `task_manager.py` - One task tracker for all running tasks
- `model_downloader.py` - One model cache manager

**Per-Request** (`app/core/instance/`):
- `config_loader.py` - Loads config for each task independently
- `instance_manager.py` - Tracks one container's logs and events
- `task_request_handler.py` - Orchestrates pipeline for one task request

### Why Three Config Files Instead of One?

**Alternative**: Single `model_presets.yaml` with nested structure

**Our Choice**: Three separate files (`task_definitions.yaml`, `task_actions.yaml`, `model_paths.yaml`)

**Rationale**:
- **Separation of concerns**: Task metadata vs Docker config vs file paths are distinct responsibilities
- **Reusability**: Multiple tasks can reference the same Docker image without duplication
- **Flexibility**: Update model file paths without touching task definitions
- **Validation**: Each file has clear schema, easier to validate independently
- **Maintainability**: Smaller files, clearer purpose, less cognitive load
- **Extensibility**: Easy to add fourth config file (e.g., resource_limits.yaml) without complex nesting

---

## Future Enhancements

**Phase 2:**
- Redis for session persistence (survive restarts)
- PostgreSQL for job history
- Metrics and monitoring (Prometheus)
- Advanced scheduling (priority queues, preemption)
- Multi-GPU support per task
- Health checks for containers
- Graceful shutdown and draining

**Phase 3:**
- Auto-scaling (spin up additional GPU VMs)
- Spot instance support
- Cost optimization (cheaper GPUs for low-priority tasks)
- Model quantization support
- Distributed tracing

---

*This design document is a living document and will be updated as the system evolves.*
