import ctypes
import time
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_void_p, c_wchar_p, byref

import comtypes

from .IAudioSessionNotification import IAudioSessionNotification, AudioSessionNotification
from .ISimpleAudioVolume import PySimpleAudioVolume
from .IAudioSessionControl import PyAudioSessionControl
from .IAudioSessionEnumerator import IAudioSessionEnumerator, PyAudioSessionEnumerator
from .IAudioSessionManager import IAudioSessionManager


IID_IAudioSessionManager2 = GUID("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")


class IAudioSessionManager2(IAudioSessionManager):
    _iid_ = IID_IAudioSessionManager2
    _methods_ = IAudioSessionManager._methods_ + [
        COMMETHOD([], HRESULT, "GetSessionEnumerator",
                  (["out"], POINTER(POINTER(IAudioSessionEnumerator)), "SessionEnum")),
        COMMETHOD([], HRESULT, "RegisterSessionNotification",
                  (["in"], POINTER(IAudioSessionNotification), "SessionNotification")),
        COMMETHOD([], HRESULT, "UnregisterSessionNotification",
                  (["in"], POINTER(IAudioSessionNotification), "SessionNotification")),
        COMMETHOD([], HRESULT, "RegisterDuckNotification",
                  (["in"], c_wchar_p, "sessionID"),
                  (["in"], c_void_p, "duckNotification")),     # IAudioVolumeDuckNotification*
        COMMETHOD([], HRESULT, "UnregisterDuckNotification",
                  (["in"], c_void_p, "duckNotification")),     # IAudioVolumeDuckNotification*
    ]


# (Optional) Activate IAudioClient to prepare for capture code later
# CLSCTX_INPROC_SERVER = 0x1
CLSCTX_INPROC_SERVER = 0x1
ERROR_NOT_FOUND = 0x80070490


class PyAudioSessionManager2:

    def __init__(self, iface: IAudioSessionManager2):
        self.iface = iface

    @classmethod
    def get_from_mm_device(cls, mm_device: "PyMmDevice"):
        p_iface = mm_device.activate(byref(IID_IAudioSessionManager2), CLSCTX_INPROC_SERVER, None)
        iface = ctypes.cast(p_iface, POINTER(IAudioSessionManager2))
        return cls(iface)

    # Convenience: pass None for pSessionGuid to target the caller’s default session
    def get_audio_session_control(self, session_guid: GUID | None = None, stream_flags: int = 0) -> PyAudioSessionControl:
        ptr = self.iface.GetAudioSessionControl(byref(session_guid) if session_guid else None, stream_flags)
        return PyAudioSessionControl(ptr)

    def get_simple_audio_volume(self, session_guid: GUID | None = None, stream_flags: int = 0) -> PySimpleAudioVolume:
        ptr = self.iface.GetSimpleAudioVolume(byref(session_guid) if session_guid else None, stream_flags)
        return PySimpleAudioVolume(ptr)

    @staticmethod
    def _activate_mgr2(endpoint) -> POINTER(IAudioSessionManager2):
        p = c_void_p()
        hr = endpoint.Activate(byref(IID_IAudioSessionManager2), CLSCTX_INPROC_SERVER, None, byref(p))
        if hr != 0:
            raise OSError(f"Activate(IAudioSessionManager2) hr=0x{hr:08X}")
        return ctypes.cast(p, POINTER(IAudioSessionManager2))

    @staticmethod
    def _prime_with_iaudioclient(device: "PyMmDevice"):
        # Create a session by initializing an IAudioClient (shared mode, no Start)
        audio_client = device.get_audio_client()
        audio_client.try_default_initialization()

    def get_session_enumerator(self, device: "PyMmDevice | None" = None) -> PyAudioSessionEnumerator:
        """Return an audio session enumerator for the endpoint backing this manager.

        Because Windows only materialises the enumerator when there is at least one
        active audio session, we try a few strategies to coax CoreAudio into exposing
        it before surfacing a more descriptive error.
        """

        def _create_enumerator() -> PyAudioSessionEnumerator:
            return PyAudioSessionEnumerator(self.iface.GetSessionEnumerator())

        try:
            return _create_enumerator()
        except comtypes.COMError as e:
            if (e.hresult & 0xFFFFFFFF) != ERROR_NOT_FOUND:
                raise

        # second try, prime interface - this creates a (dummy) session container
        self.iface.GetAudioSessionControl(None, 0)
        try:
            return _create_enumerator()
        except comtypes.COMError as e:
            if (e.hresult & 0xFFFFFFFF) != ERROR_NOT_FOUND:
                raise

        if device is not None:
            # third try - initialise an IAudioClient to force a session to exist
            self._prime_with_iaudioclient(device)
            time.sleep(0.01)
            try:
                return _create_enumerator()
            except comtypes.COMError as e:
                if (e.hresult & 0xFFFFFFFF) == ERROR_NOT_FOUND:
                    raise RuntimeError(
                        "No audio sessions are currently exposed for this endpoint. "
                        "Start playback in the target app and retry."
                    ) from e
                raise

        raise RuntimeError(
            "IAudioSessionManager2 did not expose any sessions for this endpoint."
        )

    # Raw registration helpers (pass COM objects that implement these interfaces)
    def register_session_notification(self, notification_obj: AudioSessionNotification) -> None:
        hr = self.iface.RegisterSessionNotification(notification_obj)
        if hr != 0:
            raise OSError(f"RegisterSessionNotification hr=0x{hr:08X}")

    def unregister_session_notification(self, notification_obj: AudioSessionNotification) -> None:
        hr = self.iface.UnregisterSessionNotification(notification_obj)
        if hr != 0:
            raise OSError(f"UnregisterSessionNotification hr=0x{hr:08X}")

    def register_duck_notification(self, session_id: str | None, duck_obj: c_void_p) -> None:
        hr = self.iface.RegisterDuckNotification(session_id, duck_obj)
        if hr != 0:
            raise OSError(f"RegisterDuckNotification hr=0x{hr:08X}")

    def unregister_duck_notification(self, duck_obj: c_void_p) -> None:
        hr = self.iface.UnregisterDuckNotification(duck_obj)
        if hr != 0:
            raise OSError(f"UnregisterDuckNotification hr=0x{hr:08X}")