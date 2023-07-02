from __future__ import annotations

import enum
import numpy
import logging
import pyaudiowpatch as pyaudio

from device import Device


class AudioDeviceType(enum.Enum):
    Input = "input"
    Output = "output"


class AudioDevice(Device):
    """ An interface-like class that defines the main functionality for an audio device. """

    p = pyaudio.PyAudio()

    cache = {}  # this caches every audio device child instance as an audio device object. Might want to change. TODO

    audio_type = None
    chunk_size = 99999999  # placeholder

    def __init__(self, data):

        self.data = data

        self.index = data.get("index")
        self.struct_version = data.get("structVersion")
        self.host_api = data.get("hostApi")
        self.max_input_channels = data.get("maxInputChannels")
        self.max_output_channels = data.get("maxOutputChannels")
        self.default_low_input_latency = data.get("defaultLowInputLatency")
        self.default_low_output_latency = data.get("defaultLowOutputLatency")
        self.default_high_input_latency = data.get("defaultHighInputLatency")
        self.default_high_output_latency = data.get("defaultHighOutputLatency")
        self.default_sample_rate = data.get("defaultSampleRate")
        self.is_loopback_device = data.get("isLoopbackDevice")

        super().__init__(name=data.get("name"))

    @classmethod
    def get_all_devices(cls):
        for i in range(cls.p.get_host_api_info_by_index(0).get('deviceCount')):
            # I know this is awful, but it's funny
            if device := cls.cache.get((data := cls.p.get_device_info_by_host_api_device_index(0, i))["name"]):
                yield device
            else:
                yield cls(data)

    @classmethod
    def get_default_device(cls):
        key = "defaultInputDevice" if cls.audio_type == AudioDeviceType.Input else "defaultOutputDevice"
        target_id = cls.p.get_host_api_info_by_type(pyaudio.paWASAPI)[key]
        for device in cls.cache:
            if device.index == target_id:
                return device
        cls.logger.error(f"This is weird, no default {cls.__class__.__name__} instance?")

    @property
    def channels(self):
        return self.max_input_channels if self.audio_type == AudioDeviceType.Input else self.max_output_channels

    @property
    def opposite_channels(self):
        return self.max_input_channels if self.audio_type == AudioDeviceType.Output else self.max_output_channels

    def get_audio_stream(self):
        return self.p.open(
            **{
                "format": pyaudio.paInt16,
                "channels": self.channels,
                "rate": int(self.default_sample_rate),
                "input" if self.audio_type == AudioDeviceType.Input else "output": True,
                "frames_per_buffer": self.chunk_size,
                "input_device_index": self.index
            }
        )

    # def send_via_ndi(self):
    #     ndi_send = ndi.send_audio()
    #     ndi_send.add_channel()
    #     ndi_send.metadata().set_name("Audio Channel")
    #     ndi_send.metadata().set_channel_name(0, "Audio")
    #
    #     stream = self.get_audio_stream()
    #     try:
    #         while True:
    #             # Read audio data from the stream
    #             data = stream.read(self.chunk_size)
    #             audio_array = numpy.frombuffer(data, dtype=numpy.int16)
    #
    #             # Send audio data via NDI
    #             ndi_send[0].send(audio_array)
    #
    #     except KeyboardInterrupt:
    #         pass
    #
    #     stream.stop_stream()
    #     stream.close()
    #     ndi_send.destroy()

    def __repr__(self):
        return f'{self.__class__.__name__}(name={self.name})'


class Microphone(AudioDevice):

    cache = {}
    audio_type = AudioDeviceType.Input
    chunk_size = 1024

    @classmethod
    def get_all_devices(cls):
        return [d for d in super().get_all_devices() if d.channels != 0]

    @classmethod
    def get_default_device(cls):
        return cls.p.get_host_api_info_by_type(pyaudio.paWASAPI)["defaultInputDevice"]


class Speaker(AudioDevice):

    cache = {}
    audio_type = AudioDeviceType.Output
    chunk_size = 512

    def __init__(self, data):
        super().__init__(data=data)
        self.loopback_device = self.get_loopback_device()

    def get_loopback_device(self):
        for name, device in LoopbackSpeaker.cache.items():
            if self.name in name:
                return device

    @classmethod
    def get_all_devices(cls):
        return [d for d in super().get_all_devices() if d.channels != 0]

    def get_audio_stream(self):
        return self.loopback_device.get_audio_stream() if self.loopback_device else None


class LoopbackSpeaker(AudioDevice):
    """
    A class for getting a "microphone" version of a speaker

    I need some way of getting loopback audio devices from pyaudiowpatch in order to actually
    read a speaker's stream. Creating a whole new child class for this is a bit wasteful, but
    it fits well with the current AudioDevice hierarchy. I might want to change this later.
    """

    cache = {}
    audio_type = AudioDeviceType.Input  # See parent method docs
    chunk_size = 1024

    def __init__(self, data):
        super().__init__(data=data)  # do I need this? TODO

    @classmethod
    def get_all_devices(cls):
        return [cls(d) for d in cls.p.get_loopback_device_info_generator()]


LoopbackSpeaker.populate_cache()  # this is a bandaid to the speaker loopback problem TODO


if __name__ == '__main__':
    for audio_device_type in AudioDevice.__subclasses__():
        audio_device_type.populate_cache()
        audio_device_type.print_cache()
        print()

    speaker = Speaker.search_for("Main Output 1/2 (Audient EVO8)")
    microphone = Microphone.search_for("Mic | Line 1/2 (Audient EVO8)")

    audio = Speaker.get_default_device()

    speaker_stream = speaker.get_audio_stream()
    for _ in range(1000):
        speaker_data = speaker_stream.read(Speaker.chunk_size)
        speaker_audio_array = numpy.frombuffer(speaker_data, dtype=numpy.int16)
        print("speaker_stream:", speaker_audio_array)

    microphone_stream = microphone.get_audio_stream()
    for _ in range(1000):
        microphone_data = microphone_stream.read(Microphone.chunk_size)
        microphone_audio_array = numpy.frombuffer(microphone_data, dtype=numpy.int16)
        print("microphone_stream:", microphone_audio_array)
