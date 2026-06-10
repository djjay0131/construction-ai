# Sprint 2b outputs — surfaces the values GitHub Actions and operators need.

output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Full resource name of the GitHub WIF provider; copy this into the WIF_PROVIDER GitHub Actions secret."
}

output "ci_sa_email" {
  value       = google_service_account.ci_deployer.email
  description = "Email of the CI deployer service account; copy this into the CI_SA_EMAIL GitHub Actions secret."
}

output "cloud_run_runtime_sa_email" {
  value       = google_service_account.cloud_run_runtime.email
  description = "Email of the Cloud Run runtime service account; reference for audit/logging."
}

output "cloud_run_service_uri" {
  value       = google_cloud_run_v2_service.backend.uri
  description = "Cloud Run service URL once the first deploy completes."
}

output "artifact_registry_repository" {
  value       = "${google_artifact_registry_repository.backend.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}"
  description = "Docker registry path prefix; CD uses this to tag images before pushing."
}
