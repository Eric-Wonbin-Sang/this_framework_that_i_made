from __future__ import annotations
import ctypes, ctypes.wintypes as wt
from ctypes import POINTER, byref, sizeof, c_void_p, c_uint32, c_uint, c_ulong
import time
import threading
import comtypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from comtypes.client import CreateObject
import numpy as np

# pip install comtypes
import ctypes
from ctypes import POINTER, byref, c_uint, c_ulong, c_void_p, c_wchar_p
import comtypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from comtypes.client import CreateObject















# # --- Win32/WASAPI constants & GUIDs ------------------------------------------
# # Share mode
# AUDCLNT_SHAREMODE_SHARED = 0
# # Stream flags
# AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
# AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000  # optional
# # CLSIDs / IIDs
# CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
# IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
# IID_IAudioClient = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
# IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
# # ActivateAudioInterfaceAsync
# IID_IActivateAudioInterfaceAsyncOperation = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")

# # Process Loopback activation types (enum values per audioclientactivationparams.h)
# AUDIOCLIENT_ACTIVATION_TYPE_DEFAULT = 0
# AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1

# # --- Activation payloads for PROCESS LOOPBACK --------------------------------
# # These structs match Windows headers (audioclientactivationparams.h).
# # AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS
# class AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
#     _fields_ = [
#         ("TargetProcessId", wt.DWORD),
#         ("ProcessLoopbackMode", wt.DWORD),  # 0 = include descendants, 1 = exclude
#     ]

# # AUDIOCLIENT_ACTIVATION_PARAMS (flexible payload)
# class AUDIOCLIENT_ACTIVATION_PARAMS(ctypes.Structure):
#     _fields_ = [
#         ("ActivationType", wt.ULONG),
#         ("ActivationDataSize", wt.ULONG),
#         ("ActivationData", AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS),
#     ]

# # Minimal PROPVARIANT with VT_BLOB support
# VT_EMPTY = 0
# VT_BLOB = 0x0041

# # IActivateAudioInterfaceAsyncOperation (callback result holder)
# class IActivateAudioInterfaceAsyncOperation(IUnknown):
#     _iid_ = IID_IActivateAudioInterfaceAsyncOperation
#     _methods_ = [
#         COMMETHOD([], HRESULT, "GetActivateResult",
#                   (['out'], POINTER(HRESULT), 'activateResult'),
#                   (['out'], POINTER(c_void_p), 'activatedInterface')),
#     ]

# # Signature: ActivateAudioInterfaceAsync(LPCWSTR, REFIID, PROPVARIANT*, IActivateAudioInterfaceCompletionHandler*, IActivateAudioInterfaceAsyncOperation**)
# # We’ll call with activation params blob; no completion handler (poll via operation?); simplest is to use a helper that blocks until completion by using a handler.

# # Define a completion handler
# class IActivateAudioInterfaceCompletionHandler(IUnknown):
#     _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
#     _methods_ = [
#         COMMETHOD([], HRESULT, "ActivateCompleted",
#                   (['in'], POINTER(IActivateAudioInterfaceAsyncOperation), 'activateOperation')),
#     ]

# # A tiny handler that captures the result and signals an event
# class ActivateHandler(comtypes.CoClass):
#     _reg_clsid_ = GUID("{D5B6A08E-7E47-4F9E-8A75-96B6C09C4F01}")
#     _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler]

# class ActivateCompletedSink(comtypes.COMObject):
#     _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler]
#     def __init__(self):
#         super().__init__()
#         self.hEvent = kernel32.CreateEventW(None, True, False, None)
#         self.hres = HRESULT(0)
#         self.pIface = c_void_p(0)

#     def ActivateCompleted(self, pOp):
#         hr = HRESULT()
#         ptr = c_void_p()
#         pOp.GetActivateResult(byref(hr), byref(ptr))
#         self.hres = hr
#         self.pIface = ptr
#         kernel32.SetEvent(self.hEvent)
#         return 0

# # Load function from mmdevapi.dll
# _mmdevapi = ctypes.WinDLL("Mmdevapi.dll")
# _ActivateAudioInterfaceAsync = _mmdevapi.ActivateAudioInterfaceAsync
# # Use c_void_p for handler to avoid ctypes/comtypes pointer coercion issues
# _ActivateAudioInterfaceAsync.argtypes = [wt.LPCWSTR, POINTER(GUID), c_void_p, c_void_p, POINTER(c_void_p)]
# _ActivateAudioInterfaceAsync.restype = HRESULT

# # --- Helper: open process-loopback IAudioClient for target PID ----------------
# def open_process_loopback_iaudioclient(pid: int):
#     # Build activation params
#     plp = AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(TargetProcessId=pid, ProcessLoopbackMode=0)  # 0=include descendants
#     act = AUDIOCLIENT_ACTIVATION_PARAMS()
#     act.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
#     act.ActivationDataSize = sizeof(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS)
#     act.ActivationData = plp
#     # Get default render device ID (string) to pass as "device interface" to ActivateAudioInterfaceAsync
#     enum = comtypes.client.CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
#     eRender = 0   # eRender
#     eConsole = 0  # eConsole
#     dev = enum.GetDefaultAudioEndpoint(eRender, eConsole)
#     device_id = dev.GetId()

