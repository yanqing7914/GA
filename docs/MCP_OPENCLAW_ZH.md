# GenericAgent MCP Server OpenClaw 接入

本文档说明如何把本机 GenericAgent MCP Server 暴露给 her / OpenClaw 云端容器。

## 1. 本机启动

HTTP/SSE 模式必须配置 token：

```bash
export GA_MCP_TOKEN="replace-with-secret"
export GA_MCP_ALLOWED_ROOTS="/path/to/GenericAgent"
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

Windows PowerShell 示例：

```powershell
$env:GA_MCP_TOKEN = "replace-with-secret"
$env:GA_MCP_ALLOWED_ROOTS = "C:\Users\gongchenhao\Documents\GA"
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

不要把真实 token 写入仓库。

Phase 2 能力默认关闭。需要时逐项开启：

```powershell
$env:GA_MCP_ENABLE_DESKTOP = "true"
$env:GA_MCP_ENABLE_ADB = "true"
$env:GA_MCP_ENABLE_BROWSER_CDP = "true"
$env:GA_MCP_ENABLE_UI_DETECT = "true"
$env:GA_MCP_ENABLE_SKILLS = "true"
$env:GA_MCP_ENABLE_MEMORY = "true"
$env:GA_MCP_CONFIRM_TOKEN = "replace-with-confirm-secret"
```

键鼠、ADB tap/text 等写操作除了功能开关，还必须在 tool 参数里传入匹配的 `confirm_token`。

## 2. 健康检查

```bash
curl http://127.0.0.1:5050/healthz
```

预期返回：

```json
{
  "ok": true,
  "service": "genericagent-mcp",
  "version": "0.1.0",
  "transport": "sse"
}
```

## 3. Cloudflare Named Tunnel

推荐使用 named tunnel：

```bash
cloudflared tunnel create genericagent-mcp
cloudflared tunnel route dns genericagent-mcp genericagent-mcp.example.com
cloudflared tunnel run genericagent-mcp
```

配置示例：

```yaml
tunnel: genericagent-mcp
credentials-file: /path/to/credentials.json

ingress:
  - hostname: genericagent-mcp.example.com
    service: http://127.0.0.1:5050
  - service: http_status:404
```

`trycloudflare` 只适合临时调试，正式接入不要依赖它。

## 4. OpenClaw MCP 配置

OpenClaw 当前使用 `mcp.servers` 配置 MCP server。远程服务可使用 `url` + `transport`。

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

如果 OpenClaw 版本升级导致字段变动，以当前 OpenClaw 文档为准。

## 5. 验收

- OpenClaw 能发现 `genericagent` MCP server。
- OpenClaw 能调用 `ga_status`。
- 无 token 调用 MCP endpoint 失败。
- token 正确时 MCP endpoint 可连接。
- `~/.genericagent/mcp_audit.log` 有调用记录。

长任务不要走 MCP 阻塞工具，应走：

```text
frontends/genericagent_acp_bridge.py
```
# Auth note

HTTP/SSE now defaults to static bearer auth. `GA_MCP_TOKEN` is the direct
access token for OpenClaw/her. Do not use OAuth unless the server is started
with `--auth-mode oauth`.
