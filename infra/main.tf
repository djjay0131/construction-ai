terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
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

# =============================================================================
# Sprint 2b additions: Artifact Registry + Cloud Run + Secret Manager + WIF
# Required APIs (the operator enables these manually once before the first
# apply; see infra/README.md): artifactregistry.googleapis.com,
# run.googleapis.com, secretmanager.googleapis.com, iamcredentials.googleapis.com
# =============================================================================

variable "github_repo" {
  description = "GitHub repository allowed to impersonate the CI deployer SA (format: owner/name)"
  type        = string
  default     = "djjay0131/construction-ai"
}

# ─── Artifact Registry for backend container images ─────────────────────────

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "construction-ai"
  description   = "Docker images for the Construction AI backend (Cloud Run target)"
  format        = "DOCKER"
}

# ─── Secret Manager: Neo4j Aura credentials ──────────────────────────────────
# The resources here only create the secret containers; the operator populates
# the values via `gcloud secrets versions add` after provisioning AuraDB Free
# (Sprint 2c). Until then, Cloud Run startup logs the missing-credential case
# and falls back to DEFAULT_LUMBER_SPECS.

resource "google_secret_manager_secret" "neo4j_uri" {
  secret_id = "neo4j-uri"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "neo4j_user" {
  secret_id = "neo4j-user"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "neo4j_password" {
  secret_id = "neo4j-password"
  replication {
    auto {}
  }
}

# Secret values are owned by Terraform now that Neo4j runs on a GCE VM we
# also manage. The URI points at the VM's reserved internal IP; the password
# comes from random_password (see neo4j_vm.tf).
resource "google_secret_manager_secret_version" "neo4j_uri" {
  secret      = google_secret_manager_secret.neo4j_uri.id
  secret_data = "bolt://${google_compute_address.neo4j_internal.address}:7687"
}

resource "google_secret_manager_secret_version" "neo4j_user" {
  secret      = google_secret_manager_secret.neo4j_user.id
  secret_data = "neo4j"
}

resource "google_secret_manager_secret_version" "neo4j_password" {
  secret      = google_secret_manager_secret.neo4j_password.id
  secret_data = random_password.neo4j.result
}

# ─── Cloud Run runtime service account ───────────────────────────────────────
# Distinct from the CI deployer SA below. This SA is what the Cloud Run
# container runs *as*; it needs read access to the three secrets.

resource "google_service_account" "cloud_run_runtime" {
  account_id   = "cr-backend-runtime"
  display_name = "Construction AI backend Cloud Run runtime SA"
  description  = "Identity the backend container runs as on Cloud Run; reads Neo4j creds from Secret Manager."
}

resource "google_secret_manager_secret_iam_member" "runtime_uri_access" {
  secret_id = google_secret_manager_secret.neo4j_uri.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_user_access" {
  secret_id = google_secret_manager_secret.neo4j_user.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_password_access" {
  secret_id = google_secret_manager_secret.neo4j_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_runtime.email}"
}

# ─── Cloud Run backend service ───────────────────────────────────────────────
# First-time apply creates a placeholder service whose image points at the
# Artifact Registry path the CD workflow will push to. Cloud Run will fail
# the initial readiness probe until the CI pipeline pushes the first image;
# that's expected, and resolves automatically on the first CD run.

resource "google_cloud_run_v2_service" "backend" {
  name     = "construction-ai-backend"
  location = var.region

  template {
    service_account = google_service_account.cloud_run_runtime.email

    # VPC connector so Cloud Run can reach the Neo4j VM's internal IP.
    vpc_access {
      connector = google_vpc_access_connector.cloud_run_to_neo4j.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      # Initial revision uses GCP's public hello-world image so that the first
      # `terraform apply` can succeed before CI/CD has ever pushed an image.
      # The CD workflow replaces this with the real backend image on the first
      # master push. lifecycle.ignore_changes (below) prevents Terraform from
      # reverting that on subsequent applies.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      # Backend imports torch + ultralytics + cv2 + numpy at startup; the
      # 512 MiB Cloud Run default isn't enough (observed 2112 MiB cold-start).
      # Sized to fit comfortably with headroom for request handling.
      resources {
        limits = {
          memory = "4Gi"
          cpu    = "2"
        }
      }

      ports {
        container_port = 8080
      }

      env {
        name = "NEO4J_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_uri.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "NEO4J_USER"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_user.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "NEO4J_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_password.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  # Allow CD to update without forcing every revision to take 100% traffic
  # before the rollout completes.
  lifecycle {
    ignore_changes = [
      # The CD workflow re-tags `:latest`; without this, Terraform would
      # show a perpetual diff. The image is owned by CD, not Terraform.
      template[0].containers[0].image,
    ]
  }
}

# ─── Workload Identity Federation for GitHub Actions ────────────────────────

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "Pool for GitHub Actions OIDC tokens"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Restrict to a single repo so a misconfigured provider doesn't accept
  # tokens from any GitHub org.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ─── CI deployer SA (impersonated by GitHub Actions via WIF) ────────────────

resource "google_service_account" "ci_deployer" {
  account_id   = "ci-deployer"
  display_name = "GitHub Actions CI/CD deployer"
  description  = "Pushes images to Artifact Registry and deploys to Cloud Run."
}

# Least-privilege roles for the CI deployer SA. Intentionally NOT
# roles/owner or roles/editor.

resource "google_project_iam_member" "ci_deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.ci_deployer.email}"
}

resource "google_project_iam_member" "ci_deployer_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.ci_deployer.email}"
}

resource "google_service_account_iam_member" "ci_deployer_act_as_runtime" {
  service_account_id = google_service_account.cloud_run_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.ci_deployer.email}"
}

# Allow the GitHub repo (via WIF) to impersonate the CI deployer SA.
resource "google_service_account_iam_member" "gh_actions_impersonates_ci_deployer" {
  service_account_id = google_service_account.ci_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
