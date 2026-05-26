import tempfile
import unittest
from pathlib import Path
import os

from genericagent.mcp_server.config import McpConfig
from genericagent.mcp_server.safety import SafetyError, check_python_risks, ensure_not_secret, resolve_allowed_path


class SafetyTests(unittest.TestCase):
    def test_resolve_allowed_path_blocks_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config = McpConfig(
                repo_root=root,
                allowed_roots=(root,),
                audit_log=root / "audit.log",
                token=None,
                enable_screenshot=False,
                enable_ocr=False,
                enable_python=False,
                enable_powershell=False,
                enable_desktop=False,
                enable_adb=False,
                enable_browser_cdp=False,
                enable_ui_detect=False,
                enable_skills=False,
                enable_memory=False,
                enable_coding_agents=False,
                confirm_token=None,
                adb_path="adb",
                cdp_host="127.0.0.1",
                cdp_port=9222,
                claude_command="claude",
                codex_command="codex",
                cursor_command="cursor",
                max_output_chars=20000,
                default_timeout_seconds=10,
                max_timeout_seconds=30,
            )
            self.assertEqual(resolve_allowed_path(config, "."), root)
            with self.assertRaises(SafetyError):
                resolve_allowed_path(config, str(root.parent))

    def test_secret_policy_blocks_key_files(self):
        with self.assertRaises(SafetyError):
            ensure_not_secret(Path("id_rsa"))
        with self.assertRaises(SafetyError):
            ensure_not_secret(Path("app.env.secret"))

    def test_python_risks_do_not_flag_common_secret_words(self):
        self.assertEqual(check_python_risks("print('hello, my secret is none')"), [])
        self.assertEqual(check_python_risks("print('token string only')"), [])
        self.assertTrue(check_python_risks("import socket\nprint('x')"))

    def test_readonly_wow_tools_default_on(self):
        keys = [
            "GA_MCP_ENABLE_SCREENSHOT",
            "GA_MCP_ENABLE_OCR",
            "GA_MCP_ENABLE_PYTHON",
            "GA_MCP_ENABLE_DESKTOP",
        ]
        old = {key: os.environ.get(key) for key in keys}
        try:
            for key in keys:
                os.environ.pop(key, None)
            config = McpConfig.from_env()
            self.assertTrue(config.enable_screenshot)
            self.assertTrue(config.enable_ocr)
            self.assertFalse(config.enable_python)
            self.assertFalse(config.enable_desktop)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
