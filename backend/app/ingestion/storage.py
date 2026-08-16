"""File storage — spec §92/§93: randomized stored filenames, storage outside any
directly-served web root, original filename kept separate from the on-disk name.

Uploads are read fully into memory before validation/write (capped by
`UPLOAD_MAX_MB`, default 25) rather than streamed — this is a local, single-operator
demo app (spec §135 "avoid unnecessary infrastructure"), not an internet-facing
service, so the simpler approach is the appropriate one here.
"""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from typing import TYPE_CHECKING

from app.config.settings import Settings

if TYPE_CHECKING:
    from app.models.report import Report


def reports_dir(settings: Settings, patient_id: str) -> Path:
    directory = Path(settings.upload_dir) / "reports" / patient_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def file_path_for(settings: Settings, report: Report) -> Path:
    """Lives here (not `services/reports.py`) so both `services/reports.py` and
    `services/vision.py` can import it without either depending on the other —
    `services/vision.py` needs it too, and `services/reports.py` already needs
    `ingestion/pipeline.py` (which now calls into vision analysis), so a
    `services.vision -> services.reports` edge would cycle back."""
    return reports_dir(settings, report.patient_id) / report.stored_filename


def generate_stored_filename(extension: str) -> str:
    return f"{secrets.token_hex(16)}{extension}"


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_file(destination: Path, content: bytes) -> None:
    destination.write_bytes(content)


def delete_file(path: Path) -> None:
    path.unlink(missing_ok=True)
