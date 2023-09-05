
from __future__ import annotations

import datetime
import enum
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from fractions import Fraction
from functools import cached_property
from typing import Self

import cv2
import numpy
import pychromecast
import pygetwindow
import screeninfo
import win32con
import win32gui
import win32ui
from mss import mss
from PIL import Image, ImageGrab

from things.device import Device
from things.functions import dt_to_std_str, repr_helper


class SurfaceMixin(ABC):

    """ A mixin class for things that have some surface with content that should have image functions. """

    OUTPUT_DIR = "output"

    def __init__(self, x, y, width, height) -> None:
        
        self._x = x
        self._y = y
        self._width = width
        self._height = height

        super().__init__()

    @property
    def x(self):
        return self._x
    
    @property
    def y(self):
        return self._y
    
    @property
    def width(self):
        return self._width
    
    @property
    def height(self):
        return self._height

    def get_scaled_width(self, scalar=1):
        return int(self.width * scalar)
    
    def get_scaled_height(self, scalar=1):
        return int(self.height * scalar)

    @abstractmethod
    def get_surface_image(self, scalar=1):
        pass

    @abstractmethod
    def get_np_image(self, scalar=1):
        pass

    def get_live_view(self, scalar=1):
        try:
            while True:
                np_image = self.get_np_image(scalar=scalar)
                cv2.imshow("Captured Window", np_image)
                if cv2.waitKey(1) == ord('q'):
                    break
        except KeyboardInterrupt:
            pass
        cv2.destroyAllWindows()

    def record(self, filename, scalar=1, fps=20.0):
        # we have to keep track of scaling between the recorder initializing and
        # the frame retrival. Try to marry the two to just one specification. TODO
        recorder = XvidRecorder(
            filepath=os.path.join(self.OUTPUT_DIR, filename),
            fps=fps, 
            width=self.get_scaled_width(scalar=scalar), 
            height=self.get_scaled_height(scalar=scalar),
        )
        while True:
            start_time = datetime.now()

            frame = self.get_np_image(scalar=scalar)
            recorder.output.write(frame)
            cv2.imshow('Screen Recorder', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            height, width, channels = frame.shape
            end_time = datetime.now()
            elapsed_time = (end_time - start_time).microseconds / 1_000_000

            print(recorder)
            print(f"width={width}, height={height}, channels={channels}")
            print(f"{1/elapsed_time:.2f} fps")

        recorder.output.release()
        cv2.destroyAllWindows()


class DisplayType(enum.Enum):
    Horizontal = "horizontal"
    Vertical = "vertical"


class Display(Device, SurfaceMixin, ABC):

    """
    Is a monitor a display or is a display a monitor?

    The terms "monitor" and "display" are often used interchangeably, but they can refer to different things 
    depending on the context:

    Monitor
    A monitor typically refers to the whole unit that includes the display screen, the casing around it, and 
    other components like ports, speakers, or other built-in peripherals. Monitors are generally designed to 
    be connected to a separate computer or device. They may have various input options like HDMI, VGA, 
    DisplayPort, and sometimes even built-in speakers or USB hubs.

    Display
    The term "display" often refers to the actual screen where the images and videos are rendered. This could 
    be part of a monitor, television, smartphone, or any other device with a screen. In some contexts, 
    "display" can also refer to the whole unit (like a monitor), especially when discussing types of technology 
    (e.g., LED display, OLED display).

    Summary
    If you say a "monitor is a display," you would generally be understood to mean that a monitor contains a 
    display as one of its components.

    If you say a "display is a monitor," it might be less accurate because a display is just the screen 
    component, whereas a monitor includes additional elements like casing, ports, and sometimes speakers.

    So, in essence, all monitors have displays, but not all displays are monitors.

    --
    Sincerely,
    Bot (2023.09.04 ChatGPT-4)
    """

    logger = logging.getLogger(__name__)

    DEFAULT_REPR_KEY_LENGTH = 5
    DEFAULT_REPR_VALUE_LENGTH = 18

    def __init__(self, index, x, y, width, height) -> None:

        self.index = index

        Device.__init__(self, name=f"monitor_{self.index}")
        SurfaceMixin.__init__(self, x, y, width, height)

        self.orientation = DisplayType.Horizontal if self.width > self.height else DisplayType.Vertical
        self.aspect_ratio = Fraction(self.width, self.height)

    @abstractmethod
    def get_surface_image(self, scalar):
        pass

    @staticmethod
    def scale_surface_image(image, scalar):
        width, height = image.size
        scaled_width, scaled_height = int(width * scalar), int(height * scalar)
        return image.resize((scaled_width, scaled_height))
    
    def as_dict(self):
        return {    
            "index": self.index,        
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "orientation": self.orientation,
            "aspect_ratio": self.aspect_ratio
        }
    
    def __repr__(self) -> str:
        """ A hilariously dumb way of trying to convince someone the CacheMixin is good. """
        if not (instances := self.cache[self.__class__]):
            return f"{self.__class__.__name__}({', '.join(str(k) + '=' + str(v) for k, v in self.as_dict().items())})"
        max_key_lens, max_value_lens = [], []
        for _, instance in instances.items():
            max_key_lens = [
                max(max_key_lens[i] if max_key_lens else self.DEFAULT_REPR_KEY_LENGTH, len(str(k))) 
                for i, k in enumerate(instance.as_dict().keys())
            ]
            max_value_lens = [
                max(max_value_lens[i] if max_value_lens else self.DEFAULT_REPR_VALUE_LENGTH, len(str(v))) 
                for i, v in enumerate(instance.as_dict().values())
            ]
        return "{}({})".format(
            self.__class__.__name__,
            ", ".join(
                f"{str(k).rjust(max_key_lens[i])}={str(v).ljust(max_value_lens[i])}"
                for i, (k, v) in enumerate(self.as_dict().items())
            )
        )


class ScreenInfoMonitor(Display):

    def __init__(self, index, x, y, width, height, width_mm, height_mm) -> None:
        super().__init__(index, x, y, width, height)
        self.width_mm = width_mm  # can these be calculated?
        self.height_mm = height_mm

    @classmethod
    def get_all_devices(cls):
        devices = [
            cls(
                index=i,
                x=m.__dict__["x"], 
                y=m.__dict__["y"], 
                width=m.__dict__["width"], 
                height=m.__dict__["height"], 
                width_mm=m.__dict__["width_mm"], 
                height_mm=m.__dict__["height_mm"]
            )
            for i, m in enumerate(screeninfo.get_monitors())
        ]
        # I want to shift all the coordinates so that the least x y value is (0, 0) for cropping the full screenshot
        max_negative_x, max_negative_y = min(d.x for d in devices), min(d.y for d in devices)  # optimize TODO
        for device in devices:
            device.x += abs(max_negative_x)
            device.y += abs(max_negative_y)
        return devices
    
    @cached_property
    def bbox_data(self):
        """ A placeholder for a TODO.

        Note:
            I need to change this if I want to allow for removing displays or I can try 
            to refresh the left and top values based on some thread that checks for it? 
            Threading is going to be annoying.
        """
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def get_surface_image(self, scalar=1):
        # Why doesn't this work?
        # image = ImageGrab.grab(bbox=self.bbox_data, all_screens=True)
        image = ImageGrab.grab(all_screens=True).crop(self.bbox_data)
        return self.scale_surface_image(image, scalar=scalar)

    def get_np_image(self, scalar=1):
        np_array = numpy.array(self.get_surface_image(scalar=scalar))
        return cv2.cvtColor(np_array, cv2.COLOR_BGR2RGB)

    def as_dict(self):
        return {
            **super().as_dict(),  # yeah I'm extra
            **{
                "width_mm": self.width_mm,
                "height_mm": self.height_mm
            }
        }


class MssMonitor(Display):

    """ 
    A mixin class for sourcing Displays via MSS.

    Such a faster module than PIL.ImageGrab.
    
    Note:
        BofA Zequan says...
            "Class names be should Pascal Case and any acronyms should only uppercase the first letter."
    """

    IGNORE_FULL_DISPLAY = True  # the first monitor data shows all monitors as one screen.

    # doing this a little weird here
    mms = mss()
    
    @classmethod
    def get_all_devices(cls):
        with mss() as sct:
            # all monitors are a dict: {'left': 0, 'top': 0, 'width': 2560, 'height': 1440}
            return [
                cls(
                    index=i,
                    x=monitor["left"], 
                    y=monitor["top"], 
                    width=monitor["width"], 
                    height=monitor["height"]
                )
                for i, monitor in enumerate(
                    sct.monitors if not cls.IGNORE_FULL_DISPLAY
                    else sct.monitors[1:]
                )
            ]

    @cached_property
    def mss_sct_data(self):
        """ A placeholder for a TODO.

        Note:
            I need to change this if I want to allow for removing displays or I can try to refresh the 
            left and top values based on some thread that checks for it? Threading is going to be annoying.
        """
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}

    def get_surface_image(self, scalar=1):
        # doing this a little weird here
        sct_img = self.mms.grab(self.mss_sct_data)
        image = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
        return self.scale_surface_image(image, scalar=scalar)

    def get_np_image(self, scalar=1):
        np_image = numpy.array(self.get_surface_image(scalar=scalar))
        return cv2.cvtColor(np_image, cv2.COLOR_BGR2RGB)


