#!/usr/bin/env bash
# GMS Clinical AI — go back to the version that was installed before the last update.
#
#   ./rollback.sh          asks for confirmation
#   ./rollback.sh --yes    no questions
#
# It stops the application, puts the previous version back and restores the backup that ./update.sh took just before
# the update (the newer version may have changed the database, which an older version cannot read).
# Anything entered since that backup is NOT in the restored data; the data of the newer version is moved aside, not deleted.
set -euo pipefail
cd "$(dirname "$0")"
RED=$'\e[31m'; GRN=$'\e[32m'; BLD=$'\e[1m'; RST=$'\e[0m'
say() { echo "${BLD}==>${RST} $*"; }
die() { echo "${RED}$*${RST}" >&2; exit 1; }
YES=0; AUTO=0
for a in "$@"; do case "$a" in --yes) YES=1;; --auto) AUTO=1;; esac; done

[ -f .update-state ] || die "There is no update to roll back (no .update-state file)."
# shellcheck disable=SC1091
. ./.update-state
[ -n "${OLD_VERSION:-}" ] && [ -n "${BACKUP_FILE:-}" ] || die "The last update was already rolled back (or there is nothing to roll back)."
docker image inspect gms-clinical-ai:previous >/dev/null 2>&1 || die "The previous version's image is no longer on this machine."
if [ "$YES" = 0 ]; then
  echo "This puts version $OLD_VERSION back and restores the backup taken before the update to $NEW_VERSION ($BACKUP_FILE)."
  echo "Anything entered since then will not be in the restored data."
  read -r -p "Continue? [y/N] " a; [[ "$a" =~ ^[Yy] ]] || exit 1
fi

say "Stopping"; docker compose stop app >/dev/null 2>&1 || true
say "Putting version $OLD_VERSION back"
docker tag gms-clinical-ai:previous gms-clinical-ai:current
[ -d .prev ] && cp -f .prev/docker-compose.yml .prev/Caddyfile . 2>/dev/null || true
say "Restoring the backup $BACKUP_FILE"
docker compose run --rm -T --no-deps app python -m app.cli restore "$BACKUP_FILE" --yes | sed 's/^/    /'
say "Starting"
docker compose up -d >/dev/null 2>&1 || true
for _ in $(seq 1 90); do
  S=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="app" {print $2}')
  [ "$S" = "healthy" ] && break; sleep 2
done
[ "$S" = "healthy" ] || die "Version $OLD_VERSION was put back but is not healthy. See: docker compose logs app"
echo "$OLD_VERSION" > .installed-version
sed -i 's/^/# /' .update-state; echo "ROLLED_BACK_AT=$(date -Is)" >> .update-state
echo "${GRN}${BLD}Rolled back to $OLD_VERSION.${RST}"
