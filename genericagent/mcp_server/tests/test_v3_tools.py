import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genericagent.mcp_server.audit import AuditLogger
from genericagent.mcp_server.config import McpConfig
from genericagent.mcp_server.safety import SafetyError
from genericagent.mcp_server.tools import adb, browser_cdp, coding_agents, desktop, dryrun
from genericagent.mcp_server.vendor_ext import desktop_linux, desktop_mac


class FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorate(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorate


class FakeDesktopCtrl:
    def __init__(self):
        self.calls = []
        self.VK_CODE = {"r": 0x52, "enter": 0x0D}
        self.win32api = self
        self.win32con = self
        self.KEYEVENTF_KEYUP = 0x0002

    def SetCursorPos(self, pos):
        self.calls.append(("SetCursorPos", pos))

    def TypeUnicode(self, text, delay):
        self.calls.append(("TypeUnicode", text, delay))

    def MouseDown(self):
        self.calls.append(("MouseDown",))

    def MouseUp(self):
        self.calls.append(("MouseUp",))

    def MoveTo(self, x, y, duration):
        self.calls.append(("MoveTo", x, y, duration))

    def MouseDClick(self):
        self.calls.append(("MouseDClick",))

    def RightClick(self):
        self.calls.append(("RightClick",))

    def keybd_event(self, vk, scan, flags, extra):
        self.calls.append(("keybd_event", vk, flags))


def make_config(root: Path, **overrides):
    data = dict(
        repo_root=root,
        allowed_roots=(root,),
        audit_log=root / "audit.log",
        token=None,
        enable_screenshot=True,
        enable_ocr=True,
        enable_python=False,
        enable_powershell=False,
        enable_desktop=True,
        enable_adb=True,
        enable_browser_cdp=True,
        enable_ui_detect=False,
        enable_skills=False,
        enable_memory=False,
        enable_coding_agents=True,
        confirm_token="ok",
        skip_confirm=False,
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
    data.update(overrides)
    return McpConfig(**data)


class V3ToolHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.config = make_config(self.root)
        self.audit = AuditLogger(self.root / "audit.log")
        self.mcp = FakeMcp()

    def tearDown(self):
        self.tmp.cleanup()

    def test_vendor_ext_type_unicode_is_available(self):
        self.assertTrue(hasattr(desktop_mac, "TypeUnicode"))
        self.assertTrue(hasattr(desktop_linux, "TypeUnicode"))

    def test_ga_keyboard_type_happy_path(self):
        ctrl = FakeDesktopCtrl()
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_ctrl", return_value=ctrl):
            result = self.mcp.tools["ga_keyboard_type"]("hello", delay_ms=5, confirm_token="ok")
        self.assertEqual(result, {"ok": True, "chars": 5})
        self.assertIn(("TypeUnicode", "hello", 0.005), ctrl.calls)

    def test_ga_window_list_happy_path(self):
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_window_list", return_value=[{"hwnd": 1, "title": "飞书"}]) as list_windows:
            result = self.mcp.tools["ga_window_list"]("飞书")
        self.assertEqual(result["windows"][0]["title"], "飞书")
        list_windows.assert_called_once_with("飞书", 30)

    def test_ga_window_focus_happy_path(self):
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_focus_window", return_value={"hwnd": 1, "title": "飞书"}) as focus_window:
            result = self.mcp.tools["ga_window_focus"]("飞书", confirm_token="ok")
        self.assertTrue(result["ok"])
        self.assertEqual(result["window"]["hwnd"], 1)
        focus_window.assert_called_once_with("飞书", None)

    def test_ga_keyboard_type_window_happy_path(self):
        ctrl = FakeDesktopCtrl()
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_focus_window", return_value={"hwnd": 1, "title": "飞书"}), patch.object(desktop, "_ctrl", return_value=ctrl):
            result = self.mcp.tools["ga_keyboard_type_window"]("飞书", "hello", delay_ms=5, confirm_token="ok")
        self.assertEqual(result["chars"], 5)
        self.assertIn(("TypeUnicode", "hello", 0.005), ctrl.calls)

    def test_ga_mouse_drag_happy_path(self):
        ctrl = FakeDesktopCtrl()
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_ctrl", return_value=ctrl):
            result = self.mcp.tools["ga_mouse_drag"](1, 2, 3, 4, duration_ms=50, confirm_token="ok")
        self.assertTrue(result["ok"])
        self.assertIn(("MouseDown",), ctrl.calls)
        self.assertIn(("MoveTo", 3, 4, 0.05), ctrl.calls)
        self.assertIn(("MouseUp",), ctrl.calls)

    def test_ga_mouse_double_click_happy_path(self):
        ctrl = FakeDesktopCtrl()
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_ctrl", return_value=ctrl):
            result = self.mcp.tools["ga_mouse_double_click"](7, 8, confirm_token="ok")
        self.assertEqual(result["x"], 7)
        self.assertIn(("MouseDClick",), ctrl.calls)

    def test_ga_mouse_right_click_happy_path(self):
        ctrl = FakeDesktopCtrl()
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_ctrl", return_value=ctrl), patch.object(desktop.platform, "system", return_value="Darwin"):
            result = self.mcp.tools["ga_mouse_right_click"](9, 10, confirm_token="ok")
        self.assertEqual(result["y"], 10)
        self.assertIn(("RightClick",), ctrl.calls)

    def test_ga_key_press_accepts_windows_aliases(self):
        ctrl = FakeDesktopCtrl()
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(desktop, "_ctrl", return_value=ctrl), patch.object(desktop.platform, "system", return_value="Windows"):
            result = self.mcp.tools["ga_key_press"]("win+r", confirm_token="ok")
        self.assertEqual(result["keys"], "win+r")
        self.assertIn(("keybd_event", 0x5B, 0), ctrl.calls)
        self.assertIn(("keybd_event", 0x52, 0), ctrl.calls)
        self.assertIn(("keybd_event", 0x5B, ctrl.KEYEVENTF_KEYUP), ctrl.calls)

    def test_desktop_tools_require_confirm_token(self):
        desktop.register(self.mcp, self.config, self.audit, "unit")
        with self.assertRaises(SafetyError):
            self.mcp.tools["ga_keyboard_type"]("hello")

    def test_ga_cdp_execute_js_happy_path(self):
        browser_cdp.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(browser_cdp, "_cdp_call", return_value={"result": {"value": 2}}) as call:
            result = self.mcp.tools["ga_cdp_execute_js"]("tab-1", "1 + 1")
        self.assertIn('"value": 2', result["result"])
        call.assert_called_once()

    def test_ga_cdp_screenshot_happy_path(self):
        browser_cdp.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(browser_cdp, "_cdp_call", return_value={"data": "png-base64"}):
            result = self.mcp.tools["ga_cdp_screenshot"]("tab-1")
        self.assertEqual(result["image_base64"], "png-base64")
        self.assertEqual(result["mime_type"], "image/png")

    def test_ga_cdp_scan_page_happy_path(self):
        browser_cdp.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(browser_cdp, "_cdp_call", return_value={"result": {"value": "page text"}}):
            result = self.mcp.tools["ga_cdp_scan_page"]("tab-1", mode="text")
        self.assertEqual(result["content"], "page text")
        self.assertFalse(result["truncated"])

    def test_ga_adb_swipe_happy_path(self):
        adb.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(adb, "_adb", return_value={"exit_code": 0, "stdout": "", "stderr": "", "truncated": False}) as run:
            result = self.mcp.tools["ga_adb_swipe"](1, 2, 3, 4, 300, confirm_token="ok")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("swipe", run.call_args.args[1])

    def test_ga_adb_keyevent_happy_path(self):
        adb.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(adb, "_adb", return_value={"exit_code": 0, "stdout": "", "stderr": "", "truncated": False}) as run:
            result = self.mcp.tools["ga_adb_keyevent"]("KEYCODE_BACK", confirm_token="ok")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(run.call_args.args[1][-1], "KEYCODE_BACK")

    def test_ga_run_claude_code_happy_path(self):
        coding_agents.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(coding_agents, "_run_agent", return_value={"exit_code": 0, "stdout": "ok", "stderr": ""}) as run:
            result = self.mcp.tools["ga_run_claude_code"]("fix it", cwd=".", model="opus", confirm_token="ok")
        self.assertEqual(result["stdout"], "ok")
        self.assertEqual(run.call_args.args[0][:2], ["claude", "-p"])

    def test_ga_run_codex_happy_path(self):
        coding_agents.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(coding_agents, "_run_agent", return_value={"exit_code": 0, "stdout": "ok", "stderr": ""}) as run:
            result = self.mcp.tools["ga_run_codex"]("fix it", cwd=".", confirm_token="ok")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(run.call_args.args[0][:2], ["codex", "exec"])

    def test_ga_cursor_open_happy_path(self):
        coding_agents.register(self.mcp, self.config, self.audit, "unit")
        with patch.object(coding_agents, "_run_agent", return_value={"exit_code": 0, "stdout": "", "stderr": ""}) as run:
            result = self.mcp.tools["ga_cursor_open"](".", confirm_token="ok")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(run.call_args.args[0][0], "cursor")

    def test_ga_task_dryrun_llm_happy_path(self):
        dryrun.register(self.mcp, self.config, self.audit, "unit")
        result = self.mcp.tools["ga_task_dryrun"]("open browser", mode="llm")
        self.assertTrue(result["delegate_to_client"])
        self.assertEqual(result["recommended_path"], "Client LLM")


if __name__ == "__main__":
    unittest.main()
