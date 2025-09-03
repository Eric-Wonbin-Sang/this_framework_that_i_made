# Windows per-application audio capture (WASAPI Process Loopback) in Python
# deps: comtypes, numpy
# Tested on Windows 11; requires Windows 10+ with Process Loopback support.
from __future__ import annotations
import ctypes, platform
import numpy as np
from ctypes import POINTER, byref, c_uint, c_void_p, c_int, wintypes
import comtypes
from comtypes import IUnknown, GUID, HRESULT, COMMETHOD, STDMETHOD, HRESULT
from comtypes.client import CreateObject

if platform.system() != "Windows":
    raise OSError("per_app_loopback is Windows-only (WASAPI Process Loopback).")

# ---- Win32 helpers ----
kernel32 = ctypes.windll.kernel32
ole32 = ctypes.windll.ole32
hns_per_ms = 10_000  # 100-ns units (1 ms = 10,000 * 100ns)

def _ok(hr):
    if hr != 0:
        raise OSError(f"HRESULT 0x{hr & 0xFFFFFFFF:08X}")
    return hr

def _create_event():
    return kernel32.CreateEventW(None, True, False, None)

def _wait_event(h, ms):
    return kernel32.WaitForSingleObject(h, ms)

# Robustly obtain a string from IMMDevice.GetId, handling varying comtypes behaviors
def _get_device_id_str(dev: "IMMDevice") -> str:
    try:
        rid = dev.GetId()
    except Exception:
        # Re-raise to surface the COM error upstream
        raise
    # comtypes may return a tuple for [out] params
    if isinstance(rid, tuple):
        rid = rid[0]
    # If we somehow received a raw pointer integer, read the wide string
    if isinstance(rid, int):
        s = ctypes.wstring_at(rid)
        try:
            ole32.CoTaskMemFree(ctypes.c_void_p(rid))
        except Exception:
            pass
        return s
    # If we got a c_wchar_p, extract value
    if isinstance(rid, ctypes.c_wchar_p):
        return rid.value
    # Otherwise assume it's already a Python string
    return rid

# ---- Core Audio GUIDs ----
CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator  = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IMMDevice            = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")

IID_IAudioClient         = GUID("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
IID_IAudioCaptureClient  = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")

# ActivateAudioInterfaceAsync
IID_IActivateAudioInterfaceAsyncOperation = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
IID_IActivateAudioInterfaceCompletionHandler = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")

# AudioClient Activation Params (Process Loopback)
AUDIOCLIENT_ACTIVATION_TYPE_DEFAULT          = 0
AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1  # <- per-process capture

# Process loopback modes
PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0
PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE = 1

# Stream flags
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK      = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000

# Data flow/role (we still need a default render endpoint to hang params off)
eRender = 0
eConsole = 0

# ---- WAVEFORMATEX ----
class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag",      ctypes.c_ushort),
        ("nChannels",       ctypes.c_ushort),
        ("nSamplesPerSec",  ctypes.c_uint),
        ("nAvgBytesPerSec", ctypes.c_uint),
        ("nBlockAlign",     ctypes.c_ushort),
        ("wBitsPerSample",  ctypes.c_ushort),
        ("cbSize",          ctypes.c_ushort),
    ]

# ---- PROPVARIANT (minimal) ----
# We need to pass activation params via PROPVARIANT (VT_BLOB).
VT_EMPTY = 0
VT_BLOB  = 0x41

class BLOB(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("pBlobData", ctypes.POINTER(ctypes.c_byte))
    ]

class PROPVARIANT(ctypes.Structure):
    class _Value(ctypes.Union):
        _fields_ = [
            ("blob", BLOB),
        ]
    _anonymous_ = ("value",)
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ubyte),
        ("wReserved2", ctypes.c_ubyte),
        ("wReserved3", ctypes.c_ulong),
        ("value", _Value),
    ]

# ---- AudioClient activation structs (packed as in audioclientactivationparams.h) ----
# AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS
class AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
    _fields_ = [
        ("TargetProcessId", wintypes.DWORD),
        ("ProcessLoopbackMode", wintypes.DWORD),  # include/exclude tree
    ]

# AUDIOCLIENT_ACTIVATION_PARAMS (variable size, we use version 1)
class AUDIOCLIENT_ACTIVATION_PARAMS(ctypes.Structure):
    _fields_ = [
        ("ActivationType", wintypes.DWORD),
        ("ProcessLoopbackParams", AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS),
    ]

