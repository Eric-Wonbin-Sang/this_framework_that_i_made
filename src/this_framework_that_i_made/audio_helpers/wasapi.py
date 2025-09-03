# Windows WASAPI loopback capture as an importable module
# deps: comtypes, numpy
from __future__ import annotations
import ctypes, time, platform
import numpy as np
from ctypes import POINTER, byref, c_uint, c_void_p, cast, c_int
import comtypes
from comtypes import CLSCTX_ALL, GUID, HRESULT, COMMETHOD, IUnknown
from comtypes.client import CreateObject

try:
    import sounddevice as sd  # used for targeted WASAPI loopback by name
except Exception:  # pragma: no cover - optional at import time
    sd = None

# ---- Guard ----
if platform.system() != "Windows":
    raise OSError("audio_loopback.wasapi is Windows-only (WASAPI).")

# ---- Constants / GUIDs ----
eRender = 0
eConsole = 0
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000

CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioClient = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
IID_IPropertyStore = GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")


# ---- Minimal COM interfaces / structs (only what we use) ----
class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", ctypes.c_ushort),
        ("nChannels", ctypes.c_ushort),
        ("nSamplesPerSec", ctypes.c_uint),
        ("nAvgBytesPerSec", ctypes.c_uint),
        ("nBlockAlign", ctypes.c_ushort),
        ("wBitsPerSample", ctypes.c_ushort),
        ("cbSize", ctypes.c_ushort),
    ]


class IMMDevice(IUnknown):
    _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Activate",
                  (['in'], POINTER(GUID), 'iid'),
                  (['in'], ctypes.c_ulong, 'dwClsCtx'),
                  (['in'], c_void_p, 'pActivationParams'),
                  (['out'], POINTER(c_void_p), 'ppv')),
        COMMETHOD([], HRESULT, 'OpenPropertyStore',
                  (['in'], ctypes.c_ulong, 'stgmAccess'),
                  (['out'], POINTER(c_void_p), 'ppProperties')),
        COMMETHOD([], HRESULT, 'GetId',
                  (['out'], POINTER(ctypes.c_wchar_p), 'ppstrId')),
    ]


class IMMDeviceCollection(IUnknown):
    _iid_ = GUID('{0BD7A1BE-7A1A-44DB-8397-C0EC0BA2980D}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetCount',
                  (['out'], POINTER(c_uint), 'pcDevices')),
        COMMETHOD([], HRESULT, 'Item',
                  (['in'], c_uint, 'nDevice'),
                  (['out'], POINTER(POINTER(IMMDevice)), 'ppDevice')),
    ]


class IMMDeviceEnumerator(IUnknown):
    _iid_ = IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                  (['in'], c_int, 'dataFlow'),
                  (['in'], c_int, 'role'),
                  (['out'], POINTER(POINTER(IMMDevice)), 'ppDevice')),
        COMMETHOD([], HRESULT, 'EnumAudioEndpoints',
                  (['in'], c_int, 'dataFlow'),
                  (['in'], c_uint, 'dwStateMask'),
                  (['out'], POINTER(POINTER(IMMDeviceCollection)), 'ppDevices')),
        COMMETHOD([], HRESULT, 'GetDevice',
                  (['in'], ctypes.c_wchar_p, 'pwstrId'),
                  (['out'], POINTER(POINTER(IMMDevice)), 'ppDevice')),
    ]


class IAudioClient(IUnknown):
    _iid_ = IID_IAudioClient
    _methods_ = [
        COMMETHOD([], HRESULT, "Initialize",
                  (['in'], c_int, 'ShareMode'),
                  (['in'], c_uint, 'StreamFlags'),
                  (['in'], ctypes.c_longlong, 'hnsBufferDuration'),
                  (['in'], ctypes.c_longlong, 'hnsPeriodicity'),
                  (['in'], POINTER(WAVEFORMATEX), 'pFormat'),
                  (['in'], POINTER(GUID), 'AudioSessionGuid')),
        COMMETHOD([], HRESULT, "GetMixFormat",
                  (['out'], POINTER(POINTER(WAVEFORMATEX)), 'ppDeviceFormat')),
        COMMETHOD([], HRESULT, "GetService",
                  (['in'], POINTER(GUID), 'riid'),
                  (['out'], POINTER(c_void_p), 'ppv')),
        COMMETHOD([], HRESULT, "Start"),
        COMMETHOD([], HRESULT, "Stop"),
    ]


