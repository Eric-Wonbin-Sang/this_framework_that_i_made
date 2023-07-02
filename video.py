import cv2
import numpy
import logging
import pyautogui
import screeninfo
import pygetwindow

from PIL import ImageGrab

from device import Device


class Display(Device):

    logger = logging.getLogger(__name__)

    cache = {}

    def __init__(self, data):

        self.x = data.get("x")
        self.y = data.get("y")
        self.width = data.get("width")
        self.height = data.get("height")
        self.width_mm = data.get("width_mm")
        self.height_mm = data.get("height_mm")
        self.is_primary = data.get("is_primary")

        super().__init__(name=data.get("name"))

    @classmethod
    def get_all_devices(cls):
        for m in screeninfo.get_monitors():
            if device := cls.cache.get(m.__dict__["name"]):
                yield device
            else:
                yield cls(m.__dict__)  # could I inherit this class? TODO

    def get_default_device(self):
        for device in self.get_all_devices():
            if device.is_primary:
                return device
        self.logger.error(f"This is weird, no default {self.__class__.__name__} instance?")

    def get_surface(self):
        pass


# Set the application's name or window title
app_name = "Application Name"
# Set the window's title or partial title
window_title = "Window Title"


# Find the specific application's window
def find_application_window(app_name, window_title):
    try:
        app = pygetwindow.getWindowsWithTitle(window_title)
        if len(app) > 0:
            return app[0]
    except pygetwindow.PyGetWindowException:
        pass

    try:
        app = pygetwindow.getWindowsWithTitle(app_name)
        if len(app) > 0:
            return app[0]
    except pygetwindow.PyGetWindowException:
        pass

    return None


# Capture the window and process the image
def capture_window(app_name, window_title):
    window = find_application_window(app_name, window_title)

    if window is None:
        print("Window not found.")
        return

    print("Capturing window. Press Ctrl+C to stop.")

    try:
        while True:
            # Capture the window image
            screenshot = pyautogui.screenshot(region=(window.left, window.top, window.width, window.height))
            image = numpy.array(screenshot)
            # Process the image here (e.g., display, save to file, perform analysis, etc.)
            # Replace the print statement below with your desired image processing code
            print("Window image:", image)
            cv2.imshow("Captured Window", image)

            # Break the loop if 'q' is pressed
            if cv2.waitKey(1) == ord('q'):
                break
    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()


# Call the capture_window function with your desired application name and window title
capture_window(app_name, window_title)
