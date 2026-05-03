"""
GCS Model Store
Handles upload/download of model files to/from Google Cloud Storage.
Supports generation pinning for exact version targeting.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GCSModelStore:
    """Upload and download model files from Google Cloud Storage."""

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:  # pragma: no cover — requires GCS credentials
                from google.cloud import storage  # pragma: no cover
                self._client = storage.Client()  # pragma: no cover
            except Exception as e:  # pragma: no cover
                raise RuntimeError(  # pragma: no cover
                    f"Failed to initialize GCS client: {e}. "
                    "Ensure GOOGLE_APPLICATION_CREDENTIALS is set to a valid "
                    "service account key with storage.objects.get permission "
                    f"on bucket '{self.bucket_name}'."
                ) from e
        return self._client

    def download(
        self,
        gcs_path: str,
        local_path: Path,
        generation: Optional[int] = None,
    ) -> Path:
        """Download a model file from GCS to local path.

        Args:
            gcs_path: Path within the bucket (e.g., "yolo-boundary/v2/best.pt")
            local_path: Local destination path
            generation: GCS object generation number for pinning

        Returns:
            The local_path where the file was saved
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)

        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(gcs_path, generation=generation)

        if not blob.exists():
            raise FileNotFoundError(
                f"Model not found in GCS at gs://{self.bucket_name}/{gcs_path}"
                f"{f' (generation={generation})' if generation else ''}. "
                "Verify the file was uploaded with: "
                f"gsutil cp <model.pt> gs://{self.bucket_name}/{gcs_path}"
            )

        blob.download_to_filename(str(local_path))
        size_mb = local_path.stat().st_size / 1e6
        logger.info(
            f"Downloaded gs://{self.bucket_name}/{gcs_path} "
            f"(gen={generation}) -> {local_path} ({size_mb:.1f}MB)"
        )
        return local_path

    def upload(
        self,
        local_path: Path,
        gcs_path: str,
    ) -> int:
        """Upload a model file to GCS.

        Args:
            local_path: Local file to upload
            gcs_path: Destination path within the bucket

        Returns:
            GCS generation number of the uploaded object
        """
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(str(local_path))

        # Reload to get generation number
        blob.reload()
        generation = blob.generation

        size_mb = local_path.stat().st_size / 1e6
        logger.info(
            f"Uploaded {local_path} ({size_mb:.1f}MB) -> "
            f"gs://{self.bucket_name}/{gcs_path} (generation={generation})"
        )
        return generation

    def exists(self, gcs_path: str, generation: Optional[int] = None) -> bool:
        """Check if a model file exists in GCS."""
        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(gcs_path, generation=generation)
        return blob.exists()