#     # Call ActivateAudioInterfaceAsync on an MTA thread (required by API)
#     result = {}

#     def worker():
#         try:
#             comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
#         except Exception:
#             pass
#         try:
#             sink = ActivateCompletedSink()
#             # Build PROPVARIANT VT_BLOB with activation params
#             pv = PROPVARIANT()
#             pv.vt = VT_BLOB
#             size = sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
#             buf = (ctypes.c_byte * size).from_buffer_copy(act)
#             pv.value.blob.cbSize = size
#             pv.value.blob.pBlobData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))

#             # Query an interface pointer for the handler
#             handler_iface = sink.QueryInterface(IActivateAudioInterfaceCompletionHandler)
#             pAsync = c_void_p()
#             hr = _ActivateAudioInterfaceAsync(
#                 device_id,
#                 byref(IID_IAudioClient),
#                 byref(pv),
#                 handler_iface,
#                 byref(pAsync)
#             )
#             result['call_hr'] = hr
#             if hr == 0:
#                 kernel32.WaitForSingleObject(sink.hEvent, 15000)
#                 result['sink_hr'] = sink.hres.value
#                 result['ptr'] = sink.pIface
#         except Exception as e:
#             result['exc'] = repr(e)

#     t = threading.Thread(target=worker, daemon=True)
#     t.start()
#     t.join(16)

#     call_hr = result.get('call_hr', None)
#     if call_hr is None:
#         raise OSError(f"ActivateAudioInterfaceAsync worker did not complete in time: {result.get('exc','no result')}\nDeviceId={device_id}")
#     if call_hr != 0:
#         raise OSError(f"ActivateAudioInterfaceAsync failed hr=0x{call_hr & 0xffffffff:08X}")
#     sink_hr = result.get('sink_hr', 0)
#     if sink_hr != 0:
#         raise OSError(f"Activate result hr=0x{sink_hr & 0xffffffff:08X}")

#     # Get IAudioClient*
#     pIAudioClient = ctypes.cast(result.get('ptr'), POINTER(IAudioClient))
#     return pIAudioClient

# # --- Stream reader: yields PCM blocks (bytes or numpy array) ------------------
# def read_pcm_blocks_for_pid(pid: int, frames_per_buffer: int = 4800):
#     """Yield (ts, pcm_bytes) or (ts, numpy int16/float32 array) for the target PID.

#     Falls back to PerAppLoopback if Process Loopback activation is unavailable.
#     """
#     # Try Process Loopback first
#     try:
#         ac = open_process_loopback_iaudioclient(pid)
#     except Exception:
#         # Fallback: Per-app loopback implementation (bytes). We add timestamps for parity.
#         try:
#             from .wasapi_per_app_loopback import PerAppLoopback
#         except Exception:
#             # No fallback available
#             raise
#         # Approximate chunk size in ms assuming 48k mix rate
#         chunk_ms = max(1, int(frames_per_buffer / 48))
#         with PerAppLoopback(pid=pid, include_tree=True, chunk_ms=chunk_ms) as cap:
#             for data in cap:
#                 yield time.time(), data
#         return

#     # Format = device mix format (usually 48k, 32-bit float, stereo)
#     pwfx = ac.GetMixFormat()
#     n_channels = pwfx.contents.nChannels
#     sample_rate = pwfx.contents.nSamplesPerSec
#     bits = pwfx.contents.wBitsPerSample
#     bytes_per_sample = bits // 8

#     # 100-ns units → buffer duration
#     hns_per_sec = 10_000_000
#     buf_duration = int(hns_per_sec * frames_per_buffer / sample_rate)

#     hr = ac.Initialize(
#         AUDCLNT_SHAREMODE_SHARED,
#         AUDCLNT_STREAMFLAGS_LOOPBACK,
#         buf_duration, 0, pwfx, None
#     )
#     if hr != 0:
#         raise OSError(f"IAudioClient.Initialize failed hr=0x{hr & 0xffffffff:08X}")

#     # Get capture client
#     pCap = ac.GetService(byref(IID_IAudioCaptureClient))
#     cap = ctypes.cast(pCap, POINTER(IAudioCaptureClient))

#     # Start capture
#     ac.Start()
#     try:
#         bytes_per_frame = n_channels * bytes_per_sample

#         while True:
#             # Poll for next packet
#             packet = cap.GetNextPacketSize()
#             if packet == 0:
#                 time.sleep(0.001)
#                 continue

#             # Read the packet
#             data_ptr, nframes, flags, devpos, qpcpos = cap.GetBuffer()
#             frame_count = nframes
#             nbytes = frame_count * bytes_per_frame

