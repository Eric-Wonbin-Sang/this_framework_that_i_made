
from this_framework_that_i_made.generic.mux import Source, yield_from_sources
from this_framework_that_i_made.input_helpers.keyboard import KeyboardEventGenerator, KeyEvent
from this_framework_that_i_made.input_helpers.mouse import GlobalMouse


def test_mouse():
    m = GlobalMouse()
    try:
        for evt in m.yield_mouse_events():
            print(evt)
            # Example: break on right-click release
    finally:
        m.stop()


def test_keyboard():
    kb = KeyboardEventGenerator(dedupe_repeats=True)
    try:
        for e in kb.yield_keyboard_events():
            print(e)
            # Example exit on Ctrl+Q release
            if not e.is_pressed and e.value == "q" and "ctrl" in kb._down:
                break
    finally:
        kb.stop()


def test_inputs():
    m = GlobalMouse()
    kb = KeyboardEventGenerator(dedupe_repeats=True)
    # kb = KeyboardEventGenerator(dedupe_repeats=True, suppress=True)

    events = yield_from_sources(
        Source("mouse", m.yield_mouse_events),
        Source("keyboard", kb.yield_keyboard_events),
        # pump_timeout=0.25,
    )
    try:
        for src, event in events:
            print(src, event)
            if type(event) == KeyEvent and event.is_cmd:
                print('CMDCMDCMD')
            if type(event) == KeyEvent and event.value == 'esc':
                break
    finally:
        # If your yielders don't auto-stop in their own finally blocks,
        # you could call m.stop() / kb.stop() here. Your versions already do.
        pass


def main():
    # test_mouse()
    # test_keyboard()
    test_inputs()


if __name__ == "__main__":
    main()
