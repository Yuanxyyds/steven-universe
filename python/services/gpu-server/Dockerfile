# Use NVIDIA CUDA base image for GPU support (CUDA 13.0)
FROM nvidia/cuda:13.0.0-runtime-ubuntu24.04

# Install Python 3.12 and system dependencies (Ubuntu 24.04 default)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for Docker-outside-of-Docker pattern)
RUN curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm get-docker.sh

# Set Python 3 as default python command
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# Set working directory
WORKDIR /app

# Copy shared-schemas package first (dependency)
COPY libs/shared-schemas/ /tmp/shared-schemas/

# Install shared-schemas
# Note: --break-system-packages is safe in Docker containers (isolated environment)
RUN pip3 install --no-cache-dir --break-system-packages /tmp/shared-schemas

# Copy requirements and install dependencies
COPY services/gpu-server/requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code
COPY services/gpu-server/app/ ./app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
# NOTE: Using single worker because gpu_manager/task_manager state is in-memory
# To use multiple workers, need to implement Redis-based shared state
# Single worker + large thread pool handles concurrent requests efficiently
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "1000", "--backlog", "2048"]
