#!/usr/bin/env bash
# GMS Clinical AI — update to a new version, with a safety net.
#
#   ./update.sh gms-clinical-ai-3.1.0.tar.gz
#
# What it does, in order (and stops safely if any step fails before the switch):
#   1. checks the bundle is complete and untampered (SHA-256)          5. starts the new version
#   2. stops the application so nothing changes during the update      6. waits until it is healthy
#   3. takes an encrypted backup and checks that it can be opened      7. if it is NOT healthy: puts the old version
#   4. loads the new version, keeping the old one for rollback            back and restores that backup — automatically
# Plan for about 5 minutes of downtime. Do it outside clinic hours.
set -euo pipefail
cd "$(dirname "$0")"
RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; BLD=$'\e[1m'; RST=$'\e[0m'
say() { echo "${BLD}==>${RST} $*"; }
die() { echo "${RED}$*${RST}" >&2; exit 1; }

BUNDLE="${1:-}"; [ -n "$BUNDLE" ] && [ -f "$BUNDLE" ] || die "Usage: ./update.sh gms-clinical-ai-X.Y.Z.tar.gz"
[ -f .env ] || die "No .env here. Run this from the folder where the product was installed."
docker compose version >/dev/null 2>&1 || die "Docker Compose is not available."

wait_healthy() { # wait_healthy SECONDS
  local s
  for _ in $(seq 1 "$(($1/2))"); do
    s=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="app" {print $2}')
    [ "$s" = "healthy" ] && return 0; sleep 2
  done; return 1
}

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
say "Checking the update file"
tar -xzf "$BUNDLE" -C "$WORK"
NEW=$(find "$WORK" -mindepth 1 -maxdepth 1 -type d | head -n1)
[ -f "$NEW/SHA256SUMS" ] && [ -f "$NEW/VERSION" ] && [ -f "$NEW/images/gms-clinical-ai.tar" ] || die "This does not look like a GMS update file."
(cd "$NEW" && sha256sum -c SHA256SUMS --quiet) || die "The update file is damaged or has been changed. Do not use it; ask for a new copy."
NEW_V=$(cat "$NEW/VERSION"); OLD_V=$(cat .installed-version 2>/dev/null || echo unknown)
echo "    installed: $OLD_V     update: $NEW_V"
[ "$NEW_V" = "$OLD_V" ] && die "Version $NEW_V is already installed."
DF=$(df -Pk . | awk 'NR==2 {print int($4/1024/1024)}'); [ "$DF" -ge 5 ] || die "Only ${DF} GB free; at least 5 GB are needed for the update and the backup."

say "Stopping the application (people are signed out)"
docker compose stop app >/dev/null
say "Taking a backup"
OUT=$(docker compose run --rm -T --no-deps app python -m app.cli backup 2>&1) || { echo "$OUT"; docker compose start app >/dev/null; die "The backup failed, so nothing was changed. The application has been restarted."; }
echo "$OUT" | sed 's/^/    /'
BACKUP=$(echo "$OUT" | grep -o 'gms-backup-[0-9-]*\.\(gmsbak\|tar\.gz\)' | head -n1)
[ -n "$BACKUP" ] || { docker compose start app >/dev/null; die "Could not tell which backup was made; nothing was changed."; }
docker compose run --rm -T --no-deps app python -m app.cli backup-verify "$BACKUP" >/dev/null 2>&1 || { docker compose start app >/dev/null; die "The backup could not be opened again, so nothing was changed."; }
echo "    backup $BACKUP is intact"

say "Loading version $NEW_V"
docker tag gms-clinical-ai:current gms-clinical-ai:previous
mkdir -p .prev && cp -f docker-compose.yml Caddyfile VERSION .prev/ 2>/dev/null || true
cat > .update-state <<STATE
OLD_VERSION=$OLD_V
NEW_VERSION=$NEW_V
BACKUP_FILE=$BACKUP
UPDATED_AT=$(date -Is)
STATE
docker load -i "$NEW/images/gms-clinical-ai.tar" >/dev/null
for f in "$NEW"/images/*.tar; do [ "$f" != "$NEW/images/gms-clinical-ai.tar" ] && docker load -i "$f" >/dev/null || true; done
docker tag "gms-clinical-ai:${NEW_V}" gms-clinical-ai:current
cp -f "$NEW/docker-compose.yml" "$NEW/Caddyfile" "$NEW/VERSION" . 
[ -f "$NEW/install.sh" ] && for f in install.sh update.sh rollback.sh backup-offsite.sh; do [ -f "$NEW/$f" ] && [ "$f" != update.sh ] && cp -f "$NEW/$f" . ; done

say "Starting version $NEW_V"
docker compose up -d >/dev/null 2>&1 || true
if wait_healthy 180 && docker compose exec -T app python -m app.cli status >/dev/null 2>&1; then
  echo "$NEW_V" > .installed-version
  docker compose exec -T app python -m app.cli doctor || true
  echo; echo "${GRN}${BLD}Updated to $NEW_V.${RST}  The previous version is kept for one-command rollback: ./rollback.sh"
  echo "Pre-update backup: $BACKUP"
  exit 0
fi

echo; echo "${RED}${BLD}Version $NEW_V did not start properly. Putting version $OLD_V back.${RST}"
docker compose logs --tail 40 app 2>&1 | sed 's/^/    /' || true
./rollback.sh --yes --auto && die "Rolled back to $OLD_V. Nothing was lost. Send the log above to your supplier." || die "AUTOMATIC ROLLBACK FAILED. Run ./rollback.sh, or follow the recovery steps in the guide. The backup is $BACKUP."
