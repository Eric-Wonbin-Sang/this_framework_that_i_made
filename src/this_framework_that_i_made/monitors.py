from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
import time
from typing import List
import mss
import numpy as np

from .generics import SavableObject, ensure_savable


@ensure_savable
@dataclass
class PlaneObject:
    x: str
    y: str

    def as_dict(self):
        return {
            "x": self.x,
            "y": self.y,
        }


@ensure_savable
@dataclass
class RectangleMixin:
    width: float
    height: float

    def as_dict(self):
        return {
            "width": self.width,
            "height": self.height,
        }


class Orientation(Enum):
    VERTICAL = auto()
    HORIZONTAL = auto()


def wait_for_fps_target(fps: float):
    """Generator-like helper that yields True every 1/fps seconds."""
    
    if fps is None:
        while True:
            yield True
    
    period = (1.0 / fps)
    next_time = time.perf_counter()
    while True:
        now = time.perf_counter()
        if now < next_time:
            time.sleep(next_time - now)
        else:
            # if we fell behind, reset
            next_time = now
        yield True
        next_time += period


@ensure_savable
class Monitor(RectangleMixin, PlaneObject, SavableObject):

    def __init__(self, data):
        self.monitor_data = data
        RectangleMixin.__init__(self, width=data["width"], height=data["height"])
        PlaneObject.__init__(self, x=data["left"], y=data["top"])

    @property
    def orientation(self):
        return Orientation.HORIZONTAL if self.width > self.height else Orientation.VERTICAL

    def yield_content(self, fps=None):
        with mss.mss() as sct:  # separate instance per worker
            for _ in wait_for_fps_target(fps):
                img = sct.grab(self.monitor_data)
                frame = np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.height, img.width, 3)
                yield (self.monitor_data, time.time(), frame)

    @classmethod
    def get_monitors(cls) -> List["Monitor"]:
        with mss.mss() as probe:  # just to list monitors
            return [cls(data) for data in probe.monitors[1:]]

    def is_false(self):
        return self.width <= 1 and self.height <= 1

    def as_dict(self):
        return {
            "orientation": self.orientation,
            **RectangleMixin.as_dict(self),
            **PlaneObject.as_dict(self),
        }


@ensure_savable
class Window(ABC):
    
    @classmethod
    @abstractmethod
    def get_windows(cls):
        ...

    @abstractmethod
    def yield_video_content(self):
        ...

    @abstractmethod
    def yield_audio_content(self):
        ...

    @abstractmethod
    def as_dict(self):
        ...
