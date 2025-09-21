from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_ulong

from .ISimpleAudioVolume import ISimpleAudioVolume, PySimpleAudioVolume
from .IAudioSessionControl import IAudioSessionControl, PyAudioSessionControl


IID_IAudioSessionManager = GUID("{BFA971F1-4D5E-40BB-935E-967039BFBEE4}")


class IAudioSessionManager(IUnknown):

    _iid_ = IID_IAudioSessionManager
    _methods_ = [
        COMMETHOD([], HRESULT, "GetAudioSessionControl",
                  (["in"],  POINTER(GUID), "AudioSessionGuid"),  # can be NULL
                  (["in"],  c_ulong, "StreamFlags"),
                  (["out"], POINTER(POINTER(IAudioSessionControl)), "SessionControl")),
        COMMETHOD([], HRESULT, "GetSimpleAudioVolume",
                  (["in"],  POINTER(GUID), "AudioSessionGuid"),  # can be NULL
                  (["in"],  c_ulong, "StreamFlags"),
                  (["out"], POINTER(POINTER(ISimpleAudioVolume)), "SimpleAudioVolume")),
    ]


class PyAudioSessionManager:

    def __init__(self, iface):
        self.iface = iface
    
    def get_audio_session_control(self, audio_session_guid: GUID, stream_flags: c_ulong) -> PyAudioSessionControl:
        return PyAudioSessionControl(self.iface.GetAudioSessionControl(audio_session_guid, stream_flags))

    def get_simple_audio_volume(self, audio_session_guid: GUID, stream_flags: c_ulong) -> PySimpleAudioVolume:
        return PySimpleAudioVolume(self.iface.GetSimpleAudioVolume(audio_session_guid, stream_flags))
