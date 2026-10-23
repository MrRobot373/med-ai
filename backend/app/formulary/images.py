"""Optional medicine pictures from Wikimedia Commons (freely licensed). Only the
generic name is ever sent — never patient data. Results, including "nothing found",
are cached on disk so each medicine is looked up at most once a week. Any failure
simply means no picture."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "GMS-Clinical-AI/1.0 (self-hosted clinical decision support; medicine reference images)"
NEGATIVE_TTL = 7 * 86400
ERROR_TTL = 3600
MAX_BYTES = 2_000_000
_locks: dict[str, asyncio.Lock] = {}


def cache_dir() -> Path:
    d = get_settings().data_dir / "formulary-images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(gid: str) -> Path:
    return cache_dir() / f"{re.sub(r'[^a-z0-9_]', '', gid)}.json"


def cached(gid: str) -> dict | None:
    p = _meta_path(gid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _strip_html(text: str | None) -> str | None:
    return re.sub(r"<[^>]+>", "", text).strip() if text else None


def _fresh(meta: dict | None) -> bool:
    if not meta:
        return False
    if meta["status"] == "ok":
        return True
    ttl = ERROR_TTL if meta["status"] == "error" else NEGATIVE_TTL
    return time.time() - meta.get("fetched_at", 0) < ttl


async def fetch(gid: str, query: str, client: httpx.AsyncClient | None = None) -> dict:
    """Returns the cache record: {"status": "ok"|"none"|"error", "file", "attribution", …}."""
    meta = cached(gid)
    if _fresh(meta):
        return meta
    lock = _locks.setdefault(gid, asyncio.Lock())
    async with lock:
        meta = cached(gid)
        if _fresh(meta):
            return meta
        record = await _lookup(gid, query, client)
        _meta_path(gid).write_text(json.dumps(record))
        return record


async def _lookup(gid: str, query: str, client: httpx.AsyncClient | None) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "360",
    }
    own = client is None
    client = client or httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    try:
        r = await client.get(API, params=params)
        if r.status_code != 200:
            return {"status": "error", "fetched_at": time.time(), "detail": f"HTTP {r.status_code}"}
        pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        first_word = query.split()[0].lower()
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("mime") not in ("image/jpeg", "image/png") or first_word not in page.get("title", "").lower():
                continue
            thumb = info.get("thumburl") or info.get("url")
            img = await client.get(thumb)
            if img.status_code != 200 or len(img.content) > MAX_BYTES:
                continue
            ext = "png" if info["mime"] == "image/png" else "jpg"
            fname = f"{gid}.{ext}"
            (cache_dir() / fname).write_bytes(img.content)
            em = info.get("extmetadata") or {}
            return {
                "status": "ok",
                "fetched_at": time.time(),
                "file": fname,
                "mime": info["mime"],
                "title": page.get("title", "").removeprefix("File:"),
                "author": _strip_html((em.get("Artist") or {}).get("value")),
                "license": (em.get("LicenseShortName") or {}).get("value"),
                "source_url": info.get("descriptionurl"),
            }
        return {"status": "none", "fetched_at": time.time()}
    except (httpx.HTTPError, ValueError) as exc:
        log.info("Medicine image lookup failed for %s: %s", gid, exc)
        return {"status": "error", "fetched_at": time.time(), "detail": str(exc)[:200]}
    finally:
        if own:
            await client.aclose()


def file_path(meta: dict) -> Path | None:
    if meta.get("status") != "ok" or not meta.get("file"):
        return None
    p = cache_dir() / meta["file"]
    return p if p.exists() else None
