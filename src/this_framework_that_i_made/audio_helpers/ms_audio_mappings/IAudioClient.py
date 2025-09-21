import ctypes
from ctypes import POINTER, byref, c_int, c_uint, c_uint32, c_void_p, c_longlong
import ctypes.wintypes as wt
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT

from .IAudioCaptureClient import IAudioCaptureClient, IID_IAudioCaptureClient, PyAudioCaptureClient

# AUDCLNT_SHAREMODE_EXCLUSIVE = 1

# # ======= Constants / GUIDs =======
AUDCLNT_SHAREMODE_SHARED  = 0
AUDCLNT_STREAMFLAGS_LOOPBACK     = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000  # optional
CLSCTX_INPROC_SERVER = 0x1  # TODO: move

# # REFERENCE_TIME is 100-ns units (10,000 per ms)
# HNS_PER_SEC = 10_000_000
HNS_PER_MS  = 10_000


# (enough to read the mix format)
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


class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    _fields_ = [
        ("Format",          WAVEFORMATEX),
        ("Samples_wValidBitsPerSample", ctypes.c_ushort),  # union simplified
        ("dwChannelMask",   ctypes.c_uint),
        ("SubFormat",       GUID),
    ]


IID_IAudioClient = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")


class IAudioClient(IUnknown):
    _iid_ = IID_IAudioClient
    _methods_ = [
        COMMETHOD(
            [], HRESULT, "Initialize",
            (["in"], c_int, "ShareMode"),               # AUDCLNT_SHAREMODE
            (["in"], c_uint, "StreamFlags"),
            (["in"], c_longlong, "hnsBufferDuration"),  # REFERENCE_TIME
            (["in"], c_longlong, "hnsPeriodicity"),     # REFERENCE_TIME (0 for shared/auto)
            (["in"], POINTER(WAVEFORMATEX), "pFormat"),
            (["in"], POINTER(GUID), "AudioSessionGuid")
        ),
        COMMETHOD(
            [], HRESULT, "GetBufferSize",
            (["out"], POINTER(c_uint32), "pNumBufferFrames")
        ),
        COMMETHOD(
            [], HRESULT, "GetStreamLatency",
            (["out"], POINTER(c_longlong), "phnsLatency")
        ),
        COMMETHOD(
            [], HRESULT, "GetCurrentPadding",
            (["out"], POINTER(c_uint32), "pNumPaddingFrames")
        ),
        COMMETHOD(
            [], HRESULT, "IsFormatSupported",
            (["in"], c_int, "ShareMode"),               # AUDCLNT_SHAREMODE
            (["in"], POINTER(WAVEFORMATEX), "pFormat"),
            (["out"], POINTER(POINTER(WAVEFORMATEX)), "ppClosestMatch")
        ),
        COMMETHOD(
            [], HRESULT, "GetMixFormat",
            (["out"], POINTER(POINTER(WAVEFORMATEX)), "ppDeviceFormat")
        ),
        COMMETHOD(
            [], HRESULT, "GetDevicePeriod",
            (["out"], POINTER(c_longlong), "phnsDefaultDevicePeriod"),
            (["out"], POINTER(c_longlong), "phnsMinimumDevicePeriod")
        ),
        COMMETHOD([], HRESULT, "Start"),
        COMMETHOD([], HRESULT, "Stop"),
        COMMETHOD([], HRESULT, "Reset"),
        COMMETHOD(
            [], HRESULT, "SetEventHandle",
            (["in"], wt.HANDLE, "eventHandle")
        ),
        COMMETHOD(
            [], HRESULT, "GetService",
            (["in"], POINTER(GUID), "riid"),
            (["out"], POINTER(c_void_p), "ppv")
        ),
    ]