class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD([], HRESULT, "GetBuffer",
                  (['out'], POINTER(ctypes.c_void_p), 'ppData'),
                  (['out'], POINTER(c_uint), 'pNumFramesToRead'),
                  (['out'], POINTER(c_uint), 'pdwFlags'),
                  (['out'], POINTER(ctypes.c_longlong), 'pu64DevicePosition'),
                  (['out'], POINTER(ctypes.c_longlong), 'pu64QPCPosition')),
        COMMETHOD([], HRESULT, "ReleaseBuffer",
                  (['in'], c_uint, 'NumFramesRead')),
        COMMETHOD([], HRESULT, "GetNextPacketSize",
                  (['out'], POINTER(c_uint), 'pNumFramesInNextPacket')),
    ]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]


class PROPVARIANT(ctypes.Structure):
    class _DATA(ctypes.Union):
        _fields_ = [
            ("pwszVal", ctypes.c_wchar_p),
            ("ulVal", ctypes.c_ulong),
        ]
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("data", _DATA),
    ]


class IPropertyStore(IUnknown):
    _iid_ = IID_IPropertyStore
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetCount',
                  (['out'], POINTER(c_uint), 'cProps')),
        COMMETHOD([], HRESULT, 'GetAt',
                  (['in'], c_uint, 'iProp'),
                  (['out'], POINTER(PROPERTYKEY), 'pkey')),
        COMMETHOD([], HRESULT, 'GetValue',
                  (['in'], POINTER(PROPERTYKEY), 'key'),
                  (['out'], POINTER(PROPVARIANT), 'pv')),
    ]


STGM_READ = 0
DEVICE_STATE_ACTIVE = 0x00000001

# PKEY_Device_FriendlyName {a45c254e-df1c-4efd-8020-67d146a850e0}, 14
PKEY_Device_FriendlyName = PROPERTYKEY(
    GUID('{A45C254E-DF1C-4EFD-8020-67D146A850E0}'), 14
)


# ---- Small helpers to tolerate retval vs out-parameter COM variants ----
def _enum_audio_endpoints(enum: IMMDeviceEnumerator, data_flow: int, state_mask: int):
    # Prefer explicit out-parameter style (3 args). Fallback to retval (2 args).
    try:
        coll_ptr = POINTER(IMMDeviceCollection)()
        hr = enum.EnumAudioEndpoints(data_flow, state_mask, byref(coll_ptr))
        if hr != 0:
            raise OSError(f"EnumAudioEndpoints failed (hr=0x{hr:08x})")
        return coll_ptr
    except TypeError:
        # Some comtypes builds expose retval instead
        return enum.EnumAudioEndpoints(data_flow, state_mask)


def _collection_get_count(coll: IMMDeviceCollection) -> int:
    # Try out-parameter first, then retval fallback
    n = c_uint(0)
    try:
        hr = coll.GetCount(byref(n))
        if isinstance(hr, int) and hr != 0:
            raise OSError(f"IMMDeviceCollection.GetCount failed (hr=0x{hr:08x})")
        return int(n.value)
    except TypeError:
        return int(coll.GetCount())
    except comtypes.COMError:
        # Some builds only support retval
        return int(coll.GetCount())


def _collection_item(coll: IMMDeviceCollection, index: int):
    # Try out-parameter first, then retval
    dev = POINTER(IMMDevice)()
    try:
        hr = coll.Item(index, byref(dev))
        if isinstance(hr, int) and hr != 0:
            raise OSError(f"IMMDeviceCollection.Item({index}) failed (hr=0x{hr:08x})")
        return dev
    except TypeError:
        return coll.Item(index)
    except comtypes.COMError:
        return coll.Item(index)


def _device_open_property_store(dev: IMMDevice):
    # Try out-parameter first, then retval
    pStore = c_void_p()
    try:
        hr = dev.OpenPropertyStore(STGM_READ, byref(pStore))
        if isinstance(hr, int) and hr != 0:
            raise OSError(f"IMMDevice.OpenPropertyStore failed (hr=0x{hr:08x})")
        return pStore
    except TypeError:
        return dev.OpenPropertyStore(STGM_READ)
    except comtypes.COMError:
        return dev.OpenPropertyStore(STGM_READ)


def _store_get_value(store: IPropertyStore, pkey: PROPERTYKEY):
    # Try out-parameter first, then retval
    pv = PROPVARIANT()
    try:
        hr = store.GetValue(byref(pkey), byref(pv))
        if isinstance(hr, int) and hr != 0:
            raise OSError(f"IPropertyStore.GetValue failed (hr=0x{hr:08x})")
        return pv
    except TypeError:
        return store.GetValue(byref(pkey))
    except comtypes.COMError:
        return store.GetValue(byref(pkey))


