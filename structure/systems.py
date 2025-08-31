from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, fields, is_dataclass
from functools import cached_property, lru_cache
from typing import Any, List
import sounddevice
import platform
import psutil
import socket


sounddevice.default.samplerate = 48000


# TODO: move this somewhere else
class staticproperty(property):
    def __get__(self, obj, objtype=None):
        return self.fget()


# TODO: move this somewhere else
def group_by_name(objects):
    groups = defaultdict(list)
    for obj in objects:
        groups[obj.name].append(obj)
    return groups


class Directory:

    ...


class File:

    ...


def _is_self_dataclass_class(cls) -> bool:
    """True if `cls` is decorated with @dataclass itself (not just inheriting)."""
    return (
        is_dataclass(cls)
        and ("__dataclass_fields__" in cls.__dict__ or "__dataclass_params__" in cls.__dict__)
    )


def ensure_savable(cls):
    """Validate that a class is a dataclass (itself) or defines as_dict()."""
    if not (_is_self_dataclass_class(cls) or hasattr(cls, "as_dict")):
        raise TypeError(f"{cls.__name__} must be a dataclass or define as_dict()")
    return cls


class SavableObject:

    def _pretty(self, obj: Any, indent: int = 0) -> str:
        pad = " " * indent
        # Only treat as dataclass if the object's class is itself a dataclass
        if is_dataclass(obj) and _is_self_dataclass_class(type(obj)):
            # Pretty print nested dataclasses too
            cls = obj.__class__.__name__
            inner = []
            for f in fields(obj):
                v = getattr(obj, f.name)
                inner.append(f"{pad}  {f.name} = {self._pretty(v, indent + 2)}")
            return f"{cls}(\n" + ",\n".join(inner) + f"\n{pad})"
        elif isinstance(obj, (list, tuple, set)):
            open_, close_ = ("[", "]") if isinstance(obj, list) else ("(", ")") if isinstance(obj, tuple) else ("{", "}")
            if not obj:
                return f"{open_}{close_}"
            items = [self._pretty(v, indent + 2) for v in obj]
            inner = ",\n".join((" " * (indent + 2)) + s for s in items)
            return f"{open_}\n{inner}\n{pad}{close_}"
        elif isinstance(obj, dict):
            if not obj:
                return "{}"
            inner = []
            for k, v in obj.items():
                inner.append(f"{pad}  {k!r}: {self._pretty(v, indent + 2)}")
            return "{\n" + ",\n".join(inner) + f"\n{pad}}}"
        elif isinstance(obj, SavableObject) and hasattr(obj, 'as_dict') and callable(getattr(obj, 'as_dict', None)):
            d = obj.as_dict()
            inner = []
            for k, v in d.items():
                inner.append(f"{pad}  {k} = {self._pretty(v, indent + 2)}")
            return f"{obj.__class__.__name__}(\n" + ",\n".join(inner) + f"\n{pad})"
        else:
            # Fallback scalar formatting
            return repr(obj)

    def __str__(self) -> str:
        # Assumes self is a dataclass
        return self._pretty(self, 0)


@ensure_savable
@dataclass(slots=True)
class RuntimeEnv(SavableObject):
    python_version: str = platform.python_build()


@ensure_savable
@dataclass(slots=True)
class SystemInfo(SavableObject):
    system: str = platform.system()        # 'Windows', 'Linux', 'Darwin'
    release: str = platform.release()      # e.g., '10', '5.15.0-78-generic'
    version: str = platform.version()
    machine: str = platform.machine()      # 'x86_64', 'AMD64', 'arm64'
    processor: str = platform.processor()
    hostname: str = socket.gethostname()


@ensure_savable
@dataclass(slots=True)
class CoreInfo(SavableObject):

    index: str
    min_frequency: int
    max_frequency: int

    def get_psutil_data(self):
        return psutil.cpu_freq(percpu=True)[self.index]

    def get_curr_frequency(self):  # in MHz
        return self.get_psutil_data().current

    def __str__(self):
        return f"Core {self.index}: (min {self.min_frequency}, max {self.max_frequency})"


@ensure_savable
@dataclass(slots=True)
class CpuInfo(SavableObject):

    """ This gives overall CPU usage (beware machines with multiple CPUs) """

    physical_cores: str = psutil.cpu_count(logical=False)
    total_cores: str = psutil.cpu_count(logical=True)
    frequency_mhz: str = psutil.cpu_freq().current if psutil.cpu_freq() else None

    @staticmethod
    def _get_core_info():
        freqs = psutil.cpu_freq(percpu=True)
        return [
            CoreInfo(
                index=i,
                min_frequency=f.min,
                max_frequency=f.max,
            )
            for i, f in enumerate(freqs)
        ]
    
    @staticproperty
    def curr_usage():
        return psutil.cpu_percent()


