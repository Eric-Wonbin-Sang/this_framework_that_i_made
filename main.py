from __future__ import annotations

import numpy
import logging
import pyaudiowpatch as pyaudio

# wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI) <- get default device


class AudioDevice:

    logger = logging.getLogger(__name__)

    cache = {}  # this caches every audio device child instance as an audio device object. Might want to change. TODO
    INPUT = "input"
    OUTPUT = "output"

    p = pyaudio.PyAudio()

    chunk_size = 99999999  # placeholder

    def __init__(self, data):

        self.data = data

        self.index = data.get("index")
        self.struct_version = data.get("structVersion")
        self.name = data.get("name")
        self.host_api = data.get("hostApi")
        self.max_input_channels = data.get("maxInputChannels")
        self.max_output_channels = data.get("maxOutputChannels")
        self.default_low_input_latency = data.get("defaultLowInputLatency")
        self.default_low_output_latency = data.get("defaultLowOutputLatency")
        self.default_high_input_latency = data.get("defaultHighInputLatency")
        self.default_high_output_latency = data.get("defaultHighOutputLatency")
        self.default_sample_rate = data.get("defaultSampleRate")
        self.is_loopback_device = data.get("isLoopbackDevice")

        if self.name not in self.cache:
            self.cache[self.name] = self

    @classmethod
    def get_available_device_names(cls):
        return list(cls.cache.keys())

    @classmethod
    def get_all_devices(cls):
        return [
            cls(cls.p.get_device_info_by_host_api_device_index(0, i))
            for i in range(cls.p.get_host_api_info_by_index(0).get('deviceCount'))
        ]

    @classmethod
    def populate_cache(cls):
        cls.cache = {m.name: m for m in cls.get_all_devices()}

    @classmethod
    def print_cache(cls):
        print(f"{cls.__name__}(")
        print("\n".join([f"\t{k}: {v}" for k, v in LoopbackSpeaker.cache.items()]))
        print(")")

    @classmethod
    def search_for(cls, target_name) -> AudioDevice:
        target_device = None
        for name, device in cls.cache.items():
            if target_name.lower() in name.lower():
                if target_device is None:
                    target_device = device
                else:
                    cls.logger.warning(
                        f"Found multiple devices that could be found with name {target_device}, consider refining name"
                    )
                    break
        return target_device

    @property
    def audio_type(self):
        """ This determines if the audio source is an input our output"""
        raise Exception(f"{self.__class__.__name__} base method called, should be a child method.")

    @property
    def channels(self):
        return self.max_input_channels if self.audio_type == self.INPUT else self.max_output_channels

    def get_audio_stream(self):
        return self.p.open(
            **{
                "format": pyaudio.paInt16,
                "channels": self.channels,
                "rate": int(self.default_sample_rate),
                "input" if self.audio_type == self.INPUT else "output": True,
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
    chunk_size = 1024

    @classmethod
    def get_all_devices(cls):
        return [d for d in super().get_all_devices() if d.max_output_channels == 0]

    @property
    def audio_type(self):
        return self.INPUT


class Speaker(AudioDevice):

    cache = {}
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
        return [d for d in super().get_all_devices() if d.max_input_channels == 0]

    @property
    def audio_type(self):
        return self.OUTPUT

    def get_audio_stream(self):
        return self.loopback_device.get_audio_stream() if self.loopback_device is not None else None


class LoopbackSpeaker(AudioDevice):
    """
    A class for getting a "microphone" version of a speaker

    I need some way of getting loopback audio devices from pyaudiowpatch in order to actually
    read a speaker's stream. Creating a whole new child class for this is a bit wasteful, but
    it fits well with the current AudioDevice hierarchy. I might want to change this later.
    """

    cache = {}

    def __init__(self, data):
        # Interestingly, I need an init here for LoopbackSpeaker to populate_cache because of
        #
        super().__init__(data=data)

    @classmethod
    def get_all_devices(cls):
        return [cls(d) for d in cls.p.get_loopback_device_info_generator()]

    @property
    def audio_type(self):
        return self.INPUT


LoopbackSpeaker.populate_cache()  # this is a bandaid to the speaker loopback problem TODO


def main():
    for audio_device_type in [AudioDevice] + AudioDevice.__subclasses__():
        audio_device_type.populate_cache()

    for audio_device_type in [AudioDevice] + AudioDevice.__subclasses__():
        print(audio_device_type)
        for m in audio_device_type.get_all_devices():
            print(m)
            print(m.data)
        print("\n" * 3)

    speaker = Speaker.search_for("Main Output 1/2 (Audient EVO8)")
    microphone = Microphone.search_for("Mic | Line 1/2 (Audient EVO8)")

    speaker_stream = speaker.get_audio_stream()
    print(speaker_stream)
    for _ in range(1000):
        speaker_data = speaker_stream.read(Speaker.chunk_size)
        speaker_audio_array = numpy.frombuffer(speaker_data, dtype=numpy.int16)
        print("speaker_stream:", speaker_audio_array)

    microphone_stream = microphone.get_audio_stream()
    for _ in range(1000):
        microphone_data = microphone_stream.read(Microphone.chunk_size)
        microphone_audio_array = numpy.frombuffer(microphone_data, dtype=numpy.int16)
        print("microphone_stream:", microphone_audio_array)


if __name__ == '__main__':
    main()
