#!/usr/bin/env bash
#
# Cloud-init startup script for the Neo4j Community Edition VM.
#
# Run once on first boot. Idempotent: re-running has no effect because the
# initial-password command only succeeds before Neo4j has been started.
#
# Reads the Neo4j initial password from GCP Secret Manager (the VM's
# attached service account has roles/secretmanager.secretAccessor on
# `neo4j-password` — bound by Terraform).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

LOG=/var/log/neo4j-install.log
exec > >(tee -a "$LOG") 2>&1
echo "[install_neo4j] starting $(date -u +%FT%TZ)"

# 1. Java 17 + tooling
apt-get update
apt-get install -y openjdk-17-jre-headless wget gnupg curl ca-certificates apt-transport-https

# 2. Neo4j 5 apt repo
curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key \
  | gpg --dearmor -o /usr/share/keyrings/neo4j-archive-keyring.gpg
echo 'deb [signed-by=/usr/share/keyrings/neo4j-archive-keyring.gpg] https://debian.neo4j.com stable 5' \
  > /etc/apt/sources.list.d/neo4j.list
apt-get update
apt-get install -y neo4j

# 3. Bind on all interfaces so Cloud Run (via VPC connector) can reach us
sed -i 's/^#server.default_listen_address=.*/server.default_listen_address=0.0.0.0/' /etc/neo4j/neo4j.conf
sed -i 's/^server.default_listen_address=.*/server.default_listen_address=0.0.0.0/' /etc/neo4j/neo4j.conf

# 4. Set initial password from Secret Manager (gcloud is preinstalled on
# Debian Cloud images).
NEO4J_PASSWORD=$(gcloud secrets versions access latest --secret=neo4j-password --quiet)
if [[ -z "$NEO4J_PASSWORD" ]]; then
  echo "[install_neo4j] FATAL: could not read neo4j-password from Secret Manager" >&2
  exit 1
fi
neo4j-admin dbms set-initial-password "$NEO4J_PASSWORD"
unset NEO4J_PASSWORD

# 5. Enable + start
systemctl enable neo4j.service
systemctl start neo4j.service

echo "[install_neo4j] complete $(date -u +%FT%TZ)"
