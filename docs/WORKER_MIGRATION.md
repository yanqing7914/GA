# 从 worker.py 迁移到 ga-mcp-server

如果你已经有本机 `worker.py` 桥，例如 Flask/FastAPI HTTP endpoint，可以按下表迁移到标准 MCP。

| worker.py endpoint | ga-mcp tool |
|---|---|
| `POST /run` (Claude Code) | `ga_run_claude_code` |
| `POST /run-codex` | `ga_run_codex` |
| `POST /run-cursor` | `ga_cursor_open` |
| `POST /exec` | `ga_run_python_sandboxed` / `ga_run_powershell_sandboxed` |
| `POST /readfile` | `ga_read_project_file` |
| `POST /writefile` | TODO Phase 3: `ga_write_project_file` |

## 双跑过渡期

建议先双跑：

- `worker.py` 保留在 `5000` 端口作为 fallback。
- `ga-mcp-server` 跑在 `5050` 端口作为主入口。
- her/OpenClaw 配置主用 MCP，worker.py 留应急路径。

## 切换示例

```json
{
  "mcp": {
    "servers": {
      "genericagent": {
        "transport": "sse",
        "url": "https://ga-mcp.your-domain.com/sse",
        "headers": {
          "Authorization": "Bearer ${GA_MCP_TOKEN}"
        }
      }
    }
  }
}
```

确认 her 能通过 MCP 调到 `ga_run_claude_code`、`ga_run_codex` 或 `ga_cursor_open` 后，再停掉旧 `worker.py`。
