import tempfile
import unittest
from pathlib import Path

from genericagent.mcp_server.config import McpConfig
from genericagent.mcp_server.safety import SafetyError, ensure_not_secret, resolve_allowed_path


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
                confirm_token=None,
                adb_path="adb",
                cdp_host="127.0.0.1",
                cdp_port=9222,
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


if __name__ == "__main__":
    unittest.main()