# ---- COM interface defs ----
class IMMDevice(IUnknown):
    _iid_ = IID_IMMDevice
    _methods_ = [
        COMMETHOD([], HRESULT, "Activate",
                  (['in'], POINTER(GUID), 'riid'),
                  (['in'], ctypes.c_ulong, 'dwClsCtx'),
                  (['in'], c_void_p, 'pActivationParams'),
                  (['out'], POINTER(c_void_p), 'ppInterface')),
        COMMETHOD([], HRESULT, "OpenPropertyStore",
                  (['in'], ctypes.c_ulong, 'stgmAccess'),
                  (['out'], POINTER(c_void_p), 'ppProperties')),
        COMMETHOD([], HRESULT, "GetId",
                  (['out'], POINTER(wintypes.LPWSTR), 'ppstrId')),
        COMMETHOD([], HRESULT, "GetState",
                  (['out'], POINTER(c_uint), 'pdwState')),
    ]

class IMMDeviceEnumerator(IUnknown):
    _iid_ = IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumAudioEndpoints",
                  (['in'], ctypes.c_int, 'dataFlow'),
                  (['in'], ctypes.c_uint, 'dwStateMask'),
                  (['out'], POINTER(POINTER(IUnknown)), 'ppDevices')),
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                  (['in'], ctypes.c_int, 'dataFlow'),
                  (['in'], ctypes.c_int, 'role'),
                  (['out'], POINTER(POINTER(IMMDevice)), 'ppEndpoint')),
        COMMETHOD([], HRESULT, "GetDevice",
                  (['in'], ctypes.c_wchar_p, 'pwstrId'),
                  (['out'], POINTER(POINTER(IMMDevice)), 'ppDevice')),
        COMMETHOD([], HRESULT, "RegisterEndpointNotificationCallback",
                  (['in'], c_void_p, 'pClient')),
        COMMETHOD([], HRESULT, "UnregisterEndpointNotificationCallback",
                  (['in'], c_void_p, 'pClient')),
    ]

class IAudioClient(IUnknown):
    _iid_ = IID_IAudioClient
    _methods_ = [
        COMMETHOD([], HRESULT, "Initialize",
                  (['in'], ctypes.c_int, 'ShareMode'),
                  (['in'], ctypes.c_uint, 'StreamFlags'),
                  (['in'], ctypes.c_longlong, 'hnsBufferDuration'),
                  (['in'], ctypes.c_longlong, 'hnsPeriodicity'),
                  (['in'], POINTER(WAVEFORMATEX), 'pFormat'),
                  (['in'], POINTER(GUID), 'AudioSessionGuid')),
        COMMETHOD([], HRESULT, "GetBufferSize",
                  (['out'], POINTER(c_uint), 'pNumBufferFrames')),
        COMMETHOD([], HRESULT, "GetStreamLatency",
                  (['out'], POINTER(ctypes.c_longlong), 'phnsLatency')),
        COMMETHOD([], HRESULT, "GetCurrentPadding",
                  (['out'], POINTER(c_uint), 'pNumPaddingFrames')),
        COMMETHOD([], HRESULT, "IsFormatSupported",
                  (['in'], ctypes.c_int, 'ShareMode'),
                  (['in'], POINTER(WAVEFORMATEX), 'pFormat'),
                  (['out'], POINTER(POINTER(WAVEFORMATEX)), 'ppClosestMatch')),
        COMMETHOD([], HRESULT, "GetMixFormat",
                  (['out'], POINTER(POINTER(WAVEFORMATEX)), 'ppDeviceFormat')),
        COMMETHOD([], HRESULT, "GetDevicePeriod",
                  (['out'], POINTER(ctypes.c_longlong), 'phnsDefaultDevicePeriod'),
                  (['out'], POINTER(ctypes.c_longlong), 'phnsMinimumDevicePeriod')),
        COMMETHOD([], HRESULT, "Start"),
        COMMETHOD([], HRESULT, "Stop"),
        COMMETHOD([], HRESULT, "Reset"),
        COMMETHOD([], HRESULT, "SetEventHandle",
                  (['in'], ctypes.c_void_p, 'eventHandle')),
        COMMETHOD([], HRESULT, "GetService",
                  (['in'], POINTER(GUID), 'riid'),
                  (['out'], POINTER(c_void_p), 'ppv')),
    ]

