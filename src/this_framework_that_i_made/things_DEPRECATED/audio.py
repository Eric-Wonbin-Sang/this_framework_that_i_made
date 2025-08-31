from __future__ import annotations
from abc import ABC, abstractclassmethod, abstractmethod

import datetime
import enum
import numpy
import logging
import pyaudiowpatch as pyaudio
import matplotlib.pyplot as plt

from things.device import Device


class AudioDeviceType(enum.Enum):  # I might want to change this to AudioType TODO
    Input = "input"
    Output = "output"


class AudioDevice(Device):  # I might want to change this to Audio TODO
    """ An interface-like class that defines the main functionality for an audio device. """

    py_audio = pyaudio.PyAudio()

    audio_type = None
    chunk_size = 99999999  # placeholder

    def __init__(
            self, name, index, struct_version, host_api, max_input_channels, max_output_channels, 
            default_low_input_latency, default_low_output_latency, default_high_input_latency, 
            default_high_output_latency, default_sample_rate, is_loopback_device
        ):

        super().__init__(name=name)

        self.index = index
        self.struct_version = struct_version
        self.host_api = host_api
        self.max_input_channels = max_input_channels
        self.max_output_channels = max_output_channels
        self.default_low_input_latency = default_low_input_latency
        self.default_low_output_latency = default_low_output_latency
        self.default_high_input_latency = default_high_input_latency
        self.default_high_output_latency = default_high_output_latency
        self.default_sample_rate = default_sample_rate
        self.is_loopback_device = is_loopback_device

    @classmethod
    def get_all_devices(cls):
        """ Does yield really optimize anything here? """
        for i in range(cls.py_audio.get_host_api_info_by_index(0).get('deviceCount')):
            data = cls.py_audio.get_device_info_by_host_api_device_index(0, i)
            if device := cls.get_cache().get(data["name"]):
                yield device
            else:
                yield cls(
                    name=data.get("name"),
                    index=data.get("index"),
                    struct_version=data.get("structVersion"),
                    host_api=data.get("hostApi"),
                    max_input_channels=data.get("maxInputChannels"),
                    max_output_channels=data.get("maxOutputChannels"),
                    default_low_input_latency=data.get("defaultLowInputLatency"),
                    default_low_output_latency=data.get("defaultLowOutputLatency"),
                    default_high_input_latency=data.get("defaultHighInputLatency"),
                    default_high_output_latency=data.get("defaultHighOutputLatency"),
                    default_sample_rate=data.get("defaultSampleRate"),
                    is_loopback_device=data.get("isLoopbackDevice")
                )

    @classmethod
    def get_default_device(cls):
        key = "defaultInputDevice" if cls.audio_type == AudioDeviceType.Input else "defaultOutputDevice"
        target_id = cls.py_audio.get_host_api_info_by_type(pyaudio.paWASAPI)[key]
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

    def get_audio_stream(self, stream_callback=None):
        kwargs = {
            "format": pyaudio.paInt16,
            "channels": self.channels,
            "rate": int(self.default_sample_rate),
            "input" if self.audio_type == AudioDeviceType.Input else "output": True,
            "frames_per_buffer": self.chunk_size,
            "input_device_index": self.index
        }
        if stream_callback is not None:
            kwargs["stream_callback"] = stream_callback
        return self.py_audio.open(**kwargs)


class Microphone(AudioDevice):

    audio_type = AudioDeviceType.Input
    chunk_size = 1024

    @classmethod
    def get_all_devices(cls):
        return [d for d in super().get_all_devices() if d.channels != 0]

    @classmethod
    def get_default_device(cls):
        return cls.py_audio.get_host_api_info_by_type(pyaudio.paWASAPI)["defaultInputDevice"]


class Speaker(AudioDevice):

    audio_type = AudioDeviceType.Output
    chunk_size = 512

    def __init__(self, *args, **kwargs):
        # doing this for less spaghetti
        super().__init__(*args, **kwargs)
        self.loopback_device = self.get_loopback_device()

    def get_loopback_device(self):
        if not LoopbackSpeaker.get_cache():
            LoopbackSpeaker.populate_cache()
        for name, device in LoopbackSpeaker.get_cache().items():
            if self.name in name:
                return device

    @classmethod
    def get_all_devices(cls):
        return [d for d in super().get_all_devices() if d.channels != 0]

    def get_audio_stream(self, stream_callback=None):
        return self.loopback_device.get_audio_stream() if self.loopback_device else None

    def get_live_view(self, scalar=False):

        stream = self.get_audio_stream()
        x = numpy.arange(0, self.chunk_size * 2)

        figure = plt.figure()
        axes = figure.gca()
        axes.axis([0, self.chunk_size * 2, -self.chunk_size, self.chunk_size])
        figure.show()

        while True:
            data = stream.read(self.chunk_size)
            data_np = numpy.frombuffer(data, dtype=numpy.int16)
            axes.clear()
            axes.scatter(x, data_np)
            figure.canvas.draw()
            figure.canvas.flush_events()


