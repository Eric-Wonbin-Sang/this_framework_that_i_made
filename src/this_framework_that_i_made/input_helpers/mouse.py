from dataclasses import dataclass
from pynput import mouse
import queue

from .common import InputDevice, InputEvent


class MouseEvent(InputEvent):
    ...


class ClickEvent(MouseEvent):

    BUTTON_MAP = {
        mouse.Button.left: "left",
        mouse.Button.right: "right",
        mouse.Button.middle: "middle"
    }

    def __init__(self, button, is_pressed):
        self.value = self.get_button_as_str(button)
        self.is_pressed = is_pressed

    @classmethod
    def get_button_as_str(cls, button):
        return cls.BUTTON_MAP.get(button, str(button))

    def __str__(self):
        value = self.value
        is_pressed = self.is_pressed
        return f"{self.__class__.__name__}({value=}, {is_pressed=})"


@dataclass
class MoveEvent(MouseEvent):
    x: int
    y: int


@dataclass
class ScrollEvent(MouseEvent):
    dx: int  # horizontal scrolling
    dy: int  # vertical scrolling


class GlobalMouse(InputDevice):

    """
    TODO: this is called global because this does not differentiate between actual devices.

    Cross-platform mouse state + event stream.
    """

    def __init__(self, suppress: bool = False):
        self._listener = None
        self._queue = queue.Queue()
        self._alive = False
        self._suppress = suppress

    def _on_move(self, x, y):
        self._queue.put(MoveEvent(x, y))

    def _on_click(self, x, y, button, pressed):
        self._queue.put(ClickEvent(button, pressed))

    def _on_scroll(self, x, y, dx, dy):
        self._queue.put(ScrollEvent(dx, dy))

    # --- public API ---
    def start(self):
        if self._listener:
            return
        self._alive = True
        self._listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            suppress=self._suppress,
        )
        self._listener.start()

    def stop(self):
        self._alive = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def yield_mouse_events(self, timeout=None):
        """
        Generator yielding state snapshots whenever the mouse changes.
        Blocks until an event arrives (or until `timeout` seconds if provided).
        """
        self.start()
        try:
            while self._alive:
                try:
                    snap = self._queue.get(timeout=timeout)
                    yield snap
                except queue.Empty:
                    # Optionally emit a heartbeat/current status
                    pass
        finally:
            self.stop()
