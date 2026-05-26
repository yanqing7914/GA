# GenericAgent MCP Server 落地方案 v3

## 0. 结论

本方案采用分层架构：

```text
MCP Server       = GenericAgent 本机原子能力网关
ACP Bridge       = GenericAgent 长任务 / 会话委派入口
Cloudflare Tunnel = her / OpenClaw 云端访问本机 MCP 的传输桥
```

第一阶段不把 GenericAgent 的完整 agent loop 包装成一个长时间运行的 MCP tool。

MCP 层只暴露低风险、原子化、可审计的本机能力，例如项目文件读取、搜索、状态检查、截图、OCR、受限脚本执行等。

完整自然语言长任务仍然交给已有 ACP Bridge：

```text
frontends/genericagent_acp_bridge.py
```

如果未来确实需要从 MCP 侧提交长任务，也只能设计成异步接口，而不是阻塞式 tool：

```text
ga_submit_task
ga_get_task_status
ga_cancel_task
```

明确不实现阻塞式 `ga_run_task`。

## 1. 背景

GenericAgent 本身具备较强的本机执行能力，包括文件操作、浏览器控制、桌面 GUI 操作、ADB、OCR、屏幕理解、代码执行等。

如果直接把 GenericAgent 的完整 agent loop 暴露成 MCP tool，会有几个问题：

- MCP tool 调用不适合承载长时间、多步骤、不确定结束时间的 agent loop。
- her / OpenClaw 云端容器不在用户本机，不能只依赖 stdio transport。
- 完整 agent loop 权限边界过大，不利于审计和安全控制。
- MCP 更适合暴露原子能力，而不是再套一层完整 agent。
- 长任务委派已有 ACP Bridge，没必要重复造一套不清晰的 MCP 长任务协议。

因此本方案的核心原则是：

- MCP Server 只作为本机原子能力网关。
- ACP Bridge 继续负责完整任务委派。
- 高风险能力分阶段开放。
- 所有能力必须有配置开关、权限边界、超时控制和审计日志。

## 2. 目标

### 2.1 第一阶段目标

第一阶段实现一个安全、可验证、可远程接入的 MCP Server 外壳，并开放一组低风险原子能力。

第一阶段交付：

- 支持 stdio transport，供 Claude Desktop / Cursor / Cline 本机调用。
- 支持 HTTP+SSE 或 streamable HTTP transport，供 her / OpenClaw 云端容器调用。
- 支持 Bearer Token 鉴权。
- 支持 Cloudflare Tunnel 访问链路。
- 支持 `/healthz` 健康检查。
- 支持 audit log。
- 支持项目文件搜索和只读读取。
- 支持截图和 OCR。
- 支持受限 Python / PowerShell 执行。
- 支持自然语言任务 dry-run 权限评估。
- 提供 OpenClaw 接入文档和配置示例。

### 2.2 第二阶段目标

第二阶段再开放 GenericAgent 的高价值本机能力，但仍然拆成明确工具，不开放泛化无限权限入口。

候选能力：

- 浏览器自动化。
- 桌面 GUI 自动化。
- Android ADB 自动化。
- Chrome CDP inspection。
- UI detection。
- skill / SOP 查询与运行。
- GenericAgent memory 查询。

### 2.3 非目标

第一阶段明确不做：

- 不直接开放完整终端权限。
- 不允许任意文件写入。
- 不直接操作键鼠。
- 不直接操作浏览器。
- 不直接操作手机。
- 不自动发送飞书、微信、钉钉等消息。
- 不执行支付、下单、删除、提交审批等高风险动作。
- 不修改 GenericAgent 核心 agent loop。
- 不实现阻塞式 `ga_run_task`。

## 3. 目标客户端与 Transport

必须同时支持两类客户端。

| 客户端 | 运行位置 | 推荐 Transport | 备注 |
|---|---|---|---|
| Claude Desktop | 用户本机 | stdio | 本机开发和调试 |
| Cursor | 用户本机 | stdio | 本机开发和调试 |
| Cline | 用户本机 | stdio | 本机开发和调试 |
| her / OpenClaw | 云端容器 | HTTP+SSE 或 streamable HTTP | 必须经公网隧道访问本机 |

启动方式需要同时支持：

```bash
python ga_mcp_server.py --transport stdio
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

HTTP 模式下 token 必须从环境变量读取：

```bash
export GA_MCP_TOKEN="replace-with-secret"
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

