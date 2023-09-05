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

This structure is obviously very complicated, but the idea is that everything has some 
output which can be formed in some standard way to reuse things that inherently require 
the same data to view, send, etc. 

I think there should definitely be a better name for Device, as I'm not really sure an
application windows should be called a device. 



this is out of date:

|    module     |          command          |
|:-------------:|:-------------------------:|
|     numpy     |     pip install numpy     |
| pyaudiowpatch | pip install PyAudioWPatch |
|  pygetwindow  |  pip install pygetwindow  |
|   pyautogui   |   pip install PyAutoGUI   |
|      cv2      | pip install opencv-python |
|  screeninfo   |  pip install screeninfo   |
|  matplotlib   |  pip install matplotlib   |


## Reference

look into this:
 - pip install ndi-python


## Note

There is an issue with recording output devices in windows, which is why I had to use the PyAudioWPatch fork of PyAudio. Here's more details in this [stack overflow question](https://stackoverflow.com/questions/26573556/record-speakers-output-with-pyaudio)

Solution:
 - [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch) GitHub repo
 - Here is some [example code](https://github.com/s0d3s/PyAudioWPatch/blob/master/examples/pawp_record_wasapi_loopback.py) to get Windows speakers to work
