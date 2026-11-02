# syntax=docker/dockerfile:1
# One image: the FastAPI backend serving the built React app on port 8000.
#
#   docker build -t gms-clinical-ai:current .                      the product, no sample data (what customers get)
#   docker build --build-arg WITH_DEMO=1 -t gms-clinical-ai:demo . the same plus the Life Care Medico sample patients

# Optional prefix for the base images when Docker Hub is blocked or rate-limited, e.g. --build-arg REGISTRY=mirror.gcr.io/library/
ARG REGISTRY=
ARG WITH_DEMO=0

FROM ${REGISTRY}node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
# Behind a TLS-inspecting proxy, pass its CA:  docker build --secret id=ca,src=/path/to/ca-bundle.crt ...
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca; fi; \
    npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

# Sample patients are copied only into the demo build.
FROM ${REGISTRY}python:3.12-slim-bookworm AS demo-0
RUN mkdir -p /app
FROM ${REGISTRY}python:3.12-slim-bookworm AS demo-1
RUN mkdir -p /app
COPY patient-files/ /app/patient-files/
FROM demo-${WITH_DEMO} AS demo

FROM ${REGISTRY}python:3.12-slim-bookworm
ARG VERSION=dev
LABEL org.opencontainers.image.title="GMS Clinical AI" org.opencontainers.image.version="${VERSION}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/data APP_ENV=production
WORKDIR /app/backend
COPY backend/pyproject.toml backend/requirements.txt ./
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca SSL_CERT_FILE=/run/secrets/ca REQUESTS_CA_BUNDLE=/run/secrets/ca; fi; \
    pip install -r requirements.txt
COPY backend/ ./
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca SSL_CERT_FILE=/run/secrets/ca REQUESTS_CA_BUNDLE=/run/secrets/ca; fi; \
    pip install --no-deps -e .
COPY knowledge-packs/ /app/knowledge-packs/
COPY --from=demo /app/ /app/
COPY --from=web /web/dist /app/frontend/dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN useradd --create-home --uid 10001 gms && mkdir -p /data && chown -R gms:gms /data /app && chmod +x /usr/local/bin/docker-entrypoint.sh
# The entrypoint starts as root only to fix the ownership of a mounted data folder, then runs everything as `gms`.
ENTRYPOINT ["docker-entrypoint.sh"]
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
