"""
File Management Service API schemas.
Type-safe contracts for all file service endpoints.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class BucketType(str, Enum):
    """Bucket access type."""
    INTERNAL = "internal"
    SIGNED = "signed"
    PUBLIC = "public"
    UNKNOWN = "unknown"


class TokenType(str, Enum):
    """Authentication token type."""
    INTERNAL = "internal"
    FRONTEND = "frontend"
    INVALID = "invalid"


class UrlType(str, Enum):
    """Type of URL returned."""
    DIRECT_MINIO = "direct_minio"
    PUBLIC_PROXY = "public_proxy"


# ============================================================================
# Common Models
# ============================================================================

class FileLocation(BaseModel):
    """File location information."""
    bucket: str
    key: str
    url: str


class FileMetadata(BaseModel):
    """File metadata."""
    key: str
    url: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    last_modified: Optional[str] = None


# ============================================================================
# Upload Endpoints
# ============================================================================

class UploadResponse(BaseModel):
    """Response from file upload."""
    bucket: str
    key: str
    url: str
    sha256: Optional[str] = None  # SHA256 checksum for integrity verification
    size_bytes: Optional[int] = None  # Actual uploaded file size in bytes


# ============================================================================
# Signed URL Endpoints
# ============================================================================

class SignedUrlRequest(BaseModel):
    """Request to generate a signed URL."""
    bucket: str
    key: str
    expiration: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="URL expiration in seconds (min: 60s, max: 24h)"
    )


class SignedUrlResponse(BaseModel):
    """Response with signed URL."""
    success: bool
    url: str
    url_type: UrlType
    expires_in: int
    bucket: str
    key: str


# ============================================================================
# Download Endpoints
# ============================================================================

class GetUrlRequest(BaseModel):
    """Request to get file URL."""
    bucket: str
    key: str


class PublicUrlResponse(BaseModel):
    """Response with public URL."""
    success: bool
    url: str
    bucket: str
    key: str


# ============================================================================
# List Endpoints
# ============================================================================

class ListFilesRequest(BaseModel):
    """Request to list files in a bucket."""
    bucket: str
    prefix: str = ""


class ListFilesResponse(BaseModel):
    """Response with list of files."""
    success: bool
    bucket: str
    prefix: str
    count: int
    files: list[FileMetadata]


# ============================================================================
# Delete Endpoints
# ============================================================================

class DeleteRequest(BaseModel):
    """Request to delete a file."""
    bucket: str
    key: str


class DeleteResponse(BaseModel):
    """Response from file deletion."""
    bucket: str
    key: str
    deleted: bool


# ============================================================================
# Health Check
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    s3_connection: str
