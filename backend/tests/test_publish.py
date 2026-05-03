"""Tests for the model publish CLI."""

import pytest
import yaml
from unittest.mock import MagicMock, patch

from ml.publish import publish_model, main


class TestPublishModel:
    def _manifest_with_model(self, tmp_path):
        manifest = {
            "bucket": "test-bucket",
            "local_cache": str(tmp_path / "cache"),
            "models": {
                "yolo-boundary": {
                    "description": "Boundary detection",
                    "current_version": "v1",
                    "versions": {
                        "v1": {
                            "gcs_path": "yolo-boundary/v1/best.pt",
                            "gcs_generation": 111,
                        }
                    },
                }
            },
        }
        manifest_path = tmp_path / "models.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        return manifest_path

    def test_publish_uploads_and_updates_manifest(self, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"new model")

        mock_store = MagicMock()
        mock_store.upload.return_value = 99999

        gen = publish_model(
            model_name="yolo-boundary",
            version="v2",
            model_path=model_file,
            manifest_path=manifest_path,
            dataset="exp2",
            metrics={"mAP50": 0.95},
            store=mock_store,
        )

        assert gen == 99999
        mock_store.upload.assert_called_once_with(model_file, "yolo-boundary/v2/best.pt")

        with open(manifest_path) as f:
            updated = yaml.safe_load(f)

        v2 = updated["models"]["yolo-boundary"]["versions"]["v2"]
        assert v2["gcs_path"] == "yolo-boundary/v2/best.pt"
        assert v2["gcs_generation"] == 99999
        assert v2["dataset"] == "exp2"
        assert v2["metrics"] == {"mAP50": 0.95}

    def test_publish_unknown_model_exits(self, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        mock_store = MagicMock()

        with pytest.raises(SystemExit):
            publish_model(
                model_name="nonexistent",
                version="v1",
                model_path=model_file,
                manifest_path=manifest_path,
                store=mock_store,
            )

    def test_publish_preserves_existing_versions(self, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        mock_store = MagicMock()
        mock_store.upload.return_value = 88888

        publish_model(
            model_name="yolo-boundary",
            version="v2",
            model_path=model_file,
            manifest_path=manifest_path,
            store=mock_store,
        )

        with open(manifest_path) as f:
            updated = yaml.safe_load(f)

        assert "v1" in updated["models"]["yolo-boundary"]["versions"]
        assert "v2" in updated["models"]["yolo-boundary"]["versions"]

    def test_publish_without_optional_fields(self, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        mock_store = MagicMock()
        mock_store.upload.return_value = 77777

        gen = publish_model(
            model_name="yolo-boundary",
            version="v3",
            model_path=model_file,
            manifest_path=manifest_path,
            store=mock_store,
        )

        assert gen == 77777

        with open(manifest_path) as f:
            updated = yaml.safe_load(f)

        v3 = updated["models"]["yolo-boundary"]["versions"]["v3"]
        assert "dataset" not in v3
        assert "metrics" not in v3
        assert v3["gcs_generation"] == 77777

    def test_publish_overwrite_existing_version_warns(self, tmp_path, capsys):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        mock_store = MagicMock()
        mock_store.upload.return_value = 55555

        publish_model(
            model_name="yolo-boundary",
            version="v1",  # already exists
            model_path=model_file,
            manifest_path=manifest_path,
            store=mock_store,
        )

        captured = capsys.readouterr()
        assert "already exists" in captured.out


class TestPublishCLI:
    def _manifest_with_model(self, tmp_path):
        manifest = {
            "bucket": "test-bucket",
            "local_cache": str(tmp_path / "cache"),
            "models": {
                "yolo-boundary": {
                    "description": "Boundary detection",
                    "current_version": "v1",
                    "versions": {
                        "v1": {
                            "gcs_path": "yolo-boundary/v1/best.pt",
                            "gcs_generation": 111,
                        }
                    },
                }
            },
        }
        manifest_path = tmp_path / "models.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)
        return manifest_path

    @patch("ml.publish.publish_model")
    def test_main_parses_args_and_calls_publish(self, mock_publish, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        with patch("sys.argv", [
            "publish",
            "yolo-boundary", "v2", str(model_file),
            "--manifest", str(manifest_path),
            "--dataset", "exp3",
            "--metrics", '{"mAP50": 0.95}',
        ]):
            main()

        mock_publish.assert_called_once_with(
            model_name="yolo-boundary",
            version="v2",
            model_path=model_file,
            manifest_path=manifest_path,
            dataset="exp3",
            metrics={"mAP50": 0.95},
        )

    def test_main_missing_model_file_exits(self, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)

        with patch("sys.argv", [
            "publish",
            "yolo-boundary", "v2", str(tmp_path / "nonexistent.pt"),
            "--manifest", str(manifest_path),
        ]):
            with pytest.raises(SystemExit):
                main()

    def test_main_missing_manifest_exits(self, tmp_path):
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        with patch("sys.argv", [
            "publish",
            "yolo-boundary", "v2", str(model_file),
            "--manifest", str(tmp_path / "nonexistent.yaml"),
        ]):
            with pytest.raises(SystemExit):
                main()

    def test_main_invalid_metrics_json_exits(self, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        with patch("sys.argv", [
            "publish",
            "yolo-boundary", "v2", str(model_file),
            "--manifest", str(manifest_path),
            "--metrics", "not valid json",
        ]):
            with pytest.raises(SystemExit):
                main()

    @patch("ml.publish.publish_model")
    def test_main_without_optional_args(self, mock_publish, tmp_path):
        manifest_path = self._manifest_with_model(tmp_path)
        model_file = tmp_path / "best.pt"
        model_file.write_bytes(b"model")

        with patch("sys.argv", [
            "publish",
            "yolo-boundary", "v2", str(model_file),
            "--manifest", str(manifest_path),
        ]):
            main()

        mock_publish.assert_called_once_with(
            model_name="yolo-boundary",
            version="v2",
            model_path=model_file,
            manifest_path=manifest_path,
            dataset=None,
            metrics=None,
        )
