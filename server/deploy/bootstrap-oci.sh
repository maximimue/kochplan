#!/usr/bin/env bash
# Einmalig auf frischer OCI-Instanz (Ubuntu 24.04 aarch64, VM.Standard.A1.Flex) ausführen:
#   curl -fsSL <raw-url>/bootstrap-oci.sh | sudo bash    oder    sudo bash bootstrap-oci.sh
set -euo pipefail

apt-get update
apt-get -y upgrade
apt-get install -y docker.io docker-compose-v2 git unattended-upgrades iptables-persistent

# Oracles Ubuntu-Images haben eigene iptables-Regeln mit REJECT am Ende der INPUT-Chain.
# Die OCI Security List allein reicht NICHT — Ports müssen auch hier auf.
for port in 80 443; do
  iptables -C INPUT -p tcp --dport $port -m conntrack --ctstate NEW -j ACCEPT 2>/dev/null \
    || iptables -I INPUT -p tcp --dport $port -m conntrack --ctstate NEW -j ACCEPT
done
iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT -p udp --dport 443 -j ACCEPT  # HTTP/3
netfilter-persistent save

# 2 GB Swap als Puffer
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

systemctl enable --now docker
usermod -aG docker ubuntu
dpkg-reconfigure -f noninteractive unattended-upgrades

# Tägliches DB-Backup
install -m 755 "$(dirname "$0")/backup.sh" /usr/local/bin/kochplan-backup 2>/dev/null || true
echo "15 3 * * * root COMPOSE_DIR=/home/ubuntu/kochplan/server /usr/local/bin/kochplan-backup >> /var/log/kochplan-backup.log 2>&1" > /etc/cron.d/kochplan-backup

echo "Fertig. Neu einloggen (docker-Gruppe), dann: cd kochplan/server && cp .env.example .env (COMPOSE_FILE auf compose.caddy.yml setzen) && docker compose up -d --build"
