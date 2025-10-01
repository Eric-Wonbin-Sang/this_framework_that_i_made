# This Framework That I Made

TODO: this is getting unruly fast. It makes more sense to split this project up into standardized modules that work together in this framework.

My Main Goal: get, set, combine, stream and/or execute anything or everything easily anywhere

to test this:

```
# all in the repo top dir
# create the framework's egg:
pip install -e .

# run the test script:
python -m tests.test

# generate requirements
pip-compile pyproject.toml --output-file=requirements.txt
# install requirements
pip install -r requirements.txt
# to get name/version info
pip show psutil
```

# everything under this is out of date, fix!

# computer_recorder

A project for capturing anything on your computer.

Ideally, I want to be able to capture:
 - [X] input audio devices
 - [X] output audio devices
 - [X] webcams
 - [X] monitors
 - [ ] windows
 - [ ] windows with audio
 - [ ] gifs, images, and video
 - [ ] youtube videos
 - [ ] key and mouse logger

And for processing these, I'd want:
 - [ ] ways to view any device output
 - [ ] sending data via NDI
 - [ ] a way to create scenes like OBS
 - [ ] direct streaming to twitch (this is a stretch)

This project heavily utilizes OOP and follows something like this:

- CacherMixin
    - Device
        - Display, SurfaceMixin
            - Display, DisplayType
                - VideoDevice
                    - Monitor via monitor_factory:
                        - ScreenInfoMonitor
                        - MssMonitor
            - ApplicationScreen
       - Camera
       - Chromecast
            - Chromecastspeaker
            - ChromecastMonitor
       - AudioDeviceType
            - AudioDevice
                - Microphone
                - Speaker (which need LoopbackSpeakers)
                - LoopbackSpeaker
- Users
    - Viewers
        - SurfaceMixin
            - Recorder
                - Xvid Recorder
            - AudioVisualizer
                - AudioGraphVisualizer
    - Senders
        - AudioTransmitter
        - AudioNdiTransmitter


NEW STRUCTURE




This structure is obviously very complicated, but the idea is that everything has some 
output which can be formed in some standard way to reuse things that inherently require 
the same data to view, send, etc. 

I think there should definitely be a better name for Device, as I'm not really sure an
application windows should be called a device. 


this is out of date:

| module                      | command                              |
| --------------------------- | ------------------------------------ |
| numpy                       | pip install numpy                    |
| pyaudiowpatch               | pip install PyAudioWPatch            |
| pygetwindow                 | pip install pygetwindow              |
| pyautogui                   | pip install PyAutoGUI                |
| cv2                         | pip install opencv-python            |
| screeninfo                  | pip install screeninfo               |
| matplotlib                  | pip install matplotlib               |
| mss                         | pip install pip install mss          |
| pychromecast                | pip install pip install PyChromecast |
| win32gui, win32ui, win32con | pip install pywin32                  |


## Reference

look into this:
 - pip install ndi-python
 - https://github.com/skorokithakis/catt


## Note

There is an issue with recording output devices in windows, which is why I had to use the PyAudioWPatch fork of PyAudio. Here's more details in this [stack overflow question](https://stackoverflow.com/questions/26573556/record-speakers-output-with-pyaudio)

Solution:
 - [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch) GitHub repo
 - Here is some [example code](https://github.com/s0d3s/PyAudioWPatch/blob/master/examples/pawp_record_wasapi_loopback.py) to get Windows speakers to work
