from __future__ import annotations

import os
import subprocess
import sys
import time

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import (
    SafetyError,
    check_python_risks,
    check_powershell_command,
    clamp_timeout,
    require_confirm,
    resolve_allowed_path,
    truncate_text,
)


SAFE_ENV_KEYS = {
    "path",
    "pathext",
    "systemroot",
    "windir",
    "temp",
    "tmp",
    "userprofile",
    "home",
    "appdata",
    "localappdata",
    "programdata",
    "programfiles",
    "programfiles(x86)",
    "programw6432",
    "processor_architecture",
    "psmodulepath",
    "comspec",
}


def _safe_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key.lower() in SAFE_ENV_KEYS}


def _run(cmd: list[str], cwd: str, timeout: int, max_output: int) -> dict:
    started = time.perf_counter()
    timed_out = False
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
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout = exc.stdout or ""
        stderr = exc.stderr or "Process timed out"
    stdout, out_trunc = truncate_text(stdout, max_output)
    stderr, err_trunc = truncate_text(stderr, max_output)
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "timed_out": timed_out,
        "truncated": out_trunc or err_trunc,
    }


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_run_python_sandboxed(
        code: str,
        cwd: str = ".",
        timeout_seconds: int | None = None,
        confirm_token: str | None = None,
    ) -> dict:
        """Run a short Python snippet in an allowed cwd. Disabled by default."""
        with audit.call("ga_run_python_sandboxed", transport, cwd=cwd) as audit_record:
            if not config.enable_python:
                raise SafetyError("ga_run_python_sandboxed is disabled by policy")
            risks = check_python_risks(code)
            if risks:
                audit_record["risk_level"] = "high"
                audit_record["python_risks"] = risks
                require_confirm(config, confirm_token, f"ga_run_python_sandboxed risks={risks}")
            workdir = resolve_allowed_path(config, cwd)
            if not workdir.is_dir():
                raise NotADirectoryError("cwd must be a directory")
            timeout = clamp_timeout(config, timeout_seconds)
            result = _run([sys.executable, "-I", "-c", code], str(workdir), timeout, config.max_output_chars)
            audit_record["truncated"] = result["truncated"]
            audit_record["exit_code"] = result["exit_code"]
            return result

    @mcp.tool()
    def ga_run_powershell_sandboxed(command: str, cwd: str = ".", timeout_seconds: int | None = None) -> dict:
        """Run a denylisted PowerShell command in an allowed cwd. Disabled by default."""
        with audit.call("ga_run_powershell_sandboxed", transport, cwd=cwd) as audit_record:
            if not config.enable_powershell:
                raise SafetyError("ga_run_powershell_sandboxed is disabled by policy")
            check_powershell_command(command)
            workdir = resolve_allowed_path(config, cwd)
            if not workdir.is_dir():
                raise NotADirectoryError("cwd must be a directory")
            timeout = clamp_timeout(config, timeout_seconds)
            result = _run(
                ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                str(workdir),
                timeout,
                config.max_output_chars,
            )
            audit_record["truncated"] = result["truncated"]
            audit_record["exit_code"] = result["exit_code"]
            return result