class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD([], HRESULT, "GetBuffer",
                  (['out'], POINTER(POINTER(ctypes.c_byte)), 'ppData'),
                  (['out'], POINTER(c_uint), 'pNumFramesToRead'),
                  (['out'], POINTER(c_uint), 'pdwFlags'),
                  (['out'], POINTER(c_uint), 'pu64DevicePosition'),
                  (['out'], POINTER(c_uint), 'pu64QPCPosition')),
        COMMETHOD([], HRESULT, "ReleaseBuffer",
                  (['in'], c_uint, 'NumFramesRead')),
        COMMETHOD([], HRESULT, "GetNextPacketSize",
                  (['out'], POINTER(c_uint), 'pNumFramesInNextPacket')),
    ]

# ActivateAudioInterfaceAsync types
class IActivateAudioInterfaceAsyncOperation(IUnknown):
    _iid_ = IID_IActivateAudioInterfaceAsyncOperation
    _methods_ = [
        COMMETHOD([], HRESULT, "GetActivateResult",
                  (['out'], POINTER(HRESULT), 'activateResult'),
                  (['out'], POINTER(c_void_p), 'activatedInterface')),
    ]

class IActivateAudioInterfaceCompletionHandler(IUnknown):
    _iid_ = IID_IActivateAudioInterfaceCompletionHandler
    _methods_ = [
        COMMETHOD([], HRESULT, "ActivateCompleted",
                  (['in'], POINTER(IActivateAudioInterfaceAsyncOperation), 'activateOperation')),
    ]

# COM class for the completion handler
class ActivateHandler(comtypes.COMObject):
    _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler]

    def __init__(self, event_handle):
        super().__init__()
        self._event = event_handle
        self.hr = HRESULT(0)
        self.punk = c_void_p()

    def ActivateCompleted(self, operation):
        hr = HRESULT()
        punk = c_void_p()
        operation.GetActivateResult(byref(hr), byref(punk))
        self.hr = hr
        self.punk = punk
        kernel32.SetEvent(self._event)
        return 0  # S_OK

# Signature of ActivateAudioInterfaceAsync (from mmdeviceapi)
# HRESULT ActivateAudioInterfaceAsync(
#   LPCWSTR deviceInterfacePath,
#   REFIID riid,
#   PROPVARIANT *activationParams,
#   IActivateAudioInterfaceCompletionHandler *completionHandler,
#   IActivateAudioInterfaceAsyncOperation **operation);
# ActivateAudioInterfaceAsync = ctypes.WINFUNCTYPE(
#     HRESULT,
#     wintypes.LPCWSTR,
#     POINTER(GUID),
#     POINTER(PROPVARIANT),
#     POINTER(IActivateAudioInterfaceCompletionHandler),
#     POINTER(POINTER(IActivateAudioInterfaceAsyncOperation)),
# )("ActivateAudioInterfaceAsync", ctypes.WinDLL("Mmdevapi").ActivateAudioInterfaceAsync)
# Prototype
prototype = ctypes.WINFUNCTYPE(
    HRESULT,
    wintypes.LPCWSTR,                                    # deviceInterfacePath
    ctypes.POINTER(GUID),                                # riid
    ctypes.POINTER(PROPVARIANT),                         # activationParams
    ctypes.POINTER(IActivateAudioInterfaceCompletionHandler),  # completionHandler
    ctypes.POINTER(ctypes.POINTER(IActivateAudioInterfaceAsyncOperation))  # operation**
)

# Bind to the function exported by Mmdevapi.dll
_mmdevapi = ctypes.windll.Mmdevapi
ActivateAudioInterfaceAsync = prototype(("ActivateAudioInterfaceAsync", _mmdevapi))

