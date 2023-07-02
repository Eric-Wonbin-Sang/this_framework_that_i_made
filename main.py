import numpy

from audio import AudioDevice, Microphone, Speaker


def main():
    for audio_device_type in AudioDevice.__subclasses__():
        audio_device_type.populate_cache()
        audio_device_type.print_cache()
        print()

    speaker = Speaker.search_for("Main Output 1/2 (Audient EVO8)")
    microphone = Microphone.search_for("Mic | Line 1/2 (Audient EVO8)")

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


if __name__ == '__main__':
    main()
