from __future__ import annotations

from ..audit import AuditLogger
from ..config import McpConfig


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_task_dryrun(task: str) -> dict:
        """Estimate required capabilities for a natural-language task without executing it."""
        with audit.call("ga_task_dryrun", transport) as audit_record:
            text = task.lower()
            required: set[str] = set()
            if any(word in text for word in ("browser", "chrome", "网页", "浏览器", "登录", "下载")):
                required.update({"browser", "filesystem"})
            if any(word in text for word in ("adb", "android", "手机", "app", "tap")):
                required.add("adb")
            if any(word in text for word in ("click", "mouse", "keyboard", "键鼠", "点击", "输入")):
                required.add("desktop_control")
            if any(word in text for word in ("write", "save", "delete", "删除", "写入", "保存")):
                required.add("filesystem")
            if any(word in text for word in ("run", "script", "python", "powershell", "执行", "脚本")):
                required.add("code_run")
            if any(word in text for word in ("send", "feishu", "wechat", "飞书", "微信", "钉钉", "消息")):
                required.add("messaging")

            high_risk = {"browser", "adb", "desktop_control", "messaging"} & required
            if high_risk:
                recommended = "ACP Bridge"
                risk = "high" if {"adb", "messaging", "desktop_control"} & required else "medium"
            elif "code_run" in required:
                recommended = "MCP" if config.enable_python or config.enable_powershell else "Needs Human Confirmation"
                risk = "medium"
            else:
                recommended = "MCP"
                risk = "low"

            audit_record["risk_level"] = risk
            return {
                "risk": risk,
                "recommended_path": recommended,
                "required_capabilities": sorted(required),
                "requires_human_confirmation": risk != "low",
                "reason": _reason(recommended, required),
            }


def _reason(recommended: str, required: set[str]) -> str:
    if recommended == "ACP Bridge":
        return "The task appears multi-step or stateful; use GenericAgent ACP Bridge instead of a blocking MCP tool."
    if recommended == "Needs Human Confirmation":
        return "The task requires a disabled or higher-risk capability."
    if required:
        return "The task can be decomposed into enabled MCP atomic tools if policy allows it."
    return "No high-risk capability was detected."
