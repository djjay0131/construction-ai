"""Tests for GCSModelStore."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock


class TestGCSModelStore:
    """Tests for GCS upload/download with generation pinning."""

    def _make_store(self):
        from app.core.ml.model_store import GCSModelStore
        store = GCSModelStore("test-bucket")
        store._client = MagicMock()
        return store

    def test_download_creates_parent_dirs(self, tmp_path):
        store = self._make_store()
        local_path = tmp_path / "sub" / "dir" / "model.pt"

        blob = MagicMock()
        blob.exists.return_value = True
        blob.download_to_filename = MagicMock(
            side_effect=lambda p: Path(p).write_bytes(b"fake model")
        )
        store.client.bucket.return_value.blob.return_value = blob

        result = store.download("yolo/v1/best.pt", local_path)

        assert result == local_path
        assert local_path.parent.exists()
        blob.download_to_filename.assert_called_once_with(str(local_path))

    def test_download_with_generation_pinning(self, tmp_path):
        store = self._make_store()
        local_path = tmp_path / "model.pt"

        blob = MagicMock()
        blob.exists.return_value = True
        blob.download_to_filename = MagicMock(
            side_effect=lambda p: Path(p).write_bytes(b"fake model")
        )
        store.client.bucket.return_value.blob.return_value = blob

        store.download("yolo/v1/best.pt", local_path, generation=12345)

        store.client.bucket.return_value.blob.assert_called_once_with(
            "yolo/v1/best.pt", generation=12345
        )

    def test_download_missing_file_raises(self, tmp_path):
        store = self._make_store()
        local_path = tmp_path / "model.pt"

        blob = MagicMock()
        blob.exists.return_value = False
        store.client.bucket.return_value.blob.return_value = blob

        with pytest.raises(FileNotFoundError, match="Model not found in GCS"):
            store.download("yolo/v99/best.pt", local_path)

    def test_download_missing_file_error_includes_gsutil_hint(self, tmp_path):
        store = self._make_store()
        local_path = tmp_path / "model.pt"

        blob = MagicMock()
        blob.exists.return_value = False
        store.client.bucket.return_value.blob.return_value = blob

        with pytest.raises(FileNotFoundError, match="gsutil cp"):
            store.download("yolo/v99/best.pt", local_path)

    def test_upload_returns_generation(self, tmp_path):
        store = self._make_store()
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"fake model data")

        blob = MagicMock()
        blob.generation = 9876543210
        store.client.bucket.return_value.blob.return_value = blob

        gen = store.upload(model_file, "yolo/v3/best.pt")

        assert gen == 9876543210
        blob.upload_from_filename.assert_called_once_with(str(model_file))
        blob.reload.assert_called_once()

    def test_upload_missing_file_raises(self, tmp_path):
        store = self._make_store()
        missing = tmp_path / "does_not_exist.pt"

        with pytest.raises(FileNotFoundError, match="Local file not found"):
            store.upload(missing, "yolo/v1/best.pt")

    def test_exists_delegates_to_blob(self):
        store = self._make_store()
        blob = MagicMock()
        blob.exists.return_value = True
        store.client.bucket.return_value.blob.return_value = blob

        assert store.exists("yolo/v1/best.pt") is True
        store.client.bucket.return_value.blob.assert_called_once_with(
            "yolo/v1/best.pt", generation=None
        )

    def test_exists_with_generation(self):
        store = self._make_store()
        blob = MagicMock()
        blob.exists.return_value = False
        store.client.bucket.return_value.blob.return_value = blob

        assert store.exists("yolo/v1/best.pt", generation=111) is False
        store.client.bucket.return_value.blob.assert_called_once_with(
            "yolo/v1/best.pt", generation=111
        )

    def test_client_init_failure_gives_clear_message(self):
        from app.core.ml.model_store import GCSModelStore
        store = GCSModelStore("test-bucket")

        with patch("app.core.ml.model_store.GCSModelStore.client", new_callable=PropertyMock) as mock_client:
            mock_client.side_effect = RuntimeError("GOOGLE_APPLICATION_CREDENTIALS")
            with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
                _ = store.client
