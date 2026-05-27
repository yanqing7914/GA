from __future__ import annotations

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class StaticBearerTokenVerifier(TokenVerifier):
    def __init__(self, token: str):
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token, self._token):
            return AccessToken(token="redacted", client_id="genericagent-mcp", scopes=["ga:mcp"])
        return None


class StaticBearerMiddleware:
    def __init__(self, app: ASGIApp, token: str, protected_prefixes: tuple[str, ...]):
        self.app = app
        self._token = token
        self._protected_prefixes = protected_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        if not any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in self._protected_prefixes):
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers", [])}
        header = headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() == "bearer" and secrets.compare_digest(value, self._token):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            {"error": "invalid_token"},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="genericagent-mcp"'},
        )
        await response(scope, receive, send)


class SseNoBufferingMiddleware:
    def __init__(self, app: ASGIApp, sse_path: str):
        self.app = app
        self._sse_path = sse_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != self._sse_path:
            await self.app(scope, receive, send)
            return

        first_body = True

        async def send_with_headers(message):
            nonlocal first_body
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers = [(key, value) for key, value in headers if key.lower() not in {b"cache-control", b"x-accel-buffering"}]
                headers.append((b"cache-control", b"no-cache, no-transform"))
                headers.append((b"x-accel-buffering", b"no"))
                message["headers"] = headers
            elif message["type"] == "http.response.body" and first_body and message.get("body"):
                first_body = False
                # Some reverse tunnels buffer tiny SSE chunks; a comment padding
                # frame keeps MCP events intact while forcing an early flush.
                message["body"] = message.get("body", b"") + b": " + (b" " * 131072) + b"\r\n\r\n"
            await send(message)

        await self.app(scope, receive, send_with_headers)
