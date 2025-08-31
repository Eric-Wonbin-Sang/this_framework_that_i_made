from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import List
import sounddevice

from .generics import SavableObject, ensure_savable, group_by


sounddevice.default.samplerate = 48000


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

    @cached_property
    def name(self):
        return self.endpoints[0].name

    def __str__(self):
        name = self.name
        hostapi_to_endpoint = group_by(self.endpoints, lambda e: e.hostapi_name)
        hostapis = list(hostapi_to_endpoint.keys())
        return f"{self.__class__.__name__}({name=}, {hostapis=})"


@ensure_savable
@dataclass(slots=True)
class AudioInputDevice(AudioDevice):
    ...


@ensure_savable
@dataclass(slots=True)
class AudioOutputDevice(AudioDevice):
    ...


@ensure_savable
class AudioSystem(SavableObject):

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
            for endpoints in group_by(cls._get_audio_endpoints(), lambda e: e.name).values()
        ]

    def as_dict(self):
        return {
            "audio_devices": self.audio_devices,
        }
