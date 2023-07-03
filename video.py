from __future__ import annotations

import datetime

import cv2
import enum
import numpy
import logging
import pyautogui
import screeninfo
import pygetwindow

from PIL import Image, ImageGrab
from fractions import Fraction

from device import Device


class DisplayType(enum.Enum):
    Horizontal = "horizontal"
    Vertical = "vertical"


class SurfaceMixin:

    """ A mixin class for things that have some surface with content that should have image functions. """

    def get_surface_image(self, resize=False):
        raise Exception(f"{self.__class__.__name__} base method called, should be a child's method.")

    def get_np_image(self, resize=False):
        raise Exception(f"{self.__class__.__name__} base method called, should be a child's method.")

    def record(self, seconds, resize=False):
        filename = f"output\\monitor_{self.index}_recording.avi"
        resolution = (self.width, self.height)
        codec = cv2.VideoWriter_fourcc(*"XVID")
        fps = 60.0

        print(f"Recording monitor {self.index}: saving to {filename}")

        result = cv2.VideoWriter(filename, codec, fps, resolution)
        init_dt = datetime.datetime.now()
        while ((now := datetime.datetime.now()) - init_dt).seconds < seconds:
            print(now)
            frame = self.get_np_image(resize=resize)
            result.write(frame)
        result.release()

    def get_live_view(self, resize=False):
        try:
            while True:
                np_image = self.get_np_image(resize=resize)
                cv2.imshow("Captured Window", np_image)
                if cv2.waitKey(1) == ord('q'):
                    break
        except KeyboardInterrupt:
            pass
        cv2.destroyAllWindows()


class Display(Device, SurfaceMixin):  # I might want to change this to DisplayDevice? TODO

    logger = logging.getLogger(__name__)

    cache = {}

    def __init__(self, index, data):

        self.index = index

        self.x = data.get("x")
        self.y = data.get("y")
        self.width = data.get("width")
        self.height = data.get("height")
        self.width_mm = data.get("width_mm")  # not sure how these are calculated
        self.height_mm = data.get("height_mm")
        self.is_primary = data.get("is_primary")

        self.orientation = DisplayType.Horizontal if self.width > self.height else DisplayType.Vertical
        self.aspect_ratio = Fraction(self.width, self.height)

        super().__init__(name=data.get("name"))

    @classmethod
    def get_all_devices(cls):
        devices = []
        for i, m in enumerate(screeninfo.get_monitors()):
            if device := cls.cache.get(m.__dict__["name"]):
                devices.append(device)
            else:
                devices.append(device := cls(i, m.__dict__))  # could I inherit this class? TODO
                cls.cache[device.name] = device
        # I want to shift all the coordinates so that the least x y value is (0, 0) for cropping the full screenshot
        max_negative_x, max_negative_y = min(d.x for d in devices), min(d.y for d in devices)  # optimize TODO
        for device in devices:
            device.x += abs(max_negative_x)
            device.y += abs(max_negative_y)
        return devices

    def get_default_device(self):
        for device in self.get_all_devices():
            if device.is_primary:
                return device
        self.logger.error(f"This is weird, no default {self.__class__.__name__} instance?")

    def get_surface_image(self, resize=False):
        image = ImageGrab.grab(all_screens=True).crop((self.x, self.y, self.x + self.width, self.y + self.height))
        if not resize:
            return image
        scalar = 800 // max(self.aspect_ratio.numerator, self.aspect_ratio.denominator)
        return image.resize(
            (self.aspect_ratio.numerator * scalar, self.aspect_ratio.denominator * scalar)
        )

    def get_np_image(self, resize=False):
        image = self.get_surface_image(resize=resize)
        return cv2.cvtColor(numpy.array(image), cv2.COLOR_BGR2RGB)


class Camera(Device):

    cache = {}

    def __init__(self, index):
        self.index = index

        self.capture = None
        self.is_open = False

        super().__init__(self.index)

    @classmethod
    def get_all_devices(cls) -> [Camera]:
        cls.logger.info("Retrieving cameras...")
        devices, index = [], 0
        while True:
            try:
                if camera := cls.cache.get(index):
                    cls.logger.info(f" - found cached camera at index {index}")
                    devices.append(camera)
                else:
                    # stupid work around because cv2 doesn't have this implemented
                    capture = cv2.VideoCapture(index)  # this "opens" the camera, so it's being blocked from other apps
                    if capture.isOpened():             # if it can be opened, it's a camera
                        capture.release()
                        devices.append(Camera(index))
                        cls.logger.info(f" - found camera at index {index}")
                    else:
                        cls.logger.info(f"Camera index ends at {index}")
                        break
                index += 1
            except Exception as e:
                cls.logger.error(f"Exception occurred while getting {cls.__name__} devices:")
                cls.logger.exception(e)
                break
        return devices

    def get_default_device(self):
        self.logger.error("implement this")

    def open(self):  # use __with__ method? TODO
        if not self.is_open:
            self.capture = cv2.VideoCapture(self.index)
            self.is_open = True

    def close(self):
        if self.is_open:
            self.capture.release()
            self.is_open = False

    def get_surface_image(self, resize=False):
        if self.is_open:
            ret, frame = self.capture.read()
            return frame

    def get_np_image(self, resize=False):
        image = self.get_surface_image(resize=resize)
        return cv2.cvtColor(numpy.array(image), cv2.COLOR_BGR2RGB)

    def get_live_view(self, resize=False):
        self.open()
        while True:
            cv2.imshow('frame', self.get_surface_image())
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.close()


def main():

    # Camera.populate_cache()
    # for camera in Camera.get_all_devices():
    #     print(camera)
    #     camera.get_live_view()

    Display.populate_cache()
    for display in Display.get_all_devices():
        display.get_live_view(resize=True)
        # display.record(5, resize=True)


if __name__ == '__main__':
    main()
