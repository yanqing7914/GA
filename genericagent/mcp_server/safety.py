from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from .config import McpConfig


SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials*",
    "*token*",
    "*secret*",
)

DEFAULT_EXCLUDES = (
    "**/.git/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/node_modules/**",
)

POWERSHELL_DENYLIST = (
    "Remove-Item",
    "rm",
    "del",
    "Invoke-WebRequest",
    "curl",
    "wget",
    "Start-Process",
    "Set-ExecutionPolicy",
    "Stop-Process",
    "Restart-Computer",
    "shutdown",
    "reg",
    "net user",
    "New-LocalUser",
    "Add-LocalGroupMember",
)

PYTHON_DENY_PATTERNS = (
    r"\bimport\s+(socket|requests|urllib|httpx|aiohttp|ftplib|smtplib)\b",
    r"\bfrom\s+(socket|requests|urllib|httpx|aiohttp|ftplib|smtplib)\b",
    r"\bsubprocess\b",
    r"\bos\.system\b",
    r"\bPopen\b",
    r"\bStart-Process\b",
    r"id_rsa",
    r"id_dsa",
    r"id_ed25519",
    r"\.pem",
    r"\.key",
)


class SafetyError(ValueError):
    pass


def _norm(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def is_within(child: Path, parent: Path) -> bool:
    child_s = _norm(child)
    parent_s = _norm(parent)
    try:
        return os.path.commonpath([child_s, parent_s]) == parent_s
    except ValueError:
        return False


def resolve_allowed_path(config: McpConfig, path: str | os.PathLike[str]) -> Path:
    raw = Path(path)
    candidates = [raw.expanduser()] if raw.is_absolute() else [root / raw for root in config.allowed_roots]
    for candidate in candidates:
        resolved = candidate.resolve()
        if any(is_within(resolved, root) for root in config.allowed_roots):
            return resolved
    raise SafetyError("Path outside allowed roots is not allowed")


def relative_display_path(config: McpConfig, path: Path) -> str:
    resolved = path.resolve()
    for root in config.allowed_roots:
        if is_within(resolved, root):
            try:
                return resolved.relative_to(root).as_posix() or "."
            except ValueError:
                pass
    return resolved.name


def is_secret_path(path: Path) -> bool:
    name = path.name
    lowered = name.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in SECRET_PATTERNS)


def ensure_not_secret(path: Path) -> None:
    if any(is_secret_path(part) for part in [path, *path.parents]):
        raise SafetyError("Access denied by secret file policy")


def should_exclude(rel_path: str, patterns: list[str] | tuple[str, ...] | None = None) -> bool:
    rel = rel_path.replace("\\", "/")
    for pattern in patterns or DEFAULT_EXCLUDES:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch("/" + rel, pattern):
            return True
    return False


def is_binary_bytes(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def clamp_timeout(config: McpConfig, timeout_seconds: int | None) -> int:
    if timeout_seconds is None:
        return config.default_timeout_seconds
    return max(1, min(int(timeout_seconds), config.max_timeout_seconds))


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n...[truncated]", True


def check_powershell_command(command: str) -> None:
    lowered = command.lower()
    for denied in POWERSHELL_DENYLIST:
        pattern = r"(?<![\w-])" + re.escape(denied.lower()) + r"(?![\w-])"
        if re.search(pattern, lowered):
            raise SafetyError(f"Command denied by policy: {denied}")


def check_python_risks(code: str) -> list[str]:
    risks: list[str] = []
    for pattern in PYTHON_DENY_PATTERNS:
        if re.search(pattern, code, flags=re.IGNORECASE):
            risks.append(pattern)
    return risks


def require_confirm(config, confirm_token: str | None, action: str) -> None:
    expected = getattr(config, "confirm_token", None)
    if not expected:
        raise SafetyError(f"{action} requires GA_MCP_CONFIRM_TOKEN to be configured")
    if not confirm_token or not isinstance(confirm_token, str):
        raise SafetyError(f"{action} requires confirm_token")
    import secrets

    if not secrets.compare_digest(confirm_token, expected):
        raise SafetyError(f"{action} confirm_token rejected")