禁止把真实 token 写进代码、配置样例或 README。

## 4. 总体架构

### 4.1 本机客户端链路

```text
Claude Desktop / Cursor / Cline
        |
        | stdio
        v
ga_mcp_server.py
        |
        v
GenericAgent local capabilities
```

本机开发和调试优先使用 stdio，避免网络层复杂度。

### 4.2 her / OpenClaw 云端访问链路

```text
her / OpenClaw cloud
        |
        | HTTPS + Bearer Token
        v
Cloudflare named tunnel
        |
        v
127.0.0.1:5050
        |
        v
ga_mcp_server.py --transport sse
        |
        v
GenericAgent local capabilities
```

HTTP 服务只监听本机：

```text
--host 127.0.0.1
```

公网访问只通过 Cloudflare named tunnel 暴露。

不允许默认监听：

```text
0.0.0.0
```

`trycloudflare` 只能作为临时调试方案，不作为正式接入方案。

## 5. 推荐工程结构

建议新增目录：

```text
genericagent/
  mcp_server/
    ga_mcp_server.py
    config.py
    safety.py
    audit.py
    transports/
      stdio.py
      sse.py
    tools/
      status.py
      files.py
      screen.py
      execute.py
      dryrun.py
    README.md
    tests/
      test_safety.py
      test_files.py
      test_dryrun.py
```

职责划分：

- `ga_mcp_server.py`：入口，解析参数，注册 tools。
- `config.py`：读取环境变量和默认配置。
- `safety.py`：路径校验、权限校验、secret 文件拦截、命令风险判断。
- `audit.py`：统一写 JSONL 审计日志。
- `tools/status.py`：状态工具。
- `tools/files.py`：文件列举、搜索、读取。
- `tools/screen.py`：截图、OCR。
- `tools/execute.py`：受限 Python / PowerShell 执行。
- `tools/dryrun.py`：自然语言任务权限评估。
- `README.md`：启动方式、配置方式、OpenClaw 接入方式、验收方式。

## 6. Phase 0：MCP Server 外壳与远程访问链路

### 6.1 目标

Phase 0 只负责打通 MCP Server 基础链路：

- stdio 模式可启动。
- HTTP+SSE 模式可启动。
- `/healthz` 可访问。
- Bearer Token 鉴权生效。
- MCP endpoint 未鉴权请求会被拒绝。
- audit log 可写入。
- Cloudflare Tunnel 可转发到本机服务。

### 6.2 必须支持的启动参数

