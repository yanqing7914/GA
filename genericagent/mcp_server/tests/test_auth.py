import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from genericagent.mcp_server.config import McpConfig
from genericagent.mcp_server.server import build_server


def make_config(root: Path):
    return McpConfig(
        repo_root=root,
        allowed_roots=(root,),
        audit_log=root / "audit.log",
        token="test-token",
        enable_screenshot=True,
        enable_ocr=True,
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


class StaticBearerAuthTests(unittest.TestCase):
    def test_static_auth_does_not_advertise_oauth_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp).resolve())
            mcp = build_server(config, "sse", require_auth=True, auth_mode="static")
            client = TestClient(mcp.sse_app())

            response = client.get("/sse")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "invalid_token"})
        www_authenticate = response.headers.get("www-authenticate", "")
        self.assertEqual(www_authenticate, 'Bearer realm="genericagent-mcp"')
        self.assertNotIn("oauth-protected-resource", www_authenticate)


if __name__ == "__main__":
    unittest.main()
