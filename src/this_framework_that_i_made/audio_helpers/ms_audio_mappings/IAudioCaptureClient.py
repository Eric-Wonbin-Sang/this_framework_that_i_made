import ctypes
from ctypes import POINTER, byref, c_int, c_uint, c_uint32, c_void_p, c_longlong
import ctypes.wintypes as wt
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT


IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")


class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD([], HRESULT, "GetBuffer",
                  (["out"], POINTER(POINTER(ctypes.c_ubyte)), "ppData"),
                  (["out"], POINTER(c_uint32), "pNumFramesToRead"),
                  (["out"], POINTER(c_uint), "pdwFlags"),
                  (["out"], POINTER(ctypes.c_uint64), "pu64DevicePosition"),
                  (["out"], POINTER(ctypes.c_uint64), "pu64QPCPosition")),
        COMMETHOD([], HRESULT, "ReleaseBuffer",
                  (["in"], c_uint32, "NumFramesRead")),
        COMMETHOD([], HRESULT, "GetNextPacketSize",
                  (["out"], POINTER(c_uint32), "pNumFramesInNextPacket")),
    ]


class PyAudioCaptureClient:

    def __init__(self, iface):
        self.iface = iface

    def get_buffer(self):
        return dict(zip(
            [
                "pp_data",                # (POINTER(ctypes.c_ubyte))
                "pnum_frames_to_read",    # (c_uint32)
                "pdw_flags",              # (c_uint)
                "p_u64_device_position",  # (ctypes.c_uint64)
                "p_u64_qpc_position",     # (ctypes.c_uint64)
            ],
            self.iface.GetBuffer()
        ))

    def release_buffer(self, NumFramesRead: c_uint32):
        return self.iface.ReleaseBuffer(NumFramesRead)

    def get_next_packet_size(self) -> c_uint32:
        return self.iface.GetNextPacketSize()  # pNumFramesInNextPacket
