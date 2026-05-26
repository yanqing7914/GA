from __future__ import annotations

import platform

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError, require_confirm


def _ctrl():
    if platform.system() != "Windows":
        raise SafetyError("Desktop control Phase 2 currently supports Windows only")
    from memory import ljqCtrl

    return ljqCtrl


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_desktop_status() -> dict:
        """Return desktop-control availability without moving mouse or typing."""
        with audit.call("ga_desktop_status", transport):
            return {
                "enabled": config.enable_desktop,
                "platform": platform.system(),
                "write_actions_require_confirm_token": True,
            }

    @mcp.tool()
    def ga_mouse_move(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Move mouse to physical screen coordinates. Disabled by default."""
        with audit.call("ga_mouse_move", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_move is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_move")
            ctrl = _ctrl()
            ctrl.SetCursorPos((int(x), int(y)))
            return {"ok": True, "x": int(x), "y": int(y)}

    @mcp.tool()
    def ga_mouse_click(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Click physical screen coordinates. Disabled by default."""
        with audit.call("ga_mouse_click", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_click is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_click")
            ctrl = _ctrl()
            ctrl.Click(int(x), int(y))
            return {"ok": True, "x": int(x), "y": int(y)}

    @mcp.tool()
    def ga_key_press(keys: str, confirm_token: str | None = None) -> dict:
        """Press a key chord like ctrl+c. Disabled by default."""
        with audit.call("ga_key_press", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_key_press is disabled by policy")
            require_confirm(config, confirm_token, "ga_key_press")
            ctrl = _ctrl()
            ctrl.Press(keys)
            return {"ok": True, "keys": keys}
