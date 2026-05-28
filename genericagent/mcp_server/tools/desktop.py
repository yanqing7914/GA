from __future__ import annotations

import platform
import time

from ..audit import AuditLogger
from ..config import McpConfig
from ..safety import SafetyError, require_confirm


def _ctrl():
    system = platform.system()
    if system == "Windows":
        from memory import ljqCtrl

        return ljqCtrl
    if system == "Darwin":
        from ..vendor_ext import desktop_mac

        return desktop_mac
    from ..vendor_ext import desktop_linux

    return desktop_linux


def _type_unicode_windows(text: str, delay: float) -> None:
    import ctypes
    from ctypes import wintypes

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    send_input = ctypes.windll.user32.SendInput
    for char in text:
        code = ord(char)
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            item = INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(0, code, flags, 0, None)))
            send_input(1, ctypes.byref(item), ctypes.sizeof(item))
        if delay > 0:
            time.sleep(delay)


def _type_unicode(ctrl, text: str, delay: float) -> None:
    if hasattr(ctrl, "TypeUnicode"):
        ctrl.TypeUnicode(text, delay)
        return
    if platform.system() == "Windows":
        _type_unicode_windows(text, delay)
        return
    if hasattr(ctrl, "typewrite"):
        ctrl.typewrite(text, delay)
        return
    raise SafetyError("Unicode typing is not supported on this platform")


def _move_to(ctrl, x: int, y: int, duration: float) -> None:
    if hasattr(ctrl, "MoveTo"):
        ctrl.MoveTo(x, y, duration)
        return
    steps = max(1, int(duration / 0.02))
    for _ in range(steps - 1):
        time.sleep(duration / steps)
    ctrl.SetCursorPos((x, y))


_KEY_ALIASES = {
    "cmd": "left_win",
    "cmd_l": "left_win",
    "command": "left_win",
    "meta": "left_win",
    "super": "left_win",
    "super_l": "left_win",
    "win": "left_win",
    "winleft": "left_win",
    "windows": "left_win",
}

_WINDOWS_EXTRA_VK = {
    "left_win": 0x5B,
    "right_win": 0x5C,
}


def _key_parts(keys: str) -> list[str]:
    return [_KEY_ALIASES.get(part.strip().lower(), part.strip().lower()) for part in keys.split("+") if part.strip()]


def _press_keys(ctrl, keys: str) -> None:
    parts = _key_parts(keys)
    if not parts:
        raise SafetyError("No keys were provided")
    if platform.system() != "Windows":
        ctrl.Press("+".join(parts))
        return

    vk_code = getattr(ctrl, "VK_CODE", {})
    pressed: list[int] = []
    try:
        for part in parts:
            vk = _WINDOWS_EXTRA_VK.get(part, vk_code.get(part))
            if vk is None:
                raise SafetyError(f"Unsupported key: {part}")
            ctrl.win32api.keybd_event(vk, 0, 0, 0)
            pressed.append(vk)
            time.sleep(0.02)
    finally:
        for vk in reversed(pressed):
            time.sleep(0.02)
            ctrl.win32api.keybd_event(vk, 0, ctrl.win32con.KEYEVENTF_KEYUP, 0)


def _window_list_windows(title_contains: str = "", max_results: int = 30) -> list[dict]:
    import win32gui

    needle = title_contains.lower().strip()
    windows: list[dict] = []

    def visit(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
        if needle and needle not in title.lower():
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        windows.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "rect": {"left": left, "top": top, "right": right, "bottom": bottom},
            }
        )

    win32gui.EnumWindows(visit, None)
    return windows[: max(1, min(int(max_results), 100))]


def _window_list(title_contains: str = "", max_results: int = 30) -> list[dict]:
    if platform.system() != "Windows":
        raise SafetyError("Window listing is currently implemented for Windows only")
    return _window_list_windows(title_contains, max_results)


def _focus_window_windows(hwnd: int) -> dict:
    import ctypes
    import win32con
    import win32gui
    import win32process

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = int(hwnd)
    if not win32gui.IsWindow(hwnd):
        raise SafetyError(f"Window not found: {hwnd}")
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    foreground = user32.GetForegroundWindow()
    current_thread = kernel32.GetCurrentThreadId()
    target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
    foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
    attached: list[int] = []
    try:
        for thread_id in {target_thread, foreground_thread}:
            if thread_id and thread_id != current_thread:
                user32.AttachThreadInput(current_thread, thread_id, True)
                attached.append(thread_id)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        user32.AllowSetForegroundWindow(0xFFFFFFFF)
        user32.keybd_event(0x12, 0, 0, 0)  # Alt down unlocks SetForegroundWindow on Windows.
        user32.keybd_event(0x12, 0, 0x0002, 0)
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        for thread_id in attached:
            user32.AttachThreadInput(current_thread, thread_id, False)

    time.sleep(0.2)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return {
        "hwnd": hwnd,
        "title": win32gui.GetWindowText(hwnd),
        "rect": {"left": left, "top": top, "right": right, "bottom": bottom},
    }


def _focus_window(title_contains: str = "", hwnd: int | None = None) -> dict:
    if platform.system() != "Windows":
        raise SafetyError("Window focus is currently implemented for Windows only")
    target = int(hwnd) if hwnd is not None else None
    if target is None:
        matches = _window_list_windows(title_contains, 10)
        if not matches:
            raise SafetyError(f"No window matched title_contains={title_contains!r}")
        needle = title_contains.lower().strip()
        exact = next((item for item in matches if item["title"].lower().strip() == needle), None) if needle else None
        target = int((exact or matches[0])["hwnd"])
    return _focus_window_windows(target)


