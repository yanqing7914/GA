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

export GA_MCP_ENABLE_SCREENSHOT=false
export GA_MCP_ENABLE_OCR=false
export GA_MCP_ENABLE_PYTHON=false
export GA_MCP_ENABLE_POWERSHELL=false
export GA_MCP_ENABLE_DESKTOP=false
export GA_MCP_ENABLE_ADB=false
export GA_MCP_ENABLE_BROWSER_CDP=false
export GA_MCP_ENABLE_UI_DETECT=false
export GA_MCP_ENABLE_SKILLS=false
export GA_MCP_ENABLE_MEMORY=false

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

Disabled until explicitly enabled:

- `ga_screenshot`
- `ga_ocr_screenshot`
- `ga_run_python_sandboxed`
- `ga_run_powershell_sandboxed`

Phase 2 tools, also disabled by default:

- `ga_desktop_status`
- `ga_mouse_move`
- `ga_mouse_click`
- `ga_key_press`
- `ga_adb_devices`
- `ga_adb_screenshot`
- `ga_adb_tap`
- `ga_adb_text`
- `ga_cdp_status`
- `ga_cdp_tabs`
- `ga_ui_detect_screenshot`
- `ga_skill_search`
- `ga_skill_run`
- `ga_memory_query`

The execution tools are policy-restricted helpers, not a strong OS sandbox.
They use allowlisted working directories, static risk checks, timeouts, trimmed
environment variables, and output limits. Use a low-privilege user or container
before exposing them to untrusted clients.

Mutating Phase 2 tools require both their feature flag and a matching
`confirm_token` argument. Configure the expected value with
`GA_MCP_CONFIRM_TOKEN`; do not commit real confirm tokens.

## OpenClaw Example

```json
{
  "mcpServers": {
    "genericagent": {
      "transport": "sse",
      "url": "https://genericagent-mcp.example.com/sse",
      "headers": {
        "Authorization": "Bearer ${GA_MCP_TOKEN}"
      }
    }
  }
}
```

Adjust field names to the current OpenClaw MCP configuration format.
