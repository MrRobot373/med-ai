from __future__ import annotations


class AppError(Exception):
    """Domain error with an HTTP status and a user-presentable message."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ServiceUnavailable(AppError):
    """An AI / retrieval dependency is unreachable or misconfigured. Never silently
    papered over with an ungrounded fallback."""

    status_code = 503
    code = "service_unavailable"
