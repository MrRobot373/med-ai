"""Optional malware scanning of uploads through a ClamAV daemon (`clamd`) over TCP.

Off unless `CLAMAV_HOST` is set. When on, a file is scanned before it is stored; an infected file is
rejected, and — unless `CLAMAV_FAIL_CLOSED=false` — so is any upload made while the scanner cannot be
reached, because an unscanned file in a clinical record is the risk the scanner exists to remove.
"""

from __future__ import annotations

import socket
import struct

from app.core.config import get_settings
from app.core.errors import AppError, ServiceUnavailable

_CHUNK = 64 * 1024


def enabled() -> bool:
    return bool(get_settings().clamav_host)


def _scan(host: str, port: int, data: bytes, timeout: float = 20.0) -> str:
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(b"zINSTREAM\0")
        for i in range(0, len(data), _CHUNK):
            part = data[i : i + _CHUNK]
            s.sendall(struct.pack("!I", len(part)) + part)
        s.sendall(struct.pack("!I", 0))
        reply = b""
        while not reply.endswith(b"\0") and len(reply) < 4096:
            chunk = s.recv(4096)
            if not chunk:
                break
            reply += chunk
    return reply.rstrip(b"\0\n").decode(errors="replace")


def check(data: bytes, filename: str = "") -> None:
    """Raises `AppError` (422) for an infected file and `ServiceUnavailable` if the scanner is required but down."""
    cfg = get_settings()
    if not cfg.clamav_host:
        return
    try:
        reply = _scan(cfg.clamav_host, cfg.clamav_port, data)
    except OSError as exc:
        if cfg.clamav_fail_closed:
            raise ServiceUnavailable(
                "The virus scanner is not reachable, so this file cannot be accepted right now."
            ) from exc
        return
    if reply.endswith("FOUND"):
        sig = reply.split(":", 1)[-1].replace("FOUND", "").strip()
        raise AppError(
            f"This file was blocked: the virus scanner reported {sig or 'malware'}.", status_code=422, code="malware"
        )
    if not reply.endswith("OK") and cfg.clamav_fail_closed:
        raise ServiceUnavailable(
            "The virus scanner returned an unexpected answer, so this file cannot be accepted right now."
        )
