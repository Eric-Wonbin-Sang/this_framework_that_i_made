
from this_framework_that_i_made.systems import WindowsSystem


def test_monitors():
    system = WindowsSystem()
    monitors = system.monitors
    print("\n".join(map(str, (m.as_dict() for m in monitors))))
    print(monitors)

    for screenshot in monitors[0].yield_content():
        print(screenshot)


def test_windows():
    system = WindowsSystem()
    print(system)

    windows = system.windows
    window = next(filter(lambda w: "Zen Browser".lower() in w.title.lower(), windows))

    for content in window.yield_audio_content():
        print(content)

    # for content in system.windows[0].yield_video_content(fps=10):
    #     print(content)


def main():
    # test_monitors()
    test_windows()


if __name__ == "__main__":
    main()
