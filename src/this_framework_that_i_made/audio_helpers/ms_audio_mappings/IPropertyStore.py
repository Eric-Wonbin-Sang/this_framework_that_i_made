from typing import List
from comtypes import IUnknown, COMMETHOD, HRESULT
from ctypes import POINTER, c_ulong
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT

from .ms_audio_common import PROPERTYKEY, PROPVARIANT


IID_IPropertyStore = GUID("{886d8eeb-8cf2-4446-8d02-cdba1dbdcf99}")


class IPropertyStore(IUnknown):

    """

    https://learn.microsoft.com/en-us/windows/win32/api/propsys/nn-propsys-ipropertystore
    
    """

    _iid_ = IID_IPropertyStore
    _methods_ = [
        COMMETHOD(
            [], HRESULT, "GetCount",
            (["out"], POINTER(c_ulong), "cProps")
        ),
        COMMETHOD(
            [], HRESULT, "GetAt",
            (["in"], c_ulong, "iProp"),
            (["out"], POINTER(PROPERTYKEY), "pkey")
        ),
        COMMETHOD(
            [], HRESULT, "GetValue",
            (["in"], POINTER(PROPERTYKEY), "key"),
            (["out"], POINTER(PROPVARIANT), "pv")
        ),
        COMMETHOD(
            [], HRESULT, "SetValue",
            (["in"], POINTER(PROPERTYKEY), "key"),
            (["in"], POINTER(PROPVARIANT), "pv")
        ),
        COMMETHOD([], HRESULT, "Commit"),
    ]


class PyPropertyStore:

    def __init__(self, iface):
        self.iface = iface

    def get_count(self) -> c_ulong:
        return self.iface.GetCount()  # POINTER(c_ulong) "cProps"

    def get_at(self, i_prop: c_ulong) -> PROPERTYKEY:
        return self.iface.GetAt(i_prop)  # POINTER(PROPERTYKEY) "cPpkeyrops"

    def get_value(self, key: PROPERTYKEY) -> PROPVARIANT:
        return self.iface.GetValue(key)  # POINTER(PROPVARIANT) "pv"

    def set_value(self, key: PROPERTYKEY, pv: PROPVARIANT):
        self.iface.SetValue(key, pv)

    def commit(self):
        self.iface.Commit()

    def get_keys(self) -> List[PROPVARIANT]:
        return [self.get_at(i) for i in range(self.get_count())]

    def as_dict(self) -> List[PROPVARIANT]:
        return {p_var: self.get_value(p_var).to_python() for p_var in self.get_keys()}
