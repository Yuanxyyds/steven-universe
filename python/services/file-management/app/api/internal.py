"""
Internal API endpoints (Type 1: Private + Internal Only).
These endpoints require internal token authentication and are for backend services only.
"""

import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Request
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError

from shared_schemas.file_service import (
    UploadResponse,
    DeleteRequest,
    DeleteResponse,
    ListFilesRequest,
    ListFilesResponse,
    FileMetadata,
    GetUrlRequest,
    PublicUrlResponse,
)
from shared_schemas.common import SuccessResponse
from app.core.auth import verify_internal_token
from app.core.config import BucketType, get_bucket_type
from app.s3.client import s3_client
from app.utils.content_type import detect_content_type

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal",
    tags=["internal"]
)


@router.put("/upload/{bucket}/{key:path}", response_model=SuccessResponse[UploadResponse])
async def upload_file(
    bucket: str,
    key: str,
    request: Request,
    _auth: None = Depends(verify_internal_token)
):
    """
    Upload file to internal bucket (raw binary streaming).

    Streams file directly to MinIO without buffering - supports files of any size.
    Content-Type is auto-detected from file extension if not provided.

    Examples:
        # Auto-detect Content-Type from extension
        curl -X PUT "http://server/internal/upload/models/document.pdf" \\
          -H "Authorization: Bearer TOKEN" \\
          --data-binary "@document.pdf"
        # → Content-Type: application/pdf (auto-detected)

        # Explicitly specify Content-Type
        curl -X PUT "http://server/internal/upload/models/archive.tar.gz" \\
          -H "Authorization: Bearer TOKEN" \\
          -H "Content-Type: application/gzip" \\
          --data-binary "@archive.tar.gz"

    Supported auto-detection (common types):
        .pdf      → application/pdf
        .jpg/jpeg → image/jpeg
        .png      → image/png
        .mp4      → video/mp4
        .tar.gz   → application/gzip
        .zip      → application/zip
        .json     → application/json
        .txt      → text/plain

    Args:
        bucket: Bucket name (from URL path)
        key: Object key (from URL path)
        request: FastAPI Request with raw binary body

    Returns:
        Upload result with bucket, key, URL, SHA256, and size
    """
    start_time = time.time()

    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as an internal bucket"
        )

    try:
        # Ensure bucket exists with proper policy
        s3_client.ensure_bucket_exists(bucket)

        # Auto-detect content type from file extension
        provided_type = request.headers.get("content-type")
        content_type = detect_content_type(key, provided_type)

        if content_type != provided_type:
            logger.info(f"[INTERNAL UPLOAD] Auto-detected Content-Type: {content_type} for {key}")

        # Progress callback
        uploaded_bytes = [0]
        last_log_mb = [0]

        def progress(bytes_amount):
            uploaded_bytes[0] += bytes_amount
            current_mb = uploaded_bytes[0] / 1024 / 1024
            if current_mb - last_log_mb[0] >= 50:  # Log every 50MB
                logger.info(f"[INTERNAL UPLOAD] Progress: {current_mb:.2f}MB uploaded ({bucket}/{key})")
                last_log_mb[0] = current_mb

        # Create chunk iterator directly from request stream
        async def chunk_iterator():
            async for chunk in request.stream():
                yield chunk

        # Stream upload
        logger.info(f"[INTERNAL UPLOAD] Starting: {bucket}/{key}")
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
            f"[INTERNAL UPLOAD] Completed: {bucket}/{key} "
            f"({size_mb:.2f}MB in {duration:.2f}s, SHA256: {sha256})"
        )

        return SuccessResponse(
            success=True,
            message="File uploaded successfully",
            data=UploadResponse(
                bucket=result["bucket"],
                key=result["key"],
                url=result["url"],
                sha256=sha256,
                size_bytes=actual_size
            )
        )

    except ClientError as e:
        logger.error(f"[INTERNAL UPLOAD] S3 error: {bucket}/{key} :: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[INTERNAL UPLOAD] Unexpected error: {bucket}/{key} :: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/delete", response_model=SuccessResponse[DeleteResponse])
async def delete_from_internal_bucket(
    request: DeleteRequest = Depends(),
    _auth: None = Depends(verify_internal_token)
):
    """
    Delete file from private internal bucket.
    Only accessible by backend services with internal token.

    Args:
        request: DeleteRequest with bucket and key

    Returns:
        Deletion result
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as an internal bucket"
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

        logger.info(f"Internal deletion successful: {request.bucket}/{request.key}")

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
        logger.error(f"S3 error during internal deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during internal deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/list", response_model=ListFilesResponse)
async def list_internal_bucket_files(
    request: ListFilesRequest = Depends(),
    _auth: None = Depends(verify_internal_token)
):
    """
    List files in private internal bucket.
    Only accessible by backend services with internal token.

    Args:
        request: ListFilesRequest with bucket and prefix

    Returns:
        List of file keys
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as an internal bucket"
        )

    try:
        files = s3_client.list_files(bucket=request.bucket, prefix=request.prefix)

        # Convert to FileMetadata objects
        files_with_metadata = [
            FileMetadata(
                key=file_key,
                url=s3_client.get_public_url(request.bucket, file_key)
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
        logger.error(f"S3 error during internal listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during internal listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/download/{bucket}/{key:path}")
async def download_from_internal_bucket(
    bucket: str,
    key: str,
    _auth: None = Depends(verify_internal_token)
):
    """
    Download file from private internal bucket (streaming endpoint).
    Only accessible by backend services with internal token.

    Args:
        bucket: Bucket name (must be in INTERNAL_BUCKETS)
        key: Object key (file path)

    Returns:
        File stream
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as an internal bucket"
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
                'Content-Disposition': f'attachment; filename="{key.split("/")[-1]}"'
            }
        )

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error during internal download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during internal download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/url", response_model=PublicUrlResponse)
async def get_internal_url(
    request: GetUrlRequest = Depends(),
    _auth: None = Depends(verify_internal_token)
):
    """
    Get direct URL for a file in internal bucket.
    Only accessible by backend services with internal token.

    Args:
        request: GetUrlRequest with bucket and key

    Returns:
        Direct MinIO URL
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as an internal bucket"
        )

    try:
        # Check if file exists
        if not s3_client.file_exists(request.bucket, request.key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.bucket}/{request.key}"
            )

        # Return direct MinIO URL (internal services only)
        url = s3_client.get_public_url(request.bucket, request.key)

        logger.info(f"Retrieved internal URL for {request.bucket}/{request.key}")

        return PublicUrlResponse(
            success=True,
            url=url,
            bucket=request.bucket,
            key=request.key
        )

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error retrieving internal URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve URL: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving internal URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
