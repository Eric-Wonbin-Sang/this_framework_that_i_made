from things.audio import Speaker
from things.video import (Camera, MssMonitor, ScreenInfoMonitor,
                          monitor_factory, ChromecastMonitor)


def test_speakers():
    pass


def test_mics():
    pass


def test_monitors():
    
    scalar = .4

    for display_class in [ScreenInfoMonitor, MssMonitor]:

        monitor_class = monitor_factory(subclass=display_class)

        for monitor in monitor_class.get_all_devices():
            print(monitor)
            # monitor.get_live_view(scalar=scalar)
            monitor.record(scalar=scalar)


def test_cameras():
    
    for camera in Camera.get_all_devices():
        print(camera)
        camera.get_live_view()


def test_chromecasts():
    for chromecast in ChromecastMonitor.get_all_devices():
        print(chromecast)


if __name__ == '__main__':
    # test_monitors()
    # test_cameras()
    test_chromecasts()
