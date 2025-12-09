FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.3

# Copy shared_schemas (copied into worker dir by build.sh)
COPY shared_schemas /app/shared_schemas

# Copy worker script
COPY worker.py /app/worker.py

# Make executable
RUN chmod +x /app/worker.py

# Expose port
EXPOSE 8000

# Run worker
CMD ["python", "/app/worker.py"]
