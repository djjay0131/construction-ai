# =============================================================================
# Self-hosted Neo4j Community Edition on Compute Engine.
# Replaces AuraDB Free in the Sprint 2 design — everything in vt-gcp-00042,
# no external SaaS, no manual signup, no 30-day idle pause.
# Cloud Run reaches the VM via a Serverless VPC Access Connector.
# =============================================================================

# Random password generated once at apply time; persisted in Secret Manager
# (versions block below) and read by the VM's startup script on first boot.
resource "random_password" "neo4j" {
  length  = 32
  special = false # avoid shell-escaping headaches in the startup script
}

# Reserve a stable internal IP so the Cloud Run env var (set via Secret
# Manager's neo4j-uri) doesn't change every time the VM is recreated.
resource "google_compute_address" "neo4j_internal" {
  name         = "neo4j-internal-ip"
  region       = var.region
  subnetwork   = "default"
  address_type = "INTERNAL"
}

# Service account the VM runs as. Needs only secretmanager.secretAccessor
# on the neo4j-password secret. No other privileges.
resource "google_service_account" "neo4j_vm" {
  account_id   = "neo4j-vm"
  display_name = "Neo4j VM runtime"
  description  = "Runs the self-hosted Neo4j Community Edition VM. Reads its initial password from Secret Manager."
}

resource "google_secret_manager_secret_iam_member" "neo4j_vm_password_access" {
  secret_id = google_secret_manager_secret.neo4j_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.neo4j_vm.email}"
}

# The VM itself. Debian 12 + the startup script in infra/scripts/install_neo4j.sh.
# e2-small ≈ $13/mo in us-east4 (1 vCPU shared, 2 GB RAM). Plenty for the
# Phase 1 seed (10s of nodes); upgrade to e2-medium if Phase 2 agent traffic
# demands more.
resource "google_compute_instance" "neo4j" {
  name         = "construction-ai-neo4j"
  machine_type = "e2-small"
  zone         = "${var.region}-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
      type  = "pd-balanced"
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.neo4j_internal.address
    # Ephemeral external IP — needed for outbound apt-get during the
    # startup-script Neo4j install (Debian package mirrors aren't reachable
    # via Private Google Access). Inbound is still locked down by the
    # firewall rules below (only port 7687 from VPC-connector subnet, only
    # SSH from IAP).
    access_config {
      network_tier = "STANDARD"
    }
  }

  metadata = {
    enable-oslogin = "TRUE"
    startup-script = file("${path.module}/scripts/install_neo4j.sh")
  }

  service_account {
    email  = google_service_account.neo4j_vm.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot = true
    enable_vtpm        = true
  }

  tags = ["neo4j-server"]

  # Allow stopping/starting the VM without Terraform fighting the IP
  allow_stopping_for_update = true
}

# Allow port 7687 (bolt) from the VPC connector subnet only.
resource "google_compute_firewall" "neo4j_bolt_from_vpc_connector" {
  name        = "allow-neo4j-bolt-from-cloud-run"
  network     = "default"
  description = "Permit bolt traffic from the Cloud Run VPC connector to the Neo4j VM."

  allow {
    protocol = "tcp"
    ports    = ["7687"]
  }

  source_ranges = [google_vpc_access_connector.cloud_run_to_neo4j.ip_cidr_range]
  target_tags   = ["neo4j-server"]
}

# Optional: allow SSH from IAP for operators (gcloud compute ssh works via
# IAP without a public IP). Cheap to add; useful for debugging.
resource "google_compute_firewall" "neo4j_ssh_from_iap" {
  name        = "allow-neo4j-ssh-from-iap"
  network     = "default"
  description = "Permit SSH via Identity-Aware Proxy to the Neo4j VM."

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP's TCP forwarding source range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["neo4j-server"]
}

# Serverless VPC Access connector — the bridge from Cloud Run to the VM's
# private IP. Required because Cloud Run runs in a Google-managed VPC by
# default and can't reach user-VPC internal IPs without one.
resource "google_vpc_access_connector" "cloud_run_to_neo4j" {
  name          = "construction-ai-conn"
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.8.0.0/28"
  min_throughput = 200
  max_throughput = 300
}
