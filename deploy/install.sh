#!/usr/bin/env bash
# GMS Clinical AI — first-time installer.
#
#   ./install.sh                       asks a few questions
#   ./install.sh --yes --org "Life Care Medico" --admin-email dr@lifecare.in --site clinic.local   no questions
#
# It checks the machine, creates this clinic's own secret keys, loads the product, starts it and
# runs a health check. It never overwrites an existing .env: re-running it is safe.
set -euo pipefail
cd "$(dirname "$0")"

RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; BLD=$'\e[1m'; RST=$'\e[0m'
ok()   { echo "  ${GRN}OK${RST}    $*"; }
warn() { echo "  ${YEL}WARN${RST}  $*"; WARNINGS=$((WARNINGS+1)); }
fail() { echo "  ${RED}FAIL${RST}  $*"; FAILURES=$((FAILURES+1)); }
WARNINGS=0; FAILURES=0

YES=0; ORG=""; ADMIN_EMAIL=""; ADMIN_NAME=""; SITE=""; TZ_NAME="Asia/Kolkata"; AI_URL=""; DATA_PATH="./data"; DISK_ENCRYPTED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --yes) YES=1;; --org) ORG="$2"; shift;; --admin-email) ADMIN_EMAIL="$2"; shift;; --admin-name) ADMIN_NAME="$2"; shift;;
    --site) SITE="$2"; shift;; --timezone) TZ_NAME="$2"; shift;; --ai-url) AI_URL="$2"; shift;; --data-path) DATA_PATH="$2"; shift;;
    --disk-encrypted) DISK_ENCRYPTED="true";;
    -h|--help) sed -n '2,9p' "$0"; exit 0;;
    *) echo "Unknown option $1"; exit 2;;
  esac; shift
done
ask() { # ask VAR "Question" default
  local var="$1" q="$2" def="$3" ans
  if [ -n "${!var}" ]; then return; fi
  if [ "$YES" = 1 ]; then printf -v "$var" '%s' "$def"; return; fi
  read -r -p "$q [$def]: " ans; printf -v "$var" '%s' "${ans:-$def}"
}
gen_b64() { python3 -c 'import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())' 2>/dev/null || head -c 32 /dev/urandom | base64 | tr '+/' '-_'; }
gen_secret() { python3 -c 'import secrets;print(secrets.token_urlsafe(48))' 2>/dev/null || head -c 48 /dev/urandom | base64 | tr -d '+/=\n'; }
gen_pass() { python3 - <<'PY' 2>/dev/null || echo "Cl1nic-$(head -c 9 /dev/urandom | base64 | tr -d '+/=\n')-Start"
import secrets
words = "amber anchor aspen bamboo basil birch breeze cedar clover coral dawn delta ember fern flint forest garnet harbor hazel indigo iris jade juniper lagoon lotus maple meadow mint moss oak olive onyx opal orchid pearl pine quartz reef river sage sierra slate sparrow spruce stone summit tulip velvet willow zephyr".split()
print("-".join(secrets.choice(words).capitalize() for _ in range(4)) + "-" + str(secrets.randbelow(9000) + 1000))
PY
}

echo "${BLD}GMS Clinical AI — installation check${RST}"
echo "Checking this computer"
# Docker
if command -v docker >/dev/null 2>&1; then ok "Docker $(docker --version | sed 's/Docker version //; s/,.*//')"; else fail "Docker is not installed. Install Docker Engine (Linux) or Docker Desktop (Windows/macOS) first."; fi
if docker compose version >/dev/null 2>&1; then ok "Docker Compose $(docker compose version --short)"; else fail "Docker Compose v2 is missing."; fi
if docker info >/dev/null 2>&1; then ok "Docker is running and you may use it"; else fail "Cannot talk to Docker. Start it, or add your user to the 'docker' group."; fi
# Resources
CPUS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
[ "$CPUS" -ge 4 ] && ok "$CPUS CPU cores" || { [ "$CPUS" -ge 2 ] && warn "$CPUS CPU cores (4 or more recommended)" || fail "Only $CPUS CPU core"; }
MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$MEM_KB" -gt 0 ]; then
  MEM_GB=$((MEM_KB/1024/1024))
  if [ "$MEM_GB" -ge 8 ]; then ok "${MEM_GB} GB memory"; elif [ "$MEM_GB" -ge 4 ]; then warn "${MEM_GB} GB memory (8 GB or more recommended; the AI models need more)"; else fail "Only ${MEM_GB} GB memory"; fi