def _open_named_loopback(device_name: str):
    enum = CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
    coll = _enum_audio_endpoints(enum, eRender, DEVICE_STATE_ACTIVE)

    count = _collection_get_count(coll)

    target_lc = device_name.strip().lower()
    chosen = POINTER(IMMDevice)()
    for i in range(count):
        dev = _collection_item(coll, i)
        if not dev:
            continue
        # Read friendly name
        pStore = _device_open_property_store(dev)
        if not pStore:
            continue
        store = cast(pStore, POINTER(IPropertyStore))
        pv = _store_get_value(store, PKEY_Device_FriendlyName)
        if pv and pv.vt == 31:  # VT_LPWSTR
            name = pv.data.pwszVal or ''
            if target_lc in name.lower():
                chosen = dev
                break

    if not chosen:
        raise ValueError(f"No WASAPI render endpoint found matching '{device_name}'")

    # Activate IAudioClient on chosen device
    pAudioClient = c_void_p()
    hr = chosen.Activate(byref(IID_IAudioClient), CLSCTX_ALL, None, byref(pAudioClient))
    if hr != 0:
        raise OSError(f"Activate(IAudioClient) failed (hr=0x{hr:08x})")
    audio_client = cast(pAudioClient, POINTER(IAudioClient))

    pwfx = POINTER(WAVEFORMATEX)()
    hr = audio_client.GetMixFormat(byref(pwfx))
    if hr != 0:
        raise OSError(f"GetMixFormat failed (hr=0x{hr:08x})")

    channels     = int(pwfx.contents.nChannels)
    samplerate   = int(pwfx.contents.nSamplesPerSec)
    bits_per_smp = int(pwfx.contents.wBitsPerSample)
    bytes_per_smp = bits_per_smp // 8

    hns = int(0.02 * 10_000_000)  # 20 ms
    hr = audio_client.Initialize(
        AUDCLNT_SHAREMODE_SHARED,
        AUDCLNT_STREAMFLAGS_LOOPBACK,
        hns, 0, pwfx, None
    )
    if hr != 0:
        raise OSError(f"IAudioClient.Initialize failed (hr=0x{hr:08x})")

    pCap = c_void_p()
    hr = audio_client.GetService(byref(IID_IAudioCaptureClient), byref(pCap))
    if hr != 0:
        raise OSError(f"GetService(IAudioCaptureClient) failed (hr=0x{hr:08x})")
    cap = cast(pCap, POINTER(IAudioCaptureClient))

    hr = audio_client.Start()
    if hr != 0:
        raise OSError(f"IAudioClient.Start failed (hr=0x{hr:08x})")

    return audio_client, cap, channels, samplerate, bytes_per_smp


# ---- Core open function ----
def _open_default_loopback():
    enum = CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
    dev = POINTER(IMMDevice)()
    hr = enum.GetDefaultAudioEndpoint(eRender, eConsole, byref(dev))
    if hr != 0:
        raise OSError(f"GetDefaultAudioEndpoint failed (hr=0x{hr:08x})")

    pAudioClient = c_void_p()
    hr = dev.Activate(byref(IID_IAudioClient), CLSCTX_ALL, None, byref(pAudioClient))
    if hr != 0:
        raise OSError(f"Activate(IAudioClient) failed (hr=0x{hr:08x})")
    audio_client = cast(pAudioClient, POINTER(IAudioClient))

    pwfx = POINTER(WAVEFORMATEX)()
    hr = audio_client.GetMixFormat(byref(pwfx))
    if hr != 0:
        raise OSError(f"GetMixFormat failed (hr=0x{hr:08x})")

    channels = int(pwfx.contents.nChannels)
    samplerate = int(pwfx.contents.nSamplesPerSec)
    bits_per_smp = int(pwfx.contents.wBitsPerSample)
    bytes_per_smp = bits_per_smp // 8

    hns = int(0.02 * 10_000_000)  # 20 ms
    hr = audio_client.Initialize(
        AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, hns, 0, pwfx, None
    )
    if hr != 0:
        raise OSError(f"IAudioClient.Initialize failed (hr=0x{hr:08x})")

    pCap = c_void_p()
    hr = audio_client.GetService(byref(IID_IAudioCaptureClient), byref(pCap))
    if hr != 0:
        raise OSError(f"GetService(IAudioCaptureClient) failed (hr=0x{hr:08x})")
    cap = cast(pCap, POINTER(IAudioCaptureClient))

    hr = audio_client.Start()
    if hr != 0:
        raise OSError(f"IAudioClient.Start failed (hr=0x{hr:08x})")

    return audio_client, cap, channels, samplerate, bytes_per_smp