```bash
python ga_mcp_server.py --transport stdio
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

参数：

- `--transport`：可选 `stdio`、`sse`。
- `--host`：HTTP 模式监听地址，默认 `127.0.0.1`。
- `--port`：HTTP 模式监听端口，默认 `5050`。
- `--log-level`：日志等级，默认 `info`。

环境变量：

- `GA_MCP_TOKEN`
- `GA_MCP_ALLOWED_ROOTS`
- `GA_MCP_AUDIT_LOG`
- `GA_MCP_ENABLE_SCREENSHOT`
- `GA_MCP_ENABLE_OCR`
- `GA_MCP_ENABLE_PYTHON`
- `GA_MCP_ENABLE_POWERSHELL`
- `GA_MCP_MAX_OUTPUT_CHARS`
- `GA_MCP_DEFAULT_TIMEOUT_SECONDS`
- `GA_MCP_MAX_TIMEOUT_SECONDS`

### 6.3 健康检查

提供：

```text
GET /healthz
```

返回示例：

```json
{
  "ok": true,
  "service": "genericagent-mcp",
  "version": "0.1.0",
  "transport": "sse"
}
```

`/healthz` 不得返回：

- token。
- 完整环境变量。
- 用户目录敏感路径。
- allowed roots 的完整隐私信息。
- secret 文件路径。

### 6.4 鉴权

HTTP MCP endpoint 必须校验：

```text
Authorization: Bearer <token>
```

token 来源：

```text
GA_MCP_TOKEN
```

规则：

- 没有配置 `GA_MCP_TOKEN` 时，HTTP 模式应拒绝启动，或者只允许显式 `--allow-unauthenticated-local` 的本机调试模式。
- token 不允许出现在日志里。
- token 不允许出现在错误信息里。
- token 不允许写入 README 的真实样例。
- `/healthz` 可以不鉴权，但不得泄漏敏感信息。
- MCP tool endpoint 必须鉴权。

## 7. Phase 1：低风险原子能力

Phase 1 开放以下 MCP tools：

- `ga_status`
- `ga_list_project_files`
- `ga_search_project`
- `ga_read_project_file`
- `ga_screenshot`
- `ga_ocr_screenshot`
- `ga_run_python_sandboxed`
- `ga_run_powershell_sandboxed`
- `ga_task_dryrun`

默认开启：

- `ga_status`
- `ga_list_project_files`
- `ga_search_project`
- `ga_read_project_file`
- `ga_task_dryrun`

默认关闭，需要显式配置开启：

- `ga_screenshot`
- `ga_ocr_screenshot`
- `ga_run_python_sandboxed`
- `ga_run_powershell_sandboxed`

## 8. Tool 设计

### 8.1 `ga_status`

用途：返回 MCP Server 和 GenericAgent 本机能力状态。

返回字段：

- server 状态。
- transport 类型。
- enabled tools。
- safety config 摘要。
- 当前工作目录。
- GenericAgent repo 路径摘要。
- 版本号。
- commit hash，如果可获得。

不得返回：

- token。
- 完整环境变量。
- secret 文件内容。
- 用户隐私目录列表。

示例返回：

```json
{
  "ok": true,
  "service": "genericagent-mcp",
  "version": "0.1.0",
  "transport": "sse",
  "enabled_tools": [
    "ga_status",
    "ga_list_project_files",
    "ga_search_project",
    "ga_read_project_file",
    "ga_task_dryrun"
  ],
  "safety": {
    "python_enabled": false,
    "powershell_enabled": false,
    "screenshot_enabled": false,
    "ocr_enabled": false
  }
}
```

### 8.2 `ga_list_project_files`

用途：列出 allowlist roots 内的项目文件。

输入参数：

```json
{
  "path": ".",
  "include": "**/*",
  "exclude": ["**/.git/**", "**/__pycache__/**"],
  "max_results": 200
}
```

限制：

- 只能访问 allowlist roots。
- 默认最大返回 200 条。
- 支持 glob include / exclude。
- 不跟随 symlink 到 allowlist 外。
- 默认排除 `.git`、缓存目录、虚拟环境目录。
- 返回路径应尽量相对化，避免泄漏用户机器完整目录结构。

### 8.3 `ga_search_project`

用途：在 allowlist roots 内搜索文件内容。

输入参数：

```json
{
  "query": "MCP",
  "path": ".",
  "max_results": 50,
  "case_sensitive": false
}
```

实现建议：

- 优先使用 ripgrep。
- 如果系统没有 ripgrep，再 fallback 到 Python 搜索。

限制：

- 只能搜索 allowlist roots。
- 最大结果数限制。
- 单条结果最大长度限制。
- 不搜索 secret 文件。
- 不跟随 symlink 到 allowlist 外。
- 不返回超大文件内容。

返回示例：

```json
{
  "matches": [
    {
      "path": "frontends/genericagent_acp_bridge.py",
      "line": 42,
      "text": "class GenericAgentACPBridge:"
    }
  ],
  "truncated": false
}
```

### 8.4 `ga_read_project_file`

用途：只读读取 allowlist roots 内的文件。

输入参数：

```json
{
  "path": "README.md",
  "offset": 0,
  "limit": 20000
}
```

限制：

- 只能读取 allowlist roots。
- 禁止读取 secret 文件。
- 单次读取最大字节数限制。
- 不跟随 symlink 到 allowlist 外。
- 二进制文件默认拒绝或只返回 metadata。
- 超大文件必须分页读取。

禁止读取的文件模式至少包括：

```text
.env
.env.*
id_rsa
id_dsa
id_ed25519
*.pem
*.key
*.p12
*.pfx
credentials*
*token*
*secret*
```

返回示例：

```json
{
  "path": "README.md",
  "content": "...",
  "offset": 0,
  "next_offset": 20000,
  "truncated": true
}
```

### 8.5 `ga_screenshot`

用途：截取当前屏幕。

输入参数：

```json
{
  "display": 0,
  "max_width": 1600
}
```

返回：

- 图片路径或 base64。
- 屏幕尺寸。
- 时间戳。

限制：

- 默认关闭，需要 `GA_MCP_ENABLE_SCREENSHOT=true`。
- 默认只保存到临时目录。
- 不自动上传外部服务。
- 不自动执行后续动作。
- audit log 记录调用方、时间、结果状态。
- 如系统无图形环境，应返回明确错误。

### 8.6 `ga_ocr_screenshot`

用途：对当前屏幕截图做 OCR。

输入参数：

```json
{
  "display": 0,
  "max_width": 1600,
  "region": null
}
```

返回：

- OCR 文本。
- 可选区域坐标。
- 时间戳。

限制：

- 默认关闭，需要 `GA_MCP_ENABLE_OCR=true`。
- 默认最大图片尺寸限制。
- 默认最大 OCR 文本长度限制。
- 不自动点击、输入或执行后续动作。
- OCR 失败时返回明确错误，不抛出大段内部堆栈。

### 8.7 `ga_run_python_sandboxed`

用途：在受限目录执行 Python 脚本。

输入参数：

```json
{
  "code": "print('hello')",
  "cwd": ".",
  "timeout_seconds": 10
}
```

硬约束：

- 默认关闭，需要 `GA_MCP_ENABLE_PYTHON=true`。
- cwd 必须在 allowlist roots 内。
- 默认超时 10 秒。
- 最大超时 30 秒。
- stdout / stderr 最大长度限制。
- 环境变量白名单。
- 默认禁止读取 secret 文件。
- 默认不允许网络访问，除非配置显式开启。
- 每次执行写 audit log。
- 返回 exit code、stdout、stderr、耗时。
- 不允许长期后台进程。
- 超时必须杀掉子进程。

返回示例：

```json
{
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_ms": 120,
  "truncated": false
}
```

### 8.8 `ga_run_powershell_sandboxed`

用途：执行受限 PowerShell 命令。

输入参数：

```json
{
  "command": "Get-ChildItem",
  "cwd": ".",
  "timeout_seconds": 10
}
```

硬约束：

- 默认关闭，需要 `GA_MCP_ENABLE_POWERSHELL=true`。
- cwd 必须在 allowlist roots 内。
- 默认超时 10 秒。
- 最大超时 30 秒。
- stdout / stderr 最大长度限制。
- 环境变量白名单。
- 每次执行写 audit log。
- 返回 exit code、stdout、stderr、耗时。
- 不允许长期后台进程。
- 超时必须杀掉子进程。

高风险命令 denylist 至少包括：

```text
Remove-Item
rm
del
Invoke-WebRequest
curl
wget
Start-Process
Set-ExecutionPolicy
Stop-Process
Restart-Computer
shutdown
reg
net user
New-LocalUser
Add-LocalGroupMember
```

注意：PowerShell 风险较高，第一版可以只实现框架和 denylist，默认关闭。

### 8.9 `ga_task_dryrun`

用途：评估自然语言任务会需要哪些权限，但不真正执行。

输入参数：

```json
{
  "task": "帮我打开浏览器登录某个网站并下载文件"
}
```

输出字段：

- 风险等级。
- 需要的能力类别。
- 推荐路径。
- 是否需要人工确认。
- 是否适合 MCP 原子工具。
- 是否建议走 ACP Bridge。

示例返回：

```json
{
  "risk": "medium",
  "recommended_path": "ACP Bridge",
  "required_capabilities": [
    "browser",
    "filesystem",
    "network"
  ],
  "requires_human_confirmation": true,
  "reason": "任务包含浏览器登录和文件下载，属于多步骤长任务，不适合阻塞式 MCP tool。"
}
```

推荐路径枚举：

- `MCP`
- `ACP Bridge`
- `Reject`
- `Needs Human Confirmation`

## 9. 安全模型

### 9.1 Allowlist Roots

所有文件相关能力必须限制在 allowlist roots 内。

示例：

```bash
export GA_MCP_ALLOWED_ROOTS="/path/to/GenericAgent"
```

多个目录可用系统分隔符或 JSON 配置表达。

路径处理要求：

- 所有输入路径必须 normalize。
- 必须 resolve symlink。
- resolve 后路径必须仍在 allowlist roots 内。
- 禁止 `../` 越界。
- 禁止通过 symlink 跳出 allowlist。
- 返回给客户端的路径尽量相对化。

### 9.2 Secret 文件保护

对以下文件默认拒绝读取、搜索、返回：

```text
.env
.env.*
*.pem
*.key
*.p12
*.pfx
id_rsa
id_dsa
id_ed25519
credentials*
*secret*
*token*
```

拒绝时返回：

```json
{
  "ok": false,
  "error": "Access denied by secret file policy"
}
```

不要返回真实 secret 内容。

### 9.3 输出限制

统一限制：

```bash
GA_MCP_MAX_OUTPUT_CHARS=20000
```

所有 tool 输出都必须支持截断，并返回 `truncated: true`。

### 9.4 Timeout

统一配置：

```bash
GA_MCP_DEFAULT_TIMEOUT_SECONDS=10
GA_MCP_MAX_TIMEOUT_SECONDS=30
```

所有可能长时间运行的工具必须有 timeout。

### 9.5 高风险能力默认关闭

默认关闭：

```bash
GA_MCP_ENABLE_SCREENSHOT=false
GA_MCP_ENABLE_OCR=false
GA_MCP_ENABLE_PYTHON=false
GA_MCP_ENABLE_POWERSHELL=false
```

用户必须显式开启。

## 10. Audit Log

每次 MCP tool 调用必须写 audit log。

日志格式：JSONL。

每条记录包含：

- timestamp。
- request id。
- tool name。
- caller transport。
- cwd。
- normalized path，如果适用。
- risk level。
- result status。
- duration。
- output truncated flag。
- error type，如果失败。

示例：

```json
{"ts":"2026-05-26T12:00:00Z","request_id":"req_123","tool":"ga_read_project_file","transport":"sse","status":"ok","duration_ms":15,"truncated":false}
```

要求：

- 不记录 token。
- 不记录完整 secret 内容。
- stdout / stderr 只记录截断摘要。
- 失败也要记录。
- audit log 路径可配置。

默认路径：

```text
~/.genericagent/mcp_audit.log
```

## 11. 配置示例

环境变量示例：

```bash
export GA_MCP_TOKEN="replace-with-secret"
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
export GA_MCP_CONFIRM_TOKEN="replace-with-confirm-secret"

