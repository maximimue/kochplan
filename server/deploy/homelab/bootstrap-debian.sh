#!/usr/bin/env bash
# IN DER VM (Debian 13) ausführen: sudo bash deploy/homelab/bootstrap-debian.sh
set -euo pipefail
TARGET_USER=${SUDO_USER:-kochplan}
REPO_DIR=$(cd "$(dirname "$0")/../.." && pwd)

apt-get update
apt-get -y upgrade
apt-get install -y ca-certificates curl git qemu-guest-agent unattended-upgrades
systemctl enable --now qemu-guest-agent

# Docker aus dem offiziellen Repo (aktuelles Compose-Plugin)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $VERSION_CODENAME stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "$TARGET_USER"

# Container-Logs begrenzen
cat > /etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "20m", "max-file": "3" } }
JSON
systemctl restart docker

dpkg-reconfigure -f noninteractive unattended-upgrades

# Tägliches DB-Backup (Ziel per BACKUP_DIR anpassen, z. B. NFS-Mount vom TrueNAS)
install -m 755 "$REPO_DIR/deploy/backup.sh" /usr/local/bin/kochplan-backup
cat > /etc/cron.d/kochplan-backup <<CRON
15 3 * * * root COMPOSE_DIR=$REPO_DIR BACKUP_DIR=/var/backups/kochplan /usr/local/bin/kochplan-backup >> /var/log/kochplan-backup.log 2>&1
CRON

echo
echo "Fertig. Neu einloggen (docker-Gruppe), dann:"
echo "  cd $REPO_DIR && cp .env.example .env && cp .env.dns.example .env.dns && nano .env .env.dns"
echo "  docker compose up -d --build"
