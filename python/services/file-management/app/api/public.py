"""
Public API endpoints (Type 3: Public Buckets).
Direct URLs work for these buckets. Writes require auth, reads don't.
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError

from shared_schemas.file_service import (
    UploadResponse,
    GetUrlRequest,
    PublicUrlResponse,
    DeleteRequest,
    DeleteResponse,
    ListFilesRequest,
    ListFilesResponse,
    FileMetadata,
)
from shared_schemas.common import SuccessResponse
from app.core.auth import verify_api_access
from app.core.config import BucketType, get_bucket_type, settings
from app.s3.client import s3_client
from app.utils.content_type import detect_content_type

logger = logging.getLogger(__name__)

# Router for authenticated operations (upload, delete)
router_auth = APIRouter(
    prefix="/public",
    tags=["public"]
)

# Router for unauthenticated operations (get URL)
router_no_auth = APIRouter(
    prefix="/public",
    tags=["public"]
)


@router_auth.put("/upload/{bucket}/{key:path}", response_model=SuccessResponse[UploadResponse])
async def upload_file(
    bucket: str,
    key: str,
    request: Request,
    _auth: None = Depends(verify_api_access)
):
    """
    Upload file to public bucket (raw binary streaming).

    Streams file directly to MinIO without buffering - supports files of any size.
    Content-Type is auto-detected from file extension if not provided.
    Requires frontend or internal token to prevent abuse.

    Example:
        curl -X PUT "http://server/public/upload/public/image.jpg" \\
          -H "Authorization: Bearer TOKEN" \\
          --data-binary "@image.jpg"

    Args:
        bucket: Bucket name (must be in PUBLIC_BUCKETS)
        key: Object key / file path
        request: FastAPI Request with raw binary body

    Returns:
        Upload result with direct public URL, SHA256, and size
    """
    start_time = time.time()

    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a public bucket"
        )

    try:
        # Ensure bucket exists with public policy
        s3_client.ensure_bucket_exists(bucket)

        # Auto-detect content type from file extension
        provided_type = request.headers.get("content-type")
        content_type = detect_content_type(key, provided_type)

        # Progress callback
        uploaded_bytes = [0]
        last_log_mb = [0]

        def progress(bytes_amount):
            uploaded_bytes[0] += bytes_amount
            current_mb = uploaded_bytes[0] / 1024 / 1024
            if current_mb - last_log_mb[0] >= 50:
                logger.info(f"[PUBLIC UPLOAD] Progress: {current_mb:.2f}MB uploaded ({bucket}/{key})")
                last_log_mb[0] = current_mb

        # Create chunk iterator directly from request stream
        async def chunk_iterator():
            async for chunk in request.stream():
                yield chunk

        # Stream upload
        logger.info(f"[PUBLIC UPLOAD] Starting: {bucket}/{key}")
        result = await s3_client.upload_file_streaming(
            bucket=bucket,
            key=key,
            chunk_iterator=chunk_iterator(),
            content_type=content_type,
            progress_callback=progress
        )

        duration = time.time() - start_time
        size_mb = result.get("size_bytes", 0) / 1024 / 1024
        sha256 = result.get("sha256")
        actual_size = result.get("size_bytes", 0)

        logger.info(
            f"[PUBLIC UPLOAD] Completed: {bucket}/{key} "
            f"({size_mb:.2f}MB in {duration:.2f}s, SHA256: {sha256})"
        )

        # Return public service URL instead of MinIO URL
        public_url = f"{settings.PUBLIC_SERVICE_URL}/public/download/{result['bucket']}/{result['key']}"

        return SuccessResponse(
            success=True,
            message="File uploaded successfully to public bucket",
            data=UploadResponse(
                bucket=result["bucket"],
                key=result["key"],
                url=public_url,
                sha256=sha256,
                size_bytes=actual_size
            )
        )

    except ClientError as e:
        logger.error(f"[PUBLIC UPLOAD] S3 error: {bucket}/{key} :: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PUBLIC UPLOAD] Unexpected error: {bucket}/{key} :: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_auth.delete("/delete", response_model=SuccessResponse[DeleteResponse])
async def delete_from_public_bucket(
    request: DeleteRequest = Depends()
):
    """
    Delete file from public bucket.
    Requires frontend or internal token.

    Args:
        request: DeleteRequest with bucket and key

    Returns:
        Deletion result
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as a public bucket"
        )

    try:
        # Check if file exists
        if not s3_client.file_exists(request.bucket, request.key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.bucket}/{request.key}"
            )

        # Delete file
        s3_client.delete_file(bucket=request.bucket, key=request.key)

        logger.info(f"Public bucket deletion successful: {request.bucket}/{request.key}")

        return SuccessResponse(
            success=True,
            message="File deleted successfully",
            data=DeleteResponse(
                bucket=request.bucket,
                key=request.key,
                deleted=True
            )
        )

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error during public bucket deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during public bucket deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_no_auth.get("/download/{bucket}/{key:path}")
async def download_public_file(bucket: str, key: str):
    """
    Download file from public bucket (proxy endpoint).
    No authentication required.
    Proxies the file from MinIO to the client.

    Args:
        bucket: Bucket name (must be in PUBLIC_BUCKETS)
        key: Object key (file path)

    Returns:
        File stream
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a public bucket"
        )

    try:
        # Check if file exists
        if not s3_client.file_exists(bucket, key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {bucket}/{key}"
            )

        # Get file from MinIO
        response = s3_client.client.get_object(Bucket=bucket, Key=key)

        # Get content type
        content_type = response.get('ContentType', 'application/octet-stream')

        # Stream the file
        return StreamingResponse(
            response['Body'],
            media_type=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{key.split("/")[-1]}"'
            }
        )

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error during public file download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during public file download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_no_auth.get("/url", response_model=PublicUrlResponse)
async def get_public_url(request: GetUrlRequest = Depends()):
    """
    Get public URL for a file (returns service proxy URL, not MinIO URL).
    No authentication required.

    Args:
        request: GetUrlRequest with bucket and key

    Returns:
        Public service URL
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as a public bucket"
        )

    try:
        # Check if file exists
        if not s3_client.file_exists(request.bucket, request.key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.bucket}/{request.key}"
            )

        # Return public service URL instead of MinIO URL
        url = f"{settings.PUBLIC_SERVICE_URL}/public/download/{request.bucket}/{request.key}"

        logger.info(f"Retrieved public URL for {request.bucket}/{request.key}")

        return PublicUrlResponse(
            success=True,
            url=url,
            bucket=request.bucket,
            key=request.key
        )

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error retrieving public URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve URL: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving public URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_no_auth.get("/list", response_model=ListFilesResponse)
async def list_public_bucket_files(
    request: ListFilesRequest = Depends()
):
    """
    List files in public bucket.
    No authentication required.

    Args:
        request: ListFilesRequest with bucket and prefix

    Returns:
        List of file keys with public URLs
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as a public bucket"
        )

    try:
        files = s3_client.list_files(bucket=request.bucket, prefix=request.prefix)

        # Add public service URLs to each file
        files_with_metadata = [
            FileMetadata(
                key=file_key,
                url=f"{settings.PUBLIC_SERVICE_URL}/public/download/{request.bucket}/{file_key}"
            )
            for file_key in files
        ]

        return ListFilesResponse(
            success=True,
            bucket=request.bucket,
            prefix=request.prefix,
            count=len(files_with_metadata),
            files=files_with_metadata
        )

    except ClientError as e:
        logger.error(f"S3 error during public bucket listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during public bucket listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Export both routers
routers = [router_auth, router_no_auth]