#             # Copy to bytes (contiguous)
#             buf = ctypes.string_at(data_ptr, nbytes)
#             cap.ReleaseBuffer(frame_count)

#             ts = time.time()

#             if np is not None and bits in (16, 32):
#                 # Assume IEEE float32 or PCM int16 depending on mix format
#                 if bits == 16:
#                     arr = np.frombuffer(buf, dtype=np.int16).reshape(-1, n_channels)
#                 else:
#                     # Most devices expose float32 mix format
#                     arr = np.frombuffer(buf, dtype=np.float32).reshape(-1, n_channels)
#                 yield ts, arr
#             else:
#                 yield ts, buf
#     finally:
#         ac.Stop()
# # kernel32 helpers (events)
# kernel32 = ctypes.windll.kernel32
# kernel32.CreateEventW.argtypes = [c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
# kernel32.CreateEventW.restype = wt.HANDLE
# kernel32.SetEvent.argtypes = [wt.HANDLE]
# kernel32.SetEvent.restype = wt.BOOL
# kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
# kernel32.WaitForSingleObject.restype = wt.DWORD


def read_pcm_blocks_for_pid(pid: int, frames_per_buffer: int = 4800):
    raise Exception('not implemented')

# ===== Core Audio GUIDs =====
CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator  = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")

# Optional: IAudioClient IID so IMMDevice->Activate can give you one
IID_IAudioClient         = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")

# ===== Enums =====
# EDataFlow
eRender = 0
eCapture = 1
eAll = 2

# ERole
eConsole = 0
eMultimedia = 1
eCommunications = 2

# DEVICE_STATE_*
DEVICE_STATE_ACTIVE = 0x00000001

# STGM
STGM_READ = 0x00000000

# ===== PROPKEY / PROPVARIANT helpers (for friendly name) =====
# # PROPERTYKEY struct
# class PROPERTYKEY(ctypes.Structure):
#     _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]

# Common property key: PKEY_Device_FriendlyName
# {a45c254e-df1c-4efd-8020-67d146a850e0}, pid 14
# PKEY_Device_FriendlyName = PROPERTYKEY(
#     GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"),
#     14
# )

VARTYPE = ctypes.c_ushort
VT_LPWSTR = 31


# ===== Utilities =====

def get_device_friendly_name(dev: IMMDevice) -> str:
    """Read PKEY_Device_FriendlyName via IPropertyStore."""
    prop_store = POINTER(IPropertyStore)()
    hr = dev.OpenPropertyStore(STGM_READ, byref(prop_store))
    if hr != 0:
        return "<unknown>"

    pv = PROPVARIANT()
    hr = prop_store.GetValue(byref(PKEY_Device_FriendlyName), byref(pv))
    if hr != 0:
        return "<unknown>"

    # Expect VT_LPWSTR
    if pv.vt == VT_LPWSTR and pv._union.pwszVal:
        return pv._union.pwszVal
    return "<unknown>"


def get_default_render_device() -> IMMDevice:
    """Create the MMDeviceEnumerator and fetch the default render (speaker) endpoint."""
    # CreateObject will call CoCreateInstance under the hood (and CoInitialize if needed)
    enum = CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
    dev_ptr = POINTER(IMMDevice)()
    hr = enum.GetDefaultAudioEndpoint(eRender, eConsole, byref(dev_ptr))
    if hr != 0:
        raise OSError(f"GetDefaultAudioEndpoint failed, HRESULT=0x{hr:08X}")
    return dev_ptr


def demo():
    dev = get_default_render_device()

    # Device state
    state = c_ulong()
    hr = dev.GetState(byref(state))
    if hr != 0:
        raise OSError(f"GetState failed, HRESULT=0x{hr:08X}")
    print("Device state:", hex(state.value))

    # Device ID (string)
    dev_id = c_wchar_p()
    hr = dev.GetId(byref(dev_id))
    if hr != 0:
        raise OSError(f"GetId failed, HRESULT=0x{hr:08X}")
    print("Device ID:", dev_id.value)

    # Friendly name via property store
    print("Friendly name:", get_device_friendly_name(dev))

    # (Optional) Activate IAudioClient to prepare for capture code later
    # CLSCTX_INPROC_SERVER = 0x1
    CLSCTX_INPROC_SERVER = 0x1
    p_iaudioclient = c_void_p()
    hr = dev.Activate(byref(IID_IAudioClient), CLSCTX_INPROC_SERVER, None, byref(p_iaudioclient))
    if hr != 0:
        raise OSError(f"Activate(IAudioClient) failed, HRESULT=0x{hr:08X}")
    # Cast to a typed interface if you fleshed it out:
    iaudioclient = ctypes.cast(p_iaudioclient, POINTER(IAudioClient))
    print("Got IAudioClient pointer:", iaudioclient)


if __name__ == "__main__":
    demo()
