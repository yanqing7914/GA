from __future__ import annotations

import subprocess
from pathlib import Path

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import (
    DEFAULT_EXCLUDES,
    SafetyError,
    ensure_not_secret,
    is_within,
    is_binary_bytes,
    is_secret_path,
    relative_display_path,
    resolve_allowed_path,
    should_exclude,
    truncate_text,
)


def _iter_files(config: McpConfig, root: Path, include: str, exclude: list[str]) -> list[Path]:
    results: list[Path] = []
    for path in root.rglob("*"):
        rel = relative_display_path(config, path)
        if should_exclude(rel, [*DEFAULT_EXCLUDES, *exclude]):
            continue
        if path.is_symlink():
            resolved = path.resolve()
            if not any(is_within(resolved, allowed) for allowed in config.allowed_roots):
                continue
        if path.is_file() and path.match(include) and not is_secret_path(path):
            results.append(path)
    return results


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_list_project_files(
        path: str = ".",
        include: str = "**/*",
        exclude: list[str] | None = None,
        max_results: int = 200,
    ) -> dict:
        """List files inside allowed roots without leaking absolute paths."""
        with audit.call("ga_list_project_files", transport, path=path) as audit_record:
            root = resolve_allowed_path(config, path)
            if not root.exists():
                raise FileNotFoundError("Path not found")
            if root.is_file():
                files = [root]
            else:
                files = _iter_files(config, root, include, exclude or [])
            max_results = max(1, min(int(max_results), 1000))
            visible = files[:max_results]
            audit_record["truncated"] = len(files) > len(visible)
            return {
                "files": [relative_display_path(config, item) for item in visible],
                "truncated": len(files) > len(visible),
            }

    @mcp.tool()
    def ga_search_project(
        query: str,
        path: str = ".",
        max_results: int = 50,
        case_sensitive: bool = False,
    ) -> dict:
        """Search text files inside allowed roots."""
        with audit.call("ga_search_project", transport, path=path) as audit_record:
            if not query:
                raise ValueError("query is required")
            root = resolve_allowed_path(config, path)
            max_results = max(1, min(int(max_results), 200))
            matches = _search_with_rg(config, root, query, max_results, case_sensitive)
            if matches is None:
                matches = _search_with_python(config, root, query, max_results, case_sensitive)
            audit_record["truncated"] = len(matches) >= max_results
            return {"matches": matches, "truncated": len(matches) >= max_results}

    @mcp.tool()
    def ga_read_project_file(path: str, offset: int = 0, limit: int = 20000) -> dict:
        """Read a text file inside allowed roots with paging."""
        with audit.call("ga_read_project_file", transport, path=path) as audit_record:
            target = resolve_allowed_path(config, path)
            ensure_not_secret(target)
            if not target.is_file():
                raise FileNotFoundError("File not found")
            limit = max(1, min(int(limit), min(config.max_output_chars, 1_000_000)))
            offset = max(0, int(offset))
            with target.open("rb") as fh:
                fh.seek(offset)
                data = fh.read(limit + 1)
            if is_binary_bytes(data):
                raise SafetyError("Binary files are not returned by default")
            truncated = len(data) > limit
            audit_record["truncated"] = truncated
            content = data[:limit].decode("utf-8", errors="replace")
            return {
                "path": relative_display_path(config, target),
                "content": content,
                "offset": offset,
                "next_offset": offset + limit if truncated else None,
                "truncated": truncated,
            }


def _search_with_rg(
    config: McpConfig,
    root: Path,
    query: str,
    max_results: int,
    case_sensitive: bool,
) -> list[dict] | None:
    cmd = ["rg", "--no-heading", "--line-number", "--no-follow", "--color", "never"]
    if not case_sensitive:
        cmd.append("--ignore-case")
    for pattern in DEFAULT_EXCLUDES:
        cmd.extend(["--glob", "!" + pattern])
    for pattern in ("*.pem", "*.key", "*.p12", "*.pfx", ".env", ".env.*", "*token*", "*secret*", "credentials*"):
        cmd.extend(["--glob", "!" + pattern])
    cmd.extend([query, str(root)])
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=10)
    except Exception:
        return None
    if proc.returncode not in (0, 1):
        return None
    matches: list[dict] = []
    for line in proc.stdout.splitlines():
        if len(matches) >= max_results:
            break
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        file_path = Path(parts[0]).resolve()
        try:
            ensure_not_secret(file_path)
        except SafetyError:
            continue
        text, _ = truncate_text(parts[2], 500)
        matches.append({"path": relative_display_path(config, file_path), "line": int(parts[1]), "text": text})
    return matches


def _search_with_python(
    config: McpConfig,
    root: Path,
    query: str,
    max_results: int,
    case_sensitive: bool,
) -> list[dict]:
    needle = query if case_sensitive else query.lower()
    matches: list[dict] = []
    files = _iter_files(config, root, "**/*", [])
    for file_path in files:
        if len(matches) >= max_results:
            break
        try:
            ensure_not_secret(file_path)
            data = file_path.read_bytes()
        except Exception:
            continue
        if len(data) > 1_000_000 or is_binary_bytes(data):
            continue
        for line_no, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), start=1):
            hay = line if case_sensitive else line.lower()
            if needle in hay:
                text, _ = truncate_text(line, 500)
                matches.append({"path": relative_display_path(config, file_path), "line": line_no, "text": text})
                if len(matches) >= max_results:
                    break
    return matches