# ---- Our high-level capture class (per PID) ----
class PerAppLoopback:
    """
    Capture only the audio of a specific process (by PID), using WASAPI Process Loopback.
    Iterates PCM int16 chunks (~chunk_ms each).
    """
    def __init__(self, pid: int, include_tree: bool = True, chunk_ms: int = 10):
        self.pid = int(pid)
        self.include_tree = bool(include_tree)
        self.chunk_ms = max(1, int(chunk_ms))
        self.sample_rate = None
        self.channels = None
        self._client = None
        self._cap = None
        self._event = None

    def __enter__(self):
        # 1) Build activation params blob
        alp = AUDIOCLIENT_ACTIVATION_PARAMS()
        alp.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
        alp.ProcessLoopbackParams.TargetProcessId = self.pid
        alp.ProcessLoopbackParams.ProcessLoopbackMode = (
            PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE if self.include_tree
            else PROCESS_LOOPBACK_MODE_EXCLUDE_TARGET_PROCESS_TREE
        )

        blob_size = ctypes.sizeof(alp)
        buf = (ctypes.c_byte * blob_size).from_buffer_copy(alp)

        prop = PROPVARIANT()
        prop.vt = VT_BLOB
        prop.value.blob.cbSize = blob_size
        prop.value.blob.pBlobData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))

        # 2) We still need a device interface string; default render endpoint is fine
        enum = CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
        # comtypes converts [out] parameters to return values. Do not pass byref here.
        dev = enum.GetDefaultAudioEndpoint(eRender, eConsole)

        # Retrieve device interface path (string) directly
        device_interface_path = _get_device_id_str(dev)

        # 3) Async activation to get IAudioClient configured for process loopback
        completed = _create_event()
        handler = ActivateHandler(completed)
        op = POINTER(IActivateAudioInterfaceAsyncOperation)()

        _ok(ActivateAudioInterfaceAsync(
            device_interface_path,
            byref(IID_IAudioClient),
            byref(prop),
            handler,  # COM object
            byref(op)
        ))

        # Wait for callback
        _wait_event(completed, 5000)  # 5s
        _ok(handler.hr.value)

        # Get IAudioClient*
        pclient = handler.punk
        self._client = ctypes.cast(pclient, POINTER(IAudioClient))

        # 4) Get mix format and configure capture
        # GetMixFormat returns a POINTER(WAVEFORMATEX)
        ppwf = self._client.GetMixFormat()
        wf = ppwf.contents
        self.sample_rate = int(wf.nSamplesPerSec)
        self.channels = int(wf.nChannels)

        buffer_hns = 100 * hns_per_ms  # ~100 ms overall buffer
        self._client.Initialize(
            AUDCLNT_SHAREMODE_SHARED,
            AUDCLNT_STREAMFLAGS_EVENTCALLBACK,
            buffer_hns,
            0,
            ppwf,
            None
        )

        # Event-driven capture: set event handle after Initialize
        self._event = _create_event()
        self._client.SetEventHandle(self._event)

        # 5) Get capture client & start
        pcap = c_void_p()
        self._client.GetService(byref(IID_IAudioCaptureClient), byref(pcap))
        self._cap = ctypes.cast(pcap, POINTER(IAudioCaptureClient))
        self._client.Start()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._client:
                self._client.Stop()
        finally:
            self._cap = None
            self._client = None

    def __iter__(self):
        """
        Yields interleaved s16le PCM bytes (~chunk_ms each when data is available).
        """
        target_frames = max(1, (self.sample_rate * self.chunk_ms) // 1000)

        while True:
            _wait_event(self._event, self.chunk_ms * 2)
            frames_accum = 0
            out = bytearray()

            next_frames = self._cap.GetNextPacketSize()
            while next_frames > 0:
                # GetBuffer returns (ppData, pNumFramesToRead, pdwFlags, pu64DevicePosition, pu64QPCPosition)
                ppData, nFrames, flags, devpos, qpcpos = self._cap.GetBuffer()
                nf = int(nFrames)

                # The loopback mix format on modern Windows is typically float32
                # Convert to int16 for convenience. Keep float32 if you prefer.
                fptr = ctypes.cast(ppData, ctypes.POINTER(ctypes.c_float))
                nsamp = nf * self.channels
                arr = np.ctypeslib.as_array(fptr, shape=(nsamp,)).astype(np.float32)
                pcm16 = np.clip(arr, -1.0, 1.0)
                pcm16 = (pcm16 * 32767.0).astype(np.int16)
                out.extend(pcm16.tobytes())

                self._cap.ReleaseBuffer(nf)
                frames_accum += nf
                next_frames = self._cap.GetNextPacketSize()

            if frames_accum:
                yield bytes(out)
            else:
                # No frames; continue. You could yield silence for fixed pacing if needed.
                continue
