from typing import List
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_uint

from .IMMDevice import IMMDevice, PyMmDevice


IID_IMMDeviceCollection = GUID("{0BD7A1BE-7A1A-44DB-8397-C0F926C3998C}")


# Forward decl to avoid circular ref in signature
class IMMDeviceCollection(IUnknown):
    _iid_ = IID_IMMDeviceCollection
    _methods_ = [
        COMMETHOD(
            [], HRESULT, "GetCount",
            (["out"], POINTER(c_uint), "pcDevices")
        ),
        COMMETHOD(
            [], HRESULT, "Item",
            (["in"], c_uint, "nDevice"),
            (["out"], POINTER(POINTER(IMMDevice)), "ppDevice")
        ),
    ]


class PyMmDeviceCollection:

    def __init__(self, iface):
        self.iface = iface
    
    def get_count(self) -> int:
        return self.iface.GetCount()  # pcDevices

    def get_item(self, n_device: c_uint) -> PyMmDevice:
        return PyMmDevice(self.iface.Item(n_device))  # ppDevice

    def get_items(self) -> List[PyMmDevice]:
        return [self.get_item(i) for i in range(self.get_count())]
