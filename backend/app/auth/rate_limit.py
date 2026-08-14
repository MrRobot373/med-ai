"""Minimal in-process login rate limiter — spec §92 "rate limiting on authentication".

This is intentionally a plain in-memory sliding window, not Redis-backed: the app runs
as a single local uvicorn process for this demo (spec §135 "avoid unnecessary
infrastructure"). It will NOT coordinate across multiple worker processes — documented
here rather than silently pretending to be production-grade multi-worker protection.
"""

from __future__ import annotations

import time
from collections import defaultdict

from app.config.settings import Settings


class LoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, window_seconds: int) -> None:
        cutoff = time.monotonic() - window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t >= cutoff]

    def is_blocked(self, key: str, settings: Settings) -> bool:
        self._prune(key, settings.login_rate_limit_window_seconds)
        return len(self._attempts[key]) >= settings.login_rate_limit_attempts

    def record_attempt(self, key: str) -> None:
        self._attempts[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


# Process-lifetime singleton — deliberately module-level rather than DI-constructed
# per-request, since the whole point is to accumulate state across requests.
login_rate_limiter = LoginRateLimiter()
