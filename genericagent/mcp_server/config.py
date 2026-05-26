from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _split_roots(raw: str | None) -> list[Path]:
    if not raw:
        return [REPO_ROOT]
    parts: list[str] = []
    text = raw.strip()
    if text.startswith("["):
        try:
            import json

            loaded = json.loads(text)
            if isinstance(loaded, list):
                parts = [str(item) for item in loaded]
        except Exception:
            parts = []
    if not parts:
        parts = [part for part in text.split(os.pathsep) if part.strip()]
    return [Path(part).expanduser().resolve() for part in parts] or [REPO_ROOT]


@dataclass(frozen=True)
class McpConfig:
    repo_root: Path
    allowed_roots: tuple[Path, ...]
    audit_log: Path
    token: str | None
    enable_screenshot: bool
    enable_ocr: bool
    enable_python: bool
    enable_powershell: bool
    enable_desktop: bool
    enable_adb: bool
    enable_browser_cdp: bool
    enable_ui_detect: bool
    enable_skills: bool
    enable_memory: bool
    confirm_token: str | None
    adb_path: str
    cdp_host: str
    cdp_port: int
    max_output_chars: int
    default_timeout_seconds: int
    max_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "McpConfig":
        audit_default = Path.home() / ".genericagent" / "mcp_audit.log"
        max_timeout = max(1, _env_int("GA_MCP_MAX_TIMEOUT_SECONDS", 30))
        default_timeout = max(1, min(_env_int("GA_MCP_DEFAULT_TIMEOUT_SECONDS", 10), max_timeout))
        return cls(
            repo_root=REPO_ROOT,
            allowed_roots=tuple(_split_roots(os.getenv("GA_MCP_ALLOWED_ROOTS"))),
            audit_log=Path(os.getenv("GA_MCP_AUDIT_LOG", str(audit_default))).expanduser(),
            token=os.getenv("GA_MCP_TOKEN"),
            enable_screenshot=_env_bool("GA_MCP_ENABLE_SCREENSHOT", False),
            enable_ocr=_env_bool("GA_MCP_ENABLE_OCR", False),
            enable_python=_env_bool("GA_MCP_ENABLE_PYTHON", False),
            enable_powershell=_env_bool("GA_MCP_ENABLE_POWERSHELL", False),
            enable_desktop=_env_bool("GA_MCP_ENABLE_DESKTOP", False),
            enable_adb=_env_bool("GA_MCP_ENABLE_ADB", False),
            enable_browser_cdp=_env_bool("GA_MCP_ENABLE_BROWSER_CDP", False),
            enable_ui_detect=_env_bool("GA_MCP_ENABLE_UI_DETECT", False),
            enable_skills=_env_bool("GA_MCP_ENABLE_SKILLS", False),
            enable_memory=_env_bool("GA_MCP_ENABLE_MEMORY", False),
            confirm_token=os.getenv("GA_MCP_CONFIRM_TOKEN"),
            adb_path=os.getenv("GA_MCP_ADB_PATH", "adb"),
            cdp_host=os.getenv("GA_MCP_CDP_HOST", "127.0.0.1"),
            cdp_port=_env_int("GA_MCP_CDP_PORT", 9222),
            max_output_chars=max(1000, _env_int("GA_MCP_MAX_OUTPUT_CHARS", 20000)),
            default_timeout_seconds=default_timeout,
            max_timeout_seconds=max_timeout,
        )

    def capability_summary(self) -> dict[str, bool]:
        return {
            "screenshot_enabled": self.enable_screenshot,
            "ocr_enabled": self.enable_ocr,
            "python_enabled": self.enable_python,
            "powershell_enabled": self.enable_powershell,
            "desktop_enabled": self.enable_desktop,
            "adb_enabled": self.enable_adb,
            "browser_cdp_enabled": self.enable_browser_cdp,
            "ui_detect_enabled": self.enable_ui_detect,
            "skills_enabled": self.enable_skills,
            "memory_enabled": self.enable_memory,
        }
