from .common import InputDevice, InputEvent


class GamepadEvent(InputEvent):

    def __init__(self):
        ...


class GlobalGamepad(InputDevice):

    """ TODO: this is called global because this does not differentiate between actual devices. """

    def __init__(self):
        ...
