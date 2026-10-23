"""Text extraction per file type. Each parser returns a list of pages:
`{"page": int, "text": str}` (page numbers are 1-based; non-paginated formats are one
page per sheet/section). Images return no text here — they go through vision."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

SUPPORTED = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "csv",
    "application/json": "json",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
}
EXTENSIONS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
MAGIC = {
    "pdf": [b"%PDF"],
    "docx": [b"PK"],
    "xlsx": [b"PK"],
    "image": [b"\x89PNG", b"\xff\xd8\xff", b"RIFF"],
}


@dataclass
class Parsed:
    pages: list[dict]
    kind: str  # parser family

    @property
    def text(self) -> str:
        return "\n\n".join(p["text"] for p in self.pages if p["text"].strip())


def detect_mime(filename: str, declared: str | None) -> str | None:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in EXTENSIONS:
        return EXTENSIONS[ext]
    if declared in SUPPORTED:
        return declared
    return None


def verify_magic(family: str, data: bytes) -> bool:
    sigs = MAGIC.get(family)
    return True if not sigs else any(data.startswith(s) for s in sigs)


def parse(data: bytes, mime: str) -> Parsed:
    family = SUPPORTED[mime]
    if family == "pdf":
        return Parsed(_pdf(data), family)
    if family == "docx":
        return Parsed(_docx(data), family)
    if family == "xlsx":
        return Parsed(_xlsx(data), family)
    if family == "csv":
        return Parsed([{"page": 1, "text": _csv(data)}], family)
    if family == "json":
        return Parsed([{"page": 1, "text": _json(data)}], family)
    if family == "image":
        return Parsed([], family)
    return Parsed([{"page": 1, "text": data.decode("utf-8", errors="replace")}], family)


def _pdf(data: bytes) -> list[dict]:
    import pymupdf

    pages = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            # Tables: render rows as pipe-separated lines so lab parsing and the LLM keep structure.
            try:
                for table in page.find_tables().tables:
                    rows = [" | ".join((c or "").strip() for c in row) for row in table.extract()]
                    if rows:
                        text += "\n\n" + "\n".join(rows)
            except Exception:
                pass
            pages.append({"page": i, "text": text})
    return pages


def _docx(data: bytes) -> list[dict]:
    import docx

    d = docx.Document(io.BytesIO(data))
    parts = []
    for para in d.paragraphs:
        if para.text.strip():
            style = (para.style.name or "").lower() if para.style is not None else ""
            parts.append(("## " if style.startswith("heading") else "") + para.text.strip())
    for table in d.tables:
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        parts.append("\n".join(rows))
    return [{"page": 1, "text": "\n".join(parts)}]


def _xlsx(data: bytes) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    pages = []
    for i, ws in enumerate(wb.worksheets, start=1):
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cells):
                rows.append(" | ".join(cells))
        pages.append({"page": i, "text": f"## {ws.title}\n" + "\n".join(rows)})
    return pages


def _csv(data: bytes) -> str:
    reader = csv.reader(io.StringIO(data.decode("utf-8", errors="replace")))
    return "\n".join(" | ".join(r) for r in reader)


_TITLE_KEYS = ("title", "name", "disease", "condition", "drug", "topic", "heading")


def _render_value(value, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, list):
        return "\n".join(f"{pad}- {_render_value(v, indent + 1).strip()}" for v in value)
    if isinstance(value, dict):
        return "\n".join(
            f"{pad}{k.replace('_', ' ').capitalize()}: {_render_value(v, indent + 1).strip()}" for k, v in value.items()
        )
    return f"{pad}{value}"


def _json(data: bytes) -> str:
    """Structured knowledge packs (a list of records) become one readable section per
    record so each chunk stays a coherent topic."""
    try:
        value = json.loads(data)
    except ValueError:
        return data.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        for key in ("items", "entries", "records", "data"):
            if isinstance(value.get(key), list):
                value = value[key]
                break
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        sections = []
        for record in value:
            title = next((str(record[k]) for k in _TITLE_KEYS if record.get(k)), "Entry")
            body = "\n".join(
                f"{k.replace('_', ' ').capitalize()}: {_render_value(v, 1).strip()}"
                for k, v in record.items()
                if str(record.get(k)) != title
            )
            sections.append(f"## {title}\n{body}")
        return "\n\n".join(sections)
    return json.dumps(value, indent=2, ensure_ascii=False)
