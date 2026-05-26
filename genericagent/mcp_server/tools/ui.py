from __future__ import annotations

import tempfile
from pathlib import Path

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_ui_detect_screenshot(mode: str = "crop", max_results: int = 100) -> dict:
        """Run UI detection on a fresh screenshot. Disabled by default."""
        with audit.call("ga_ui_detect_screenshot", transport):
            if not config.enable_ui_detect:
                raise SafetyError("ga_ui_detect_screenshot is disabled by policy")
            try:
                from PIL import ImageGrab
                from memory.ui_detect import detect
            except Exception as exc:
                raise RuntimeError(f"UI detection dependencies are not available: {type(exc).__name__}") from exc
            image = ImageGrab.grab()
            tmp = Path(tempfile.gettempdir()) / "ga_mcp_ui_detect.png"
            image.save(tmp)
            elements = detect(str(tmp), mode=mode)
            max_results = max(1, min(int(max_results), 500))
            return {"elements": elements[:max_results], "truncated": len(elements) > max_results}
