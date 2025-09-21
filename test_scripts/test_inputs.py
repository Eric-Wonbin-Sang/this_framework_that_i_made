
from this_framework_that_i_made.input_helpers.mouse import GlobalMouse


def test_mouse():
    m = GlobalMouse(include_move=True)
    try:
        for evt in m.yield_mouse_events():
            print(evt)
            # Example: break on right-click release
            if evt["type"] == "click" and evt["detail"][0] == "right" and evt["detail"][1] is False:
                break
    finally:
        m.stop()


def main():
    test_mouse()


if __name__ == "__main__":
    main()
