"""
S3 Upload Configuration.
Constants for multipart upload and streaming settings.
"""

from app.core.config import settings

# Multipart Upload Settings
MULTIPART_THRESHOLD = 5 * 1024 * 1024   # 5MB (S3/MinIO minimum for multipart)
MULTIPART_CHUNKSIZE = 10 * 1024 * 1024  # 10MB per part
MAX_CONCURRENCY = 1                      # Serial uploads (predictable memory usage)

# Streaming Settings
READ_CHUNK_SIZE = 256 * 1024             # 256KB read buffer

# Maximum buffered chunks (controls backpressure and memory usage)
# Configurable via MAX_BUFFERED_CHUNKS environment variable
# Default: 10 chunks × 256KB = 2.5MB (suitable for 100-500 Mbps networks)
# High-speed: 50 chunks × 256KB = 12.5MB (suitable for 1Gbps+ networks)
MAX_BUFFERED_CHUNKS = settings.MAX_BUFFERED_CHUNKS

# Upload Limits
MAX_FILE_SIZE = 50 * 1024 * 1024 * 1024  # 50GB maximum file size
