from .common import InputDevice, InputEvent


class KeyEvent(InputEvent):

    def __init__(self):
        ...


class GlobalKeyboard(InputDevice):

    """ TODO: this is called global because this does not differentiate between actual devices. """

    def __init__(self):
        ...
