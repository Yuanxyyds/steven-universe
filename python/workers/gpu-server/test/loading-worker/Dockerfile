# Test Worker - GPU Loading Simulator
FROM python:3.11-slim

WORKDIR /app

# Copy worker script
COPY worker.py /app/worker.py

# Make script executable
RUN chmod +x /app/worker.py

# Run worker
CMD ["python", "/app/worker.py"]
