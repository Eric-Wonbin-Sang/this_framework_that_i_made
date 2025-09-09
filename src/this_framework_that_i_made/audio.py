from dataclasses import dataclass
from enum import Enum
from functools import cached_property
import logging
from typing import List

from this_framework_that_i_made.audio_helpers.volume_helpers import WindowVolumeControllerFactory

from .audio_helpers.pyaudio_helper import PyAudioWrapper, get_pcm_blocks
from .audio_helpers.audio_standards import (
    SampleFormat,
    PYAUDIO_SAMPLE_FORMAT,
    NUMPY_SAMPLE_FORMAT,
)
from .generics import SavableObject, TftimException, ensure_savable, staticproperty


"""

General takeaway:
- all computers have at least one "hostapi"
- each hostapi allows for audio endpoints
- certain types of hostapis allow you to get audio data
- portaudio is a unified framework across all OS envs
- we only care about it working, so the audio device should just have one default stream

"""

logger = logging.getLogger(__name__)


@ensure_savable
class HostApiData(SavableObject):

    def __init__(self, py_audio_data):

        self.init_data = py_audio_data

        # lookup key in PortAudio’s internal list
        self.index: int = py_audio_data["index"]
        # the actual API family (MME, WASAPI, etc.), always the same number across machines
        self.port_audio_type: str = py_audio_data["type"]
        # PortAudio's way of maintaining compatibility with different hostapi revisions
        self.struct_version: str = py_audio_data["structVersion"]
        self.name: str = py_audio_data["name"]
        self.device_count: str = py_audio_data["deviceCount"]
        self.default_input_device: str = py_audio_data["defaultInputDevice"]
        self.default_output_device: str = py_audio_data["defaultOutputDevice"]

    def as_dict(self):
        return {
            "index": self.index,
            "port_audio_type": self.port_audio_type,
            "struct_version": self.struct_version,
            "name": self.name,
            "device_count": self.device_count,
            "default_input_device": self.default_input_device,
            "default_output_device": self.default_output_device,
        }


class AudioEndpointType(Enum):
    INPUT = "input"
    OUTPUT = "output"
    DUPLEX = "duplex"