def monitor_factory(subclass=MssMonitor):

    if not issubclass(subclass, Display):
         raise Exception(f"subclass {subclass} is not a subclass of {Display.__name__}")
    
    class Monitor(subclass):
        
        """
        This represents the current machine's displays. It should inherit from any subclass of Display.

        Not sure how to do this correctly, probably has something TODO with __new__.
        """

        @property
        def filename(self):
            return f"{dt_to_std_str(datetime.now())}_{subclass.__name__}_{self.index}.avi"
        
        def record(self, filename=None, scalar=1, fps=20.0):
            if filename is None:
                filename = self.filename
            super().record(filename=filename, scalar=scalar, fps=fps)
        
    return Monitor


class Camera(Display):

    def __init__(self, index, width, height) -> None:
        super().__init__(index=index, x=0, y=0, width=width, height=height)
        
        self.capture = None
        self.is_open = False

    @classmethod
    def get_all_devices(cls) -> [Self]:
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
                        
                        _, frame = capture.read()
                        width, height, _ = frame.shape
                        capture.release()

                        devices.append(
                            cls(
                                index=index,
                                width=width,
                                height=height
                            )
                        )
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

    def open(self):  # use __with__ method? TODO
        if not self.is_open:
            self.capture = cv2.VideoCapture(self.index)
            self.is_open = True

    def close(self):
        if self.is_open:
            self.capture.release()
            self.is_open = False

    def get_surface_image(self, scalar=1):
        if self.is_open:
            _, frame = self.capture.read()
            # return self.scale_surface_image(frame, scalar=scalar)
            return frame

    def get_np_image(self, scalar=1):
        image = self.get_surface_image(scalar=scalar)
        np_array = numpy.array(image, dtype=numpy.uint8)
        return numpy.array(image)

    def get_live_view(self, scalar=1):
        self.open()
        super().get_live_view(scalar=scalar)
        self.close()
    
    @property
    def filename(self):
        return f"{dt_to_std_str(datetime.now())}_{self.__class__.__name__}_{self.index}.avi"

    def record(self, filename=None, scalar=1, fps=20.0):
        self.open()
        if filename is None:
            filename = self.filename
        super().record(filename=filename, scalar=scalar, fps=fps)
        self.close()


