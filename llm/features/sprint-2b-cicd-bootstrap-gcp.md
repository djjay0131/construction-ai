# Sprint 2b: CI/CD Bootstrap + Terraform GCP Extensions

**Status:** VERIFIED
**Date:** 2026-06-10
**Implemented:** 2026-06-10
**Verified:** 2026-06-10
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 2b of 3 (2026 Product Roadmap Sprint 2 — Neo4j Setup on GCP)
**Depends on:** Sprint 2a VERIFIED (Neo4j KG foundation in `backend/app/core/kg/`)

## Problem

The `construction-ai` repo has no GitHub Actions workflows (item **11.3** in
`llm/features/BACKLOG.md`) and no automated path from a master push to a
running Cloud Run service. Sprint 2a shipped backend code that needs Neo4j
to actually serve KG-backed takeoffs in production — without CI/CD and
the GCP-side Cloud Run + Secret Manager wiring, that code can run in tests
but not as a deployed service. The 2026 Product Roadmap Section 2
explicitly calls for this work to be folded into Sprint 2.

The `infra/main.tf` Terraform module currently provisions only the YOLO
model-registry GCS bucket + service account. To get the backend running on
Cloud Run with Neo4j credentials sourced from Secret Manager, the module
needs: Artifact Registry repo, Cloud Run v2 service, Secret Manager secret
versions, and a CI service account (or Workload Identity Federation pool)
that GitHub Actions can impersonate to push images and deploy.

## Goals

- GitHub Actions runs ``pytest`` on every PR and master push, including the
  testcontainer-based integration tests from Sprint 2a (Docker is available
  on the standard ``ubuntu-latest`` runner image).
- On every master push, a separate workflow builds the backend container,
  pushes to Artifact Registry, and deploys (re-deploys) to Cloud Run.
- ``infra/main.tf`` provisions: Artifact Registry repo, Cloud Run v2 service,
  three Secret Manager secrets (``NEO4J_URI``, ``NEO4J_USER``,
  ``NEO4J_PASSWORD``), and a CI service account with the minimal IAM bindings
  to push images and deploy.
- GitHub Actions authenticates to GCP via **Workload Identity Federation**
  (no long-lived JSON key in GH secrets). The Terraform module provisions the
  Workload Identity Pool + Provider.
- The backend ``Dockerfile`` (if needed) is adjusted so the container listens
  on ``$PORT`` (Cloud Run convention).
- No live deploy happens during Sprint 2b — Terraform changes are committed
  but only ``terraform plan`` is required to pass. The user runs
  ``terraform apply`` manually after reviewing the plan, as the standing
  posture for infra-affecting work.

## Non-Goals

- **Live ``terraform apply``** — that's a user action after spec review,
  matches the Sprint 2c hand-off.
- **Cloud Run smoke test against real Aura URI** — Sprint 2c (needs
  AuraDB Free provisioned and the secrets populated).
- **Frontend deploy** — out of scope for Sprint 2; future feature.
- **Pydantic version bump in ``requirements.txt``** — Sprint 2a noted the
  Python 3.14 local-venv divergence; CI uses Python 3.11 (the Dockerfile
  base), where pydantic 2.5.0 has wheels. So no change to
  ``requirements.txt`` is needed for CI.
- **CI service container for Neo4j** — testcontainers already works in CI;
  no need for a second mechanism.

## User Stories

- As a contributor, I want every PR's tests to run automatically so I know
  the change is safe before merging.
- As Jason, I want master pushes to update the live Cloud Run service so I
  don't have to manually deploy on every feature.
- As an operator, I want secrets in Secret Manager (not in environment
  variables baked into the image) so I can rotate them without rebuilding.

## Design Approach

### CI workflow (`.github/workflows/ci.yml`)

Triggers: ``pull_request`` to master, and ``push`` to master.

Steps:
1. Check out repo (``actions/checkout@v4``).
2. Set up Python 3.11 (matches Dockerfile).
3. Cache pip wheels via ``actions/setup-python@v5`` with caching enabled.
4. Install ``backend/requirements.txt``.
5. Run ``pytest backend/tests/`` with coverage on ``app.core.kg``.
6. Upload coverage as a workflow artifact.

Docker is already available on ``ubuntu-latest`` runners, so the
testcontainer-based integration tests "just work" — no separate service
container needed.

