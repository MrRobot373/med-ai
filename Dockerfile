# syntax=docker/dockerfile:1
# Single image: FastAPI backend serving the built React app on port 8000.

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/data APP_ENV=production
WORKDIR /app/backend
COPY backend/pyproject.toml backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
RUN pip install --no-deps -e .
COPY knowledge-packs/ /app/knowledge-packs/
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --create-home --uid 10001 gms && mkdir -p /data && chown -R gms:gms /data /app
USER gms
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
