from abc import ABC, abstractmethod
from dataclasses import dataclass, fields, is_dataclass
from typing import Any
import sounddevice
import platform
import psutil
import socket


sounddevice.default.samplerate = 48000


# move this somewhere else
class staticproperty(property):
    def __get__(self, obj, objtype=None):
        return self.fget()


class Directory:

    ...


class File:

    ...


def ensure_savable(cls):
    if not (is_dataclass(cls) or hasattr(cls, "as_dict")):
        raise TypeError(f"{cls.__name__} must be a dataclass or define as_dict()")
    # if not is_dataclass(cls) and not hasattr(cls, "from_dict"):
    #     raise TypeError(f"{cls.__name__} must define from_dict() when not a dataclass")
    return cls


class SavableObject:

    def _pretty(self, obj: Any, indent: int = 0) -> str:
        pad = " " * indent
        if is_dataclass(obj):
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
class OperatingSystem(ABC, SavableObject):

    def __init__(self):
        self.system_info = SystemInfo()
        self.cpu_info = CpuInfo()
        self.audio_devices = self._get_audio_devices()

    @classmethod
    def read(cls):
        ...

    @staticmethod
    def _get_hostname():
        ...

    @staticmethod
    def _get_audio_devices():
        return sounddevice.query_devices()

    def get_audio_device(self, target_str):
        for device in self.audio_devices:
            if target_str.lower() in device['name'].lower():
                return device
        raise RuntimeError(f"No device contains: {target_str}")

    def as_dict(self):
        return {
            "system_info": self.system_info,
            "cpu_info": self.cpu_info,
            "audio_devices": self.audio_devices,
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
