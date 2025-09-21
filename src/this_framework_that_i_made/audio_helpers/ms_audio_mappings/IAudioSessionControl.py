from enum import Enum
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_void_p, c_int, c_wchar_p


IID_IAudioSessionControl = GUID("{F4B1A599-7266-4319-A8CA-E70ACB11E8CD}")


class IAudioSessionControl(IUnknown):

    _iid_ = IID_IAudioSessionControl
    _methods_ = [
        COMMETHOD([], HRESULT, "GetState",
                  (["out"], POINTER(c_int), "pRetVal")),  # AudioSessionState
        COMMETHOD([], HRESULT, "GetDisplayName",
                  (["out"], POINTER(c_wchar_p), "pRetVal")),
        COMMETHOD([], HRESULT, "SetDisplayName",
                  (["in"],  c_wchar_p, "Value"),
                  (["in"],  POINTER(GUID), "EventContext")),
        COMMETHOD([], HRESULT, "GetIconPath",
                  (["out"], POINTER(c_wchar_p), "pRetVal")),
        COMMETHOD([], HRESULT, "SetIconPath",
                  (["in"],  c_wchar_p, "Value"),
                  (["in"],  POINTER(GUID), "EventContext")),
        COMMETHOD([], HRESULT, "GetGroupingParam",
                  (["out"], POINTER(GUID), "pRetVal")),
        COMMETHOD([], HRESULT, "SetGroupingParam",
                  (["in"],  POINTER(GUID), "Override"),
                  (["in"],  POINTER(GUID), "EventContext")),
        # Keep notification parameters as void* to avoid defining the whole events interface here
        COMMETHOD([], HRESULT, "RegisterAudioSessionNotification",
                  (["in"], c_void_p, "NewNotifications")),     # IAudioSessionEvents*
        COMMETHOD([], HRESULT, "UnregisterAudioSessionNotification",
                  (["in"], c_void_p, "NewNotifications")),     # IAudioSessionEvents*
    ]


class AudioSessionState(Enum):
    INACTIVE = 0
    ACTIVE   = 1
    EXPIRED  = 2


class PyAudioSessionControl:

    def __init__(self, iface: IAudioSessionControl):
        self.iface = iface

    def get_state(self) -> AudioSessionState:
        return AudioSessionState(self.iface.GetState())

    def get_display_name(self) -> str | None:
        return self.iface.GetDisplayName()

    def get_icon_path(self) -> str | None:
        return self.iface.GetIconPath()

    def get_grouping_param(self) -> GUID:
        return self.iface.GetGroupingParam()
