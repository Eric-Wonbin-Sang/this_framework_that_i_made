from abc import ABC
from dataclasses import dataclass
from functools import cached_property
import platform
from typing import Any, Dict, List, Optional
import psutil
import socket

from this_framework_that_i_made.audio_helpers.volume_helpers import WindowVolumeControllerFactory
from this_framework_that_i_made.video_helpers.monitors import Monitor
from this_framework_that_i_made.video_helpers.msft_windows import MsftWindow

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


def _safe(call, default=None):
    try:
        return call()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return default


@ensure_savable
@dataclass(slots=True)
class Process(SavableObject):

    pid: str

    @cached_property
    def process(self):
        try:
            return psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            return None

    @property
    def is_alive(self):
        return psutil.pid_exists(self.pid)

    @staticmethod
    def _get_simple_snapshot(p):
        # values that require additional computation from the initial grab
        return {
            "pid": p.pid,
            "ppid": _safe(p.ppid, None),
            "name": _safe(p.name, None),
            "exe": _safe(p.exe, None),
            "cmdline": _safe(p.cmdline, None),
            "username": _safe(p.username, None),
            "status": _safe(p.status, None),
            "create_time": _safe(p.create_time, None),
            "cwd": _safe(p.cwd, None),
        } if p else {}
    
    @property
    def simple_snapshot(self):
        return self._get_simple_snapshot(self.process)

    @cached_property
    def name(self):
        return self.simple_snapshot.get("name", None)
    
    @staticmethod
    def _get_complex_snapshot(p):
        # values that require additional computation from the initial grab
        return {
            "cpu_percent": _safe(lambda: p.cpu_percent(interval=None)),  # None = non-blocking
            "memory_rss":  _safe(lambda: p.memory_info().rss),
            "memory_vms":  _safe(lambda: p.memory_info().vms),
            "nice":        _safe(lambda: p.nice()),  # "niceness" - scheduling priority hint a process gives to the operating system’s CPU scheduler
        } if p else {}
    
    @property
    def complex_snapshot(self):
        return self._get_complex_snapshot(self.process)

    @property
    def open_files(self):
        return _safe(lambda: [f.path for f in self.process.open_files()], [])

    @property
    def connections(self):
        return _safe(
            lambda: [
                {
                    "fd": c.fd,
                    "type": int(c.type),
                    "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                    "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                    "status": c.status,
                }
                for c in self.process.net_connections()
            ],
            [],
        )

    @property
    def children_tree(self) -> Dict[str, Any]:
        """Return a simple parent→children tree rooted at pid."""
        try:
            root = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            return {"pid": self.pid, "missing": True}
        def node(proc: psutil.Process) -> Dict[str, Any]:
            return {
                "pid": proc.pid,
                "name": _safe(proc.name, ""),
                "children": [_safe(lambda: node(c), None) for c in _safe(proc.children, [])],
            }
        n = node(root)
        # filter Nones if any AccessDenied happened
        def prune(d):
            d["children"] = [c for c in d["children"] if c]
            for c in d["children"]:
                prune(c)
        prune(n)
        return n
    
    @property
    def volume_controller(self):
        return WindowVolumeControllerFactory.get_process_volume_controller_by_pid(self.pid)

    def __repr__(self):
        name = self.name
        pid = self.pid
        return f"{self.__class__.__name__}({name=}, {pid=})"


@ensure_savable
class OperatingSystem(ABC, SavableObject):

    def __init__(self):
        self.system_info: SystemInfo = SystemInfo()
        self.cpu_info: CpuInfo = CpuInfo()
        self.audio_system: AudioSystem = AudioSystem()

        self._pid_to_process = {}

    @classmethod
    def read(cls):
        ...
        
    @property
    def processes(self) -> List[Process]:
        pids = psutil.pids()
        new_pids = [pid for pid in pids if pid not in self._pid_to_process]
        for pid in new_pids:
            self._pid_to_process[pid] = Process(pid)
        lost_pids = [pid for pid in self._pid_to_process if pid not in pids]
        for pid in lost_pids:
            print(f"Removing {pid}")
            del self._pid_to_process[pid]
        return list(self._pid_to_process.values())

    @property
    def processes_with_audio_controls(self) -> List[Process]:
        sessions = WindowVolumeControllerFactory.get_app_sessions()
        self.processes  # get up-to-date processes in internal cache
        return [self._pid_to_process[session.ProcessId] for session in sessions]

    def get_processes_by_name(self, target_name):
        return [
            process for process in self.processes
            if target_name.lower() in process.simple_snapshot.get("name", "").lower()
        ]

    @property
    def monitors(self):
        return Monitor.get_monitors()

    def as_dict(self):
        return {
            "system_info": self.system_info,
            "cpu_info": self.cpu_info,
            "audio_system": self.audio_system,
        }


class WindowsApplication:

    def processes(self):
        ...
    
    def windows(self):
        ...


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

    @property
    def windows(self):
        return MsftWindow.get_windows()


class UnixSystem(OperatingSystem):
    ...


class LinuxSystem(UnixSystem):
    ...


class ArchSystem(LinuxSystem):
    ...


class LinuxSystem(UnixSystem):
    ...