export GA_MCP_MAX_OUTPUT_CHARS=20000
export GA_MCP_DEFAULT_TIMEOUT_SECONDS=10
export GA_MCP_MAX_TIMEOUT_SECONDS=30
```

本机 stdio 启动：

```bash
python ga_mcp_server.py --transport stdio
```

本机 HTTP+SSE 启动：

```bash
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

## 12. Cloudflare Tunnel 接入

推荐使用 named tunnel。

示例：

```bash
cloudflared tunnel create genericagent-mcp
cloudflared tunnel route dns genericagent-mcp genericagent-mcp.example.com
cloudflared tunnel run genericagent-mcp
```

Cloudflare config 示例：

```yaml
tunnel: genericagent-mcp
credentials-file: /path/to/credentials.json

ingress:
  - hostname: genericagent-mcp.example.com
    service: http://127.0.0.1:5050
  - service: http_status:404
```

临时调试可用：

```bash
cloudflared tunnel --url http://127.0.0.1:5050
```

但 `trycloudflare` URL 不作为正式方案，因为重启后地址会变化。

## 13. OpenClaw 接入示例

OpenClaw MCP 配置示例：

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

具体字段按 OpenClaw 当前 MCP 配置格式调整。

验收时需要确认：

- OpenClaw 能发现 `genericagent` MCP server。
- OpenClaw 能调用 `ga_status`。
- 无 token 时调用失败。
- token 正确时调用成功。
- audit log 能看到调用记录。

