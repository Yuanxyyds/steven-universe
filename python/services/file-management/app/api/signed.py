"""
Signed URL API endpoints (Type 2: Private + Signed URLs).
Frontend and backend services can request time-limited signed URLs for private content.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from botocore.exceptions import ClientError

from app.core.auth import verify_api_access, TokenType
from app.core.config import BucketType, settings, get_bucket_type
from app.s3.client import s3_client

logger = logging.getLogger(__name__)

# Router for authenticated operations (upload, delete, generate URL)
router_auth = APIRouter(
    prefix="/signed",
    tags=["signed"],
    dependencies=[Depends(verify_api_access)]
)

# Router for unauthenticated operations (download with signed URL)
router_no_auth = APIRouter(
    prefix="/signed",
    tags=["signed"]
)


class SignedURLRequest(BaseModel):
    """Request model for signed URL generation."""
    bucket: str
    key: str
    expiration: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="URL expiration in seconds (min: 60s, max: 24h)"
    )


@router_auth.post("/upload")
async def upload_to_signed_bucket(
    bucket: str = Form(...),
    key: str = Form(...),
    file: UploadFile = File(...),
    token_type: TokenType = Depends(verify_api_access)
):
    """
    Upload file to private bucket that supports signed URL access.
    - Internal token: Returns direct MinIO URL
    - Frontend token: Returns public service proxy URL

    Args:
        bucket: Bucket name (must be in SIGNED_BUCKETS)
        key: Object key (file path in bucket)
        file: File to upload
        token_type: Token type from authentication

    Returns:
        Upload result with bucket, key, and URL (direct or proxy)
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a signed-URL bucket"
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

        logger.info(f"Signed bucket upload successful: {bucket}/{key}")

        # Return URL based on token type
        if token_type == TokenType.INTERNAL:
            url = result["url"]  # Direct MinIO URL
        else:
            url = f"{settings.PUBLIC_SERVICE_URL}/signed/download/{result['bucket']}/{result['key']}"

        return {
            "success": True,
            "message": "File uploaded successfully",
            "data": {
                "bucket": result["bucket"],
                "key": result["key"],
                "url": url
            }
        }

    except ClientError as e:
        logger.error(f"S3 error during signed bucket upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during signed bucket upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_auth.post("/url")
async def generate_signed_url(
    request: SignedURLRequest,
    token_type: TokenType = Depends(verify_api_access)
):
    """
    Generate time-limited access URL for private file.
    - Internal token: Returns direct MinIO signed URL (faster, local network)
    - Frontend token: Returns public service proxy URL (accessible from internet)

    Args:
        request: SignedURLRequest with bucket, key, and expiration
        token_type: Token type from authentication

    Returns:
        Signed URL (direct or proxy) with expiration time
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as a signed-URL bucket"
        )

    # Validate expiration limits
    if request.expiration > settings.MAX_SIGNED_URL_EXPIRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expiration cannot exceed {settings.MAX_SIGNED_URL_EXPIRATION} seconds"
        )

    try:
        # Check if file exists
        if not s3_client.file_exists(request.bucket, request.key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.bucket}/{request.key}"
            )

        # Generate URL based on token type
        if token_type == TokenType.INTERNAL:
            # Internal services get direct MinIO signed URL (faster, local network)
            url = s3_client.generate_presigned_url(
                bucket=request.bucket,
                key=request.key,
                expiration=request.expiration
            )
            url_type = "direct_minio"
            logger.info(f"Generated direct MinIO signed URL for {request.bucket}/{request.key} (internal service)")
        else:
            # Frontend gets public service proxy URL (accessible from internet)
            url = f"{settings.PUBLIC_SERVICE_URL}/signed/download/{request.bucket}/{request.key}"
            url_type = "public_proxy"
            logger.info(f"Generated public proxy URL for {request.bucket}/{request.key} (frontend)")

        return {
            "success": True,
            "url": url,
            "url_type": url_type,  # Help caller understand what type of URL they got
            "expires_in": request.expiration,
            "bucket": request.bucket,
            "key": request.key
        }

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error generating signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error generating signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_auth.delete("/delete")
async def delete_from_signed_bucket(
    bucket: str,
    key: str
):
    """
    Delete file from signed URL bucket.
    Requires frontend or internal token.

    Args:
        bucket: Bucket name (must be in SIGNED_BUCKETS)
        key: Object key to delete

    Returns:
        Deletion result
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a signed-URL bucket"
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

        logger.info(f"Signed bucket deletion successful: {bucket}/{key}")

        return {
            "success": True,
            "message": "File deleted successfully",
            "data": result
        }

    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"S3 error during signed bucket deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during signed bucket deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_no_auth.get("/download/{bucket}/{key:path}")
async def download_file(bucket: str, key: str):
    """
    Download file from signed bucket (proxy endpoint).
    This endpoint is publicly accessible and does not require auth.
    Proxies the file from MinIO to the client.

    Args:
        bucket: Bucket name (must be in SIGNED_BUCKETS)
        key: Object key (file path)

    Returns:
        File stream
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a signed-URL bucket"
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
        logger.error(f"S3 error during file download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during file download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_auth.get("/list")
async def list_signed_bucket_files(
    bucket: str,
    prefix: Optional[str] = "",
    token_type: TokenType = Depends(verify_api_access)
):
    """
    List files in signed URL bucket.
    - Internal token: Returns direct MinIO URLs
    - Frontend token: Returns public service proxy URLs

    Args:
        bucket: Bucket name (must be in SIGNED_BUCKETS)
        prefix: Optional prefix to filter files
        token_type: Token type from authentication

    Returns:
        List of file keys with URLs (direct or proxy)
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a signed-URL bucket"
        )

    try:
        files = s3_client.list_files(bucket=bucket, prefix=prefix)

        # Return files with URLs based on token type
        if token_type == TokenType.INTERNAL:
            # Internal services get direct MinIO URLs
            files_with_urls = [
                {
                    "key": file_key,
                    "url": s3_client.get_public_url(bucket, file_key)  # Direct MinIO URL
                }
                for file_key in files
            ]
        else:
            # Frontend gets public service proxy URLs
            files_with_urls = [
                {
                    "key": file_key,
                    "url": f"{settings.PUBLIC_SERVICE_URL}/signed/download/{bucket}/{file_key}"
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
        logger.error(f"S3 error during signed bucket listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during signed bucket listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Export both routers
routers = [router_auth, router_no_auth]
