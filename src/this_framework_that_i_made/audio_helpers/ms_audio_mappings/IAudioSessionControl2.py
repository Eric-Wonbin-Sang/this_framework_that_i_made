import ctypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_wchar_p, c_uint, c_int

from .IAudioSessionControl import IAudioSessionControl, PyAudioSessionControl


IID_IAudioSessionControl2 = GUID("{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}")


class IAudioSessionControl2(IAudioSessionControl):
    _iid_ = IID_IAudioSessionControl2
    _methods_ = IAudioSessionControl._methods_ + [
        COMMETHOD([], HRESULT, "GetSessionIdentifier",
                  (["out"], POINTER(c_wchar_p), "pRetVal")),
        COMMETHOD([], HRESULT, "GetSessionInstanceIdentifier",
                  (["out"], POINTER(c_wchar_p), "pRetVal")),
        COMMETHOD([], HRESULT, "GetProcessId",
                  (["out"], POINTER(c_uint), "pRetVal")),
        COMMETHOD([], HRESULT, "IsSystemSoundsSession"),
        COMMETHOD([], HRESULT, "SetDuckingPreference",
                  (["in"], c_int, "optOut")),  # BOOL
    ]


class PyAudioSessionControl2(PyAudioSessionControl):

    def __init__(self, iface: IAudioSessionControl2):
        super().__init__(iface)

    def get_session_identifier(self) -> str | None:
        return self.iface.GetSessionIdentifier()

    def get_session_instance_identifier(self) -> str | None:
        return self.iface.GetSessionInstanceIdentifier()

    def get_process_id(self) -> int:
        return int(self.iface.GetProcessId())

    def is_system_sounds(self) -> bool:
        # S_OK (0) means "true" in this HRESULT-returning method
        return self.iface.IsSystemSoundsSession() == 0

    def set_ducking_preference(self, opt_out: bool) -> None:
        hr = self.iface.SetDuckingPreference(1 if opt_out else 0)
        if hr != 0:
            raise OSError(f"SetDuckingPreference hr=0x{hr:08X}")
