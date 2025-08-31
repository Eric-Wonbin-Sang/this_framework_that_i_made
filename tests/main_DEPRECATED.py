import numpy
from things.audio import AudioGraphVisualizer, Microphone, Speaker
from things.video import (ApplicationWindow, Camera, MssMonitor, ScreenInfoMonitor,
                          monitor_factory, ChromecastMonitor)


def test_speakers():

    Speaker.populate_cache()
    Speaker.print_cache()

    speaker = Speaker.search_for("Main Output 1/2 (Audient EVO8)")
    AudioGraphVisualizer.show(speaker, band_count=20)

    # speaker_stream = speaker.get_audio_stream()
    # for _ in range(1000):
    #     speaker_data = speaker_stream.read(Speaker.chunk_size)
    #     speaker_audio_array = numpy.frombuffer(speaker_data, dtype=numpy.int16)
    #     print("speaker_stream:", speaker_audio_array)


def test_mics():

    Microphone.populate_cache()
    Microphone.print_cache()

    microphone = Microphone.search_for("Mic | Line 1/2 (Audient EVO8)")
    AudioGraphVisualizer.show(microphone, band_count=20)

    # microphone_stream = microphone.get_audio_stream()
    # for _ in range(1000):
    #     microphone_data = microphone_stream.read(Microphone.chunk_size)
    #     microphone_audio_array = numpy.frombuffer(microphone_data, dtype=numpy.int16)
    #     print("microphone_stream:", microphone_audio_array)

    # audio = Speaker.get_default_device()
    # print(audio)


def test_monitors():
    
    scalar = .4

    for display_class in [ScreenInfoMonitor, MssMonitor]:

        display_class.populate_cache()
        display_class.print_cache()

        monitor_class = monitor_factory(subclass=display_class)

        for monitor in monitor_class.get_all_devices():
            print(monitor)
            monitor.get_live_view(scalar=scalar)
            # monitor.record(scalar=scalar)


def test_applications():
    
    scalar = .4
    for application in ApplicationWindow.get_all_devices():
        print(application)
        application.get_live_view(scalar=scalar)


def test_cameras():
    
    for camera in Camera.get_all_devices():
        print(camera)
        camera.get_live_view()


def test_chromecasts():
    for chromecast in ChromecastMonitor.get_all_devices():
        print(chromecast)


if __name__ == '__main__':
    test_speakers()
    # test_mics()
    # test_monitors()
    # test_applications()
    # test_cameras()
    # test_chromecasts()
