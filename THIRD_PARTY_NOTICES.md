# Third-Party Notices

GMS Clinical AI is built entirely on open-source / locally-runnable components. This
file is updated as each build phase introduces new dependencies — see the version
pinned in `backend/requirements.txt` / `frontend/package.json` for the exact version in
use at any time.

## Backend (Phase 01)

| Package | Project | License |
|---|---|---|
| FastAPI | https://github.com/fastapi/fastapi | MIT |
| Uvicorn | https://github.com/encode/uvicorn | BSD-3-Clause |
| Pydantic / pydantic-settings | https://github.com/pydantic/pydantic | MIT |
| SQLAlchemy | https://github.com/sqlalchemy/sqlalchemy | MIT |
| Alembic | https://github.com/sqlalchemy/alembic | MIT |
| httpx | https://github.com/encode/httpx | BSD-3-Clause |
| argon2-cffi | https://github.com/hynek/argon2-cffi | MIT |
| python-multipart | https://github.com/Kludex/python-multipart | Apache-2.0 |
| pytest / pytest-asyncio | https://github.com/pytest-dev/pytest | MIT |
| Ruff | https://github.com/astral-sh/ruff | MIT |

## Backend (Phase 03 — auth)

| Package | Project | License |
|---|---|---|
| email-validator | https://github.com/JoshData/python-email-validator | CC0-1.0 |

## Backend (Phase 05 — report ingestion)

| Package | Project | License |
|---|---|---|
| PyMuPDF | https://github.com/pymupdf/PyMuPDF | AGPL-3.0 (also offers a commercial license; used here as a local, non-distributed tool — see note below) |
| python-docx | https://github.com/python-openxml/python-docx | MIT |
| openpyxl | https://foss.heptapod.net/openpyxl/openpyxl | MIT |
| Pillow | https://github.com/python-pillow/Pillow | MIT-CMU |
| pydicom | https://github.com/pydicom/pydicom | MIT |
| EasyOCR | https://github.com/JaidedAI/EasyOCR | Apache-2.0 |

PyMuPDF's AGPL-3.0 obliges anyone who *distributes* a modified or unmodified copy (or
runs it as a network service reachable by others) to make the corresponding source
available under the same terms. This project runs it purely as a local, offline
processing tool on the operator's own machine (spec §136) and is not distributed as a
hosted service to third parties; re-verify this before any SaaS/hosted deployment, or
switch to PyMuPDF's commercial license for that use case.

EasyOCR is used here as an open-source, Windows-reliable substitute for the Master Build
Prompt's suggested PaddleOCR (spec §51) — both are CPU-capable, license-compatible OCR
engines; the choice is purely an installation-reliability decision, not a capability
downgrade.

## Backend (declared now, used starting Phase 07 — RAG core)

| Package | Project | License |
|---|---|---|
| qdrant-client | https://github.com/qdrant/qdrant-client | Apache-2.0 |
| sentence-transformers | https://github.com/UKPLab/sentence-transformers | Apache-2.0 |
| transformers | https://github.com/huggingface/transformers | Apache-2.0 |
| Qwen3-Embedding-0.6B | https://huggingface.co/Qwen/Qwen3-Embedding-0.6B | Apache-2.0 |
| Qwen3-Reranker-0.6B | https://huggingface.co/Qwen/Qwen3-Reranker-0.6B | Apache-2.0 |
| Qwen3.5 (via Ollama) | https://ollama.com/library/qwen3.5 | Qwen license (see model card) |

## Infrastructure

| Component | Project | License |
|---|---|---|
| Qdrant (Docker, pinned `v1.19.0`) | https://github.com/qdrant/qdrant | Apache-2.0 |
| Ollama | https://github.com/ollama/ollama | MIT |
| SearXNG (Research Mode, optional, Phase 11) | https://github.com/searxng/searxng | AGPL-3.0 |

## Frontend (Phase 01)

| Package | Project | License |
|---|---|---|
| React / React DOM | https://github.com/facebook/react | MIT |
| React Router | https://github.com/remix-run/react-router | MIT |
| TanStack Query | https://github.com/TanStack/query | MIT |
| Vite | https://github.com/vitejs/vite | MIT |
| Tailwind CSS | https://github.com/tailwindlabs/tailwindcss | MIT |
| lucide-react | https://github.com/lucide-icons/lucide | ISC |
| TypeScript | https://github.com/microsoft/TypeScript | Apache-2.0 |
| Vitest / Testing Library | https://github.com/vitest-dev/vitest / https://github.com/testing-library/react-testing-library | MIT |
| @testing-library/user-event | https://github.com/testing-library/user-event | MIT |

## Domain reference data (not source code)

The ophthalmology reference PDFs and `eye_conditions.json` under `data/` are
user-supplied source material for the local knowledge base, not redistributed
third-party software — confirm licensing/usage terms for each document independently
before any redistribution beyond this local deployment.

## Not bundled (by design)

- **CPT** content is not bundled (AMA-licensed) — see spec §76. The coding module only
  ever loads properly licensed, customer-supplied CPT data through an import adapter.
- No proprietary/paid cloud SDKs are used anywhere in this project.
