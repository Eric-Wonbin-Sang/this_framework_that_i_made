from dataclasses import dataclass
from enum import Enum
from functools import cached_property
import logging
from typing import Iterator, List, Optional, Tuple, Union
import numpy as np
import soundcard
import sounddevice

from .generics import SavableObject, TftimException, ensure_savable, group_by, staticproperty


logger = logging.getLogger(__name__)


sounddevice.default.samplerate = 48000


SoundcardDevice = Union[
    "soundcard.coreaudio._Microphone",
    "soundcard.pulseaudio._Microphone",
    "soundcard.mediafoundation._Speaker",
    "soundcard.coreaudio._Speaker",
    "soundcard.pulseaudio._Speaker",
]



class AudioEndpointType(Enum):  # I might want to change this to AudioType TODO
    INPUT = "input"
    OUTPUT = "output"


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
    max_input_channels: int           # How many input channels (mic, line-in, etc.)
    max_output_channels: int          # How many output channels (0 means input-only device)
    default_low_input_latency: str    # Suggested low-latency buffer (seconds)
    default_low_output_latency: str  
    default_high_input_latency: str   # Suggested high-latency buffer (seconds)
    default_high_output_latency: str
    default_samplerate: str           # Default sample rate (Hz)
    endpoint_type: AudioEndpointType = None

    def _get_endpoint_type(self):
        if self.max_input_channels > 0:
            return AudioEndpointType.INPUT
        elif self.max_output_channels > 0:
            return AudioEndpointType.OUTPUT
        raise TftimException("{self.max_input_channels=} and {self.max_output_channels=} don't make sense")

    def __post_init__(self):
        self.endpoint_type = self._get_endpoint_type()

    @property
    def channels(self):
        """ since a device is only an output or an input (at least I think), we can abstract channels """
        return self.max_input_channels if self.endpoint_type == AudioEndpointType.INPUT else self.max_output_channels

    @property
    def opposite_channels(self):
        return self.max_input_channels if self.endpoint_type == AudioEndpointType.OUTPUT else self.max_output_channels


class SoundCardManager:

    """

    This soundcard module seems great, although the inheritance structure is conceptually really different.

    I just care about having some way to get the pcm blocks, so simplifies a lot of stuff for me.

    """

    @staticmethod
    def get_soundcard_mics():
        return soundcard.all_microphones(include_loopback=True)
    
    @staticmethod
    def get_soundcard_speakers():
        return soundcard.all_speakers()
    
    @classmethod
    def get_source_by_name(cls, name: str, endpoint_type: AudioEndpointType):
        try:
            if endpoint_type == AudioEndpointType.INPUT:
                return soundcard.get_microphone(name)
            elif endpoint_type == AudioEndpointType.OUTPUT:
                # a loopback is required to listen to an output since outputs don't have this feature by default
                for mic in cls.get_soundcard_mics():
                    target_name = name.strip().lower()
                    mic_name = mic.name.lower()
                    if target_name in mic_name and ("loopback" in mic_name or "monitor" in mic_name):
                        return mic
            raise TftimException(f"{endpoint_type=} for search {name=} is not correct")
        except Exception as e:
            logger.warning(f"could not find {name=} with {endpoint_type=}: {e}")
            return None


class PcmEncoding(Enum):

    """
    
    Pulse-Code Modulation encodings
    
    Float32 (“f32”)
        Each sample is a 32-bit float, usually in range -1.0 to +1.0.
        This is what most Python audio libs (NumPy, sounddevice, soundcard) give you by default.
        Easy to do math/processing on.

    Int16 (“i16”)
        Each sample is a 16-bit signed integer, in range -2768…32767.
        Common in WAV files, sound cards, and network/audio protocols.
        Smaller bandwidth than float32 (2 bytes vs 4 bytes per sample).
    
    """

    # common formats
    FLOAT_32 = "f32"
    INT_16 = "i16"

    # less used
    INT_8 = "i8"
    INT_24 = "i24"
    INT_32 = "i32"
    FLOAT_64 = "f64"


