from __future__ import annotations

import subprocess

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError, require_confirm, resolve_allowed_path, truncate_text
from .execute import _safe_env


def _agent_timeout(config: McpConfig, timeout: int) -> int:
    return max(1, min(int(timeout), max(config.max_timeout_seconds, 600)))


def _run_agent(cmd: list[str], cwd: str, timeout: int, max_output: int) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_safe_env(),
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SafetyError(f"Executable not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or "Process timed out"
        stdout, out_trunc = truncate_text(stdout, max_output)
        stderr, err_trunc = truncate_text(stderr, max_output)
        return {"exit_code": -1, "stdout": stdout, "stderr": stderr, "timed_out": True, "truncated": out_trunc or err_trunc}
    stdout, out_trunc = truncate_text(proc.stdout, max_output)
    stderr, err_trunc = truncate_text(proc.stderr, max_output)
    return {
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": False,
        "truncated": out_trunc or err_trunc,
    }


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_run_claude_code(
        prompt: str,
        cwd: str = ".",
        model: str | None = None,
        timeout: int = 600,
        confirm_token: str | None = None,
    ) -> dict:
        """Invoke local Claude Code CLI with a prompt. Disabled by default."""
        with audit.call("ga_run_claude_code", transport, cwd=cwd, risk_level="high"):
            if not config.enable_coding_agents:
                raise SafetyError("ga_run_claude_code is disabled by policy")
            require_confirm(config, confirm_token, "ga_run_claude_code")
            workdir = resolve_allowed_path(config, cwd)
            cmd = [config.claude_command, "-p", prompt]
            if model:
                cmd.extend(["--model", model])
            return _run_agent(cmd, str(workdir), _agent_timeout(config, timeout), config.max_output_chars)

    @mcp.tool()
    def ga_run_codex(
        prompt: str,
        cwd: str = ".",
        timeout: int = 600,
        confirm_token: str | None = None,
    ) -> dict:
        """Invoke local Codex CLI with a prompt. Disabled by default."""
        with audit.call("ga_run_codex", transport, cwd=cwd, risk_level="high"):
            if not config.enable_coding_agents:
                raise SafetyError("ga_run_codex is disabled by policy")
            require_confirm(config, confirm_token, "ga_run_codex")
            workdir = resolve_allowed_path(config, cwd)
            return _run_agent([config.codex_command, "exec", prompt], str(workdir), _agent_timeout(config, timeout), config.max_output_chars)

    @mcp.tool()
    def ga_cursor_open(path: str = ".", confirm_token: str | None = None) -> dict:
        """Open a workspace path in Cursor. Disabled by default."""
        with audit.call("ga_cursor_open", transport, path=path, risk_level="medium"):
            if not config.enable_coding_agents:
                raise SafetyError("ga_cursor_open is disabled by policy")
            require_confirm(config, confirm_token, "ga_cursor_open")
            target = resolve_allowed_path(config, path)
            return _run_agent([config.cursor_command, str(target)], str(target if target.is_dir() else target.parent), 30, config.max_output_chars)
