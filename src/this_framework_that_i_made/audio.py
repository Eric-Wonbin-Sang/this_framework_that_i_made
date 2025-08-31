from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import List
import sounddevice

from .generics import SavableObject, TftimException, ensure_savable, group_by, staticproperty


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
@dataclass(slots=True)
class HostApi(SavableObject):
    name: str
    devices: List[str]
    default_input_device: int
    default_output_device: int

    @staticmethod
    def get_by_name(name, hostapis):
        for hostapi in hostapis:
            if name == hostapi.name:
                return hostapi
        raise TftimException(f"name {name} does not exist in existing hostapis: {', '.join(h.name for h in hostapis)}")


@ensure_savable
class AudioSystem(SavableObject):

    """

    General info on sound host APIs:

        In PortAudio (which sounddevice wraps), a host API is the underlying audio backend that
        PortAudio uses to talk to the system.

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
        
    About default audio devices:

        It seems like Windows's host APIs technically have a different default per API, so there can
        be multiple defaults. MacOS just has one "Core Audio" API, so there's only one default, and
        then Linux doesn't require a default input/output, but most host APIs do. What we can do is
        just say that every host API can potentially have a default, and then the AudioSystem 
        abstraction can handle the multiple defaults by just returning every specified default
        in the system. It's up to whatever is next to handle those default endpoints.

    """

    @staticproperty
    def host_apis():
        # this is called a bit wastefully. ideally, this should update at some rate in another thread and then this reads that state
        return [HostApi(**data) for data in sounddevice.query_hostapis()]

    @property
    def name_to_host_api(self):
        """ for convenience, also should this be names_to_host_apis? """
        return {hostapi.name: hostapi for hostapi in self.host_apis}

    @property
    def audio_endpoints(self):
        # remember data["hostapi"] is the idex of the hostapi, stupid
        return [
            AudioEndpoint(hostapi_name=self.host_apis[data["hostapi"]].name, **data)
            for data in sounddevice.query_devices()
        ]

    @property
    def audio_devices(self):
        return [
            AudioDevice(endpoints=endpoints)
            for endpoints in group_by(self.audio_endpoints, lambda e: e.name).values()
        ]

    @property
    def default_endpoints(self):
        return list(filter(
            lambda endpoint: endpoint.index in self.name_to_host_api[endpoint.hostapi_name],
            self.audio_endpoints
        ))
    
    @property
    def default_input_endpoints(self):
        return list(filter(
            lambda endpoint: endpoint.index == self.name_to_host_api[endpoint.hostapi_name].default_input_device,
            self.audio_endpoints
        ))
    
    @property
    def default_output_endpoints(self):
        return list(filter(
            lambda endpoint: endpoint.index == self.name_to_host_api[endpoint.hostapi_name].default_output_device,
            self.audio_endpoints
        ))
    
    def as_dict(self):
        return {
            "audio_devices": self.audio_devices,
        }
