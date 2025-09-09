

from enum import Enum, auto
import platform

import numpy as np


pyaudio = None
if platform.system() == "Windows":
    import pyaudiowpatch
    pyaudio = pyaudiowpatch
else:
    import pyaudio
    pyaudio = pyaudio


class SampleFormat(Enum):
    INT_16 = auto()
    INT_24 = auto()
    INT_32 = auto()
    FLOAT_32 = auto()
    UINT_8 = auto()


PYAUDIO_SAMPLE_FORMAT = {
    SampleFormat.INT_16: pyaudio.paInt16,      # 16-bit signed integer (most common for PCM audio)
    SampleFormat.INT_24: pyaudio.paInt24,      # 24-bit signed integer
    SampleFormat.INT_32: pyaudio.paInt32,      # 32-bit signed integer
    SampleFormat.FLOAT_32: pyaudio.paFloat32,  # 32-bit float (values between –1.0 and +1.0)
    SampleFormat.UINT_8: pyaudio.paUInt8,      # 8-bit unsigned integer
}


NUMPY_SAMPLE_FORMAT = {
    SampleFormat.INT_16: np.int16,
    SampleFormat.INT_24: np.int32,
    SampleFormat.INT_32: np.int32,
    SampleFormat.FLOAT_32: np.float32,
    SampleFormat.UINT_8: np.uint8,
}


class PcmBlock:

    """ Pulse Code Modulation Blocks """

    __slots__ = ("_bytes", "_dtype", "_channels", "_array")

    def __init__(self, data: bytes, dtype, channels: int):
        self._bytes = data                # wire format
        self._dtype = dtype
        self._channels = channels
        self._array = None                # created lazily

    @property
    def bytes(self) -> bytes:
        return self._bytes                # send over network

    @property
    def array(self) -> np.ndarray:
        if self._array is None:
            arr = np.frombuffer(self._bytes, dtype=self._dtype)   # zero-copy view
            if self._channels > 1:
                arr = arr.reshape(-1, self._channels)             # still a view
            self._array = arr
        return self._array
