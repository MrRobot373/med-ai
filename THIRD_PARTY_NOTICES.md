# Third-party notices

Runtime dependencies and their licences. Versions are those resolved in the lockfile / environment at the time of writing.

## Backend (Python)

| Package | Licence |
|---|---|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| pydantic | MIT |
| pydantic-settings | MIT |
| SQLAlchemy | MIT |
| alembic | MIT |
| httpx | BSD-3-Clause |
| argon2-cffi | MIT |
| cryptography | Apache-2.0 / BSD |
| python-multipart | Apache-2.0 |
| qdrant-client | Apache-2.0 |
| pypdfium2 (PDFium) | Apache-2.0 / BSD-3-Clause |
| reportlab | BSD-3-Clause |
| python-docx | MIT |
| openpyxl | MIT |
| Pillow | MIT-CMU |
| sentence-transformers (optional) | Apache-2.0 |

> The product no longer depends on PyMuPDF (AGPL-3.0). The developer-only patient-file generator in `scripts/patient_files` and the film tooling still use it to *author* sample PDFs; it is not part of the shipped application or image.

## Frontend (npm)

| Package | Version | Licence |
|---|---|---|
| @fontsource-variable/inter | 5.3.0 | OFL-1.1 |
| @radix-ui/react-checkbox | 1.4.1 | MIT |
| @radix-ui/react-collapsible | 1.2.1 | MIT |
| @radix-ui/react-dialog | 1.3.1 | MIT |
| @radix-ui/react-dropdown-menu | 2.2.1 | MIT |
| @radix-ui/react-label | 2.1.17 | MIT |
| @radix-ui/react-popover | 1.3.1 | MIT |
| @radix-ui/react-scroll-area | 1.4.0 | MIT |
| @radix-ui/react-select | 2.4.1 | MIT |
| @radix-ui/react-separator | 1.2.0 | MIT |
| @radix-ui/react-slider | 1.6.1 | MIT |
| @radix-ui/react-slot | 1.5.0 | MIT |
| @radix-ui/react-switch | 1.4.1 | MIT |
| @radix-ui/react-tabs | 1.2.1 | MIT |
| @radix-ui/react-tooltip | 1.4.1 | MIT |
| @tanstack/react-query | 5.104.5 | MIT |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| clsx | 2.1.1 | MIT |
| cmdk | 1.1.1 | MIT |
| date-fns | 4.4.0 | MIT |
| lucide-react | 0.577.0 | ISC |
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-markdown | 10.1.0 | MIT |
| react-router | 7.18.4 | MIT |
| recharts | 3.10.1 | MIT |
| remark-gfm | 4.0.1 | MIT |
| sonner | 2.0.8 | MIT |
| tailwind-merge | 2.6.1 | MIT |

## Services and data

| Component | Licence |
|---|---|
| Qdrant (server, optional) | Apache-2.0 |
| Ollama (optional) | MIT |
| Inter typeface (@fontsource-variable/inter) | SIL Open Font License 1.1 |
| Wikimedia Commons (optional medicine pictures) | Each image under its own free licence; author and licence are shown with the picture |
