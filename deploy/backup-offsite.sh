#!/usr/bin/env bash
# Copies new backups to a second place (USB drive, NAS share, another disk). Backups on the same disk do not
# survive that disk failing. Safe to run from cron:   0 3 * * *  /opt/gms/backup-offsite.sh /mnt/usb
set -euo pipefail
cd "$(dirname "$0")"
DEST="${1:?Usage: backup-offsite.sh DESTINATION_FOLDER}"
mkdir -p "$DEST"
# Backups are owned by the application's own user, so they are read through the container (works for any host user).
docker compose exec -T app test -d /data/backups || { echo "No backups folder yet"; exit 1; }
n=0
for b in $(docker compose exec -T app sh -c 'ls -1 /data/backups | grep "^gms-backup-" | grep -v "\.part$"'); do
  b=$(echo "$b" | tr -d '\r')
  [ -f "$DEST/$b" ] && continue
  docker compose exec -T app cat "/data/backups/$b" > "$DEST/$b.part" && mv "$DEST/$b.part" "$DEST/$b"; n=$((n+1))
done
# keep the 30 newest copies there
ls -1t "$DEST"/gms-backup-* 2>/dev/null | tail -n +31 | xargs -r rm -f
echo "Copied $n new backup(s) to $DEST"