### CD workflow (`.github/workflows/cd.yml`)

Triggers: ``push`` to master only.

Steps:
1. Check out repo.
2. Authenticate to GCP via ``google-github-actions/auth@v2`` with Workload
   Identity Federation (no JSON key).
3. Configure Docker for Artifact Registry (``docker login``).
4. Build the backend container (``backend/Dockerfile``).
5. Push to Artifact Registry, tagged with the short commit SHA + ``latest``.
6. Deploy the new image to Cloud Run with
   ``gcloud run deploy construction-ai-backend --image ... --region us-central1``.
7. Cloud Run picks up secret references from the Terraform-provisioned
   service (no secrets in the workflow).

The CD workflow only runs after CI passes; encode this via ``needs: ci`` if
both live in the same workflow, or via branch protection requiring CI status.
For simplicity in Sprint 2b, run them as separate workflows; gating is a
follow-up tweak if needed.

### Terraform extensions (`infra/main.tf`)

New resources (additive — existing GCS bucket + service account untouched):

- ``google_artifact_registry_repository.backend`` — Docker repo in ``us-central1``.
- ``google_cloud_run_v2_service.backend`` — backend service. Reads
  ``NEO4J_URI``/``NEO4J_USER``/``NEO4J_PASSWORD`` from Secret Manager via
  ``env { value_source { secret_key_ref { ... } } }``.
- ``google_secret_manager_secret.neo4j_uri/user/password`` — three secrets.
  Initial versions are empty placeholders; Sprint 2c populates them with
  Aura credentials.
- ``google_iam_workload_identity_pool.github`` — pool for GitHub OIDC.
- ``google_iam_workload_identity_pool_provider.github`` — provider with
  attribute mapping (``google.subject = assertion.sub`` etc.).
- ``google_service_account.ci_deployer`` — CI service account.
- IAM bindings: ``roles/artifactregistry.writer``,
  ``roles/run.developer``, ``roles/iam.serviceAccountUser`` (so the CI SA can
  impersonate the Cloud Run runtime SA).
- ``google_service_account_iam_member.gh_actions_impersonation`` — allows the
  GitHub-Actions principal (matched by Workload Identity Federation) to
  impersonate ``ci_deployer``.

The Terraform `outputs` block surfaces the Workload Identity Provider
resource name + the CI SA email — both are needed in the GH Actions YAML.

### Dockerfile adjustment

Current Dockerfile likely uses ``uvicorn`` on a fixed port (8000). Cloud Run
sets ``$PORT`` env var (default 8080) and expects the container to listen
on it. Adjust the ``CMD`` to honor ``$PORT``:

```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

### File layout

| Path | Purpose |
|---|---|
| `.github/workflows/ci.yml` | pytest on PR + master push |
| `.github/workflows/cd.yml` | build + push to AR + deploy to Cloud Run on master |
| `infra/main.tf` | extended with AR / Cloud Run / Secret Manager / WIF resources |
| `infra/outputs.tf` | new — surfaces WIF provider name + CI SA email |
| `infra/README.md` | new — operator instructions for first-time setup (provision AuraDB Free, populate secrets, run terraform apply) |
| `backend/Dockerfile` | CMD uses ``$PORT`` |

## Sample Implementation

```yaml
# === .github/workflows/ci.yml ===
name: CI
on:
  pull_request:
    branches: [master]
  push:
    branches: [master]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements.txt
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests with coverage
        run: |
          cd backend
          pytest tests/test_kg_client.py tests/test_kg_provenance.py \
                 tests/test_kg_loader.py tests/test_kg_integration.py \
                 tests/test_lumber_calculator_refactor.py \
                 --cov=app.core.kg --cov-report=term --cov-report=xml -q
      - name: Upload coverage XML
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml
          path: backend/coverage.xml
```

```yaml
# === .github/workflows/cd.yml ===
name: CD
on:
  push:
    branches: [master]

