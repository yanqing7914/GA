from __future__ import annotations


def _pg():
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui is required for macOS desktop control") from exc
    return pyautogui


def SetCursorPos(pos):
    _pg().moveTo(int(pos[0]), int(pos[1]))


def Click(x, y=None):
    if y is None:
        x, y = x
    _pg().click(int(x), int(y))


def MouseDown():
    _pg().mouseDown()


def MouseUp():
    _pg().mouseUp()


def MouseDClick():
    _pg().doubleClick()


def RightClick():
    _pg().rightClick()


def Press(keys):
    parts = keys.lower().split("+") if isinstance(keys, str) else list(keys)
    _pg().hotkey(*parts)


def TypeUnicode(text: str, delay: float = 0.03):
    _pg().write(text, interval=delay)


def MoveTo(x: int, y: int, duration: float = 0.2):
    _pg().moveTo(int(x), int(y), duration=duration)
