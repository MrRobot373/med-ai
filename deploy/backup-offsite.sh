#!/usr/bin/env bash
# Copies new backups to a second place (USB drive, NAS share, another disk). Backups on the same disk do not
# survive that disk failing. Safe to run from cron:   0 3 * * *  /opt/gms/backup-offsite.sh /mnt/usb
set -euo pipefail
cd "$(dirname "$0")"
DEST="${1:?Usage: backup-offsite.sh DESTINATION_FOLDER}"
SRC="$(grep '^DATA_PATH=' .env | cut -d= -f2)/backups"
[ -d "$SRC" ] || { echo "No backups folder yet at $SRC"; exit 1; }
mkdir -p "$DEST"
n=0
for f in "$SRC"/gms-backup-*; do
  [ -f "$f" ] || continue
  b=$(basename "$f")
  [ -f "$DEST/$b" ] && cmp -s "$f" "$DEST/$b" && continue
  cp "$f" "$DEST/$b.part" && mv "$DEST/$b.part" "$DEST/$b"; n=$((n+1))
done
# keep the 30 newest copies there
ls -1t "$DEST"/gms-backup-* 2>/dev/null | tail -n +31 | xargs -r rm -f
echo "Copied $n new backup(s) to $DEST"
