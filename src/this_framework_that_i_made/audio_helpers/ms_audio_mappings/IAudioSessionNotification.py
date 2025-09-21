import comtypes
from ctypes import HRESULT, POINTER
from comtypes import GUID, IUnknown, COMMETHOD

from .IAudioSessionControl import IAudioSessionControl
from .IAudioSessionControl2 import IID_IAudioSessionControl2, PyAudioSessionControl2

IID_IAudioSessionNotification = GUID("{641DD20B-4D41-49CC-AB75-3A0C39A3C785}")


class IAudioSessionNotification(IUnknown):
    _iid_ = IID_IAudioSessionNotification
    _methods_ = [
        COMMETHOD([], HRESULT, "OnSessionCreated",
                  (["in"], POINTER(IAudioSessionControl), "NewSession")),  # we'll QI for IAudioSessionControl2
    ]


class AudioSessionNotification(comtypes.COMObject):
    _com_interfaces_ = [IAudioSessionNotification]

    def __init__(self, endpoint):
        super().__init__()
        self.endpoint = endpoint  # e.g. PyMmDevice or PyAudioSessionManager2

    def OnSessionCreated(self, new_session):
        ctrl2 = PyAudioSessionControl2(
            new_session.QueryInterface(IID_IAudioSessionControl2)
        )
        try:
            endpoint_id = self.endpoint.get_id()
        except AttributeError:
            endpoint_id = getattr(self.endpoint, "iface", None)

        print(
            f"[{endpoint_id}] new session "
            f"state={ctrl2.get_state().name} "
            f"pid={ctrl2.get_process_id()} "
            f"display={ctrl2.get_display_name()}"
        )
        return 0  # S_OK