@ensure_savable
@dataclass(slots=True)
class AudioEndpoint(SavableObject):

    """
    Each physical interface (like your Audient EVO8) exposes multiple endpoints to Windows/PortAudio:
    - Different input jacks (mic, line-in, loopback, etc.)
    - Different output jacks (headphones, speakers, loopback)
    - Sometimes Windows duplicates them as WDM/DirectSound/WASAPI devices.
    
    PortAudio doesn't collapse them — it lists each separately so you can choose exactly what stream you want.
    
    """

    name: str                          
    index: str                        # Device index (used when opening streams)
    hostapi: str                      # Which host API (WASAPI, DirectSound, ASIO, etc.)
    hostapi_name: str                 # need to get the hostapi name via sounddevice.query_hostapis()
    max_input_channels: str           # How many input channels (mic, line-in, etc.)
    max_output_channels: str          # How many output channels (0 means input-only device)
    default_low_input_latency: str    # Suggested low-latency buffer (seconds)
    default_low_output_latency: str  
    default_high_input_latency: str   # Suggested high-latency buffer (seconds)
    default_high_output_latency: str
    default_samplerate: str           # Default sample rate (Hz)


@ensure_savable
@dataclass
class AudioDevice(SavableObject):
    endpoints: List[AudioEndpoint]


@ensure_savable
@dataclass(slots=True)
class AudioInputDevice(AudioDevice):
    ...


@ensure_savable
@dataclass(slots=True)
class AudioOutputDevice(AudioDevice):
    ...


@ensure_savable
class AudioSystem(AudioDevice):

    """
    In PortAudio (which sounddevice wraps), a host API is the underlying audio backend that PortAudio uses to talk to the system.

    Each operating system exposes different backends, so the list depends on your platform.

    Common host APIs by OS
    - Windows
        - MME (old, high-latency, but always available)
        - DirectSound
        - WASAPI (modern Windows audio, low latency, supports loopback)
        - ASIO (pro audio, needs special driver, lowest latency)
    - macOS
        - Core Audio (the only real one, very good quality/latency)
    - Linux
        - ALSA (standard)
        - JACK (pro audio, low latency, routing between apps)
        - OSS (legacy)

    Cross-platform perspective
        - sounddevice/PortAudio makes the API consistent, but the host APIs you see differ per OS.
        - Example: "WASAPI" only exists on Windows; "Core Audio" only exists on macOS.
        - Some names may be present but not functional (e.g. JACK if not installed).
    
    """

    ALL_HOST_APIS = sounddevice.query_hostapis()

    @classmethod
    @lru_cache(maxsize=1)
    def available_hostapis(cls):
        return tuple(t['name'] for t in cls.ALL_HOST_APIS)

    def __init__(self):
        self.audio_devices: List[AudioDevice] = self._get_audio_devices()
    
    @classmethod
    def _get_audio_endpoints(cls):
        return [
            AudioEndpoint(
                hostapi_name=cls.available_hostapis()[data["hostapi"]],
                **data,
            )
            for data in sounddevice.query_devices()
        ]

    @classmethod
    def _get_audio_devices(cls):
        return [
            AudioDevice(endpoints=endpoints)
            for endpoints in group_by_name(cls._get_audio_endpoints()).values()
        ]

    def as_dict(self):
        return {
            "audio_devices": self.audio_devices,
        }


@ensure_savable
class OperatingSystem(ABC, SavableObject):

    def __init__(self):
        self.system_info: SystemInfo = SystemInfo()
        self.cpu_info: CpuInfo = CpuInfo()
        self.audio_system: AudioSystem = AudioSystem()

    @classmethod
    def read(cls):
        ...

    def as_dict(self):
        return {
            "system_info": self.system_info,
            "cpu_info": self.cpu_info,
            "audio_system": self.audio_system,
        }


class WindowsSystem(OperatingSystem):
    ...


class UnixSystem(OperatingSystem):
    ...


class LinuxSystem(UnixSystem):
    ...


class ArchSystem(LinuxSystem):
    ...


class LinuxSystem(UnixSystem):
    ...


def main():
    system = OperatingSystem()
    print(system)


if __name__ == "__main__":
    main()
