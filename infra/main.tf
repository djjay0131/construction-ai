terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "vt-gcp-00042"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-east4"
}

variable "bucket_name" {
  description = "GCS bucket name for model storage"
  type        = string
  default     = "construction-ai-models"
}

# ─── GCS Bucket for YOLO model weights ───────────────────────────────────────

resource "google_storage_bucket" "models" {
  name     = var.bucket_name
  location = var.region

  # Prevent accidental deletion of the bucket
  force_destroy = false

  # Enable object versioning — overwrites create new versions, nothing is lost
  versioning {
    enabled = true
  }

  # Lifecycle policy:
  # 1. Delete noncurrent versions older than 90 days
  # 2. BUT always keep at least 1 previous version (num_newer_versions = 1)
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 90
      num_newer_versions         = 1
    }
    action {
      type = "Delete"
    }
  }

  # Uniform bucket-level access (simpler IAM, no per-object ACLs)
  uniform_bucket_level_access = true
}

# ─── Service account for model access ────────────────────────────────────────

resource "google_service_account" "model_registry" {
  account_id   = "model-registry"
  display_name = "Model Registry Service Account"
  description  = "Used by the Construction AI backend to download/upload YOLO models"
}

# Grant the service account read/write on the models bucket
resource "google_storage_bucket_iam_member" "model_registry_object_admin" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.model_registry.email}"
}

# Generate a JSON key for the service account
resource "google_service_account_key" "model_registry_key" {
  service_account_id = google_service_account.model_registry.name
}

# ─── Outputs ─────────────────────────────────────────────────────────────────

output "bucket_name" {
  value       = google_storage_bucket.models.name
  description = "GCS bucket for model storage"
}

output "bucket_url" {
  value       = google_storage_bucket.models.url
  description = "GCS bucket URL"
}

output "service_account_email" {
  value       = google_service_account.model_registry.email
  description = "Service account email for model access"
}

output "service_account_key" {
  value       = base64decode(google_service_account_key.model_registry_key.private_key)
  description = "Service account JSON key (save to a file, set GOOGLE_APPLICATION_CREDENTIALS)"
  sensitive   = true
}
