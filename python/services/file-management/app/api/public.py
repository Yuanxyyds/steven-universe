"""
Public API endpoints (Type 3: Public Buckets).
Direct URLs work for these buckets. Writes require auth, reads don't.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError

from app.core.auth import verify_api_access
from app.core.config import BucketType, get_bucket_type, settings
from app.s3.client import s3_client

logger = logging.getLogger(__name__)

# Router for authenticated operations (upload, delete)
router_auth = APIRouter(
    prefix="/public",
    tags=["public"],
    dependencies=[Depends(verify_api_access)]
)

# Router for unauthenticated operations (get URL)
router_no_auth = APIRouter(
    prefix="/public",
    tags=["public"]
)


@router_auth.post("/upload")
async def upload_to_public_bucket(
    bucket: str = Form(...),
    key: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload file to public bucket.
    Requires frontend or internal token to prevent abuse.

    Args:
        bucket: Bucket name (must be in PUBLIC_BUCKETS)
        key: Object key (file path in bucket)
        file: File to upload

    Returns:
        Upload result with direct public URL
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a public bucket"
        )

    try:
        # Ensure bucket exists with public policy
        s3_client.ensure_bucket_exists(bucket)

        # Upload file
        result = s3_client.upload_file(
            bucket=bucket,
            key=key,
            file_obj=file.file,
            content_type=file.content_type
        )

        logger.info(f"Public bucket upload successful: {bucket}/{key}")

        # Return public service URL instead of MinIO URL
        public_url = f"{settings.PUBLIC_SERVICE_URL}/public/download/{result['bucket']}/{result['key']}"

        return {
            "success": True,
            "message": "File uploaded successfully to public bucket",
            "data": {
                "bucket": result["bucket"],
                "key": result["key"],
                "public_url": public_url
            }
        }

    except ClientError as e:
        logger.error(f"S3 error during public bucket upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during public bucket upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_auth.delete("/delete")
async def delete_from_public_bucket(
    bucket: str,
    key: str
):
    """
    Delete file from public bucket.
    Requires frontend or internal token.

    Args:
        bucket: Bucket name (must be in PUBLIC_BUCKETS)
        key: Object key to delete

    Returns:
        Deletion result
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

        # Delete file
        result = s3_client.delete_file(bucket=bucket, key=key)

        logger.info(f"Public bucket deletion successful: {bucket}/{key}")

        return {
            "success": True,
            "message": "File deleted successfully",
            "data": result
        }

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


@router_no_auth.get("/url")
async def get_public_url(bucket: str, key: str):
    """
    Get public URL for a file (returns service proxy URL, not MinIO URL).
    No authentication required.

    Args:
        bucket: Bucket name (must be in PUBLIC_BUCKETS)
        key: Object key

    Returns:
        Public service URL
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

        # Return public service URL instead of MinIO URL
        url = f"{settings.PUBLIC_SERVICE_URL}/public/download/{bucket}/{key}"

        logger.info(f"Retrieved public URL for {bucket}/{key}")

        return {
            "success": True,
            "url": url,
            "bucket": bucket,
            "key": key
        }

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


@router_no_auth.get("/list")
async def list_public_bucket_files(
    bucket: str,
    prefix: Optional[str] = ""
):
    """
    List files in public bucket.
    No authentication required.

    Args:
        bucket: Bucket name (must be in PUBLIC_BUCKETS)
        prefix: Optional prefix to filter files

    Returns:
        List of file keys with public URLs
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a public bucket"
        )

    try:
        files = s3_client.list_files(bucket=bucket, prefix=prefix)

        # Add public service URLs to each file
        files_with_urls = [
            {
                "key": file_key,
                "url": f"{settings.PUBLIC_SERVICE_URL}/public/download/{bucket}/{file_key}"
            }
            for file_key in files
        ]

        return {
            "success": True,
            "bucket": bucket,
            "prefix": prefix,
            "count": len(files_with_urls),
            "files": files_with_urls
        }

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
