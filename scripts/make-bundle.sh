#!/usr/bin/env bash
# Builds the delivery package: the product image + everything needed to install or update it on a clinic's own server.
#
#   scripts/make-bundle.sh                 → dist/gms-clinical-ai-<version>.tar.gz           (what customers receive)
#   scripts/make-bundle.sh --demo          → dist/gms-clinical-ai-<version>-demo.tar.gz      (same, plus the sample patients)
#   scripts/make-bundle.sh --with clamav,qdrant     also include those optional images, for servers with no internet
#
# The same file is used for a first installation (./install.sh) and for upgrades (./update.sh <file>).
set -euo pipefail
cd "$(dirname "$0")/.."
DEMO=0; WITH=""
while [ $# -gt 0 ]; do case "$1" in --demo) DEMO=1;; --with) WITH="$2"; shift;; *) echo "Unknown option $1"; exit 2;; esac; shift; done

VERSION=$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' backend/app/api/system.py)
[ -n "$VERSION" ] || { echo "Cannot read APP_VERSION"; exit 1; }
NAME="gms-clinical-ai-${VERSION}$([ "$DEMO" = 1 ] && echo -demo)"
OUT="dist/${NAME}"
rm -rf "$OUT"; mkdir -p "$OUT/images" "$OUT/docs"

echo "Building image gms-clinical-ai:${VERSION} (demo=${DEMO})"
# REGISTRY (optional) is a prefix for the base images, e.g. REGISTRY=mirror.gcr.io/library/ when Docker Hub is limited.
REGISTRY="${REGISTRY:-}"
SECRET=(); [ -n "${CA_BUNDLE:-}" ] && SECRET=(--secret "id=ca,src=${CA_BUNDLE}")   # CA_BUNDLE: a TLS-inspecting proxy's certificate, if any
docker build "${SECRET[@]}" --build-arg REGISTRY="$REGISTRY" --build-arg WITH_DEMO="$DEMO" --build-arg VERSION="$VERSION" -t "gms-clinical-ai:${VERSION}" .
docker save "gms-clinical-ai:${VERSION}" -o "$OUT/images/gms-clinical-ai.tar"

echo "Saving supporting images"
docker pull -q "${REGISTRY}caddy:2.8-alpine" >/dev/null && { [ -z "$REGISTRY" ] || docker tag "${REGISTRY}caddy:2.8-alpine" caddy:2.8-alpine; } && docker save caddy:2.8-alpine -o "$OUT/images/caddy.tar"
for p in ${WITH//,/ }; do
  case "$p" in
    clamav) img=clamav/clamav:1.4;; qdrant) img=qdrant/qdrant:v1.12.4;; ollama) img=ollama/ollama:0.12.6;;
    *) echo "Unknown optional image $p"; exit 2;;
  esac
  docker pull -q "$img" >/dev/null && docker save "$img" -o "$OUT/images/$p.tar"
done

cp deploy/docker-compose.yml deploy/Caddyfile deploy/.env.template deploy/install.sh deploy/update.sh deploy/rollback.sh deploy/backup-offsite.sh "$OUT/"
cp docs/INSTALL.md docs/OPERATIONS.md docs/SECURITY_OPERATIONS.md "$OUT/docs/" 2>/dev/null || true
cp THIRD_PARTY_NOTICES.md "$OUT/" 2>/dev/null || true
echo "$VERSION" > "$OUT/VERSION"
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
mkdir -p dist && tar -czf "dist/${NAME}.tar.gz" -C dist "${NAME}"
sha256sum "dist/${NAME}.tar.gz" | tee "dist/${NAME}.tar.gz.sha256"
du -h "dist/${NAME}.tar.gz"
