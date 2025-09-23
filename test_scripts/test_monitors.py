
import io
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
    window.get_icon().show()

    for content in window.yield_audio_content():
        print(content)

    # for content in system.windows[0].yield_video_content(fps=10):
    #     print(content)


def test_icon():
    hwnd = 5441638
    system = WindowsSystem()

    if (window := system.get_window_by_hwnd(hwnd)) is None:
        return
    if (icon := window.get_icon(size=400)) is None:
        return
    try:
        # Prefer PNG to preserve transparency
        buf = io.BytesIO()
        icon.save(buf, format="PNG")   # or JPEG (see note below)
        buf.seek(0)
        print("buf:", buf)
    except Exception as e:
        print("error:", e)


def main():
    test_monitors()
    # test_windows()
    # test_icon()


if __name__ == "__main__":
    main()