fi
mkdir -p "$DATA_PATH"
FREE_GB=$(df -Pk "$DATA_PATH" | awk 'NR==2 {print int($4/1024/1024)}')
MIN_GB="${GMS_MIN_DISK_GB:-15}"   # lower only on a test machine
if [ "$FREE_GB" -ge 50 ]; then ok "${FREE_GB} GB free for data"; elif [ "$FREE_GB" -ge "$MIN_GB" ]; then warn "${FREE_GB} GB free for data (50 GB or more recommended)"; else fail "Only ${FREE_GB} GB free where data will be stored (at least ${MIN_GB} GB needed)"; fi
# Ports
for p in 80 443; do
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${p}$"; then warn "Port $p is already in use (set HTTP_PORT / HTTPS_PORT in .env to use others)"; else ok "Port $p is free"; fi
done
# Clock
if command -v timedatectl >/dev/null 2>&1; then
  timedatectl show -p NTPSynchronized --value 2>/dev/null | grep -q yes && ok "Clock is synchronised" || warn "Clock is not synchronised. Prescription dates and audit times depend on it: enable time sync (NTP)."
fi
# Disk encryption (Linux): is the data folder on a LUKS volume?
if [ -z "$DISK_ENCRYPTED" ] && command -v lsblk >/dev/null 2>&1; then
  SRC=$(df -P "$DATA_PATH" | awk 'NR==2 {print $1}')
  if lsblk -no TYPE "$SRC" 2>/dev/null | grep -q crypt || lsblk -s -no TYPE "$SRC" 2>/dev/null | grep -q crypt; then DISK_ENCRYPTED="true"; ok "Data is on an encrypted volume"; fi
fi
if [ -z "$DISK_ENCRYPTED" ]; then
  warn "Could not confirm the disk is encrypted. Encrypt it (LUKS / BitLocker) — patient records are stored on it. Re-run with --disk-encrypted once it is."
  DISK_ENCRYPTED="false"
fi
# Product files
if [ -f images/gms-clinical-ai.tar ] || docker image inspect gms-clinical-ai:current >/dev/null 2>&1; then ok "Product image found"; else fail "images/gms-clinical-ai.tar is missing from this folder."; fi
[ -f docker-compose.yml ] && [ -f Caddyfile ] && ok "Deployment files present" || fail "docker-compose.yml / Caddyfile missing"

if [ "$FAILURES" -gt 0 ]; then echo; echo "${RED}$FAILURES problem(s) must be fixed before installing.${RST}"; exit 1; fi
[ "$WARNINGS" -gt 0 ] && [ "$YES" = 0 ] && { read -r -p "$WARNINGS warning(s) above. Continue anyway? [y/N] " a; [[ "$a" =~ ^[Yy] ]] || exit 1; }

if [ -f .env ]; then
  echo; echo "${YEL}An existing .env was found and is kept unchanged${RST} (your keys are never regenerated over existing data)."
  ADMIN_PASSWORD=""
