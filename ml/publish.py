"""
Model Publish CLI
Upload a trained model to GCS and update the manifest in one command.

Usage:
    python -m ml.publish <model-name> <version> <path-to-pt> [options]

Example:
    python -m ml.publish yolo-boundary v3 ./best.pt --dataset "exp4" --metrics '{"mAP50": 0.93}'
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path) as f:
        return yaml.safe_load(f)


def save_manifest(manifest_path: Path, manifest: dict):
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)


def publish_model(
    model_name: str,
    version: str,
    model_path: Path,
    manifest_path: Path,
    dataset: str = None,
    metrics: dict = None,
    store=None,
) -> int:
    """Upload model to GCS and update manifest.

    Args:
        store: Optional GCSModelStore instance (injected for testing).

    Returns the GCS generation number.
    """
    manifest = load_manifest(manifest_path)

    if model_name not in manifest.get("models", {}):
        print(f"Error: Model '{model_name}' not found in manifest.", file=sys.stderr)
        print(f"Available: {list(manifest['models'].keys())}", file=sys.stderr)
        sys.exit(1)

    model_def = manifest["models"][model_name]
    versions = model_def.setdefault("versions", {})

    if version in versions:
        print(f"Warning: Version '{version}' already exists for '{model_name}'. Overwriting.")

    gcs_path = f"{model_name}/{version}/best.pt"
    bucket = manifest["bucket"]

    if store is None:  # pragma: no cover — requires GCS credentials for real store
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
        from app.core.ml.model_store import GCSModelStore
        store = GCSModelStore(bucket)

    print(f"Uploading {model_path} -> gs://{bucket}/{gcs_path}")
    generation = store.upload(model_path, gcs_path)

    version_entry = {
        "gcs_path": gcs_path,
        "gcs_generation": generation,
        "trained_at": str(date.today()),
    }
    if dataset:
        version_entry["dataset"] = dataset
    if metrics:
        version_entry["metrics"] = metrics

    versions[version] = version_entry
    save_manifest(manifest_path, manifest)

    print(f"Published {model_name}:{version} (generation={generation})")
    print(f"Manifest updated at {manifest_path}")
    print(f"To activate: update current_version to '{version}' in {manifest_path} and commit.")

    return generation


def main():
    parser = argparse.ArgumentParser(
        description="Publish a trained model to GCS and update the manifest."
    )
    parser.add_argument("model_name", help="Model name (e.g., yolo-boundary)")
    parser.add_argument("version", help="Version identifier (e.g., v3)")
    parser.add_argument("model_path", type=Path, help="Path to the .pt file")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("ml/models.yaml"),
        help="Path to models.yaml (default: ml/models.yaml)",
    )
    parser.add_argument("--dataset", help="Training dataset name")
    parser.add_argument(
        "--metrics",
        type=str,
        help='Model metrics as JSON (e.g., \'{"mAP50": 0.93}\')',
    )

    args = parser.parse_args()

    if not args.model_path.exists():
        print(f"Error: Model file not found: {args.model_path}", file=sys.stderr)
        sys.exit(1)

    if not args.manifest.exists():
        print(f"Error: Manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    metrics = None
    if args.metrics:
        try:
            metrics = json.loads(args.metrics)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --metrics: {e}", file=sys.stderr)
            sys.exit(1)

    publish_model(
        model_name=args.model_name,
        version=args.version,
        model_path=args.model_path,
        manifest_path=args.manifest,
        dataset=args.dataset,
        metrics=metrics,
    )


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    main()