## 14. Phase 0 验收标准

Phase 0 完成后必须满足：

- `python ga_mcp_server.py --transport stdio` 可启动。
- `python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050` 可启动。
- `/healthz` 返回 ok。
- `/healthz` 不泄漏 token。
- 未带 Bearer Token 调 MCP endpoint 会被拒绝。
- Bearer Token 正确时 MCP tool 可调用。
- `ga_status` 可返回基础状态。
- audit log 产生记录。
- Cloudflare Tunnel 可从 OpenClaw 云端访问。
- README 包含启动、鉴权、Tunnel、OpenClaw 接入说明。

## 15. Phase 1 验收标准

Phase 1 完成后必须满足：

- `ga_status` 返回服务状态和 enabled tools。
- `ga_list_project_files` 只能列出 allowlist 内文件。
- `ga_list_project_files` 不会通过 symlink 越界。
- `ga_search_project` 能搜索 GenericAgent 项目内容。
- `ga_search_project` 不搜索 secret 文件。
- `ga_read_project_file` 能读取普通代码文件。
- `ga_read_project_file` 不能读取 `.env`、key、pem 文件。
- `ga_read_project_file` 支持 offset / limit。
- `ga_screenshot` 默认关闭。
- 开启后 `ga_screenshot` 能返回截图。
- `ga_ocr_screenshot` 默认关闭。
- 开启后 `ga_ocr_screenshot` 能返回 OCR 文本。
- `ga_run_python_sandboxed` 默认关闭。
- 开启后 `ga_run_python_sandboxed` 能执行简单 Python。
- `ga_run_python_sandboxed` 超时会被杀掉。
- `ga_run_python_sandboxed` stdout / stderr 会被截断。
- `ga_run_powershell_sandboxed` 默认关闭。
- 开启后 `ga_run_powershell_sandboxed` 能执行低风险命令。
- `ga_run_powershell_sandboxed` 拒绝 denylist 命令。
- `ga_task_dryrun` 能给出风险等级和推荐路径。
- 所有 tool 调用都有 audit log。

