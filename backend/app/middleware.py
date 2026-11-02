"""Browser protections applied to every response: security headers, no caching of patient data,
and a cross-site request check on anything that changes state."""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

# The built app is served from its own origin, loads nothing from elsewhere, and needs inline *styles*
# only (React style props, chart libraries); there are no inline scripts.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return None


class SecurityMiddleware:
    """Pure ASGI (no response buffering, so streamed AI answers stay streamed)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        method = scope["method"]
        path: str = scope["path"]

        if method in UNSAFE and self._cross_site(scope, settings):
            body = b'{"detail":"Cross-site request blocked.","code":"csrf"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])]
                names = {k.lower() for k, _ in headers}

                def add(k: str, v: str) -> None:
                    if k.encode() not in names:
                        headers.append((k.encode(), v.encode()))

                add("x-content-type-options", "nosniff")
                add("x-frame-options", "DENY")
                add("referrer-policy", "same-origin")
                add("permissions-policy", "camera=(), geolocation=(), payment=(), usb=()")
                add("cross-origin-opener-policy", "same-origin")
                ctype = next((v.decode() for k, v in headers if k.lower() == b"content-type"), "")
                if ctype.startswith("text/html"):
                    add("content-security-policy", CSP)
                if settings.cookie_secure:
                    add("strict-transport-security", "max-age=31536000; includeSubDomains")
                if path.startswith("/api/"):
                    add("cache-control", "no-store")
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

    @staticmethod
    def _cross_site(scope: Scope, settings) -> bool:
        """A browser always sends Origin on a cross-site POST. If it names a different site than the one being
        called (and is not a configured origin), the request is refused. Clients that send no Origin
        (scripts, integration calls with a token) are not browsers and are unaffected."""
        site = _header(scope, b"sec-fetch-site")
        if site == "cross-site":
            return True
        origin = _header(scope, b"origin")
        if not origin:
            return False
        if origin == "null":  # sandboxed frames and local files; never a legitimate caller of this API
            return True
        host = _header(scope, b"host") or ""
        o = urlparse(origin)
        if o.netloc.lower() == host.lower():
            return False
        return origin.rstrip("/") not in {x.rstrip("/") for x in settings.cors_origin_list}