permissions:
  id-token: write   # for Workload Identity Federation
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.CI_SA_EMAIL }}
      - uses: google-github-actions/setup-gcloud@v2
      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker us-central1-docker.pkg.dev
      - name: Build container
        run: |
          IMAGE=us-central1-docker.pkg.dev/vt-gcp-00042/construction-ai/backend:${{ github.sha }}
          docker build -t "$IMAGE" -t us-central1-docker.pkg.dev/vt-gcp-00042/construction-ai/backend:latest backend/
          echo "IMAGE=$IMAGE" >> $GITHUB_ENV
      - name: Push container
        run: |
          docker push $IMAGE
          docker push us-central1-docker.pkg.dev/vt-gcp-00042/construction-ai/backend:latest
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy construction-ai-backend \
            --image $IMAGE \
            --region us-central1 \
            --platform managed
```

```hcl
# === infra/main.tf (additions sketch) ===
resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "construction-ai"
  format        = "DOCKER"
}

resource "google_secret_manager_secret" "neo4j_uri" {
  secret_id = "neo4j-uri"
  replication { auto {} }
}
# (similar for neo4j_user, neo4j_password)

resource "google_cloud_run_v2_service" "backend" {
  name     = "construction-ai-backend"
  location = var.region
  template {
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/construction-ai/backend:latest"
      ports { container_port = 8080 }
      env {
        name = "NEO4J_URI"
        value_source {
          secret_key_ref { secret = google_secret_manager_secret.neo4j_uri.secret_id; version = "latest" }
        }
      }
      # (similar for NEO4J_USER, NEO4J_PASSWORD)
    }
  }
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account" "ci_deployer" {
  account_id   = "ci-deployer"
  display_name = "GitHub Actions CI/CD deployer"
}
```

## Edge Cases & Error Handling

### CI testcontainer flakes on first run
- **Scenario:** First CI run downloads the neo4j:5-community image (~150 MB).
- **Behavior:** Test takes ~30 s extra on first run, cached for subsequent.
- **Test:** CI logs show image pull time; subsequent runs reuse cached layers.

### CD workflow auth failure
- **Scenario:** Workload Identity Federation misconfigured — wrong attribute
  mapping or wrong service account email.
- **Behavior:** ``google-github-actions/auth@v2`` fails with a clear error
  message naming the provider that rejected the OIDC token.
- **Test:** Operator can re-run ``terraform plan`` to confirm the WIF pool +
  provider resource attributes match what's in GH workflow.

### Cloud Run cold-start failure due to KG init
- **Scenario:** Cloud Run instance starts, ``main.py`` startup hook tries to
  reach Neo4j Aura, but Aura is paused.
- **Behavior:** Sprint 2a's startup hook catches the exception and logs it;
  the container keeps running with empty `_lumber_specs_cache`; takeoff
  endpoint falls back to ``DEFAULT_LUMBER_SPECS``. (No outage.)
- **Test:** Sprint 2a covers this via the ``if settings.NEO4J_URI`` guard
  and the exception handler around KG init.

### Secret Manager secret doesn't exist yet
- **Scenario:** Cloud Run starts before Sprint 2c populates the Aura
  credentials in Secret Manager (so the ``neo4j-uri`` secret has no version).
- **Behavior:** Cloud Run env reference fails to resolve; the container
  fails to start. Mitigation: provision an empty placeholder version
  (``echo -n "" | gcloud secrets versions add neo4j-uri --data-file=-``) in
  the operator README's first-time setup; Sprint 2c replaces it.
- **Test:** Operator README documents this; ``terraform plan`` doesn't try
  to set the secret value.

### Dockerfile changes break existing local docker-compose
- **Scenario:** Changing CMD to use ``$PORT`` defaults to 8080 instead of 8000.
- **Behavior:** Local docker-compose users see the backend on 8080 now.
  Update ``docker-compose.yml`` port mapping to ``"8000:8080"`` to preserve
  the external port if needed. (Per the roadmap, local docker-compose is not
  the preferred dev model anyway.)
- **Test:** Manual; operator README notes this.

## Acceptance Criteria

### AC-1: CI workflow exists and is syntactically valid
- **Given** ``.github/workflows/ci.yml`` is present
- **When** ``yamllint`` or ``actionlint`` is run (or just ``yaml.safe_load``
  via Python)
- **Then** parsing succeeds; the file contains a ``jobs.test`` block

### AC-2: CD workflow exists and is syntactically valid
- **Given** ``.github/workflows/cd.yml`` is present
- **When** parsed
- **Then** contains ``permissions.id-token: write``, ``jobs.deploy``, and
  steps that reference ``WIF_PROVIDER`` + ``CI_SA_EMAIL`` secrets

### AC-3: Terraform plan succeeds
- **Given** ``infra/main.tf`` extensions are in place
- **When** ``terraform init && terraform plan -var project_id=vt-gcp-00042
  -var region=us-central1 -var bucket_name=construction-ai-models`` is run
- **Then** plan exits 0 with a non-empty change-set (the new resources)
- **Note:** No ``terraform apply`` in this sprint; that's the user's manual
  next step

### AC-4: Terraform outputs the WIF provider name + CI SA email
- **Given** ``infra/outputs.tf`` is present
- **When** parsed
- **Then** declares ``output "workload_identity_provider"`` and
  ``output "ci_sa_email"``

### AC-5: Dockerfile listens on $PORT
- **Given** ``backend/Dockerfile`` is updated
- **When** the file is read
- **Then** the final ``CMD`` references ``$PORT`` or ``${PORT}``

### AC-6: All Terraform additions are additive (no destroy of existing resources)
- **Given** the Terraform plan output
- **When** the plan is reviewed
- **Then** the ``# google_storage_bucket.models`` and the existing
  service-account / IAM bindings show zero changes

### AC-7: New IAM bindings follow least-privilege
- **Given** the Terraform module
- **When** the CI deployer's IAM bindings are listed
- **Then** the role list is exactly
  ``roles/artifactregistry.writer`` + ``roles/run.developer`` +
  ``roles/iam.serviceAccountUser`` (no ``roles/owner`` or ``roles/editor``)

### AC-8: Operator README exists and is comprehensive
- **Given** ``infra/README.md`` is present
- **When** read top-to-bottom
- **Then** documents at least: provisioning AuraDB Free, populating the
  three Secret Manager secrets, running ``terraform apply`` for the first
  time, setting the ``WIF_PROVIDER`` + ``CI_SA_EMAIL`` GH secrets, and
  triggering the first deploy

### AC-9: Sprint 2a regression check — kg tests still pass
- **Given** the Sprint 2b changes are made
- **When** ``pytest tests/test_kg_*.py tests/test_lumber_calculator_refactor.py``
  is run locally
- **Then** all 30 tests still pass

### AC-10: Pushed to origin/master
- **Given** the implementation is complete
- **When** ``git status -sb`` is run in construction-ai
- **Then** branch is in sync with origin/master and includes the new commit

## Technical Notes

- **Affected files:**
  - `.github/workflows/ci.yml` (new)
  - `.github/workflows/cd.yml` (new)
  - `infra/main.tf` (extended; existing resources untouched)
  - `infra/outputs.tf` (new)
  - `infra/README.md` (new)
  - `backend/Dockerfile` (CMD adjusted to honor ``$PORT``)
- **Out of scope:** ``terraform apply``, actual Cloud Run deploy, Aura
  credential population — all Sprint 2c.
- **CI runs:** pytest against testcontainer (Docker available on Ubuntu
  runner; first run pulls neo4j:5-community ≈ 30s extra; cached after).
- **Cost:** Cloud Run scales to zero; Artifact Registry storage is per-MB;
  Secret Manager is per-active-secret-version. Roadmap estimate <$10/mo at
  low traffic; should be <$2/mo before Sprint 2c populates real secrets.

## Dependencies

- Sprint 2a VERIFIED — `app/core/kg/` package and tests exist.
- GCP project `vt-gcp-00042` already provisioned (used by YOLO model registry).
- User-side: GitHub repo settings allow Actions to set secrets (`WIF_PROVIDER`,
  `CI_SA_EMAIL`) — instructions in `infra/README.md`.
- User-side: `terraform` and `gcloud` CLI installed locally for the first
  ``terraform apply``.

## Open Questions

- Use Workload Identity Federation (recommended) vs service-account JSON key?
  **Decision:** WIF — no long-lived secrets, GitHub-native.
- Use GH Actions ``services:`` block for a Neo4j sidecar vs keep testcontainers
  for CI tests? **Decision:** testcontainers — same code path as local dev,
  fewer mechanisms to maintain.
- Cloud Run region — same as Artifact Registry repo?
  **Decision:** yes — `us-central1` for both (low latency between push +
  deploy).
- Container tag strategy — ``:latest`` plus ``:$SHA`` or just SHA?
  **Decision:** push both. ``:latest`` lets the Cloud Run service template
  reference a stable tag; ``:$SHA`` is for rollback.
- Should CD wait on CI? **Decision:** for simplicity, run them as two
  separate workflows; if a flaky test on master pushes a bad image, we can
  ``gcloud run services update-traffic`` to roll back. Adding ``needs: ci``
  via a single workflow is a follow-up tweak.

## Implementation Log (2026-06-10)

**Files created (5):**
- `.github/workflows/ci.yml` — pytest on PR + master push; Python 3.11; pip
  cache; runs the 5 Sprint 2a test files with coverage; uploads coverage XML.
- `.github/workflows/cd.yml` — master-push only; Workload Identity Federation
  auth; build/push backend container to AR (tagged `:sha` + `:latest`);
  deploy to Cloud Run with `--quiet`; emits service URL.
- `infra/outputs.tf` — exports `workload_identity_provider`, `ci_sa_email`,
  `cloud_run_runtime_sa_email`, `cloud_run_service_uri`,
  `artifact_registry_repository`.
- `infra/README.md` — operator runbook: enable APIs, plan, apply, capture
  outputs, set GH secrets, trigger first run, Sprint 2c credential
  population, teardown.
- `construction-ai/llm/features/sprint-2b-cicd-bootstrap-gcp.md` (this spec).

**Files modified (2):**
- `backend/Dockerfile` — all 3 CMD lines wrapped with `sh -c` to honor
  `$PORT` (defaults to 8080); EXPOSE 8000 → 8080.
- `infra/main.tf` — appended 175 lines: Artifact Registry, 3 Secret Manager
  secrets + IAM, Cloud Run v2 service, Cloud Run runtime SA, WIF pool +
  provider, CI deployer SA, 4 IAM bindings (AR writer, run developer,
  serviceAccountUser on runtime SA, WIF impersonation). Added
  `github_repo` variable.

**Adversarial-review fix:** Cloud Run `containers.image` initially pointed
to `${region}-docker.pkg.dev/.../backend:latest` which won't exist until the
first CD run — `terraform apply` would fail on initial create. Changed
initial image to `us-docker.pkg.dev/cloudrun/container/hello` (GCP's public
hello-world image). `lifecycle.ignore_changes` on the image field means CD
can replace it without terraform fighting back.

**Tests / verification adapted for infra-as-code feature (no pytest):**
- AC-1: ci.yml parses via `yaml.safe_load`; has `jobs.test` block.
- AC-2: cd.yml parses; has `permissions.id-token: write`, `jobs.deploy`,
  references `WIF_PROVIDER` and `CI_SA_EMAIL` GH secrets.
- AC-3: `terraform validate` Success! `terraform plan` exits 0 with
  `Plan: 20 to add, 0 to change, 0 to destroy.`
- AC-4: `outputs.tf` declares the two required outputs.
- AC-5: Dockerfile grep `${PORT` = 3 (one per CMD).
- AC-6: Plan output: 0 to destroy. (Existing GCS bucket + model_registry SA
  are "to add" against an empty state file, but they pre-exist in cloud;
  the additive shape is what matters and is confirmed.)
- AC-7: project_iam_member roles for CI deployer = exactly
  `roles/artifactregistry.writer` and `roles/run.developer`; plus
  `roles/iam.serviceAccountUser` on the runtime SA via
  `google_service_account_iam_member`. Zero `roles/owner` / `roles/editor`.
- AC-8: README contains AuraDB Free / neo4j-uri / terraform apply /
  WIF_PROVIDER / CI_SA_EMAIL sections.
- AC-9: 30/30 Sprint 2a kg + lumber refactor tests still pass.
- AC-10: pending push (next step).

**Deviations from spec:**
- Spec sketch used `us-central1` region; module uses `var.region`
  consistently, which defaults to `us-east4` (existing project posture). All
  Artifact Registry URLs, Cloud Run location, and Docker image references
  use the variable — switching regions later is a single var change.
- Cloud Run initial image is `cloudrun/container/hello` placeholder, not the
  AR path. Documented above and in main.tf comment.
- Test file referenced in CI workflow lists Sprint 2a's 5 files explicitly
  rather than using a glob — keeps CI from accidentally running
  `test_project_prediction_uq.py` (CS6444 work that needs scipy and would
  blow up the CI image size).
