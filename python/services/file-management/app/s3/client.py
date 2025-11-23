"""
MinIO S3 Client wrapper.
Handles all S3 operations including upload, delete, signed URLs, and bucket policies.
"""

import json
import logging
from typing import BinaryIO, Optional, Literal
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import BucketType, settings, get_bucket_type

logger = logging.getLogger(__name__)


class S3Client:
    """Wrapper for MinIO S3 operations."""

    def __init__(self):
        """Initialize S3 client with MinIO configuration."""
        # Parse endpoint to extract protocol and host
        endpoint_url = settings.MINIO_ENDPOINT
        if not endpoint_url.startswith(('http://', 'https://')):
            protocol = 'https' if settings.MINIO_SECURE else 'http'
            endpoint_url = f"{protocol}://{endpoint_url}"

        self.client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'  # MinIO doesn't care about region
        )

        self.endpoint_url = endpoint_url
        logger.info(f"S3 client initialized with endpoint: {endpoint_url}")

    def upload_file(
        self,
        bucket: str,
        key: str,
        file_obj: BinaryIO,
        content_type: Optional[str] = None
    ) -> dict:
        """
        Upload a file to S3/MinIO.

        Args:
            bucket: Bucket name
            key: Object key (file path in bucket)
            file_obj: File-like object to upload
            content_type: MIME type of the file

        Returns:
            Dict with upload result

        Raises:
            ClientError: If upload fails
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type

            self.client.upload_fileobj(
                file_obj,
                bucket,
                key,
                ExtraArgs=extra_args
            )

            logger.info(f"Uploaded file: {bucket}/{key}")

            return {
                "success": True,
                "bucket": bucket,
                "key": key,
                "url": self._get_object_url(bucket, key)
            }

        except ClientError as e:
            logger.error(f"Failed to upload {bucket}/{key}: {e}")
            raise

    def delete_file(self, bucket: str, key: str) -> dict:
        """
        Delete a file from S3/MinIO.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Dict with deletion result

        Raises:
            ClientError: If deletion fails
        """
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted file: {bucket}/{key}")

            return {
                "success": True,
                "bucket": bucket,
                "key": key
            }

        except ClientError as e:
            logger.error(f"Failed to delete {bucket}/{key}: {e}")
            raise

    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary access to a file.

        Args:
            bucket: Bucket name
            key: Object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL string

        Raises:
            ClientError: If URL generation fails
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )

            logger.info(f"Generated presigned URL for {bucket}/{key} (expires in {expiration}s)")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {bucket}/{key}: {e}")
            raise

    def get_public_url(self, bucket: str, key: str) -> str:
        """
        Get direct public URL for a file in a public bucket.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Direct URL to the object
        """
        return self._get_object_url(bucket, key)

    def _get_object_url(self, bucket: str, key: str) -> str:
        """Construct direct URL to an object."""
        return f"{self.endpoint_url}/{bucket}/{key}"

    def file_exists(self, bucket: str, key: str) -> bool:
        """
        Check if a file exists in the bucket.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def list_files(self, bucket: str, prefix: str = "") -> list:
        """
        List files in a bucket with optional prefix.

        Args:
            bucket: Bucket name
            prefix: Key prefix to filter results

        Returns:
            List of object keys

        Raises:
            ClientError: If listing fails
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            return [obj['Key'] for obj in response['Contents']]

        except ClientError as e:
            logger.error(f"Failed to list files in {bucket}: {e}")
            raise

    def set_bucket_policy(self, bucket: str, policy_type: Literal['private', 'public']) -> None:
        """
        Set bucket policy based on access type.

        Args:
            bucket: Bucket name
            policy_type: 'private' or 'public'

        Raises:
            ClientError: If policy setting fails
        """
        if policy_type == 'public':
            # Public read policy
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket}/*"]
                    }
                ]
            }
        else:
            # Private policy (no public access)
            policy = {
                "Version": "2012-10-17",
                "Statement": []
            }

        try:
            self.client.put_bucket_policy(
                Bucket=bucket,
                Policy=json.dumps(policy)
            )
            logger.info(f"Set {policy_type} policy for bucket: {bucket}")

        except ClientError as e:
            logger.error(f"Failed to set policy for {bucket}: {e}")
            raise

    def ensure_bucket_exists(self, bucket: str) -> None:
        """
        Ensure bucket exists, create if it doesn't.

        Args:
            bucket: Bucket name

        Raises:
            ClientError: If bucket creation fails
        """
        try:
            self.client.head_bucket(Bucket=bucket)
            logger.info(f"Bucket exists: {bucket}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    self.client.create_bucket(Bucket=bucket)
                    logger.info(f"Created bucket: {bucket}")

                    # Set appropriate policy based on bucket type
                    bucket_type = get_bucket_type(bucket)
                    if bucket_type == BucketType.PUBLIC:
                        self.set_bucket_policy(bucket, 'public')
                    else:
                        self.set_bucket_policy(bucket, 'private')

                except ClientError as create_error:
                    logger.error(f"Failed to create bucket {bucket}: {create_error}")
                    raise
            else:
                logger.error(f"Error checking bucket {bucket}: {e}")
                raise


# Global S3 client instance
s3_client = S3Client()
