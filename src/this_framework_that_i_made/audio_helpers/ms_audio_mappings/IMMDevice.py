import ctypes
from enum import Enum, IntFlag
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_ulong, c_void_p, c_wchar_p, byref

from .IAudioSessionManager import PyAudioSessionManager
from .IAudioSessionManager2 import PyAudioSessionManager2
from .IAudioClient import CLSCTX_INPROC_SERVER, IAudioClient, IID_IAudioClient, PyAudioClient
from .IPropertyStore import IPropertyStore, PyPropertyStore
from .ms_audio_common import PROPERTYKEY


# Core Audio GUID
IID_IMMDevice = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")


class IMMDevice(IUnknown):
    _iid_ = IID_IMMDevice
    _methods_ = [
        COMMETHOD(
            [], HRESULT, "Activate",
            (["in"], POINTER(GUID), "iid"),
            (["in"], c_ulong, "dwClsCtx"),
            (["in"], c_void_p, "pActivationParams"),
            (["out"], POINTER(c_void_p), "ppInterface")
        ),
        COMMETHOD(
            [], HRESULT, "OpenPropertyStore",
            (["in"], c_ulong, "stgmAccess"),
            (["out"], POINTER(POINTER(IPropertyStore)), "ppProperties")
        ),
        COMMETHOD(
            [], HRESULT, "GetId",
            (["out"], POINTER(c_wchar_p), "ppstrId")
        ),
        COMMETHOD(
            [], HRESULT, "GetState",
            (["out"], POINTER(c_ulong), "pdwState")
        ),
    ]


class DeviceState(IntFlag):
    ACTIVE      = 0x00000001  # DEVICE_STATE_ACTIVE
    DISABLED    = 0x00000002  # DEVICE_STATE_DISABLED
    NOTPRESENT  = 0x00000004  # DEVICE_STATE_NOTPRESENT
    UNPLUGGED   = 0x00000008  # DEVICE_STATE_UNPLUGGED
    ALL         = 0x0000000F  # DEVICE_STATEMASK_ALL


class StoreAccessMode(Enum):
    STGM_READ      : int = 0
    STGM_WRITE     : int = 1
    STGM_READWRITE : int = 2


class PyMmDevice:
    
    PKEY_Device_FriendlyName = PROPERTYKEY(GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)

    def __init__(self, iface):
        self.iface = iface

    def activate(self, iid: GUID, dwClsCtx: c_ulong, pActivationParams: c_void_p) -> c_void_p:
        return self.iface.Activate(iid, dwClsCtx, pActivationParams)  # ppInterface

    def open_property_store(self, mode: StoreAccessMode = StoreAccessMode.STGM_READ) -> PyPropertyStore:
        return PyPropertyStore(self.iface.OpenPropertyStore(mode.value))  # ppProperties

    def get_id(self) -> str:
        return self.iface.GetId()  # ppstrId

    def get_name(self) -> str | None:
        store = self.open_property_store()
        return value.to_python() if (value := store.get_value(byref(self.PKEY_Device_FriendlyName))) else None

    def get_state(self) -> DeviceState:
        return DeviceState(self.iface.GetState())  # pdwState

    def get_audio_client(self) -> PyAudioClient:
        p_iface = self.activate(byref(IID_IAudioClient), CLSCTX_INPROC_SERVER, None)
        iaudio = ctypes.cast(p_iface, POINTER(IAudioClient))
        return PyAudioClient(iaudio)

    def get_audio_session_manager(self) -> PyAudioSessionManager:
        return PyAudioSessionManager.get_from_mm_device(self)

    def get_audio_session_manager_2(self) -> PyAudioSessionManager2:
        return PyAudioSessionManager2.get_from_mm_device(self)

    def __repr__(self) -> str:
        name = self.get_name()
        return f"{self.__class__.__name__}({name=} [{self.get_state().name}])"