## 16. Codex 执行要求

请基于本方案实现 Phase 0 + Phase 1。

优先级如下：

1. 实现最小 MCP Server，可通过 stdio / sse 启动。
2. 实现配置读取、Bearer Token 鉴权、`/healthz`。
3. 实现 audit log。
4. 实现 `ga_status`。
5. 实现 allowlist roots 和路径安全校验。
6. 实现 `ga_list_project_files`。
7. 实现 `ga_search_project`。
8. 实现 `ga_read_project_file`。
9. 实现 `ga_task_dryrun`。
10. 实现 `ga_screenshot`。
11. 实现 `ga_ocr_screenshot`。
12. 实现 `ga_run_python_sandboxed`。
13. 实现 `ga_run_powershell_sandboxed`。
14. 补 README。
15. 补 OpenClaw 接入示例。
16. 补最小测试或手工验收脚本。

明确不要做：

- 不要实现阻塞式 `ga_run_task`。
- 不要开放任意 shell。
- 不要默认开启 Python / PowerShell 执行。
- 不要默认开启截图 / OCR。
- 不要把 token 写进代码。
- 不要把真实 token 写进 README。
- 不要修改 GenericAgent 核心 agent loop。
- 不要实现浏览器、桌面、ADB 自动化；这些留到 Phase 2。

## 17. Phase 2 预留方向

Phase 2 再考虑以下工具：

- `ga_browser_task`
- `ga_desktop_task`
- `ga_adb_task`
- `ga_cdp_inspect`
- `ga_ui_detect`
- `ga_skill_search`
- `ga_skill_run`
- `ga_memory_query`

当前实现的 Phase 2 原子工具：

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

Phase 2 的每个工具都必须满足：

- 有独立权限开关。
- 有 timeout。
- 有 audit log。
- 有 dry-run。
- 有高风险动作确认机制。
- 不做泛化无限权限入口。

Phase 2 原子工具已在本次 Codex 实现中落地，但全部默认关闭。浏览器/桌面/ADB 的开放式长任务仍不在 MCP 范围内，继续走 ACP Bridge。

## 18. 最小手工验收命令建议

本机启动：

```bash
export GA_MCP_TOKEN="replace-with-secret"
export GA_MCP_ALLOWED_ROOTS="/path/to/GenericAgent"
python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
```

健康检查：

```bash
curl http://127.0.0.1:5050/healthz
```

无 token 调用应失败：

```bash
curl http://127.0.0.1:5050/sse
```

带 token 调用应进入 MCP 流程：

```bash
curl -H "Authorization: Bearer replace-with-secret" http://127.0.0.1:5050/sse
```

检查 audit log：

```bash
tail -f ~/.genericagent/mcp_audit.log
```

## 19. 成功标准

本阶段成功的标准不是 GenericAgent 能通过 MCP 完整执行任意任务，而是：

- 外部 MCP 客户端能发现 GenericAgent MCP Server。
- her / OpenClaw 云端能通过 Cloudflare Tunnel 访问本机 MCP Server。
- 所有 MCP 调用都有清晰鉴权。
- 所有 MCP 调用都有审计日志。
- 文件访问被限制在 allowlist roots 内。
- secret 文件不会被读出。
- 高风险能力默认关闭。
- 低风险原子能力可稳定调用。
- 长任务仍然走 ACP Bridge，不混入 MCP 阻塞 tool。

这一阶段完成后，再评估是否进入 Phase 2。
