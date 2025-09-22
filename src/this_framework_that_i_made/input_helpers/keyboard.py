from functools import cached_property
from typing import Generator
from pynput import keyboard
import queue

from .common import InputDevice, InputEvent


class KeyboardEvent(InputEvent):
    ...


class KeyEvent(KeyboardEvent):
    """
    Press/release of a key.
    Attributes:
      value: normalized key name (e.g., "a", "enter", "ctrl")
      is_pressed: True for key down, False for key up
      is_modifier: whether this key is a modifier (ctrl/alt/shift/cmd/meta/super)
    """

    MOD_NAMES = {"ctrl", "alt", "shift", "cmd", "meta", "super"}

    def __init__(self, value, is_modifier, is_pressed):
        self.value = value
        self.is_modifier = is_modifier
        self.is_pressed = is_pressed

    @classmethod
    def get_from_key(cls, key, is_pressed):
        # Special keys (keyboard.Key.*)
        if isinstance(key, keyboard.Key):
            value = str(key).split(".")[-1]
            return cls(
                value=value,
                is_modifier=value.split()[0] in KeyEvent.MOD_NAMES,
                is_pressed=is_pressed,
            )
        # Printable keys (keyboard.KeyCode)
        elif isinstance(key, keyboard.KeyCode):
            ch = key.char
            if ch:
                return cls(
                    value=ch,
                    is_modifier=False,
                    is_pressed=is_pressed,
                )
            # Fallback to virtual-key code if present
            vk = getattr(key, "vk", None)
            return cls(
                value=(f"vk{vk}" if vk is not None else "unknown"),
                is_modifier=False,
                is_pressed=is_pressed,
            )
        # Ultimate fallback
        else:
            return cls(
                value=str(key),
                is_modifier=False,
                is_pressed=is_pressed,
            )

    @cached_property
    def is_ctrl(self):
        return self.value in ["ctrl", "ctrl_l", "ctrl_r"]

    @cached_property
    def is_shift(self):
        return self.value in ["shift", "shift_l", "shift_r"]

    @cached_property
    def is_alt(self):
        return self.value in ["alt", "alt_l", "alt_r"]

    @cached_property
    def is_cmd(self):
        return self.value in ["cmd", "cmd_l", "cmd_r"]

    def __str__(self):
        value = self.value
        is_modifier = self.is_modifier
        is_pressed = self.is_pressed
        return f"{self.__class__.__name__}({value=}, {is_modifier=}, {is_pressed=})"


class KeyboardInputter:

    def __init__(self):
        self._ctl = keyboard.Controller()

    # def play_event(self, event: KeyboardEvent):
    #     if self._suppress and self._pass_through and self._allow(event) and not self._replaying:
    #         # re-inject the same event so other apps see it
    #         self._replaying = True
    #         try:
    #             key = event._raw if hasattr(event, "_raw") else None  # add _raw in your KeyEvent if you want
    #             if key is None:  # fallback: rebuild from evt.value
    #                 key = getattr(keyboard.Key, event.value, keyboard.KeyCode.from_char(event.value))
    #             if event.is_pressed:
    #                 self._ctl.press(key)
    #             else:
    #                 self._ctl.release(key)
    #         finally:
    #             self._replaying = False


class KeyboardEventGenerator(InputDevice):
    """
    Cross-platform keyboard event stream (Windows/macOS/Linux X11).
    Yields KeyEvent on every press/release.

    Notes:
      • macOS requires Accessibility/Input Monitoring permission.
      • On Wayland, global capture may be restricted by the compositor.

    OS key repeat (“typematic”): When you hold a key, the OS waits a delay (e.g., ~250-600 ms)
    then emits “press/character” events at a steady rate (e.g., ~20-40 Hz) until you release.
    Many APIs surface these as repeated key-down events without an intervening key-up.

    Library abstraction: pynput doesn't expose a “this is a repeat” flag (some native APIs do),
    so you'll just see multiple on_press calls for the same key while it's held.
    """

    def __init__(self, *, dedupe_repeats: bool = True, suppress: bool = False):
        self._listener = None
        self._queue = queue.Queue()
        self._alive = False
        self._down = set()  # for repeat-dedupe
        self._dedupe = dedupe_repeats
        self._suppress = suppress

    # --- callbacks ---
    def _on_press(self, key):
        event = KeyEvent.get_from_key(key, is_pressed=True)
        if self._dedupe and event.value in self._down:
            return  # ignore OS key-repeat
        self._down.add(event.value)
        self._queue.put(event)

    def _on_release(self, key):
        event = KeyEvent.get_from_key(key, is_pressed=False)
        self._down.discard(event.value)
        self._queue.put(event)

    # --- public API ---
    def start(self):
        if self._listener:
            return
        self._alive = True
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=self._suppress,
        )
        self._listener.start()

    def stop(self):
        self._alive = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._down.clear()

    def yield_keyboard_events(self, timeout=None) -> Generator[KeyboardEvent]:
        """
        Generator yielding KeyEvent whenever keyboard state changes.
        Blocks until an event arrives (or until `timeout` seconds if provided).
        """
        self.start()
        try:
            while self._alive:
                try:
                    evt = self._queue.get(timeout=timeout)
                    yield evt
                except queue.Empty:
                    # Optional: emit heartbeat/current state if desired
                    pass
        finally:
            self.stop()
