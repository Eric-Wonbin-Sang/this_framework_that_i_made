import cv2
import numpy
import pyautogui

from PIL import ImageGrab

from audio import Speaker
from video import Display


def example_0():

    # Specify resolution
    resolution = (1920, 1080)

    # Specify video codec
    codec = cv2.VideoWriter_fourcc(*"XVID")

    # Specify name of Output file
    filename = "Recording.avi"

    # Specify frames rate. We can choose any
    # value and experiment with it
    fps = 60.0

    # Creating a VideoWriter object
    out = cv2.VideoWriter(filename, codec, fps, resolution)

    # Create an Empty window
    cv2.namedWindow("Live", cv2.WINDOW_NORMAL)

    # Resize this window
    cv2.resizeWindow("Live", 480, 270)

    while True:
        # Take screenshot using PyAutoGUI
        img = pyautogui.screenshot()

        # Convert the screenshot to a numpy array
        frame = numpy.array(img)

        # Convert it from BGR(Blue, Green, Red) to
        # RGB(Red, Green, Blue)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Write it to the output file
        out.write(frame)

        # Optional: Display the recording screen
        cv2.imshow('Live', frame)

        # Stop recording when we press 'q'
        if cv2.waitKey(1) == ord('q'):
            break

    # Release the Video writer
    out.release()

    # Destroy all windows
    cv2.destroyAllWindows()


def scratch_paper():

    # example_0()

    # screenshot = ImageGrab.grab(all_screens=True)
    # screenshot.show()

    print(Display.get_all_devices())


def main():
    pass


if __name__ == '__main__':
    scratch_paper()
    # main()
