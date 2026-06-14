# Infrastructure — Operator Runbook

Terraform module for the Construction.AI GCP infrastructure.
Project: `vt-gcp-00042`. Region: `us-east4`.

This module provisions:
- **YOLO model registry** — GCS bucket + service account (Phase 0).
- **Sprint 2b** — Artifact Registry, Cloud Run, Secret Manager (Neo4j
  credentials), Workload Identity Federation for GitHub Actions CI/CD.
- **Sprint 2c (self-host pivot)** — Compute Engine VM running Neo4j
  Community Edition 5, reserved internal IP, Serverless VPC Access
  connector, and the firewall rules wiring it all together.

**There is no external Neo4j Aura dependency.** Everything lives in
`vt-gcp-00042`. No third-party signups required.

## First-Time Setup

### 1. Enable required GCP APIs

```bash
gcloud config set project vt-gcp-00042
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  compute.googleapis.com \
  vpcaccess.googleapis.com
```

### 2. Import existing model-registry resources

If you've already deployed the YOLO model registry (gs://construction-ai-models
+ model-registry SA), import them into local state so the next plan doesn't
try to recreate them:

```bash
cd infra
terraform init
terraform import google_storage_bucket.models construction-ai-models
terraform import google_service_account.model_registry \
  projects/vt-gcp-00042/serviceAccounts/model-registry@vt-gcp-00042.iam.gserviceaccount.com
terraform import 'google_storage_bucket_iam_member.model_registry_object_admin' \
  'b/construction-ai-models roles/storage.objectAdmin serviceAccount:model-registry@vt-gcp-00042.iam.gserviceaccount.com'
```

(If you're starting from a clean GCP project, skip this step.)

### 3. Plan + apply

```bash
terraform plan -out tfplan
# review the plan — expect ~28 resources to add
terraform apply tfplan
```

What gets created (in addition to the existing YOLO registry):

- **Cloud Run + AR + IAM**: Artifact Registry repo, Cloud Run v2 service,
  Cloud Run runtime SA, CI deployer SA, WIF pool + provider, IAM bindings.
- **Secret Manager**: 3 secrets (`neo4j-uri`, `neo4j-user`, `neo4j-password`)
  with versions populated by Terraform (URI = VM private IP, password =
  `random_password.neo4j.result`).
- **Neo4j**: `e2-small` VM in `us-east4-a` running Debian 12 + Neo4j 5
  (installed via the `infra/scripts/install_neo4j.sh` startup script),
  reserved internal IP, dedicated runtime SA with `secretAccessor` on
  `neo4j-password`, 2 firewall rules (bolt from VPC connector, SSH from
  IAP).
- **Bridge**: Serverless VPC Access connector so Cloud Run can reach the
  VM's private IP.

First apply typically takes ~5 minutes. The VM startup script runs
afterwards (apt-installs Neo4j, reads password from SM, starts the
service); allow another 3–5 minutes after `apply` completes for Neo4j
to come online.

### 4. Capture Terraform outputs

```bash
terraform output workload_identity_provider
terraform output ci_sa_email
```

Copy these two values.

### 5. Set GitHub Actions secrets

```bash
gh secret set WIF_PROVIDER --body "$(terraform output -raw workload_identity_provider)"
gh secret set CI_SA_EMAIL  --body "$(terraform output -raw ci_sa_email)"
```

### 6. Trigger the first CI + CD run

```bash
git commit --allow-empty -m "Trigger first CI/CD run"
git push origin master
```

Watch the runs:

```bash
gh run list --limit 3
```

CI ~3 min (Python install + pytest). CD ~5 min (Docker build + push +
Cloud Run deploy + smoke test). The smoke test verifies the deployed
backend can reach Neo4j over the VPC connector and that the seed +
loader ran successfully.

## Day-to-Day

- **Code changes to `backend/`** → CD auto-deploys on master push and
  smoke-tests against Neo4j.
- **Rotate the Neo4j password** → run `terraform taint random_password.neo4j
  && terraform apply` (rare; only if a credential leak is suspected).
  Cloud Run picks up the new value on next revision.
- **Stop the VM to save money during long idle periods** →
  `gcloud compute instances stop construction-ai-neo4j --zone=us-east4-a`.
  Restart with `start`. Neo4j data persists on the boot disk.

## Verify Neo4j is healthy

From any shell authenticated to `vt-gcp-00042`:

```bash
gcloud compute ssh construction-ai-neo4j --zone=us-east4-a --tunnel-through-iap \
  --command='sudo systemctl is-active neo4j'
# → "active"

PWD=$(gcloud secrets versions access latest --secret=neo4j-password)
gcloud compute ssh construction-ai-neo4j --zone=us-east4-a --tunnel-through-iap \
  --command="cypher-shell -u neo4j -p '$PWD' -a bolt://localhost:7687 'RETURN 1;'"
# → "1"
```

Or hit the deployed Cloud Run smoke endpoint:

```bash
URL=$(gcloud run services describe construction-ai-backend \
  --region us-east4 --format='value(status.url)')

python backend/scripts/smoke_test.py --url "$URL"
# → "PASS: kg_status=ready, lumber_specs_loaded=6"
```

## Cost

Per the 2026 Product Roadmap Section 2 estimate, refined after self-host
pivot:

| Component | Estimated cost |
|---|---|
| Compute Engine `e2-small` (always-on) | ~$13/mo |
| Persistent disk 20 GB `pd-balanced` | ~$2/mo |
| Serverless VPC Access connector | ~$8.50/mo (always-on) |
| Cloud Run (scales to zero) | <$1/mo at low traffic |
| Artifact Registry storage | ~$0.10/mo (one image) |
| Secret Manager (3 active versions) | ~$0.20/mo |
| Network egress | <$1/mo at low traffic |
| **Total** | **~$25/mo** |

Higher than the original AuraDB Free estimate (<$10/mo) because the VPC
connector and the always-on VM aren't free, but the VM stays up regardless
of dev gaps and there's no Aura signup or 30-day idle-pause concern.

To cut cost during long idle periods, stop the VM
(`gcloud compute instances stop construction-ai-neo4j --zone=us-east4-a`)
and the VPC connector (delete + recreate via Terraform). Both come back
clean.

## Teardown

To destroy Sprint 2 resources without removing the YOLO model registry:

```bash
terraform destroy \
  -target google_compute_instance.neo4j \
  -target google_vpc_access_connector.cloud_run_to_neo4j \
  -target google_cloud_run_v2_service.backend \
  -target google_artifact_registry_repository.backend \
  -target google_secret_manager_secret.neo4j_uri \
  -target google_secret_manager_secret.neo4j_user \
  -target google_secret_manager_secret.neo4j_password
```

WIF pool + CI deployer SA can be kept for future use.
