
from ctypes import windll, wintypes
from typing import List
import win32con
import win32gui
import win32ui
import win32process
import pygetwindow

from PIL import Image

from this_framework_that_i_made.audio_helpers.msft_audio import read_pcm_blocks_for_pid
from this_framework_that_i_made.audio_helpers.wasapi_per_app_loopback import PerAppLoopback
from this_framework_that_i_made.generics import SavableObject, ensure_savable
from this_framework_that_i_made.video_helpers.monitors import Window, wait_for_fps_target


PW_RENDERFULLCONTENT = 0x00000002  # Win8+


class MsftWindowVideoCapurer:

    @staticmethod
    def _capture_printwindow(hwnd):
        # Get window bounds
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except win32gui.error:
            return None
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return None

        # Window DCs
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            return None
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        # Prepare WinAPI PrintWindow
        user32 = windll.user32
        user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        user32.PrintWindow.restype = wintypes.BOOL

        # Ask window/DWM to render
        ok = user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
        # If PW_RENDERFULLCONTENT fails (0), try flags=0
        if ok == 0:
            ok = user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)

        # Extract bytes → image
        img = None
        if ok != 0:
            bmpinfo = save_bitmap.GetInfo()
            bmpbytes = save_bitmap.GetBitmapBits(True)
            # BGRX → RGB
            img = Image.frombuffer("RGB",
                                   (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                                   bmpbytes, "raw", "BGRX", 0, 1)

        # Cleanup GDI objects
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return img

    @staticmethod
    def _capture_bitblt_visible(hwnd):
        # Visible-only fallback if PrintWindow fails
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except win32gui.error:
            return None
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return None

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            return None
        src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bmp)

        mem_dc.BitBlt((0, 0), (width, height), src_dc, (0, 0), win32con.SRCCOPY)

        bmpinfo = bmp.GetInfo()
        bmpbytes = bmp.GetBitmapBits(True)
        img = Image.frombuffer("RGB",
                               (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                               bmpbytes, "raw", "BGRX", 0, 1)

        win32gui.DeleteObject(bmp.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return img

    @classmethod
    def yield_content(cls, hwnd, fps=None):
        """Yield frames forever (until window closes). PIL.Image (or numpy array if as_numpy=True)."""
        for _ in wait_for_fps_target(fps):
            # Stop if window is gone
            if not win32gui.IsWindow(hwnd):
                return
            img = cls._capture_printwindow(hwnd)
            if img is None:
                # Fallback visible-only BitBlt (occlusion/minimize may show black/partial)
                img = cls._capture_bitblt_visible(hwnd)

            if img is None:
                continue
            yield img


@ensure_savable
class MsftWindowAudioCapurer(SavableObject):

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.tid, self.pid = win32process.GetWindowThreadProcessId(hwnd)

    def yield_content(self, frames_per_buffer: int = 4800):
        # Preferred path: process loopback via msft_audio helper
        try:
            for ts, chunk in read_pcm_blocks_for_pid(self.pid, frames_per_buffer):
                yield ts, chunk
            return
        except Exception:
            pass
        # Fallback: use PerAppLoopback implementation (bytes-only, we add timestamp)
        try:
            from time import time as _now
            with PerAppLoopback(pid=self.pid, include_tree=True, chunk_ms=max(1, int(frames_per_buffer / 48))) as cap:
                for chunk in cap:
                    yield (_now(), chunk)
        except Exception:
            return

    def as_dict(self):
        return {
            "hwnd": self.hwnd,
            "tid": self.tid,
            "pid": self.pid,
        }

    def __repr__(self):
        hwnd = self.hwnd
        tid = self.tid
        pid = self.pid
        return f"{self.__class__.__name__}({hwnd=}, {tid=}, {pid=})"


@ensure_savable
class MsftWindow(Window):

    def __init__(self, window):
        self.window = window
        self.hwnd = window._hWnd  # a window handle

    @classmethod
    def get_windows(cls) -> List["Win32Window"]:
        return [cls(window) for window in pygetwindow.getAllWindows()]

    @property
    def title(self):
        return self.window.title

    @property
    def is_minimized(self):
        return self.window.isMinimized

    @property
    def is_maximized(self):
        return self.window.isMaximized

    @property
    def is_active(self):
        return self.window.isActive

    @property
    def visible(self):
        return self.window.visible

    def activate(self):
        self.window.activate()
        
    def close(self):
        self.window.close()
        
    def hide(self):
        self.window.hide()
        
    def maximize(self):
        self.window.maximize()
        
    def minimize(self):
        self.window.minimize()
        
    def move(self, x_offset, y_offset):
        self.window.move(x_offset, y_offset)
        
    def move_to(self, left, top):
        self.window.moveTo(left, top)
        
    def resize(self, width_offset, height_offset):
        self.window.resize(width_offset, height_offset)
        
    def resize_to(self, width, height):
        self.window.resizeTo(width, height)
        
    def restore(self):
        self.window.restore()
        
    def show(self):
        self.window.show()

    def yield_video_content(self, fps=None):
        for content in MsftWindowVideoCapurer.yield_content(self.hwnd, fps):
            yield content

    @property
    def audio_capturer(self):
        try:
            return MsftWindowAudioCapurer(self.hwnd)
        except Exception:
            return None

    def yield_audio_content(self, frames_per_buffer: int = 4800):
        capturer = self.audio_capturer
        for ts, chunk in capturer.yield_content(frames_per_buffer):
            yield ts, chunk

    def as_dict(self):
        return {
            "hwnd": self.hwnd,
        }

    def __repr__(self):
        title = self.title
        is_active = self.is_active
        visible = self.visible
        return f"{self.__class__.__name__}({title=}, {is_active=}, {visible=})"
