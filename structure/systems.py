from abc import ABC, abstractmethod
from dataclasses import dataclass
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


@dataclass(slots=True)
class RuntimeEnv:
    python_version: str = platform.python_build()


@dataclass(slots=True)
class SystemInfo:
    system: str = platform.system()        # 'Windows', 'Linux', 'Darwin'
    release: str = platform.release()      # e.g., '10', '5.15.0-78-generic'
    version: str = platform.version()
    machine: str = platform.machine()      # 'x86_64', 'AMD64', 'arm64'
    processor: str = platform.processor()
    hostname: str = socket.gethostname()


@dataclass(slots=True)
class CoreInfo:

    index: str
    min_frequency: int
    max_frequency: int

    def get_psutil_data(self):
        return psutil.cpu_freq(percpu=True)[self.index]

    def get_curr_frequency(self):  # in MHz
        return self.get_psutil_data().current

    def __str__(self):
        return f"Core {self.index}: (min {self.min_frequency}, max {self.max_frequency})"


@dataclass(slots=True)
class CpuInfo:

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


class OperatingSystem(ABC):

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