else
  echo; echo "A few questions"
  ask ORG "Clinic name" "My Clinic"
  ask ADMIN_NAME "Administrator's full name" "Clinic Administrator"
  ask ADMIN_EMAIL "Administrator's email (used to sign in)" "admin@example.com"
  DEF_SITE=$(hostname -I 2>/dev/null | awk '{print $1}'); ask SITE "Address people will type (name or IP of this server)" "${DEF_SITE:-localhost}"
  ask TZ_NAME "Time zone" "Asia/Kolkata"
  ask AI_URL "Where the AI model server (Ollama) runs" "http://host.docker.internal:11434"
  ADMIN_PASSWORD=$(gen_pass)
  APP_KEY=$(gen_secret); DATA_KEY=$(gen_b64); BACKUP_KEY=$(gen_b64)
  sed -e "s|@TIMEZONE@|$TZ_NAME|g" -e "s|@SITE_ADDRESS@|$SITE|g" -e "s|@DATA_PATH@|$DATA_PATH|g" \
      -e "s|@APP_SECRET_KEY@|$APP_KEY|g" -e "s|@DATA_ENCRYPTION_KEY@|$DATA_KEY|g" -e "s|@BACKUP_ENCRYPTION_KEY@|$BACKUP_KEY|g" \
      -e "s|@DISK_ENCRYPTED@|$DISK_ENCRYPTED|g" -e "s|@ADMIN_EMAIL@|$ADMIN_EMAIL|g" -e "s|@ADMIN_NAME@|$ADMIN_NAME|g" \
      -e "s|@ADMIN_PASSWORD@|$ADMIN_PASSWORD|g" -e "s|@AI_URL@|$AI_URL|g" .env.template > .env
  chmod 600 .env
  mkdir -p certs offsite
  ok "Created .env with new keys (permissions 600)"
fi

echo; echo "Loading the product"
[ -f images/gms-clinical-ai.tar ] && docker load -i images/gms-clinical-ai.tar | tail -n1
for f in images/*.tar; do [ -f "$f" ] && [ "$f" != images/gms-clinical-ai.tar ] && docker load -i "$f" >/dev/null && ok "Loaded $(basename "$f")"; done
VERSION=$(cat VERSION 2>/dev/null || echo unknown)
docker image inspect "gms-clinical-ai:${VERSION}" >/dev/null 2>&1 && docker tag "gms-clinical-ai:${VERSION}" gms-clinical-ai:current
echo "$VERSION" > .installed-version

echo; echo "Starting"
docker compose up -d
echo -n "Waiting for the application to become healthy"
for i in $(seq 1 90); do
  S=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="app" {print $2}')
  [ "$S" = "healthy" ] && break; echo -n "."; sleep 2
done; echo
if [ "$S" != "healthy" ]; then fail "The application did not become healthy. Run: docker compose logs app"; exit 1; fi
ok "Application is healthy"
echo; echo "Final check"; docker compose exec -T app python -m app.cli doctor || true

SITE_NOW=$(grep '^SITE_ADDRESS=' .env | cut -d= -f2 || true); HTTPS_NOW=$(grep '^HTTPS_PORT=' .env | cut -d= -f2 || true)
PORT_SUFFIX=""; if [ "${HTTPS_NOW:-443}" != 443 ]; then PORT_SUFFIX=":${HTTPS_NOW}"; fi
URL="https://${SITE_NOW}${PORT_SUFFIX}"
echo
echo "${BLD}${GRN}Installed.${RST}  Open  ${BLD}${URL}${RST}"
if [ -n "${ADMIN_PASSWORD:-}" ]; then
cat <<MSG

  Sign in as   ${ADMIN_EMAIL}
  Password     ${BLD}${ADMIN_PASSWORD}${RST}     (shown only now; you must choose your own at first sign-in, and set up two-step verification)

${BLD}Do these today${RST}
  1. Copy the three keys in .env (APP_SECRET_KEY, DATA_ENCRYPTION_KEY, BACKUP_ENCRYPTION_KEY) to a password manager or a printed
     sheet in a safe — NOT on this server only. Without them a restored backup cannot be read.
  2. Browsers will warn about the certificate until the clinic's computers trust it:
       docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./clinic-root-ca.crt
     then install that file as a trusted root certificate on each computer (see the guide), or put your own certificate in ./certs.
  3. Settings → Licence & usage: send the Installation ID to your supplier to receive your licence.
  4. Copy backups off this machine regularly:  ./backup-offsite.sh /path/to/usb-or-nas
MSG
fi