class PyAudioClient:

    """Thin, pythonic helper around an IAudioClient COM interface."""

    def __init__(self, iaudio: IAudioClient):
        self.iface = iaudio

    # --- Introspection ---
    def get_mix_format(self) -> tuple[WAVEFORMATEX, dict]:
        """Return (fmt_ptr, info_dict). Keep fmt_ptr alive while using it."""
        pfmt: WAVEFORMATEX = self.iface.GetMixFormat()
        fmt = pfmt.contents
        info = {
            "tag": fmt.wFormatTag,
            "channels": fmt.nChannels,
            "samples_per_sec": fmt.nSamplesPerSec,
            "avg_bytes_per_sec": fmt.nAvgBytesPerSec,
            "block_align": fmt.nBlockAlign,
            "bits_per_sample": fmt.wBitsPerSample,
            "cb_size": fmt.cbSize,
            "is_extensible": fmt.wFormatTag == 0xFFFE and fmt.cbSize >= ctypes.sizeof(WAVEFORMATEXTENSIBLE) - ctypes.sizeof(WAVEFORMATEX),
        }
        # If extensible, cast and add more info
        if info["is_extensible"]:
            ext = ctypes.cast(pfmt, POINTER(WAVEFORMATEXTENSIBLE)).contents
            info.update({
                "valid_bits_per_sample": ext.Samples_wValidBitsPerSample,
                "channel_mask": ext.dwChannelMask,
                "subformat": str(ext.SubFormat),
            })
        return pfmt, info  # keep pfmt around while using its data

    def get_device_periods(self) -> dict[str, int]:
        return dict(zip(["default", "minimum"], self.iface.GetDevicePeriod()))

    # --- Init helpers ---
    def initialize_shared_loopback(
        self,
        format_ptr: WAVEFORMATEX = None,
        buffer_ms: int = 100,
        event_callback: bool = False
    ):
        """
        Shared-mode loopback initialize.
        buffer_ms ~ 100 is a safe default for pull-mode capture.
        If you plan to use event-driven capture, set event_callback=True and
        call SetEventHandle after Initialize.
        """
        if format_ptr is None:
            format_ptr, _ = self.get_mix_format()

        flags = AUDCLNT_STREAMFLAGS_LOOPBACK
        if event_callback:
            flags |= AUDCLNT_STREAMFLAGS_EVENTCALLBACK

        hnsBuffer = buffer_ms * HNS_PER_MS
        hr = self.iface.Initialize(
            AUDCLNT_SHAREMODE_SHARED,
            flags,
            hnsBuffer,
            0,                     # periodicity = 0 -> let WASAPI choose (shared)
            format_ptr,
            None
        )
        if hr != 0:
            raise OSError(f"IAudioClient.Initialize(loopback) failed, hr=0x{hr:08X}")

    def try_default_initialization(self):
        fmt, _ = self.get_mix_format()
        HNS_PER_MS = 10_000
        hr = self.iface.Initialize(0, 0, 100*HNS_PER_MS, 0, fmt, None)  # AUDCLNT_SHAREMODE_SHARED, no flags
        # S_OK or AUDCLNT_E_ALREADY_INITIALIZED are fine; we just want a session container
        print(f"{hr=}")

    # --- Service helpers ---
    def get_service(self, guid_ref):
        return self.iface.GetService(guid_ref)  # POINTER(c_void_p), "ppv"

    def get_audio_capture_client(self) -> PyAudioCaptureClient:
        fmt_ptr, _ = self.get_mix_format()              # keep this pointer alive!
        self.initialize_shared_loopback(format_ptr=fmt_ptr, buffer_ms=100, event_callback=False)

        iface = self.get_service(byref(IID_IAudioCaptureClient))
        iacc = ctypes.cast(iface, POINTER(IAudioCaptureClient))
        return PyAudioCaptureClient(iacc)

    # --- Run control ---
    def start(self):
        hr = self.iface.Start()
        if hr != 0:
            raise OSError(f"Start failed, hr=0x{hr:08X}")

    def stop(self):
        hr = self.iface.Stop()
        if hr != 0:
            raise OSError(f"Stop failed, hr=0x{hr:08X}")

    def reset(self):
        hr = self.iface.Reset()
        if hr != 0:
            raise OSError(f"Reset failed, hr=0x{hr:08X}")

    def set_event_handle(self, handle: wt.HANDLE):
        hr = self.iface.SetEventHandle(handle)
        if hr != 0:
            raise OSError(f"SetEventHandle failed, hr=0x{hr:08X}")
