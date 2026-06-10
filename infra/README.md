# Infrastructure — Operator Runbook

Terraform module for the Construction.AI GCP infrastructure.
Project: `vt-gcp-00042`. Region: `us-east4`.

This module provisions:
- **YOLO model registry** — GCS bucket + service account (Phase 0, already
  deployed).
- **Sprint 2b** — Artifact Registry, Cloud Run, Secret Manager (Neo4j creds),
  Workload Identity Federation for GitHub Actions CI/CD.

## First-Time Setup

### 1. Enable required GCP APIs

```bash
gcloud config set project vt-gcp-00042
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com
```

### 2. Run terraform plan + review

```bash
cd infra
terraform init
terraform plan -out tfplan
```

Review the plan. Expected new resources (additive — existing GCS bucket
and model-registry service account stay untouched):

- 1× `google_artifact_registry_repository`
- 3× `google_secret_manager_secret` (neo4j-uri / neo4j-user / neo4j-password)
- 3× `google_secret_manager_secret_iam_member` (runtime SA reads each secret)
- 1× `google_cloud_run_v2_service`
- 2× `google_service_account` (cr-backend-runtime, ci-deployer)
- 1× `google_iam_workload_identity_pool`
- 1× `google_iam_workload_identity_pool_provider`
- 2× `google_project_iam_member` (CI deployer's least-privilege bindings)
- 2× `google_service_account_iam_member` (CI act-as-runtime, GH WIF
  impersonate-CI)

### 3. Apply

```bash
terraform apply tfplan
```

The first `terraform apply` provisions the Cloud Run service with a
placeholder image pointer (`backend:latest` in Artifact Registry). The
first revision will fail its readiness probe until the CI/CD workflow
pushes the first image — that's expected.

### 4. Capture outputs

```bash
terraform output workload_identity_provider
terraform output ci_sa_email
```

Copy these two values.

### 5. Add GitHub Actions secrets

Go to GitHub → repo → Settings → Secrets and variables → Actions → New
repository secret. Add two:

- `WIF_PROVIDER` — paste the `workload_identity_provider` output.
  Format: `projects/<num>/locations/global/workloadIdentityPools/github-actions/providers/github`.
- `CI_SA_EMAIL` — paste the `ci_sa_email` output.
  Format: `ci-deployer@vt-gcp-00042.iam.gserviceaccount.com`.

### 6. Trigger the first CI + CD run

```bash
git commit --allow-empty -m "Trigger first CI/CD run"
git push origin master
```

Watch the runs:

```bash
gh run list --limit 3
```

CI runs ~2 min (Python install + pytest). CD runs ~5 min (Docker build +
push + Cloud Run deploy).

### 7. AuraDB Free Provisioning

Aura Free has no Terraform provider, so this is a one-time manual web flow:

1. Go to <https://console.neo4j.io/> and sign up / sign in.
2. Click **New Instance** → **AuraDB Free**.
3. Choose region closest to `us-east4` (e.g. `aws-us-east-1`).
4. Aura generates a password. **Copy it now** — you won't see it again.
5. Wait ~1 minute for the instance to provision.
6. Copy the connection URI from the instance details page. Format:
   `bolt+s://xxxxxxxx.databases.neo4j.io`.

You now have three values to feed to GCP Secret Manager:
- **URI:** `bolt+s://xxxxxxxx.databases.neo4j.io`
- **User:** `neo4j` (Aura's default; don't change)
- **Password:** the value Aura generated in step 4

### 8. Populate Neo4j Aura credentials in Secret Manager

Run from any shell authenticated to `vt-gcp-00042`:

```bash
echo -n "bolt+s://xxxxxxxx.databases.neo4j.io" \
  | gcloud secrets versions add neo4j-uri --data-file=-
echo -n "neo4j" \
  | gcloud secrets versions add neo4j-user --data-file=-
echo -n "<aura-generated-password>" \
  | gcloud secrets versions add neo4j-password --data-file=-
```

Cloud Run automatically picks up the new secret versions on the next
revision. Force a revision rollover via:

```bash
gcloud run services update construction-ai-backend \
  --region us-east4 \
  --update-secrets=NEO4J_URI=neo4j-uri:latest,NEO4J_USER=neo4j-user:latest,NEO4J_PASSWORD=neo4j-password:latest
```

(Or just push any commit to master; the CD workflow forces a new revision.)

### 9. First Live Smoke Test

After the secrets are populated and a new Cloud Run revision picks them up,
run the smoke test from your laptop:

```bash
URL=$(gcloud run services describe construction-ai-backend \
  --region us-east4 --format='value(status.url)')

python backend/scripts/smoke_test.py --url "$URL"
```

Expected output (last line):
```
PASS: kg_status=ready, lumber_specs_loaded=6
```

If `kg_status` is `error`, check Cloud Run logs:
```bash
gcloud run services logs read construction-ai-backend --region us-east4 --limit 50
```

If you haven't populated Secret Manager yet and want to confirm Cloud Run
itself is reachable, pass `--allow-disabled`:

```bash
python backend/scripts/smoke_test.py --url "$URL" --allow-disabled
```

The CD workflow runs this smoke test automatically on every master push
(without `--allow-disabled`), so any production-bound revision must report
`ready`.

## Day-to-Day

- Code changes to `backend/`: CD workflow auto-deploys on master push.
- Aura credential rotation: `gcloud secrets versions add` a new value;
  Cloud Run picks it up on next revision.
- Aura idle-pause (Free tier pauses after 30 days idle): Cloud Run startup
  hook logs the failure and falls back to `DEFAULT_LUMBER_SPECS` — no
  outage, just a degraded mode until Aura is resumed.

## Cost

Per the 2026 Product Roadmap Section 2 estimate: **<$10/mo** combined
(Cloud Run scales to zero; Secret Manager ~$0.06 per active version per
month; Artifact Registry storage per GB).

## Teardown

To destroy Sprint 2b resources without removing the YOLO model registry:

```bash
terraform destroy \
  -target google_cloud_run_v2_service.backend \
  -target google_artifact_registry_repository.backend \
  -target google_secret_manager_secret.neo4j_uri \
  -target google_secret_manager_secret.neo4j_user \
  -target google_secret_manager_secret.neo4j_password
```

(WIF pool and CI deployer SA can be kept for future use.)
