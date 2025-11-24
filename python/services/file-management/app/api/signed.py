"""
Signed URL API endpoints (Type 2: Private + Signed URLs).
Frontend and backend services can request time-limited signed URLs for private content.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Request
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError
import requests

from shared_schemas.file_service import (
    SignedUrlRequest,
    SignedUrlResponse,
    UrlType,
    UploadResponse,
    DeleteRequest,
    DeleteResponse,
    ListFilesRequest,
    ListFilesResponse,
    FileMetadata,
)
from shared_schemas.common import SuccessResponse
from app.core.auth import verify_api_access, TokenType
from app.core.config import BucketType, settings, get_bucket_type
from app.s3.client import s3_client

logger = logging.getLogger(__name__)


def rewrite_minio_url_for_frontend(minio_url: str) -> str:
    """
    Rewrite MinIO signed URL to use public service domain as proxy.

    Converts:
        http://192.168.50.26:9000/user-uploads/profiles/user123.jpg?X-Amz-Signature=...
    To:
        https://files.yourdomain.com/signed/download/user-uploads/profiles/user123.jpg?X-Amz-Signature=...

    The /signed/download endpoint will proxy the request back to MinIO, preserving all query
    parameters so MinIO can validate the signature and expiration.

    Args:
        minio_url: Original MinIO signed URL with signature

    Returns:
        Rewritten URL using public service domain
    """
    # Construct MinIO base URL
    minio_base = f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}"

    if minio_url.startswith(minio_base):
        # Replace MinIO endpoint with public service URL + /signed/download prefix
        return minio_url.replace(minio_base, f"{settings.PUBLIC_SERVICE_URL}/signed/download", 1)

    return minio_url

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


@router_auth.post("/upload", response_model=SuccessResponse[UploadResponse])
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

        return SuccessResponse(
            success=True,
            message="File uploaded successfully",
            data=UploadResponse(
                bucket=result["bucket"],
                key=result["key"],
                url=url
            )
        )

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


@router_auth.post("/url", response_model=SignedUrlResponse)
async def generate_signed_url(
    request: SignedUrlRequest,
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
            url_type = UrlType.DIRECT_MINIO
            logger.info(f"Generated direct MinIO signed URL for {request.bucket}/{request.key} (internal service)")
        else:
            # Frontend gets rewritten MinIO signed URL (proxied through public service)
            # Generate real MinIO signed URL with signature
            minio_signed_url = s3_client.generate_presigned_url(
                bucket=request.bucket,
                key=request.key,
                expiration=request.expiration
            )
            # Rewrite to use public domain: http://192.168.50.26:9000/... -> https://files.yourdomain.com/download/...
            url = rewrite_minio_url_for_frontend(minio_signed_url)
            url_type = UrlType.PUBLIC_PROXY
            logger.info(f"Generated rewritten signed URL for {request.bucket}/{request.key} (frontend, expires in {request.expiration}s)")

        return SignedUrlResponse(
            success=True,
            url=url,
            url_type=url_type,
            expires_in=request.expiration,
            bucket=request.bucket,
            key=request.key
        )

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


@router_auth.delete("/delete", response_model=SuccessResponse[DeleteResponse])
async def delete_from_signed_bucket(
    request: DeleteRequest = Depends()
):
    """
    Delete file from signed URL bucket.
    Requires frontend or internal token.

    Args:
        request: DeleteRequest with bucket and key

    Returns:
        Deletion result
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as a signed-URL bucket"
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

        logger.info(f"Signed bucket deletion successful: {request.bucket}/{request.key}")

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
async def download_file(bucket: str, key: str, request: Request):
    """
    Proxy endpoint that forwards signed URL requests to MinIO.

    Receives rewritten signed URLs from frontend:
        https://files.yourdomain.com/signed/download/user-uploads/user123.jpg?X-Amz-Signature=...

    Forwards to MinIO with all query parameters preserved:
        http://192.168.50.26:9000/user-uploads/user123.jpg?X-Amz-Signature=...

    MinIO validates the signature and expiration, then returns the file.
    This endpoint proxies the response back to the client.

    Args:
        bucket: Bucket name (must be in SIGNED_BUCKETS)
        key: Object key (file path)
        request: FastAPI request (to extract query parameters like X-Amz-Signature)

    Returns:
        File stream from MinIO
    """
    # Validate bucket type
    if get_bucket_type(bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{bucket}' is not configured as a signed-URL bucket"
        )

    try:
        # Construct MinIO URL with bucket and key
        minio_protocol = "https" if settings.MINIO_SECURE else "http"
        minio_url = f"{minio_protocol}://{settings.MINIO_ENDPOINT}/{bucket}/{key}"

        # Preserve all query parameters (X-Amz-Signature, X-Amz-Expires, etc.)
        query_string = str(request.url.query)
        if query_string:
            minio_url += f"?{query_string}"

        logger.info(f"Proxying signed URL request to MinIO: {bucket}/{key}")

        # Forward request to MinIO (MinIO validates signature and expiration)
        minio_response = requests.get(minio_url, stream=True)

        # Check if MinIO returned an error (e.g., signature invalid, URL expired)
        if minio_response.status_code != 200:
            logger.warning(f"MinIO rejected request for {bucket}/{key}: {minio_response.status_code}")

            # Common MinIO error responses
            if minio_response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied - signature invalid or URL expired"
                )
            elif minio_response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {bucket}/{key}"
                )
            else:
                raise HTTPException(
                    status_code=minio_response.status_code,
                    detail=f"Storage backend error: {minio_response.text}"
                )

        # Stream the file back to the client
        # Using 256KB chunks for smooth image loading (avoids line-by-line rendering)
        return StreamingResponse(
            minio_response.iter_content(chunk_size=262144),  # 256KB
            media_type=minio_response.headers.get('content-type', 'application/octet-stream'),
            headers={
                'Content-Disposition': minio_response.headers.get('content-disposition', f'inline; filename="{key.split("/")[-1]}"')
            }
        )

    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to MinIO: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to storage backend"
        )
    except Exception as e:
        logger.error(f"Unexpected error during proxy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router_auth.get("/list", response_model=ListFilesResponse)
async def list_signed_bucket_files(
    request: ListFilesRequest = Depends(),
    token_type: TokenType = Depends(verify_api_access)
):
    """
    List files in signed URL bucket.
    - Internal token: Returns direct MinIO URLs
    - Frontend token: Returns public service proxy URLs

    Args:
        request: ListFilesRequest with bucket and prefix
        token_type: Token type from authentication

    Returns:
        List of file keys with URLs (direct or proxy)
    """
    # Validate bucket type
    if get_bucket_type(request.bucket) != BucketType.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bucket '{request.bucket}' is not configured as a signed-URL bucket"
        )

    try:
        files = s3_client.list_files(bucket=request.bucket, prefix=request.prefix)

        # Return files with URLs based on token type
        if token_type == TokenType.INTERNAL:
            # Internal services get direct MinIO URLs
            files_with_metadata = [
                FileMetadata(
                    key=file_key,
                    url=s3_client.get_public_url(request.bucket, file_key)
                )
                for file_key in files
            ]
        else:
            # Frontend gets public service proxy URLs
            files_with_metadata = [
                FileMetadata(
                    key=file_key,
                    url=f"{settings.PUBLIC_SERVICE_URL}/signed/download/{request.bucket}/{file_key}"
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
