from __future__ import annotations

import json
import asyncio
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


def _target_ws_url(config: McpConfig, target_id: str) -> str:
    base = f"http://{config.cdp_host}:{config.cdp_port}"
    tabs = _get_json(base + "/json")
    for tab in tabs:
        if str(tab.get("id")) == str(target_id):
            ws = tab.get("webSocketDebuggerUrl")
            if ws:
                return str(ws)
    return f"ws://{config.cdp_host}:{config.cdp_port}/devtools/page/{target_id}"


async def _cdp_call_async(ws_url: str, method: str, params: dict | None = None, timeout: int = 10) -> dict:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websockets package is required for CDP tools") from exc
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        msg = {"id": 1, "method": method, "params": params or {}}
        await ws.send(json.dumps(msg))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            data = json.loads(raw)
            if data.get("id") == 1:
                if "error" in data:
                    raise SafetyError(f"CDP {method} failed: {data['error']}")
                return data.get("result", {})


def _cdp_call(config: McpConfig, target_id: str, method: str, params: dict | None = None, timeout: int = 10) -> dict:
    ws_url = _target_ws_url(config, target_id)
    return asyncio.run(_cdp_call_async(ws_url, method, params, timeout))


def _scan_expression(mode: str) -> str:
    if mode == "aria":
        return r"""
(() => {
  const out = [];
  const walk = (node) => {
    if (!node || node.nodeType !== 1) return;
    const el = node;
    const role = el.getAttribute('role') || el.tagName.toLowerCase();
    const name = el.getAttribute('aria-label') || el.innerText || el.value || '';
    if (name && String(name).trim()) out.push(`[${role}] ${String(name).trim().slice(0, 300)}`);
    for (const child of el.children) walk(child);
  };
  walk(document.body);
  return out.join('\n');
})()
"""
    if mode == "markdown":
        return r"""
(() => {
  const lines = [];
  for (const el of document.querySelectorAll('h1,h2,h3,p,li,button,a,input,textarea,select')) {
    const tag = el.tagName.toLowerCase();
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.href || '').trim();
    if (!text) continue;
    if (tag === 'h1') lines.push('# ' + text);
    else if (tag === 'h2') lines.push('## ' + text);
    else if (tag === 'h3') lines.push('### ' + text);
    else if (tag === 'li') lines.push('- ' + text);
    else if (tag === 'a') lines.push('[' + text + '](' + el.href + ')');
    else lines.push(text);
  }
  return lines.join('\n');
})()
"""
    return "document.body ? document.body.innerText : document.documentElement.innerText"


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

    @mcp.tool()
    def ga_cdp_execute_js(target_id: str, expression: str, timeout: int = 10) -> dict:
        """Execute JavaScript in a CDP tab. Disabled by default."""
        with audit.call("ga_cdp_execute_js", transport, risk_level="high") as audit_record:
            if not config.enable_browser_cdp:
                raise SafetyError("ga_cdp_execute_js is disabled by policy")
            result = _cdp_call(
                config,
                target_id,
                "Runtime.evaluate",
                {"expression": expression, "awaitPromise": True, "returnByValue": True},
                timeout=max(1, min(int(timeout), config.max_timeout_seconds)),
            )
            text, truncated = truncate_text(json.dumps(result, ensure_ascii=False), config.max_output_chars)
            audit_record["truncated"] = truncated
            return {"result": text, "truncated": truncated}

    @mcp.tool()
    def ga_cdp_screenshot(target_id: str, full_page: bool = False) -> dict:
        """Capture a CDP tab screenshot as base64 PNG. Disabled by default."""
        with audit.call("ga_cdp_screenshot", transport):
            if not config.enable_browser_cdp:
                raise SafetyError("ga_cdp_screenshot is disabled by policy")
            params = {"format": "png", "captureBeyondViewport": bool(full_page)}
            result = _cdp_call(config, target_id, "Page.captureScreenshot", params, timeout=10)
            return {"image_base64": result.get("data", ""), "mime_type": "image/png"}

    @mcp.tool()
    def ga_cdp_scan_page(target_id: str, mode: str = "markdown", max_chars: int = 10000) -> dict:
        """Extract simplified page content from a CDP tab. Disabled by default."""
        with audit.call("ga_cdp_scan_page", transport) as audit_record:
            if not config.enable_browser_cdp:
                raise SafetyError("ga_cdp_scan_page is disabled by policy")
            if mode not in {"markdown", "text", "aria"}:
                raise ValueError("mode must be one of: markdown, text, aria")
            result = _cdp_call(
                config,
                target_id,
                "Runtime.evaluate",
                {"expression": _scan_expression(mode), "awaitPromise": True, "returnByValue": True},
                timeout=10,
            )
            value = result.get("result", {}).get("value", "")
            text, truncated = truncate_text(str(value), max(1, min(int(max_chars), config.max_output_chars)))
            audit_record["truncated"] = truncated
            return {"mode": mode, "content": text, "truncated": truncated}
