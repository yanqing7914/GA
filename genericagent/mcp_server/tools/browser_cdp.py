from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import urlopen

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError, truncate_text


def _get_json(url: str, timeout: int = 5):
    try:
        with urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except URLError as exc:
        raise SafetyError("Chrome CDP endpoint is not reachable") from exc


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_cdp_status() -> dict:
        """Inspect Chrome DevTools Protocol availability. Disabled by default."""
        with audit.call("ga_cdp_status", transport):
            if not config.enable_browser_cdp:
                raise SafetyError("ga_cdp_status is disabled by policy")
            base = f"http://{config.cdp_host}:{config.cdp_port}"
            version = _get_json(base + "/json/version")
            return {"ok": True, "host": config.cdp_host, "port": config.cdp_port, "version": version}

    @mcp.tool()
    def ga_cdp_tabs(max_results: int = 20) -> dict:
        """List Chrome CDP tabs. Disabled by default."""
        with audit.call("ga_cdp_tabs", transport):
            if not config.enable_browser_cdp:
                raise SafetyError("ga_cdp_tabs is disabled by policy")
            base = f"http://{config.cdp_host}:{config.cdp_port}"
            tabs = _get_json(base + "/json")
            out = []
            for tab in tabs[: max(1, min(int(max_results), 100))]:
                title, _ = truncate_text(str(tab.get("title", "")), 200)
                url, _ = truncate_text(str(tab.get("url", "")), 500)
                out.append({"id": tab.get("id"), "type": tab.get("type"), "title": title, "url": url})
            return {"tabs": out, "truncated": len(tabs) > len(out)}
