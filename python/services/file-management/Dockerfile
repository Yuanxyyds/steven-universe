FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy shared-schemas package first (dependency)
COPY shared-schemas/ /tmp/shared-schemas/

# Install shared-schemas
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/shared-schemas

# Copy requirements and install other dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