class ChromecastSpeaker:
    pass


class ChromecastMonitor(Display):

    # https://pypi.org/project/PyChromecast/

    # import time
    # import pychromecast

    # # List chromecasts on the network, but don't connect
    # services, browser = pychromecast.discovery.discover_chromecasts()
    # # Shut down discovery
    # pychromecast.discovery.stop_discovery(browser)

    # # Discover and connect to chromecasts named Living Room
    # chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=["Living Room"])
    # [cc.device.friendly_name for cc in chromecasts]
    # ['Living Room']

    # cast = chromecasts[0]
    # # Start worker thread and wait for cast device to be ready
    # cast.wait()
    # print(cast.device)
    # DeviceStatus(friendly_name='Living Room', model_name='Chromecast', manufacturer='Google Inc.', uuid=UUID('df6944da-f016-4cb8-97d0-3da2ccaa380b'), cast_type='cast')

    # print(cast.status)
    # CastStatus(is_active_input=True, is_stand_by=False, volume_level=1.0, volume_muted=False, app_id='CC1AD845', display_name='Default Media Receiver', namespaces=['urn:x-cast:com.google.cast.player.message', 'urn:x-cast:com.google.cast.media'], session_id='CCA39713-9A4F-34A6-A8BF-5D97BE7ECA5C', transport_id='web-9', status_text='')

    # mc = cast.media_controller
    # mc.play_media('http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', 'video/mp4')
    # mc.block_until_active()
    # print(mc.status)
    # MediaStatus(current_time=42.458322, content_id='http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', content_type='video/mp4', duration=596.474195, stream_type='BUFFERED', idle_reason=None, media_session_id=1, playback_rate=1, player_state='PLAYING', supported_media_commands=15, volume_level=1, volume_muted=False)

    # mc.pause()
    # time.sleep(5)
    # mc.play()

    # # Shut down discovery
    # pychromecast.discovery.stop_discovery(browser)

    def __init__(self, index, width, height, services, uuid, model_name, friendly_name, host, port, cast_type, manufacturer) -> None:
        
        super().__init__(index=index, x=0, y=0, width=width, height=height)

        self.services = services
        self.uuid = uuid
        self.model_name = model_name
        self.friendly_name = friendly_name
        self.host = host
        self.port = port
        self.cast_type = cast_type
        self.manufacturer = manufacturer

    @classmethod
    def get_all_devices(cls) -> [Self]:
        devices = []
        services, browser = pychromecast.discovery.discover_chromecasts()
        # Shut down discovery
        for i, cast_info in enumerate(services):
            width = 1
            height = 1
            devices.append(
                cls(
                    index=i,
                    width=width,
                    height=height,
                    services=cast_info.services,
                    uuid=cast_info.uuid,
                    model_name=cast_info.model_name,
                    friendly_name=cast_info.friendly_name,
                    host=cast_info.host,
                    port=cast_info.port,
                    cast_type=cast_info.cast_type,
                    manufacturer=cast_info.manufacturer,
                )
            )
        pychromecast.discovery.stop_discovery(browser)
        return devices

    def get_surface_image(self, scalar=1):
        pass

    def get_np_image(self, scalar=1):
        pass

    def as_dict(self):
        return {
            **super().as_dict(),
            **{
                "services": self.services,
                "uuid": self.uuid,
                "model_name": self.model_name,
                "friendly_name": self.friendly_name,
                "host": self.host,
                "port": self.port,
                "cast_type": self.cast_type,
                "manufacturer": self.manufacturer
            }
        }


