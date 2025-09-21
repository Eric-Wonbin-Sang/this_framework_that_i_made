from enum import Enum
from typing import List
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
import ctypes
from comtypes.client import CreateObject
from ctypes import POINTER, c_void_p, c_ulong, c_wchar_p

from .IMMDevice import IMMDevice, PyMmDevice
from .IMMDeviceCollection import IMMDeviceCollection, PyMmDeviceCollection


# Core Audio GUIDs
IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")


class IMMDeviceEnumerator(IUnknown):

    """
    
    provides methods for enumerating multimedia device resources
    https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nn-mmdeviceapi-immdeviceenumerator
    
    """
    _iid_ = IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumAudioEndpoints",
                  (["in"], ctypes.c_int, "dataFlow"),          # EDataFlow
                  (["in"], c_ulong, "dwStateMask"),            # DEVICE_STATE_*
                  (["out"], POINTER(POINTER(IMMDeviceCollection)), "ppDevices")),
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                  (["in"], ctypes.c_int, "dataFlow"),          # EDataFlow
                  (["in"], ctypes.c_int, "role"),              # ERole
                  (["out"], POINTER(POINTER(IMMDevice)), "ppEndpoint")),
        COMMETHOD([], HRESULT, "GetDevice",
                  (["in"], c_wchar_p, "pwstrId"),
                  (["out"], POINTER(POINTER(IMMDevice)), "ppDevice")),
        COMMETHOD([], HRESULT, "RegisterEndpointNotificationCallback",
                  (["in"], c_void_p, "pClient")),  # IM: IIMMNotificationClient*
        COMMETHOD([], HRESULT, "UnregisterEndpointNotificationCallback",
                  (["in"], c_void_p, "pClient")),
    ]


class DeviceType(Enum):  # was EDataFlow
    OUTPUT: int = 0  # was eRender - rendering device (speaker, headphones)
    INPUT: int = 1  # was eCapture - capture device (microphone)
    DUPLEX: int = 2  # was eAll - both


class DeviceState(Enum):
    # The audio endpoint device is active. That is, the audio adapter that connects to the endpoint device is present and enabled. In addition, if the endpoint device plugs into a jack on the adapter, then the endpoint device is plugged in.
    DEVICE_STATE_ACTIVE: int = 0x00000001
    # The audio endpoint device is disabled. The user has disabled the device in the Windows multimedia control panel, Mmsys.cpl. For more information, see Remarks.
    DEVICE_STATE_DISABLED: int = 0x00000002
    # The audio endpoint device is not present because the audio adapter that connects to the endpoint device has been removed from the system, or the user has disabled the adapter device in Device Manager.
    DEVICE_STATE_NOTPRESENT: int = 0x00000004
    # The audio endpoint device is unplugged. The audio adapter that contains the jack for the endpoint device is present and enabled, but the endpoint device is not plugged into the jack. Only a device with jack-presence detection can be in this state. For more information about jack-presence detection, see Audio Endpoint Devices.
    DEVICE_STATE_UNPLUGGED: int = 0x00000008
    # Includes audio endpoint devices in all states active, disabled, not present, and unplugged.
    DEVICE_STATEMASK_ALL: int = 0x0000000F


class DeviceRole(Enum):
    E_CONSOLE: int = 0  # eConsole
    E_MULTIMEDIA: int = 1  # eMultimedia
    E_COMMUNICATIONS: int = 2  # eCommunications


class IMMNotificationClient:
    ...


class PyMmNotificationClient:

    def __init__(self, iface):
        self.iface = iface

    def __init__(self):
        raise NotImplemented


class PyMmDeviceEnumerator:

    def __init__(self, iface):
        self.iface = iface

    @classmethod
    def create(cls):
        return cls(CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator))

    def _enum_audio_endpoints(
        self,
        device_type: DeviceType = DeviceType.DUPLEX,
        device_state: DeviceState = DeviceState.DEVICE_STATE_ACTIVE,
    ) -> PyMmDeviceCollection:
        # comtypes returns out-params directly; no byref needed
        return PyMmDeviceCollection(self.iface.EnumAudioEndpoints(device_type.value, device_state.value))

    def get_devices(
        self,
        device_type: DeviceType = DeviceType.DUPLEX,
        device_state: DeviceState = DeviceState.DEVICE_STATE_ACTIVE,
    ) -> List[PyMmDevice]:
        return self._enum_audio_endpoints(device_type, device_state).get_items()

    def get_default_device(
        self,
        device_type: DeviceType = DeviceType.DUPLEX,
        role: DeviceRole = DeviceRole.E_MULTIMEDIA,
    ) -> PyMmDevice:
        return PyMmDevice(self.iface.GetDefaultAudioEndpoint(device_type.value, role.value))

    def get_default_input_device(self, role: DeviceRole = DeviceRole.E_MULTIMEDIA):
        return self.get_default_device(DeviceType.INPUT, role)
    
    def get_default_output_device(self, role: DeviceRole = DeviceRole.E_MULTIMEDIA):
        return self.get_default_device(DeviceType.OUTPUT, role)

    def get_device(self, device_id: str) -> PyMmDevice:
        return PyMmDevice(self.iface.GetDevice(device_id))

    def register_endpoint_notification_callback(self, client: PyMmNotificationClient) -> int:
        # Returns HRESULT (0 on success). You can check or let COMError bubble up.
        return PyMmNotificationClient(self.iface.RegisterEndpointNotificationCallback(client))

    def unregister_endpoint_notification_callback(self, client: PyMmNotificationClient) -> int:
        return PyMmNotificationClient(self.iface.UnregisterEndpointNotificationCallback(client))

    # Delegate unknown attributes/methods straight to the COM object
    def __getattr__(self, name):
        return getattr(self.iface, name)
