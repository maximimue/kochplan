#!/usr/bin/env bash
# pg_dump aus dem laufenden Container, 14 Tage aufbewahren.
# BACKUP_DIR auf einen NFS-Mount (TrueNAS) oder rclone/restic-Ziel legen, damit das Backup nicht auf derselben Disk liegt.
set -euo pipefail
DIR=${BACKUP_DIR:-/var/backups/kochplan}
COMPOSE_DIR=${COMPOSE_DIR:-/home/ubuntu/kochplan/server}
KEEP_DAYS=${KEEP_DAYS:-14}
mkdir -p "$DIR"
cd "$COMPOSE_DIR"
OUT="$DIR/kochplan-$(date +%F).dump"
docker compose exec -T db pg_dump -U kochplan -Fc kochplan > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
find "$DIR" -name 'kochplan-*.dump' -mtime +"$KEEP_DAYS" -delete