class LoopbackSpeaker(AudioDevice):

    """
    A class for getting a "microphone" version of a speaker

    I need some way of getting loopback audio devices from pyaudiowpatch in order to actually
    read a speaker's stream. Creating a whole new child class for this is a bit wasteful, but
    it fits well with the current AudioDevice hierarchy. I might want to change this later.

    Note:
        Simplify this class structure with a mixin TODO
    """

    audio_type = AudioDeviceType.Input  # See parent method docs
    chunk_size = 1024

    @classmethod
    def get_all_devices(cls):
        return [cls(**d) for d in cls.py_audio.get_loopback_device_info_generator()]



class AudioTransmitter(ABC):
    
    @abstractmethod
    def send(self, audio_source):
        pass


class AudioNdiTransmitter(AudioTransmitter):
    
    def send(self, audio_source):
        # ndi_send = ndi.send_audio()
        # ndi_send.add_channel()
        # ndi_send.metadata().set_name("Audio Channel")
        # ndi_send.metadata().set_channel_name(0, "Audio")
    
        # stream = self.get_audio_stream()
        # try:
        #     while True:
        #         # Read audio data from the stream
        #         data = stream.read(self.chunk_size)
        #         audio_array = numpy.frombuffer(data, dtype=numpy.int16)
    
        #         # Send audio data via NDI
        #         ndi_send[0].send(audio_array)
    
        # except KeyboardInterrupt:
        #     pass
    
        # stream.stop_stream()
        # stream.close()
        # ndi_send.destroy()
        pass


class AudioVisualizer(ABC):

    """ Not sure if I should do it like this or like the video recorder. TODO """
    
    @abstractclassmethod
    def show(cls, audio_device, band_count):
        pass


class AudioGraphVisualizer(AudioVisualizer):

    @staticmethod
    def get_frequency_bands(band_count, sample_rate):
        """ Ranges of frequencies to group audio stream by. """
        freq_bands = numpy.logspace(
            numpy.log10(20),
            numpy.log10(sample_rate / 2),
            band_count + 1,
            endpoint=True
        ).astype(int)
        return [(start_freq, end_freq) for start_freq, end_freq in zip(freq_bands[:-1], freq_bands[1:])]

    @classmethod
    def _vis_method_1(cls, audio_device, band_count):

        frequency_bands = cls.get_frequency_bands(band_count, audio_device.default_sample_rate)

        fig, ax = plt.subplots()
        ax.set_ylim(0, 1)
        ax.set_xlim(-0.5, band_count - 0.5)
        ax.set_xlabel('Frequency Band')
        ax.set_ylabel('Magnitude')
    
        x = numpy.arange(band_count)  # x-axis values for the bars
        bars = ax.bar(x, numpy.zeros(band_count), align='center')
    
        fig.show()
    
        stream = audio_device.get_audio_stream()
        while True:
            data = stream.read(audio_device.chunk_size)
            data_np = numpy.frombuffer(data, dtype=numpy.int16)  # len = self.chunk_size * 2 = 1024
            fft_result = numpy.fft.fft(data_np)  # len = 1024
    
            # we divide fft_result in half bc the second half is a negated mirror of the first half
            fft_magnitudes = numpy.abs(fft_result[:audio_device.chunk_size // 2])
    
            band_magnitudes = []
            for (start_freq, end_freq) in frequency_bands:
                # average(all the frequencies in the range)
                if not numpy.isnan(amplitude := numpy.mean(fft_magnitudes[start_freq:end_freq])):
                    band_magnitudes.append(amplitude / 100000)
                else:
                    band_magnitudes.append(0)
    
            print(band_magnitudes)
    
            # Update the equalizer bars with new magnitudes
            for bar, magnitude in zip(bars, band_magnitudes):
                bar.set_height(magnitude)
    
            # Redraw the plot
            fig.canvas.draw()
            fig.canvas.flush_events()

    @classmethod
    def _vis_method_2(cls, audio_device, band_count):

        frequency_bands = cls.get_frequency_bands(band_count, audio_device.default_sample_rate)

        plt.ion()  # enable interactivity
        fig = plt.figure()

        stream = audio_device.get_audio_stream()
        while True:
            data = numpy.fromstring(stream.read(audio_device.chunk_size), dtype=numpy.int16)
            data = data * numpy.hanning(len(data))  # smooth the FFT by windowing data

            fft = abs(numpy.fft.fft(data).real)
            fft = fft[:int(len(fft) / 2)]  # keep only first half
            freq = numpy.fft.fftfreq(audio_device.chunk_size, 1.0 / audio_device.default_sample_rate)
            freq = freq[:int(len(freq) / 2)]  # keep only first half
            # freqPeak = freq[numpy.where(fft == numpy.max(fft))[0][0]] + 1

            # print(freq)

            plt.clf()
            plt.plot(data, '-', rasterized=True, color='b')
            fig.canvas.draw()
            plt.pause(0.1)

    @classmethod
    def show(cls, audio_device, band_count):
        cls._vis_method_1(audio_device, band_count)
        cls._vis_method_2(audio_device, band_count)