@dataclass
class AudioDeviceStreamer:

    audio_device: SoundcardDevice            # or your wrapper type
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    encoding: PcmEncoding = PcmEncoding.FLOAT_32  # "f32" or "i16"
    block_ms: int = 20
    as_bytes: bool = False

    def __post_init__(self):
        # Resolve defaults from device if not provided
        # (soundcard microphones don't expose default SR/channels reliably; pick sensible defaults)
        self.sample_rate = int(self.sample_rate or 48_000)
        self.channels = int(self.channels or 2)
        self.block_size = max(1, int(round(self.sample_rate * (self.block_ms / 1000.0))))
        self._recorder = None
    
    @cached_property
    def pcm_block_metadata(self) -> dict:
        """Metadata that you can access when in the recording context."""
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format": self.encoding,
            "name": self.audio_device.name,
            "block_size": self.block_size,
        }
    
    def __enter__(self):
        if self.audio_device.soundcard_device is None:
            raise TftimException(f"audio_device {self.audio_device.name} has no soundcard_device")
        self._recorder = self.audio_device.soundcard_device.recorder(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.block_size,
        )
        self._rec_ctx = self._recorder.__enter__()   # enter context
        return self

    def stream(self) -> Iterator[Tuple[dict, np.ndarray | bytes]]:
        """
        Continuous generator of pcm_blocks until the caller stops iterating.
        Call this inside the 'with' block so the device is open.
        """
        if self._recorder is None:
            raise RuntimeError("Call stream() inside 'with AudioDeviceStreamer(...) as s:'")

        while True:
            block = self._rec_ctx.record(numframes=self.block_size)  # float32, shape (frames, ch)
            if self.encoding == "i16":
                block = (np.clip(block, -1.0, 1.0) * 32767.0).astype(np.int16)
            yield block.tobytes() if self.as_bytes else block

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if hasattr(self, "_recorder") and self._recorder is not None:
                return self.recorder.__exit__(exc_type, exc_value, traceback)
        finally:
            self._recorder = None
        return None


@ensure_savable
@dataclass
class AudioDevice(SavableObject):

    """

    A set of audio endpoints grouped by name, representing all different hostapi routes for a specific device.
    
    What's the difference between an input vs an output? Conceptually, we have some stream of data that
    a program reads. Regardless of where that data is coming from, the audio data should inherently be 
    the same. All I care about is what exists and how I can route it. This should allow for the creation
    of virtual audio devices that take in true endpoints, process them in whatever way, and then return
    a virtual device that combines the two.
    
    """

    endpoints: List[AudioEndpoint]

    @property
    def name(self):
        return self.endpoints[0].name

    @property
    def endpoint_type(self):
        return self.endpoints[0].endpoint_type

    @property
    def default_sample_rate(self):
        return self.endpoints[0].default_samplerate

    @property
    def channels(self):
        return self.endpoints[0].channels

    @property
    def soundcard_device(self):
        return SoundCardManager.get_source_by_name(self.name, self.endpoint_type)

    def __str__(self):
        name = self.name
        hostapi_to_endpoint = group_by(self.endpoints, lambda e: e.hostapi_name)
        hostapis = list(hostapi_to_endpoint.keys())
        return f"{self.__class__.__name__}({name=}, {hostapis=})"


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
@dataclass(slots=True)
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
        # remember data["hostapi"] is the index of the hostapi, stupid
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
    
    def is_endpoint_default_input(self, endpoint):
        return endpoint.index == self.name_to_host_api[endpoint.hostapi_name].default_input_device

    @property
    def default_input_endpoints(self):
        return list(filter(self.is_endpoint_default_input, self.audio_endpoints))
    
    @property
    def default_input_devices(self):
        return list(filter(
            lambda device: device.endpoint_type == AudioEndpointType.INPUT \
                and any(self.is_endpoint_default_input(e) for e in device.endpoints),
            self.audio_devices
        ))
    
    def is_endpoint_default_output(self, endpoint):
        return endpoint.index == self.name_to_host_api[endpoint.hostapi_name].default_output_device

    @property
    def default_output_endpoints(self):
        return list(filter(self.is_endpoint_default_output, self.audio_endpoints))
    
    @property
    def default_output_devices(self):
        return list(filter(
            lambda device: device.endpoint_type == AudioEndpointType.OUTPUT \
                and any(self.is_endpoint_default_output(e) for e in device.endpoints),
            self.audio_devices
        ))

    def as_dict(self):
        return {
            "audio_devices": self.audio_devices,
        }
