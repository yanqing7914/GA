# GenericAgent MCP Server

This package exposes low-risk GenericAgent local capabilities as MCP tools.
Long-running natural-language tasks should use `frontends/genericagent_acp_bridge.py`, not a blocking MCP tool.

## Install

```bash
pip install -e ".[mcp]"
```

## Environment

```bash
export GA_MCP_ALLOWED_ROOTS="/path/to/GenericAgent"
export GA_MCP_AUDIT_LOG="$HOME/.genericagent/mcp_audit.log"

# Read-only wow tools default to true.
export GA_MCP_ENABLE_SCREENSHOT=true
export GA_MCP_ENABLE_OCR=true

# Mutating or heavyweight tools default to false.
export GA_MCP_ENABLE_PYTHON=false
export GA_MCP_ENABLE_POWERSHELL=false
export GA_MCP_ENABLE_DESKTOP=false
export GA_MCP_ENABLE_ADB=false
export GA_MCP_ENABLE_BROWSER_CDP=false
export GA_MCP_ENABLE_UI_DETECT=false
export GA_MCP_ENABLE_SKILLS=false
export GA_MCP_ENABLE_MEMORY=false
export GA_MCP_ENABLE_CODING_AGENTS=false

# Required for mutating Phase 2 actions such as mouse click or adb tap.
export GA_MCP_CONFIRM_TOKEN="replace-with-confirm-secret"

export GA_MCP_MAX_OUTPUT_CHARS=20000
export GA_MCP_DEFAULT_TIMEOUT_SECONDS=10
export GA_MCP_MAX_TIMEOUT_SECONDS=30
```

For HTTP/SSE transport, set a bearer token through the environment:

```bash
export GA_MCP_TOKEN="replace-with-secret"
```

Do not commit real tokens.

## Run Locally

For local MCP clients:

```bash
python ga_mcp_server.py --transport stdio
```

For her/OpenClaw through a tunnel:

```bash
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

HTTP transports use `--auth-mode static` by default. In this mode
`GA_MCP_TOKEN` is the exact bearer token accepted by the server:

```http
Authorization: Bearer replace-with-secret
```

The legacy MCP SDK OAuth resource-server metadata mode is still available only
when explicitly requested:

```bash
python ga_mcp_server.py --transport sse --auth-mode oauth --host 127.0.0.1 --port 5050
```

The server refuses to listen on `0.0.0.0`. Use a named Cloudflare Tunnel for remote access.

## Health Check

```bash
curl http://127.0.0.1:5050/healthz
```

`/healthz` intentionally does not return tokens, full environment variables, or secret paths.

## Tools

Default enabled:

- `ga_status`
- `ga_list_project_files`
- `ga_search_project`
- `ga_read_project_file`
- `ga_task_dryrun`
- `ga_screenshot`
- `ga_ocr_screenshot`

Disabled until explicitly enabled:

- `ga_run_python_sandboxed`
- `ga_run_powershell_sandboxed`

Phase 2 tools, also disabled by default:

- `ga_desktop_status`
- `ga_mouse_move`
- `ga_mouse_click`
- `ga_mouse_double_click`
- `ga_mouse_right_click`
- `ga_mouse_drag`
- `ga_key_press`
- `ga_keyboard_type`
- `ga_adb_devices`
- `ga_adb_screenshot`
- `ga_adb_tap`
- `ga_adb_text`
- `ga_adb_swipe`
- `ga_adb_keyevent`
- `ga_cdp_status`
- `ga_cdp_tabs`
- `ga_cdp_execute_js`
- `ga_cdp_screenshot`
- `ga_cdp_scan_page`
- `ga_ui_detect_screenshot`
- `ga_skill_search`
- `ga_skill_run`
- `ga_memory_query`
- `ga_run_claude_code`
- `ga_run_codex`
- `ga_cursor_open`

The execution tools are policy-restricted helpers, not a strong OS sandbox.
They use allowlisted working directories, static risk checks, timeouts, trimmed
environment variables, and output limits. Use a low-privilege user or container
before exposing them to untrusted clients.

Mutating Phase 2 tools require both their feature flag and a matching
`confirm_token` argument. Configure the expected value with
`GA_MCP_CONFIRM_TOKEN`; do not commit real confirm tokens.

## OpenClaw Example

OpenClaw currently uses `mcp.servers` for MCP server configuration. Remote
servers can use `url` plus `transport`.

```json
{
  "mcp": {
    "servers": {
      "genericagent": {
        "transport": "sse",
        "url": "https://genericagent-mcp.example.com/sse",
        "headers": {
          "Authorization": "Bearer ${GA_MCP_TOKEN}"
        }
      }
    }
  }
}
```