def _read_default_loopback_blocks():
    """Existing default-device loopback using WASAPI COM directly (unchanged behavior)."""
    audio_client, cap, ch, fs, bps = _open_default_loopback()
    try:
        while True:
            pkt = c_uint(0)
            cap.GetNextPacketSize(byref(pkt))
            if pkt.value == 0:
                time.sleep(0.002)
                continue

            data_ptr = c_void_p()
            nframes = c_uint()
            flags = c_uint()
            devpos = ctypes.c_longlong()
            qpcpos = ctypes.c_longlong()
            cap.GetBuffer(
                byref(data_ptr),
                byref(nframes),
                byref(flags),
                byref(devpos),
                byref(qpcpos),
            )
            n = nframes.value

            byte_count = n * ch * bps
            buf = (ctypes.c_ubyte * byte_count).from_address(data_ptr.value)

            if bps == 4:  # float32 mix format
                pcm = np.frombuffer(buf, dtype=np.float32).reshape(-1, ch)
                fmt = "f32"
            else:  # assume s16
                pcm = np.frombuffer(buf, dtype=np.int16).reshape(-1, ch)
                fmt = "s16"

            yield {"fs": fs, "ch": ch, "fmt": fmt}, pcm
            cap.ReleaseBuffer(nframes.value)
    finally:
        audio_client.Stop()


def _iter_wasapi_loopback_by_name(
    device_name: str,
    block_ms: int = 20,
    samplerate: int | None = None,
    channels: int | None = None,
):
    """
    Loopback capture for a specific output endpoint using native WASAPI COM by friendly name.
    """
    audio_client, cap, ch, fs, bps = _open_named_loopback(device_name)
    try:
        while True:
            pkt = c_uint(0)
            cap.GetNextPacketSize(byref(pkt))
            if pkt.value == 0:
                time.sleep(0.002)
                continue

            data_ptr = c_void_p()
            nframes  = c_uint()
            flags    = c_uint()
            devpos   = ctypes.c_longlong()
            qpcpos   = ctypes.c_longlong()
            cap.GetBuffer(byref(data_ptr), byref(nframes), byref(flags), byref(devpos), byref(qpcpos))
            n = nframes.value

            byte_count = n * ch * bps
            buf = (ctypes.c_ubyte * byte_count).from_address(data_ptr.value)

            if bps == 4:  # float32 mix format
                pcm = np.frombuffer(buf, dtype=np.float32).reshape(-1, ch)
                fmt = "f32"
            else:         # assume s16
                pcm = np.frombuffer(buf, dtype=np.int16).reshape(-1, ch)
                fmt = "s16"

            yield {"fs": fs, "ch": ch, "fmt": fmt, "name": device_name}, pcm
            cap.ReleaseBuffer(nframes.value)
    finally:
        audio_client.Stop()


# ---- Public generator API ----
def read_loopback_blocks(
    device_name: str | None = None,
    block_ms: int = 20,
    samplerate: int | None = None,
    channels: int | None = None,
):
    """
    Yields (header: dict, pcm: np.ndarray) where pcm shape is (frames, channels).
    - Default: captures system default output via WASAPI COM.
    - If device_name is provided: captures the specified WASAPI render endpoint (loopback) using sounddevice.
    """
    if device_name:
        yield from _iter_wasapi_loopback_by_name(
            device_name, block_ms=block_ms, samplerate=samplerate, channels=channels
        )
        return
    # Fallback to default-device COM path
    yield from _read_default_loopback_blocks()


# ---- Optional: context-managed wrapper ----
class LoopbackStream:
    """Context manager + iterator for desktop audio blocks."""

    def __init__(
        self,
        device_name: str | None = None,
        block_ms: int = 20,
        samplerate: int | None = None,
        channels: int | None = None,
    ):
        self._device_name = device_name
        self._block_ms = block_ms
        self._samplerate = samplerate
        self._channels = channels

    def __enter__(self):
        self._ctx = read_loopback_blocks(
            self._device_name,
            block_ms=self._block_ms,
            samplerate=self._samplerate,
            channels=self._channels,
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        # Generator will exit on GC; nothing else required.
        return False

    def __iter__(self):
        return self._ctx
