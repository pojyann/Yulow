from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win64 handles and callback pointers must not use ctypes' default 32-bit int.
user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int, ctypes.c_void_p, wintypes.HINSTANCE, wintypes.DWORD
)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)
user32.CallNextHookEx.restype = wintypes.LPARAM
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetParent.restype = wintypes.HWND
user32.SetWindowRgn.argtypes = (wintypes.HWND, ctypes.c_void_p, wintypes.BOOL)
user32.SetWindowRgn.restype = ctypes.c_int
gdi32 = ctypes.windll.gdi32
gdi32.CreateRoundRectRgn.argtypes = (
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
)
gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_RMENU = 0xA5
HOTKEYS = {"Right Alt": 0xA5, "Right Ctrl": 0xA3, "F8": 0x77}
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56
VK_Z = 0x5A


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


class RightAltHook:
    """Toggle on Right Alt key-down and swallow it so Windows menus do not activate."""

    def __init__(self, callback: Callable[[], None], on_error: Callable[[str], None] | None = None, key: str = "Right Alt") -> None:
        self.callback = callback
        self.on_error = on_error
        self.key = HOTKEYS.get(key, VK_RMENU)
        self.thread: threading.Thread | None = None
        self.thread_id = 0
        self.hook = None
        self._pressed = False
        self._proc = LowLevelKeyboardProc(self._hook_proc)

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True, name="right-alt-hook")
        self.thread.start()

    def _run(self) -> None:
        self.thread_id = kernel32.GetCurrentThreadId()
        module = kernel32.GetModuleHandleW(None)
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, module, 0)
        if not self.hook:
            error = ctypes.get_last_error()
            if self.on_error:
                self.on_error(f"右 Alt 快捷鍵無法啟用（Windows 錯誤 {error}）；仍可點擊錄音按鈕")
            return
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        if self.hook:
            user32.UnhookWindowsHookEx(self.hook)

    def _hook_proc(self, code: int, wparam: int, lparam: int) -> int:
        if code >= 0:
            event = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if event.vkCode == self.key:
                if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN) and not self._pressed:
                    self._pressed = True
                    self.callback()
                elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                    self._pressed = False
                return 1
        return user32.CallNextHookEx(self.hook, code, wparam, lparam)

    def stop(self) -> None:
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)


def foreground_window() -> int:
    return int(user32.GetForegroundWindow())


def focus_window(hwnd: int) -> None:
    if hwnd:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.12)


def send_shortcut(key: int) -> None:
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def paste() -> None:
    send_shortcut(VK_V)


def undo() -> None:
    send_shortcut(VK_Z)


def style_title_bar(widget, dark: bool, color: str) -> None:
    """Match the native Windows caption to the app surface when DWM supports it."""
    widget.update_idletasks()
    client = wintypes.HWND(widget.winfo_id())
    parent = user32.GetParent(client)
    ancestor = user32.GetAncestor(client, 2)
    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
    dwm.DwmSetWindowAttribute.restype = ctypes.c_long
    use_dark = wintypes.BOOL(dark)
    rgb = color.lstrip("#")
    red, green, blue = (int(rgb[index:index+2], 16) for index in (0, 2, 4))
    caption = wintypes.DWORD((blue << 16) | (green << 8) | red)
    for hwnd in {client.value, parent, ancestor}:
        if hwnd:
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(use_dark), ctypes.sizeof(use_dark))
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))


def round_window(widget, width: int, height: int, radius: int) -> None:
    """Use a native rounded window region so floating surfaces have clean edges."""
    widget.update_idletasks()
    hwnd = user32.GetAncestor(wintypes.HWND(widget.winfo_id()), 2) or widget.winfo_id()
    region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
    if region:
        # Windows takes ownership of the region after this call.
        user32.SetWindowRgn(hwnd, region, True)
