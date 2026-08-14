"""Upload validation — spec §93 "Uploaded-File Safety".

Validates by file extension AND a magic-byte sniff of the actual content, not by
trusting the browser-supplied Content-Type header alone (trivially spoofable). Nothing
here ever executes uploaded content; this module only decides accept/reject.
"""

from __future__ import annotations

from dataclasses import dataclass

# extension -> (display mime type, magic-byte checker)
_MAGIC_CHECKS = {
    ".pdf": lambda head: head.startswith(b"%PDF-"),
    ".docx": lambda head: head.startswith(b"PK\x03\x04"),  # zip container
    ".xlsx": lambda head: head.startswith(b"PK\x03\x04"),
    ".png": lambda head: head.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda head: head.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda head: head.startswith(b"\xff\xd8\xff"),
    ".webp": lambda head: head[0:4] == b"RIFF" and head[8:12] == b"WEBP",
    ".dcm": lambda head: head[128:132] == b"DICM",
}

EXTENSION_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".dcm": "application/dicom",
}

ALLOWED_EXTENSIONS = frozenset(EXTENSION_MIME)
MAGIC_SNIFF_BYTES = 132  # covers the DICOM 128-byte preamble + "DICM" marker


@dataclass
class ValidationResult:
    ok: bool
    extension: str | None = None
    mime_type: str | None = None
    error: str | None = None


def sanitize_display_filename(original: str) -> str:
    """The clinician-facing name (`source_filename`) — stripped of any path
    components so a crafted filename can never influence where anything is written;
    the actual on-disk name is always a separately generated random token."""
    name = original.replace("\\", "/").rsplit("/", 1)[-1]
    return name[:255] or "upload"


def extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_upload(filename: str, head_bytes: bytes, size_bytes: int, max_mb: int) -> ValidationResult:
    ext = extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        return ValidationResult(
            ok=False,
            error=f"Unsupported file type '{ext or '(none)'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if size_bytes > max_mb * 1024 * 1024:
        return ValidationResult(ok=False, error=f"File exceeds the {max_mb} MB upload limit")

    if size_bytes == 0:
        return ValidationResult(ok=False, error="File is empty")

    checker = _MAGIC_CHECKS[ext]
    if not checker(head_bytes):
        return ValidationResult(
            ok=False,
            error=f"File content does not match its '{ext}' extension (failed signature check)",
        )

    return ValidationResult(ok=True, extension=ext, mime_type=EXTENSION_MIME[ext])
