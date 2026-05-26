from __future__ import annotations

import base64
import subprocess

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError, clamp_timeout, require_confirm, truncate_text


def _adb(config: McpConfig, args: list[str], timeout: int = 10) -> dict:
    try:
        proc = subprocess.run(
            [config.adb_path, *args],
            text=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SafetyError("adb executable not found") from exc
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    stdout, out_trunc = truncate_text(stdout, config.max_output_chars)
    stderr, err_trunc = truncate_text(stderr, config.max_output_chars)
    return {
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": out_trunc or err_trunc,
    }


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_adb_devices() -> dict:
        """List connected Android devices. Disabled by default."""
        with audit.call("ga_adb_devices", transport):
            if not config.enable_adb:
                raise SafetyError("ga_adb_devices is disabled by policy")
            return _adb(config, ["devices"], timeout=10)

    @mcp.tool()
    def ga_adb_screenshot(max_bytes: int = 2_000_000) -> dict:
        """Capture Android screenshot as base64 PNG. Disabled by default."""
        with audit.call("ga_adb_screenshot", transport):
            if not config.enable_adb:
                raise SafetyError("ga_adb_screenshot is disabled by policy")
            proc = subprocess.run(
                [config.adb_path, "exec-out", "screencap", "-p"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=clamp_timeout(config, 10),
            )
            if proc.returncode != 0:
                return {"exit_code": proc.returncode, "stderr": proc.stderr.decode("utf-8", errors="replace")}
            data = proc.stdout[: max(1, int(max_bytes))]
            return {
                "exit_code": 0,
                "mime_type": "image/png",
                "image_base64": base64.b64encode(data).decode("ascii"),
                "truncated": len(proc.stdout) > len(data),
            }

    @mcp.tool()
    def ga_adb_tap(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Tap Android screen coordinates. Requires confirm token."""
        with audit.call("ga_adb_tap", transport, risk_level="high"):
            if not config.enable_adb:
                raise SafetyError("ga_adb_tap is disabled by policy")
            require_confirm(config, confirm_token, "ga_adb_tap")
            return _adb(config, ["shell", "input", "tap", str(int(x)), str(int(y))], timeout=10)

    @mcp.tool()
    def ga_adb_text(text: str, confirm_token: str | None = None) -> dict:
        """Type text into Android device. Requires confirm token."""
        with audit.call("ga_adb_text", transport, risk_level="high"):
            if not config.enable_adb:
                raise SafetyError("ga_adb_text is disabled by policy")
            require_confirm(config, confirm_token, "ga_adb_text")
            safe = text.replace(" ", "%s")
            return _adb(config, ["shell", "input", "text", safe], timeout=10)
