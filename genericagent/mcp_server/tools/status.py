from __future__ import annotations

import subprocess
from pathlib import Path

from ..audit import AuditLogger
from ..config import McpConfig


def _git_commit(config: McpConfig) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(config.repo_root),
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str, enabled_tools: list[str]) -> None:
    @mcp.tool()
    def ga_status() -> dict:
        """Return GenericAgent MCP server status and enabled capabilities."""
        with audit.call("ga_status", transport):
            return {
                "ok": True,
                "service": "genericagent-mcp",
                "version": "0.1.0",
                "transport": transport,
                "enabled_tools": enabled_tools,
                "safety": config.capability_summary(),
                "cwd": Path.cwd().name,
                "repo": {
                    "name": "GenericAgent",
                    "root": config.repo_root.name,
                    "commit": _git_commit(config),
                },
            }
