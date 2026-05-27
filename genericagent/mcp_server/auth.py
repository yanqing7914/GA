from __future__ import annotations

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class StaticBearerTokenVerifier(TokenVerifier):
    def __init__(self, token: str):
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token, self._token):
            return AccessToken(token="redacted", client_id="genericagent-mcp", scopes=["ga:mcp"])
        return None


class StaticBearerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str, protected_prefixes: tuple[str, ...]):
        super().__init__(app)
        self._token = token
        self._protected_prefixes = protected_prefixes

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in self._protected_prefixes):
            return await call_next(request)

        header = request.headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() == "bearer" and secrets.compare_digest(value, self._token):
            return await call_next(request)

        return JSONResponse(
            {"error": "invalid_token"},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="genericagent-mcp"'},
        )
