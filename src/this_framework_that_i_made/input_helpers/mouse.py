from .common import InputDevice, InputEvent


class MouseEvent(InputEvent):

    def __init__(self):
        ...


class GlobalMouse(InputDevice):

    """ TODO: this is called global because this does not differentiate between actual devices. """

    def __init__(self):
        ...
