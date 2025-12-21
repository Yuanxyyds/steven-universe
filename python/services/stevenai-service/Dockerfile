FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy shared-schemas package (synced by deploy script)
COPY shared-schemas /tmp/shared-schemas

# Install shared-schemas
RUN pip install --no-cache-dir /tmp/shared-schemas && rm -rf /tmp/shared-schemas

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY scripts ./scripts

# Copy RAG document (from root of stevenai-service)
COPY rag_document.json ./app/data/rag_document.json

# Generate RAG QA pairs at build time
RUN python scripts/generate_rag_qa.py

# Create directory for FAISS indexes (will be populated at runtime)
RUN mkdir -p app/data/faiss_indexes

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