class ApplicationWindow(Display):

    def __init__(self, window) -> None:

        self.window = window
        self.hwnd = window._hWnd

        # I'm supplying dummy values to the Display init because they're going 
        # to constantly update anyway, might want to change this behavior. We're 
        # also gonna use hwnd as the cache key and I might want to extend this 
        # to audio and video. TODO
        super().__init__(index=self.hwnd, x=0, y=0, width=1, height=1)

        self.graft_window_methods()

    @property
    def x(self):
        return self.window.left
    
    @property
    def y(self):
        return self.window.top
    
    @property
    def width(self):
        return self.window.width
    
    @property
    def height(self):
        return self.window.height

    def graft_window_methods(self):
        """ 
        This is here purely for my convenience during testing. I did want to inherit
        the pygetwindow.Win32Window class, but not sure how that'll affect things. TODO
        """
        method_names = [
            "activate", "area", "bottom", "bottomleft", "bottomright", "box", "center", 
            "centerx", "centery", "close", "height", "hide", "isActive", "isMaximized", 
            "isMinimized", "left", "maximize", "midbottom", "midleft", "midright", 
            "midtop", "minimize", "move", "moveRel", "moveTo", "resize", "resizeRel", 
            "resizeTo", "restore", "right", "show", "size", "title", "top", "topleft", 
            "topright", "visible", "width"
        ]
        for method_name in method_names:
            method = getattr(self.window, method_name)
            setattr(self, f"window_{method_name}", method)

    @classmethod
    def get_all_devices(cls):
        """
        This is the first time I really need to consider the refreshing of devices at 
        runtime. KIM that this discovery process may lead to get_all_devices changes.
        
        Here are some pygetwindow methods that can be used to speed up window retreival:
            getActiveWindow
            getActiveWindowTitle
            getWindowsAt
            getWindowsWithTitle
            getAllWindows
            getAllTitles
        """
        return [
            cls.get_cache().get(window._hWnd, ApplicationScreen(window))
            for window in pygetwindow.getAllWindows()
            if 0 not in [window.width, window.height]
        ]
    
    @property
    def bbox_data(self):
        """ A placeholder for a TODO.

        Note:
            I need to change this if I want to allow for removing displays or I can try 
            to refresh the left and top values based on some thread that checks for it? 
            Threading is going to be annoying.

            Also unlike ScreenInfoMonitor, this is a property and not a cached_property.
        """
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def get_surface_image(self, scalar):
        # This does not account for obfuscation from  overlapping windows.
        # image = ImageGrab.grab(bbox=self.bbox_data)
        # return self.scale_surface_image(image, scalar=scalar)

        # Get the window's dimensions
        left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
        w = right - left
        h = bot - top

        # Create a device context
        hwnd_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        # Create a bitmap and select it into the device context
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(save_bitmap)

        # BitBlt the window image from the window's DC to our compatible DC
        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

        # Convert the PyCBitmap to a PIL Image
        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_str, 'raw', 'BGRX', 0, 1
        )

        # Cleanup
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwnd_dc)

        return image
    
    def get_np_image(self, scalar=1):
        np_array = numpy.array(self.get_surface_image(scalar=scalar))
        return cv2.cvtColor(np_array, cv2.COLOR_BGR2RGB)