@ensure_savable
class AudioEndpoint:

    """
    
    Endpoints can be only inputs, outputs, or both (duplex). Only some HostApis use it.
    
    """

    def __init__(self, py_audio_data):

        self.init_data = py_audio_data

        self.index: int = py_audio_data["index"]
        self.struct_version: int = py_audio_data["structVersion"]
        # self.name: str = py_audio_data["name"].rstrip(PyAudioWrapper.WASAPI_LOOPBACK_SUFFIX)
        self.name: str = py_audio_data["name"]
        self.host_api_index: int = py_audio_data["hostApi"]
        self.max_input_channels: int = py_audio_data["maxInputChannels"]
        self.max_output_channels: int = py_audio_data["maxOutputChannels"]
        self.default_low_input_latency: float = py_audio_data["defaultLowInputLatency"]
        self.default_low_output_latency: float = py_audio_data["defaultLowOutputLatency"]
        self.default_high_input_latency: float = py_audio_data["defaultHighInputLatency"]
        self.default_high_output_latency: float = py_audio_data["defaultHighOutputLatency"]
        self.default_sample_rate: float = py_audio_data["defaultSampleRate"]
        self.is_loopback_device: bool = py_audio_data["isLoopbackDevice"]  # TODO: might not exist in linux pyaudio

    @cached_property
    def audio_endpoint_type(self):
        if self.max_input_channels > 0 and self.max_output_channels > 0:
            return AudioEndpointType.DUPLEX
        if self.max_input_channels > 0:
            return AudioEndpointType.INPUT
        if self.max_output_channels > 0:
            return AudioEndpointType.OUTPUT
        raise TftimException(f"{self.max_input_channels=} and {self.max_output_channels=} are both 0?")

    @property
    def host_api_name(self):
        return PyAudioWrapper.get_host_api_name_by_index(self.host_api_index)

    # only for input/duplex types
    def get_pcm_blocks(self, sample_format: SampleFormat = SampleFormat.INT_16, frames_per_buffer=1024):
        """Yields PCM blocks for this input endpoint with sensible defaults."""
        params = {
            "rate": int(self.default_sample_rate),
            "channels": self.max_input_channels,
            "input_device_index": self.index,
            "sample_format": sample_format,
            "frames_per_buffer": frames_per_buffer,
        }
        with get_pcm_blocks(**params) as blocks:
            for block in blocks:
                yield block

    # only for output types
    @property
    def volume_controller(self):
        # TODO: make cross-platform
        return WindowVolumeControllerFactory.get_volume_controller_by_audio_endpoint_name(self.name)

    def as_dict(self):
        return {
            "struct_version": self.struct_version,
            "name": self.name,
            "hostApi": self.hostApi,
            "max_input_channels": self.max_input_channels,
            "max_output_channels": self.max_output_channels,
            "default_low_input_latency": self.default_low_input_latency,
            "default_low_output_latency": self.default_low_output_latency,
            "default_high_input_latency": self.default_high_input_latency,
            "default_high_output_latency": self.default_high_output_latency,
            "is_loopback_device": self.is_loopback_device,
        }


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

    name: str
    audio_endpoints: List[AudioEndpoint]

    def input_audio_endpoints(self):
        return [
            e for e in self.audio_endpoints
            if e.audio_endpoint_type in [AudioEndpointType.INPUT, AudioEndpointType.DUPLEX]
        ]

    def output_audio_endpoints(self):
        return [
            e for e in self.audio_endpoints
            if e.audio_endpoint_type in [AudioEndpointType.OUTPUT, AudioEndpointType.DUPLEX]
        ]

    def __str__(self):
        name = self.name
        hostapis = [e.host_api_name for e in self.audio_endpoints]
        return f"{self.__class__.__name__}({name=}, {hostapis=})"


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
        return [HostApiData(data) for data in PyAudioWrapper.get_host_api_data()]

    @property
    def name_to_host_api(self):
        """ for convenience, also should this be names_to_host_apis? """
        return {hostapi.name: hostapi for hostapi in self.host_apis}

    @property
    def audio_endpoints(self):
        # remember data["hostapi"] is the index of the hostapi, stupid
        return [AudioEndpoint(data) for data in PyAudioWrapper.get_audio_endpoint_data()]

    def _get_audio_endpoint_groups(self):
        name_to_endpoints = {}
        for audio_endpoint in self.audio_endpoints:
            # old windows MME driver names are char limited and can't display the full device name
            name = audio_endpoint.name.rstrip(PyAudioWrapper.WASAPI_LOOPBACK_SUFFIX)
            # check if the current name is a superset of any existing audio names
            if any(n in name for n in name_to_endpoints.keys()):
                target_name = next(n for n in name_to_endpoints.keys() if n in name)
                name_to_endpoints[target_name].append(audio_endpoint)
            else:
                name_to_endpoints[name] = [audio_endpoint]
        # I want the better names from the other endpoints, so let's pretty it up
        rename_to_endpoints = {
            next(reversed([e.name.rstrip(PyAudioWrapper.WASAPI_LOOPBACK_SUFFIX) for e in endpoints])): endpoints
            for endpoints in name_to_endpoints.values()
        }
        return rename_to_endpoints

    @property
    def audio_devices(self):
        return [
            AudioDevice(name, audio_endpoints)
            for name, audio_endpoints in self._get_audio_endpoint_groups().items()
        ]

    # def is_endpoint_default_input(self, endpoint):
    #     return endpoint.index == self.name_to_host_api[endpoint.hostapi_name].default_input_device

    # @property
    # def default_input_endpoints(self):
    #     return list(filter(self.is_endpoint_default_input, self.audio_endpoints))
    
    # @property
    # def default_input_devices(self):
    #     return list(filter(
    #         lambda device: device.endpoint_type == AudioEndpointType.INPUT \
    #             and any(self.is_endpoint_default_input(e) for e in device.endpoints),
    #         self.audio_devices
    #     ))
    
    # def is_endpoint_default_output(self, endpoint):
    #     return endpoint.index == self.name_to_host_api[endpoint.hostapi_name].default_output_device

    # @property
    # def default_output_endpoints(self):
    #     return list(filter(self.is_endpoint_default_output, self.audio_endpoints))
    
    # @property
    # def default_output_devices(self):
    #     return list(filter(
    #         lambda device: device.endpoint_type == AudioEndpointType.OUTPUT \
    #             and any(self.is_endpoint_default_output(e) for e in device.endpoints),
    #         self.audio_devices
    #     ))

    def as_dict(self):
        return {
            "audio_devices": self.audio_devices,
        }
