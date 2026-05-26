from __future__ import annotations

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier


class StaticBearerTokenVerifier(TokenVerifier):
    def __init__(self, token: str):
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token, self._token):
            return AccessToken(token="redacted", client_id="genericagent-mcp", scopes=["ga:mcp"])
        return None
