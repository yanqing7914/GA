from __future__ import annotations

from pathlib import Path

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError, is_binary_bytes, relative_display_path, truncate_text


SKILL_EXTENSIONS = {".md", ".txt", ".py"}


def _memory_root(config: McpConfig) -> Path:
    return config.repo_root / "memory"


def _skill_files(config: McpConfig) -> list[Path]:
    root = _memory_root(config)
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SKILL_EXTENSIONS]


def _search_memory(config: McpConfig, query: str, max_results: int) -> dict:
    needle = query.lower()
    matches = []
    for path in _skill_files(config):
        try:
            data = path.read_bytes()
        except Exception:
            continue
        if is_binary_bytes(data):
            continue
        text = data.decode("utf-8", errors="replace")
        if needle in text.lower() or needle in path.name.lower():
            preview, _ = truncate_text(text.strip().replace("\r", ""), 500)
            matches.append({"path": relative_display_path(config, path), "preview": preview})
        if len(matches) >= max_results:
            break
    return {"matches": matches, "truncated": len(matches) >= max_results}


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_skill_search(query: str, max_results: int = 20) -> dict:
        """Search GenericAgent memory/skill/SOP files. Disabled by default."""
        with audit.call("ga_skill_search", transport):
            if not config.enable_skills:
                raise SafetyError("ga_skill_search is disabled by policy")
            return _search_memory(config, query, max(1, min(int(max_results), 100)))

    @mcp.tool()
    def ga_skill_run(path: str) -> dict:
        """Return a skill/SOP file for human/agent execution; does not execute it."""
        with audit.call("ga_skill_run", transport, path=path):
            if not config.enable_skills:
                raise SafetyError("ga_skill_run is disabled by policy")
            target = (config.repo_root / path).resolve()
            root = _memory_root(config).resolve()
            if root not in target.parents and target != root:
                raise SafetyError("Only memory skill/SOP files can be loaded")
            if target.suffix.lower() not in SKILL_EXTENSIONS:
                raise SafetyError("Unsupported skill file type")
            data = target.read_bytes()
            if is_binary_bytes(data):
                raise SafetyError("Binary skill files are not supported")
            content, truncated = truncate_text(data.decode("utf-8", errors="replace"), config.max_output_chars)
            return {
                "path": relative_display_path(config, target),
                "content": content,
                "truncated": truncated,
                "executed": False,
                "note": "MCP returns the skill/SOP content only; long-running execution belongs to ACP Bridge.",
            }

    @mcp.tool()
    def ga_memory_query(query: str, max_results: int = 20) -> dict:
        """Search GenericAgent memory files. Disabled by default."""
        with audit.call("ga_memory_query", transport):
            if not config.enable_memory:
                raise SafetyError("ga_memory_query is disabled by policy")
            return _search_memory(config, query, max(1, min(int(max_results), 100)))