def register(mcp, config: McpConfig, audit: AuditLogger, transport: str) -> None:
    @mcp.tool()
    def ga_desktop_status() -> dict:
        """Return desktop-control availability without moving mouse or typing."""
        with audit.call("ga_desktop_status", transport):
            return {
                "enabled": config.enable_desktop,
                "platform": platform.system(),
                "write_actions_require_confirm_token": True,
            }

    @mcp.tool()
    def ga_window_list(title_contains: str = "", max_results: int = 30) -> dict:
        """List visible desktop windows by title. Disabled by default."""
        with audit.call("ga_window_list", transport):
            if not config.enable_desktop:
                raise SafetyError("ga_window_list is disabled by policy")
            return {"windows": _window_list(title_contains, max_results)}

    @mcp.tool()
    def ga_window_focus(title_contains: str = "", hwnd: int | None = None, confirm_token: str | None = None) -> dict:
        """Bring a visible desktop window to the foreground. Disabled by default."""
        with audit.call("ga_window_focus", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_window_focus is disabled by policy")
            require_confirm(config, confirm_token, "ga_window_focus")
            return {"ok": True, "window": _focus_window(title_contains, hwnd)}

    @mcp.tool()
    def ga_mouse_move(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Move mouse to physical screen coordinates. Disabled by default."""
        with audit.call("ga_mouse_move", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_move is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_move")
            ctrl = _ctrl()
            ctrl.SetCursorPos((int(x), int(y)))
            return {"ok": True, "x": int(x), "y": int(y)}

    @mcp.tool()
    def ga_mouse_click(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Click physical screen coordinates. Disabled by default."""
        with audit.call("ga_mouse_click", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_click is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_click")
            ctrl = _ctrl()
            ctrl.Click(int(x), int(y))
            return {"ok": True, "x": int(x), "y": int(y)}

    @mcp.tool()
    def ga_key_press(keys: str, confirm_token: str | None = None) -> dict:
        """Press a key chord like ctrl+c. Disabled by default."""
        with audit.call("ga_key_press", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_key_press is disabled by policy")
            require_confirm(config, confirm_token, "ga_key_press")
            ctrl = _ctrl()
            _press_keys(ctrl, keys)
            return {"ok": True, "keys": keys}

    @mcp.tool()
    def ga_keyboard_type(text: str, delay_ms: int = 30, confirm_token: str | None = None) -> dict:
        """Type a unicode string at current cursor position. Disabled by default."""
        with audit.call("ga_keyboard_type", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_keyboard_type is disabled by policy")
            require_confirm(config, confirm_token, "ga_keyboard_type")
            ctrl = _ctrl()
            _type_unicode(ctrl, text, max(0, int(delay_ms)) / 1000.0)
            return {"ok": True, "chars": len(text)}

    @mcp.tool()
    def ga_keyboard_type_window(
        text: str,
        title_contains: str = "",
        hwnd: int | None = None,
        delay_ms: int = 30,
        confirm_token: str | None = None,
    ) -> dict:
        """Focus a window by title and type unicode text into its active control. Disabled by default."""
        with audit.call("ga_keyboard_type_window", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_keyboard_type_window is disabled by policy")
            require_confirm(config, confirm_token, "ga_keyboard_type_window")
            window = _focus_window(title_contains, hwnd)
            ctrl = _ctrl()
            _type_unicode(ctrl, text, max(0, int(delay_ms)) / 1000.0)
            return {"ok": True, "chars": len(text), "window": window}

    @mcp.tool()
    def ga_mouse_drag(
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        duration_ms: int = 200,
        confirm_token: str | None = None,
    ) -> dict:
        """Drag from one point to another. Disabled by default."""
        with audit.call("ga_mouse_drag", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_drag is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_drag")
            ctrl = _ctrl()
            ctrl.SetCursorPos((int(from_x), int(from_y)))
            ctrl.MouseDown()
            _move_to(ctrl, int(to_x), int(to_y), max(0, int(duration_ms)) / 1000.0)
            ctrl.MouseUp()
            return {"ok": True}

    @mcp.tool()
    def ga_mouse_double_click(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Double click physical screen coordinates. Disabled by default."""
        with audit.call("ga_mouse_double_click", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_double_click is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_double_click")
            ctrl = _ctrl()
            ctrl.SetCursorPos((int(x), int(y)))
            ctrl.MouseDClick()
            return {"ok": True, "x": int(x), "y": int(y)}

    @mcp.tool()
    def ga_mouse_right_click(x: int, y: int, confirm_token: str | None = None) -> dict:
        """Right click physical screen coordinates. Disabled by default."""
        with audit.call("ga_mouse_right_click", transport, risk_level="high"):
            if not config.enable_desktop:
                raise SafetyError("ga_mouse_right_click is disabled by policy")
            require_confirm(config, confirm_token, "ga_mouse_right_click")
            ctrl = _ctrl()
            ctrl.SetCursorPos((int(x), int(y)))
            if platform.system() == "Windows":
                ctrl.win32api.mouse_event(ctrl.win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0)
                time.sleep(0.05)
                ctrl.win32api.mouse_event(ctrl.win32con.MOUSEEVENTF_RIGHTUP, 0, 0)
            elif hasattr(ctrl, "RightClick"):
                ctrl.RightClick()
            else:
                raise SafetyError("Right click is not supported on this platform")
            return {"ok": True, "x": int(x), "y": int(y)}
