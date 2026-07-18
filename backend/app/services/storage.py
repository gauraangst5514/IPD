"""
MinIO/S3 Storage Service

Handles image uploads, retrieval, and presigned URL generation.
Uses the S3-compatible API so this works with MinIO (local dev) or
AWS S3 (production) without code changes.
"""

import io
import uuid
import hashlib
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


class StorageService:
    """S3-compatible object storage for claim images. Falls back to local disk."""

    def __init__(self):
        self.use_local = True  # Default to local for dev without MinIO
        self.local_dir = Path("uploads")
        self.local_dir.mkdir(exist_ok=True)

        try:
            self.client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name="us-east-1",
            )
            self.bucket = settings.S3_BUCKET
            self._ensure_bucket()
            self.use_local = False
        except Exception:
            print("⚠️  MinIO/S3 not available — using local file storage")

    def _ensure_bucket(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except ClientError:
                raise

    def upload_image(self, file_bytes: bytes, claim_id: str, filename: str) -> dict:
        """
        Upload an image to storage.

        Returns:
            {
                "key": "claims/<claim_id>/<uuid>_<filename>",
                "url": presigned URL or local path,
                "file_hash": SHA-256 hash,
                "size_bytes": int,
            }
        """
        ext = Path(filename).suffix.lower() or ".jpg"
        unique_name = f"{uuid.uuid4().hex[:12]}_{filename}"
        key = f"claims/{claim_id}/{unique_name}"
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        if self.use_local:
            local_path = self.local_dir / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(file_bytes)
            url = f"/uploads/{key}"
        else:
            content_types = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp",
            }
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=file_bytes,
                ContentType=content_types.get(ext, "image/jpeg"),
            )
            url = self.get_presigned_url(key)

        return {"key": key, "url": url, "file_hash": file_hash, "size_bytes": len(file_bytes)}

    def upload_heatmap(self, heatmap_bytes: bytes, claim_id: str, image_id: str) -> str:
        """Upload a generated heatmap/annotated image. Returns the storage key."""
        key = f"claims/{claim_id}/heatmaps/{image_id}_annotated.png"

        if self.use_local:
            local_path = self.local_dir / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(heatmap_bytes)
        else:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=heatmap_bytes, ContentType="image/png",
            )
        return key

    def get_presigned_url(self, key: str, expires_in: int = 604800) -> str:
        """Generate a presigned URL for an object."""
        if self.use_local:
            return f"/uploads/{key}"
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def download_image(self, key: str) -> bytes:
        """Download image bytes from storage."""
        if self.use_local:
            local_path = self.local_dir / key
            return local_path.read_bytes()
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete_image(self, key: str):
        """Delete an image from storage."""
        self.client.delete_object(Bucket=self.bucket, Key=key)


# Singleton
_storage_service = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
