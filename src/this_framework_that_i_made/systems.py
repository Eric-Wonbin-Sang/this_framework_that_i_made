from abc import ABC
from dataclasses import dataclass
import platform
import psutil
import socket

from .audio import AudioSystem, AudioDevice
from .generics import SavableObject, ensure_savable, staticproperty


class Directory:

    ...


class File:

    ...


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


# sessions = AudioUtilities.GetAllSessions()
# for session in sessions:
#     print(session.Process and session.Process.name(), session)


@ensure_savable
@dataclass(slots=True)
class Process:
    ...




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
    
    def get_windows_audio_devices(self, include_loopback: bool = False) -> list[AudioDevice]:
        """Return AudioDevice objects approximating Windows Sound UI.
        Keeps a device if ANY of its endpoints would appear in the Sound menu.
        """
        preferred_hostapi = "Windows WASAPI"  # TODO: make this an enum
        excluded_prefixes = ("Microsoft Sound Mapper", "Primary Sound")

        def is_loopback(name: str) -> bool:
            s = name.lower()
            return ("loop-back" in s) or ("loopback" in s)

        def endpoint_visible(ep) -> bool:
            if ep.hostapi_name != preferred_hostapi:
                return False
            if any(ep.name.startswith(p) for p in excluded_prefixes):
                return False
            if not include_loopback and is_loopback(ep.name):
                return False
            if not (ep.max_input_channels or ep.max_output_channels):
                return False
            return True

        return [
            dev for dev in self.audio_system.audio_devices
            if any(endpoint_visible(ep) for ep in dev.endpoints)
        ]


class UnixSystem(OperatingSystem):
    ...


class LinuxSystem(UnixSystem):
    ...


class ArchSystem(LinuxSystem):
    ...


class LinuxSystem(UnixSystem):
    ...
