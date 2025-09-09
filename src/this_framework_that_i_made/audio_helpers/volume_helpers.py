
from abc import ABC, abstractmethod
from typing import Optional

# TODO: will conflict when running on non-windows. need to handle. Can separate this module to import conditionally.
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

from this_framework_that_i_made.generics import SavableObject, TftimException, ensure_savable


@ensure_savable
class VolumeController(SavableObject, ABC):

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

    def get_percent(self):
        range_values = self.get_range()
        return (self.get_volume() - range_values["min"]) / (range_values["max"] - range_values["min"])

    @abstractmethod
    def set_volume(self, value):
        ...

    def set_max_volume(self):
        self.set_volume(self.get_range()["max"])

    def set_min_volume(self):
        self.set_volume(self.get_range()["min"])

    def is_max_volume(self):
        return self.get_volume() >= self.get_range()["max"]

    def is_min_volume(self):
        return self.get_volume() <= self.get_range()["min"]

    def increment_volume(self):
        range_values = self.get_range()
        curr_volume = self.get_volume()
        if (value := curr_volume + range_values["step"]) <= range_values["max"]:
            self.set_volume(value)
            return value
        return curr_volume

    def decrement_volume(self):
        range_values = self.get_range()
        curr_volume = self.get_volume()
        if (value := curr_volume - range_values["step"]) >= range_values["min"]:
            self.set_volume(value)
            return value
        return curr_volume

    @abstractmethod
    def is_muted(self):
        ...

    @abstractmethod
    def mute(self):
        ...

    @abstractmethod
    def unmute(self):
        ...

    def as_dict(self):
        return {
            "range": self.get_range(),
            "volume": self.get_volume(),
            "percent": self.get_percent(),
            "is_muted": self.is_muted(),
        }


class ProcessVolumeController(VolumeController):

    def __init__(self, audio_session):
        self.audio_session = audio_session
        self.process_id = self.audio_session.ProcessId
        self.process = self.audio_session.Process
        self.process_name = self.process.name() if self.process else None

    def get_range(self):
        return {"min": 0, "max": 1, "step": 0.01}
    
    def get_volume(self):
        # TODO: not sure why this has so much accuracy, causes issues with SetMasterVolume
        return round(self.audio_session.SimpleAudioVolume.GetMasterVolume(), 3)

    def set_volume(self, value):
        self.audio_session.SimpleAudioVolume.SetMasterVolume(value, None)

    def is_muted(self):
        return self.audio_session.SimpleAudioVolume.GetMute() == 1

    def mute(self):
        self.audio_session.SimpleAudioVolume.SetMute(1, None)

    def unmute(self):
        self.audio_session.SimpleAudioVolume.SetMute(0, None)

    def as_dict(self):
        return {
            "process_id": self.process_id,
            "process_name": self.process_name,
            **super().as_dict(),
        }

    def __repr__(self):
        process_name = self.process_name
        return f"{self.__class__.__name__}({process_name=})"


class DeviceVolumeController(VolumeController):
    
    def __init__(self, device, volume_interface):
        self.device = device
        self.volume_interface = volume_interface

    def get_range(self):
        return dict(zip(["min", "max", "step"], self.volume_interface.GetVolumeRange()))

    def get_volume(self):
        return self.volume_interface.GetMasterVolumeLevel()

    def set_volume(self, value):
        self.volume_interface.SetMasterVolumeLevel(value, None)

    def is_muted(self):
        return self.volume_interface.GetMute() == 1

    def mute(self):
        self.volume_interface.SetMute(1, None)

    def unmute(self):
        self.volume_interface.SetMute(0, None)
    
    def as_dict(self):
        return {
            "device_name": self.device.FriendlyName,
            **super().as_dict(),
        }


class WindowVolumeControllerFactory:

    # ---- DEVICE STUFF --------------------------------------------------------
    @staticmethod
    def get_devices():
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
        device = cls.get_device_by_name(target_name)
        interface = device._dev.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        return DeviceVolumeController(device, cast(interface, POINTER(IAudioEndpointVolume)))
    
    # ---- APP STUFF --------------------------------------------------------
    @staticmethod
    def get_app_sessions():
        return AudioUtilities.GetAllSessions()
    
    def get_process_volume_controller_by_pid(pid) -> Optional[VolumeController]:
        if (session := AudioUtilities.GetProcessSession(pid)) is not None:
            return ProcessVolumeController(session)

    @classmethod
    def get_process_volume_controllers(cls):
        return [ProcessVolumeController(session) for session in cls.get_app_sessions()]

    @classmethod
    def get_process_volume_controller_by_name(cls, target_name):
        for controller in cls.get_process_volume_controllers():
            if target_name.lower() in controller.process_name.lower():
                return controller
