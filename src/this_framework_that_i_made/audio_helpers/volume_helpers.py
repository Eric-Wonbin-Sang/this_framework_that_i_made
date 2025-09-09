
from abc import ABC, abstractmethod

from this_framework_that_i_made.generics import TftimException


class VolumeController(ABC):

    # @classmethod
    # @abstractmethod
    # def from_audio_endpoint(cls, audio_endpoint):
    #     ...

    # @classmethod
    # @abstractmethod
    # def from_app(cls, app):
    #     ...

    @abstractmethod
    def get_range(self):
        ...

    @abstractmethod
    def get_volume(self):
        ...

    @abstractmethod
    def set_volume(self):
        ...

    def increment_volume(self):
        range_values = self.get_range()
        if (value := self.get_volume() + range_values["step"]) <= range_values["max"]:
            self.set_volume(value)

    def decrement_volume(self):
        range_values = self.get_range()
        if (value := self.get_volume() - range_values["step"]) >= range_values["min"]:
            self.set_volume(value)

    @abstractmethod
    def is_muted(self):
        ...

    @abstractmethod
    def mute(self):
        ...

    @abstractmethod
    def unmute(self):
        ...


class WindowVolumeControllerFactory:

    @staticmethod
    def get_devices():
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetAllDevices()

    @classmethod
    def get_device_by_name(cls, target_name):
        devices = cls.get_devices()
        for device in devices:
            if device.FriendlyName == target_name:
                return device
        raise TftimException(f"Could not find {target_name} in {', '.join(d.FriendlyName for d in devices)}")

    @classmethod
    def get_volume_controller_by_audio_endpoint_name(cls, target_name):
        from pycaw.pycaw import IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL

        device = cls.get_device_by_name(target_name)
        interface = device._dev.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )

        class WindowsVolumeController(VolumeController):

            def __init__(self):
                self.volume_interface = cast(interface, POINTER(IAudioEndpointVolume))

            def get_range(self):
                return dict(zip(["min", "max", "step"], self.volume_interface.GetVolumeRange()))

            def get_volume(self):
                return self.volume_interface.GetMasterVolumeLevel()

            def set_volume(self, value):
                self.volume_interface.SetMasterVolumeLevel(value, None)

            def is_muted(self):
                return self.volume_interface.GetMute()

            def mute(self):
                self.volume_interface.SetMute(1, None)

            def unmute(self):
                self.volume_interface.SetMute(0, None)

        return WindowsVolumeController()
