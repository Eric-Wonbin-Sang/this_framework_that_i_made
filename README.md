# computer_recorder

A project for capturing anything on your computer.

Ideally, I want to be able to capture:
 - [X] input devices
 - [X] output devices
 - [ ] webcams
 - [ ] monitors
 - [ ] windows with audio
 - [ ] gifs, images, and video
 - [ ] youtube videos

And for processing these, I'd want:
 - [ ] sending data via NDI
 - [ ] a way to create scenes like OBS
 - [ ] direct streaming to twitch (this is a stretch)

|    module     |          command          |
|:-------------:|:-------------------------:|
|     numpy     |     pip install numpy     |
| pyaudiowpatch | pip install PyAudioWPatch |
|  pygetwindow  |  pip install pygetwindow  |
|   pyautogui   |   pip install PyAutoGUI   |
|      cv2      | pip install opencv-python |
|  screeninfo   |  pip install screeninfo   |


## Reference

look into this:
 - pip install ndi-python


## Note

There is an issue with recording output devices in windows, which is why I had to use the PyAudioWPatch fork of PyAudio. Here's more details in this [stack overflow question](https://stackoverflow.com/questions/26573556/record-speakers-output-with-pyaudio)

Solution:
 - [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch) GitHub repo
 - Here is some [example code](https://github.com/s0d3s/PyAudioWPatch/blob/master/examples/pawp_record_wasapi_loopback.py) to get Windows speakers to work
