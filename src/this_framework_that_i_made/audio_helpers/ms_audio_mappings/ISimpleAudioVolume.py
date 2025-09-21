import ctypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_int, byref


IID_ISimpleAudioVolume = GUID("{87CE5498-68D6-44E5-9215-6DA47EF883D8}")


class ISimpleAudioVolume(IUnknown):

    _iid_ = IID_ISimpleAudioVolume

    _methods_ = [
        COMMETHOD([], HRESULT, "SetMasterVolume",
                  (["in"], ctypes.c_float, "fLevel"),
                  (["in"], POINTER(GUID), "EventContext")),
        COMMETHOD([], HRESULT, "GetMasterVolume",
                  (["out"], POINTER(ctypes.c_float), "pfLevel")),
        COMMETHOD([], HRESULT, "SetMute",
                  (["in"], c_int, "bMute"),
                  (["in"], POINTER(GUID), "EventContext")),
        COMMETHOD([], HRESULT, "GetMute",
                  (["out"], POINTER(c_int), "pbMute")),
    ]


class PySimpleAudioVolume:

    def __init__(self, iface: ISimpleAudioVolume):
        self.iface = iface

    def get_master_volume(self) -> float:
        return float(self.iface.GetMasterVolume())

    def set_master_volume(self, level: float, event_context: GUID | None = None) -> None:
        hr = self.iface.SetMasterVolume(level, byref(event_context) if event_context else None)
        if hr != 0:
            raise OSError(f"SetMasterVolume hr=0x{hr:08X}")

    def get_mute(self) -> bool:
        return bool(self.iface.GetMute())

    def set_mute(self, mute: bool, event_context: GUID | None = None) -> None:
        hr = self.iface.SetMute(1 if mute else 0, byref(event_context) if event_context else None)
        if hr != 0:
            raise OSError(f"SetMute hr=0x{hr:08X}")
