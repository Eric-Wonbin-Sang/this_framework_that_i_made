import ctypes
import win32api, win32con, win32gui, win32process

from this_framework_that_i_made.input_helpers.keyboard import KeyEvent, KeyboardEventGenerator
from this_framework_that_i_made.systems import WindowsSystem
from this_framework_that_i_made.video_helpers.msft_windows import MsftWindow


GA_ROOT = 2
user32 = ctypes.windll.user32


def _toplevel(hwnd):
    return user32.GetAncestor(hwnd, GA_ROOT)


def _force_foreground(hwnd):
    """Best-effort: bring hwnd to the front even if Windows' foreground lock is in the way."""
    try:
        fg = win32gui.GetForegroundWindow()
    except win32gui.error:
        fg = None

    # If already foreground, nothing to do
    if fg == hwnd:
        return

    # Try the simple path first
    try:
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)
        win32gui.SetFocus(hwnd)
        # If that worked, we're done
        if win32gui.GetForegroundWindow() == hwnd:
            return
    except Exception:
        pass

    # AttachThreadInput trick
    try:
        if fg:
            fg_tid = win32process.GetWindowThreadProcessId(fg)[0]
        else:
            fg_tid = 0
        my_tid = win32api.GetCurrentThreadId()
        user32.AttachThreadInput(fg_tid, my_tid, True)
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetActiveWindow(hwnd)
            win32gui.SetFocus(hwnd)
        finally:
            user32.AttachThreadInput(fg_tid, my_tid, False)
    except Exception:
        pass


def show_launcher(win):
    """Show + focus. Works whether window is minimized, normal, or maximized."""
    hwnd = _toplevel(win.hwnd)

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        # Ensure it's visible; SHOWNORMAL tends to be more reliable than SHOW here
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)

    _force_foreground(hwnd)


def hide_launcher(win):
    """Hide from view but keep taskbar/Alt-Tab entry."""
    hwnd = _toplevel(win.hwnd)
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)


def toggle_launcher(window: MsftWindow):
    hwnd = _toplevel(window.hwnd)
    if win32gui.IsIconic(hwnd) or not window.is_active:
        show_launcher(window)
    else:
        hide_launcher(window)


def main():

    system = WindowsSystem()
    window = system.get_window("rebel")
    print(window)

    kb = KeyboardEventGenerator(dedupe_repeats=True)
    for event in kb.yield_keyboard_events():
        print(event)
        if type(event) == KeyEvent and event.value == "f24" and event.is_pressed:
            toggle_launcher(window)


if __name__ == "__main__":
    main()
