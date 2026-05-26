from __future__ import annotations

import base64
import time
from io import BytesIO

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError


def _capture_png(max_width: int) -> tuple[bytes, tuple[int, int]]:
    from PIL import ImageGrab

    image = ImageGrab.grab()
    width, height = image.size
    if max_width and width > max_width:
        ratio = max_width / float(width)
        image = image.resize((max_width, max(1, int(height * ratio))))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue(), (width, height)


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_screenshot(display: int = 0, max_width: int = 1600) -> dict:
        """Capture the current screen. Disabled unless GA_MCP_ENABLE_SCREENSHOT=true."""
        with audit.call("ga_screenshot", transport):
            if not config.enable_screenshot:
                raise SafetyError("ga_screenshot is disabled by policy")
            if display != 0:
                raise ValueError("Only display=0 is supported in Phase 1")
            png, size = _capture_png(max(1, min(int(max_width), 4000)))
            return {
                "image_base64": base64.b64encode(png).decode("ascii"),
                "mime_type": "image/png",
                "screen_size": {"width": size[0], "height": size[1]},
                "ts": int(time.time()),
            }

    @mcp.tool()
    def ga_ocr_screenshot(display: int = 0, max_width: int = 1600, region: list[int] | None = None) -> dict:
        """OCR the current screen. Disabled unless GA_MCP_ENABLE_OCR=true."""
        with audit.call("ga_ocr_screenshot", transport):
            if not config.enable_ocr:
                raise SafetyError("ga_ocr_screenshot is disabled by policy")
            if display != 0:
                raise ValueError("Only display=0 is supported in Phase 1")
            try:
                from PIL import ImageGrab
                from memory.ocr_utils import ocr_image
            except Exception as exc:
                raise RuntimeError(f"OCR dependencies are not available: {type(exc).__name__}") from exc

            bbox = tuple(region) if region else None
            image = ImageGrab.grab(bbox=bbox)
            if max_width and image.width > max_width:
                ratio = max_width / float(image.width)
                image = image.resize((max_width, max(1, int(image.height * ratio))))
            try:
                result = ocr_image(image)
            except Exception as exc:
                return {
                    "ok": False,
                    "text": "",
                    "lines": [],
                    "region": region,
                    "ts": int(time.time()),
                    "truncated": False,
                    "error": f"OCR failed: {type(exc).__name__}",
                    "hint": "Install/configure OCR dependencies such as rapidocr-onnxruntime for full OCR support.",
                }
            text = str(result.get("text", ""))
            truncated = len(text) > config.max_output_chars
            return {
                "ok": True,
                "text": text[: config.max_output_chars],
                "lines": result.get("lines", [])[:200],
                "region": region,
                "ts": int(time.time()),
                "truncated": truncated,
            }
