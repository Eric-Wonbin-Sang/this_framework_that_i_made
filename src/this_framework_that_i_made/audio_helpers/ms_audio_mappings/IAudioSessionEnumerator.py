import ctypes
from typing import Any

from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_int, c_ulong, c_wchar_p

from .IAudioSessionControl import IAudioSessionControl, PyAudioSessionControl


IID_IAudioSessionEnumerator = GUID("{E2F5BB11-0570-40CA-ACDD-3AA01277DEE8}")


class IAudioSessionEnumerator(IUnknown):

    _iid_ = IID_IAudioSessionEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount",
                  (["out"], POINTER(c_int), "SessionCount")),
        COMMETHOD([], HRESULT, "GetSession",
                  (["in"],  c_int, "SessionIndex"),
                  (["out"], POINTER(POINTER(IAudioSessionControl)), "Session")),
    ]


class PyAudioSessionEnumerator:

    def __init__(self, iface: Any):
        self.iface = self._coerce_iface(iface)

    @staticmethod
    def _coerce_iface(iface: Any) -> POINTER(IAudioSessionEnumerator):
        if isinstance(iface, POINTER(IAudioSessionEnumerator)):
            return iface
        if isinstance(iface, tuple):
            return PyAudioSessionEnumerator._coerce_iface(iface[0])
        if isinstance(iface, ctypes.c_void_p):
            raw_ptr = iface
        elif isinstance(iface, int):
            raw_ptr = ctypes.c_void_p(iface)
        else:
            raise TypeError(f"Unsupported enumerator pointer type: {type(iface)!r}")
        if not raw_ptr:
            raise ValueError("IAudioSessionEnumerator pointer is NULL")
        return ctypes.cast(raw_ptr, POINTER(IAudioSessionEnumerator))

    def get_count(self) -> int:
        return int(self.iface.GetCount())

    def get_session(self, index: int) -> PyAudioSessionControl:
        ctrl = self.iface.GetSession(index)
        return PyAudioSessionControl(ctrl)

    def get_sessions(self):
        return [self.get_session(i) for i in range(self.get_count())]

    def get_session2(self, index: int):
        ctrl = self.get_session(index)
        from .IAudioSessionControl2 import IID_IAudioSessionControl2, PyAudioSessionControl2
        iface2 = ctrl.iface.QueryInterface(IID_IAudioSessionControl2)
        return PyAudioSessionControl2(iface2)

    def get_sessions2(self):
        return [self.get_session2(i) for i in range(self.get_count())]

    def iter_controls(self):
        n = self.get_count()
        for i in range(n):
            yield self.get_session(i)

    def iter_controls2(self):
        n = self.get_count()
        for i in range(n):
            yield self.get_session2(i)
