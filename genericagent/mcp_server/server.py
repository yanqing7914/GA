from __future__ import annotations

from starlette.responses import JSONResponse

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from .audit import AuditLogger
from .auth import SseNoBufferingMiddleware, StaticBearerMiddleware, StaticBearerTokenVerifier
from .config import McpConfig
from .tools import adb, browser_cdp, coding_agents, desktop, dryrun, execute, files, screen, skills, status, ui


def build_server(
    config: McpConfig,
    transport: str,
    require_auth: bool = False,
    host: str = "127.0.0.1",
    port: int = 5050,
    auth_mode: str = "static",
) -> FastMCP:
    token_verifier = None
    auth_settings = None
    if require_auth and auth_mode == "oauth":
        if not config.token:
            raise RuntimeError("GA_MCP_TOKEN must be set for authenticated HTTP transport")
        token_verifier = StaticBearerTokenVerifier(config.token)
        base_url = f"http://{host}:{port}"
        auth_settings = AuthSettings(issuer_url=base_url, resource_server_url=base_url, required_scopes=["ga:mcp"])
    elif require_auth and not config.token:
        raise RuntimeError("GA_MCP_TOKEN must be set for authenticated HTTP transport")

    mcp = FastMCP(
        "genericagent-mcp",
        host=host,
        port=port,
        sse_path="/sse",
        message_path="/messages/",
        streamable_http_path="/mcp",
        token_verifier=token_verifier,
        auth=auth_settings,
    )
    if require_auth and auth_mode == "static":
        _install_static_bearer_auth(mcp, config)

    audit = AuditLogger(config.audit_log)
    enabled_tools = [
        "ga_status",
        "ga_list_project_files",
        "ga_search_project",
        "ga_read_project_file",
        "ga_task_dryrun",
    ]
    if config.enable_screenshot:
        enabled_tools.append("ga_screenshot")
    if config.enable_ocr:
        enabled_tools.append("ga_ocr_screenshot")
    if config.enable_python:
        enabled_tools.append("ga_run_python_sandboxed")
    if config.enable_powershell:
        enabled_tools.append("ga_run_powershell_sandboxed")
    if config.enable_desktop:
        enabled_tools.extend(
            [
                "ga_desktop_status",
                "ga_mouse_move",
                "ga_mouse_click",
                "ga_key_press",
                "ga_keyboard_type",
                "ga_mouse_drag",
                "ga_mouse_double_click",
                "ga_mouse_right_click",
                "ga_window_list",
                "ga_window_focus",
                "ga_keyboard_type_window",
            ]
        )
    else:
        enabled_tools.append("ga_desktop_status")
    if config.enable_adb:
        enabled_tools.extend(
            [
                "ga_adb_devices",
                "ga_adb_screenshot",
                "ga_adb_tap",
                "ga_adb_text",
                "ga_adb_swipe",
                "ga_adb_keyevent",
            ]
        )
    if config.enable_browser_cdp:
        enabled_tools.extend(["ga_cdp_status", "ga_cdp_tabs", "ga_cdp_execute_js", "ga_cdp_screenshot", "ga_cdp_scan_page"])
    if config.enable_ui_detect:
        enabled_tools.append("ga_ui_detect_screenshot")
    if config.enable_skills:
        enabled_tools.extend(["ga_skill_search", "ga_skill_run"])
    if config.enable_memory:
        enabled_tools.append("ga_memory_query")
    if config.enable_coding_agents:
        enabled_tools.extend(["ga_run_claude_code", "ga_run_codex", "ga_cursor_open"])
    disabled_count = 0
    if not config.enable_screenshot:
        disabled_count += 1
    if not config.enable_ocr:
        disabled_count += 1
    if not config.enable_python:
        disabled_count += 1
    if not config.enable_powershell:
        disabled_count += 1
    if not config.enable_desktop:
        disabled_count += 10
    if not config.enable_adb:
        disabled_count += 6
    if not config.enable_browser_cdp:
        disabled_count += 5
    if not config.enable_ui_detect:
        disabled_count += 1
    if not config.enable_skills:
        disabled_count += 2
    if not config.enable_memory:
        disabled_count += 1
    if not config.enable_coding_agents:
        disabled_count += 3

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(request):
        return JSONResponse(
            {
                "ok": True,
                "service": "genericagent-mcp",
                "version": "0.1.0",
                "transport": transport,
            }
        )

    status.register(mcp, config, audit, transport, enabled_tools, disabled_count)
    files.register(mcp, config, audit, transport)
    dryrun.register(mcp, config, audit, transport)
    screen.register(mcp, config, audit, transport)
    execute.register(mcp, config, audit, transport)
    desktop.register(mcp, config, audit, transport)
    adb.register(mcp, config, audit, transport)
    browser_cdp.register(mcp, config, audit, transport)
    ui.register(mcp, config, audit, transport)
    skills.register(mcp, config, audit, transport)
    coding_agents.register(mcp, config, audit, transport)
    return mcp


def _install_static_bearer_auth(mcp: FastMCP, config: McpConfig) -> None:
    protected = (
        mcp.settings.sse_path,
        mcp.settings.message_path,
        mcp.settings.streamable_http_path,
    )

    original_sse_app = mcp.sse_app
    original_streamable_http_app = mcp.streamable_http_app

    def sse_app(mount_path: str | None = None):
        app = original_sse_app(mount_path)
        app.add_middleware(SseNoBufferingMiddleware, sse_path=mcp.settings.sse_path)
        app.add_middleware(StaticBearerMiddleware, token=config.token or "", protected_prefixes=protected)
        return app

    def streamable_http_app():
        app = original_streamable_http_app()
        app.add_middleware(StaticBearerMiddleware, token=config.token or "", protected_prefixes=protected)
        return app

    mcp.sse_app = sse_app  # type: ignore[method-assign]
    mcp.streamable_http_app = streamable_http_app  # type: ignore[method-assign]
