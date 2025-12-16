# Use vLLM official image as base
FROM vllm/vllm-openai:latest

# Install additional dependencies for worker wrapper
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    httpx==0.26.0

# Create app directory
WORKDIR /app

# Create log directory
RUN mkdir -p /var/log && chmod 777 /var/log

# Copy shared_schemas (will be copied by build.sh)
COPY shared_schemas /app/shared_schemas

# Copy worker files
COPY worker.py /app/worker.py
COPY entrypoint.sh /app/entrypoint.sh

# Make scripts executable
RUN chmod +x /app/worker.py /app/entrypoint.sh

# Expose ports
# 8000: Worker wrapper (GPU service interface)
# 8001: vLLM OpenAI API
EXPOSE 8000 8001

# Set environment defaults
ENV SERVER_PORT=8000
ENV VLLM_PORT=8001
ENV MODEL_ID=Qwen3-4B-Instruct
ENV DTYPE=auto
ENV GPU_MEMORY_UTILIZATION=0.90
ENV MAX_MODEL_LEN=4096

# Clear base image's ENTRYPOINT (vllm image has its own entrypoint that we need to override)
ENTRYPOINT []

# Use shell script as command
CMD ["/app/entrypoint.sh"]
