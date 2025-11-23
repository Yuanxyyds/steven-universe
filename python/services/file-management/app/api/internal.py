"""
Internal API endpoints (Type 1: Private + Internal Only).
These endpoints require internal token authentication and are for backend services only.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from botocore.exceptions import ClientError

from app.core.auth import verify_internal_token
from app.core.config import BucketType, settings, get_bucket_type, validate_bucket
from app.s3.client import s3_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)]
)


@router.post("/upload")
async def upload_to_internal_bucket(
    bucket: str = Form(...),
    key: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload file to private internal bucket.
    Only accessible by backend services with internal token.

    Args:
        bucket: Bucket name (must be in INTERNAL_BUCKETS)
        key: Object key (file path in bucket)
        file: File to upload

    Returns:
        Upload result with bucket, key, and URL
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as an internal bucket"
        )

    try:
        # Ensure bucket exists with proper policy
        s3_client.ensure_bucket_exists(bucket)

        # Upload file
        result = s3_client.upload_file(
            bucket=bucket,
            key=key,
            file_obj=file.file,
            content_type=file.content_type
        )

        logger.info(f"Internal upload successful: {bucket}/{key}")

        return {
            "success": True,
            "message": "File uploaded successfully",
            "data": result
        }

    except ClientError as e:
        logger.error(f"S3 error during internal upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during internal upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/delete")
async def delete_from_internal_bucket(
    bucket: str,
    key: str
):
    """
    Delete file from private internal bucket.
    Only accessible by backend services with internal token.

    Args:
        bucket: Bucket name (must be in INTERNAL_BUCKETS)
        key: Object key to delete

    Returns:
        Deletion result
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

        # Delete file
        result = s3_client.delete_file(bucket=bucket, key=key)

        logger.info(f"Internal deletion successful: {bucket}/{key}")

        return {
            "success": True,
            "message": "File deleted successfully",
            "data": result
        }

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


@router.get("/list")
async def list_internal_bucket_files(
    bucket: str,
    prefix: Optional[str] = ""
):
    """
    List files in private internal bucket.
    Only accessible by backend services with internal token.

    Args:
        bucket: Bucket name (must be in INTERNAL_BUCKETS)
        prefix: Optional prefix to filter files

    Returns:
        List of file keys
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.INTERNAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as an internal bucket"
        )

    try:
        files = s3_client.list_files(bucket=bucket, prefix=prefix)

        return {
            "success": True,
            "bucket": bucket,
            "prefix": prefix,
            "count": len(files),
            "files": files
        }

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