class Recorder:

    """ Not sure if I should do it like this or like the visualizer. TODO """

    def __init__(self, filepath, fps, width, height, codec) -> None:
        self.filepath = filepath
        self.codec = codec
        self.fps = fps
        self.width = width
        self.height = height

    @cached_property
    def resolution(self):
        return (self.width, self.height)
    
    @cached_property
    def output(self):
        return cv2.VideoWriter(self.filepath, self.codec, self.fps, self.resolution)

    def write(self, frame):
        """ Input an image as a np array to write to the file. """
        self.output.write(frame)

    def record(self, surface: SurfaceMixin, scalar):
        while True:

            start_time = datetime.now()

            frame = surface.get_np_image(scalar=scalar)
            self.output.write(frame)
            cv2.imshow('Screen Recorder', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            print(self)
            height, width, channels = frame.shape
            print(f"width={width}, height={height}, channels={channels}")

            end_time = datetime.now()
            elapsed_time = (end_time - start_time).microseconds / 1_000_000
            print(f"{1/elapsed_time:.2f} fps")

        self.output.release()
        cv2.destroyAllWindows()

    def as_dict(self):
        return {
            "filepath": self.filepath,
            "codec": self.codec,
            "fps": self.fps,
            "resolution": self.resolution
        }

    def __repr__(self):
        return repr_helper(self)


class XvidRecorder(Recorder):
    
    """ An unfortunate name, revise. TODO """

    def __init__(self, filepath, fps, width, height) -> None:
        super().__init__(filepath, fps, width, height, codec=cv2.VideoWriter_fourcc(*'XVID'))
