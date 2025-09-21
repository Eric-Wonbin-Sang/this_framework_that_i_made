from pynput import mouse
import threading, queue, time

from .common import InputDevice, InputEvent


class MouseEvent(InputEvent):

    def __init__(self):
        ...


class GlobalMouse(InputDevice):

    """
    TODO: this is called global because this does not differentiate between actual devices.

    Cross-platform mouse state + event stream.
    Yields a dict on any change: {"type": "move|click|scroll",
                                  "pos": (x, y),
                                  "buttons": {"left","right","middle"},
                                  "detail": event-specific tuple}
    """

    def __init__(self, include_move=True):
        self.include_move = include_move
        self._listener = None
        self._q = queue.Queue()
        self._pressed = set()    # {"left","right","middle"}
        self._pos = (0, 0)
        self._alive = False

    # --- internal: callbacks -> queue snapshots ---
    def _snapshot(self, etype: str, detail: tuple):
        snap = {
            "type": etype,
            "pos": self._pos,
            "buttons": set(self._pressed),  # copy
            "detail": detail
        }
        self._q.put(snap)

    def _on_move(self, x, y):
        self._pos = (x, y)
        if self.include_move:
            self._snapshot("move", (x, y))

    def _on_click(self, x, y, button, pressed):
        name = {mouse.Button.left: "left",
                mouse.Button.right: "right",
                mouse.Button.middle: "middle"}.get(button, str(button))
        if pressed:
            self._pressed.add(name)
        else:
            self._pressed.discard(name)
        self._pos = (x, y)
        self._snapshot("click", (name, pressed, (x, y)))

    def _on_scroll(self, x, y, dx, dy):
        self._pos = (x, y)
        self._snapshot("scroll", (dx, dy, (x, y)))

    # --- public API ---
    def start(self):
        if self._listener:
            return
        self._alive = True
        self._listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
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
                    snap = self._q.get(timeout=timeout)
                    yield snap
                except queue.Empty:
                    # Optionally emit a heartbeat/current status
                    # yield {"type":"heartbeat","pos":self._pos,"buttons":set(self._pressed),"detail":()}
                    pass
        finally:
            self.stop()
