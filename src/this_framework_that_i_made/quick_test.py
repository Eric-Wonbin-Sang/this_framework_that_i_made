import time
import warnings

import comtypes

from this_framework_that_i_made.audio_helpers.ms_audio_mappings.IAudioSessionNotification import AudioSessionNotification

try:
    import psutil  # type: ignore
except ModuleNotFoundError:
    psutil = None

from this_framework_that_i_made.audio_helpers.ms_audio_mappings.IMMDeviceEnumerator import DeviceRole, DeviceType, PyMmDeviceEnumerator
from this_framework_that_i_made.audio_helpers.ms_audio_mappings.ms_audio_common import PROPERTYKEY
from this_framework_that_i_made.audio_helpers.volume_helpers import WindowVolumeControllerFactory
from this_framework_that_i_made.monitors import wait_for_fps_target
from this_framework_that_i_made.python import PythonRuntimeEnv
from this_framework_that_i_made.systems import WindowsSystem


def test_audio_devices_and_endpoint():
    system = WindowsSystem()

    # testing = "input"
    testing = "output"
    # testing = "processes"

    device = system.audio_system.audio_devices[21]
    if testing == "input":
        # read from the default loopback
        audio_endpoint = device.audio_endpoints[3]
        for block in audio_endpoint.get_pcm_blocks():
            print(block)
    if testing == "output":
        audio_endpoint = device.audio_endpoints[2]
        controller = audio_endpoint.volume_controller
        print(controller)
    if testing == "processes":
        controllers = WindowVolumeControllerFactory.get_process_volume_controllers()
        controller = WindowVolumeControllerFactory.get_process_volume_controller_by_name("zen")
        print(controller)


def test_runtime_env():
    runtime_env = PythonRuntimeEnv()
    print(runtime_env)


def test_audio_capturing():
    from this_framework_that_i_made.audio_helpers.wasapi import LoopbackStream
    system = WindowsSystem()
    audio_devices = system.audio_system.default_input_devices
    audio_device = audio_devices[2]
    with LoopbackStream(
        device_name=audio_device.name,
        block_ms=20,
        samplerate=audio_device.default_sample_rate,
        channels=audio_device.channels,
    ) as blocks:
        print(blocks)
        for block in blocks:
            print(block)

    with AudioDeviceStreamer(audio_device, sample_rate=48_000, channels=2, encoding="i16", block_ms=20, as_bytes=True) as streamer:
        for payload in streamer.stream():
            print(payload)



def get_friendly_name(dev) -> str:
    from pycaw.pycaw import AudioUtilities
    with warnings.catch_warnings():
        # suppress deprecation warning for GetAllDevices
        warnings.simplefilter("ignore", UserWarning)
        
        # get the unique endpoint ID
        dev_id = dev.GetId()
        
        # AudioUtilities.GetAllDevices() yields AudioDevice wrappers
        for d in AudioUtilities.GetAllDevices():
            if d.id == dev_id:
                return d.FriendlyName
        return "Unknown Device"



def test_audio_utilities():
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        print(session.Process and session.Process.name(), session)

    # device = AudioUtilities.GetSpeakers()
    # volume = device.EndpointVolume
    # print(f"Audio output: {device.FriendlyName}")
    # print(f"- Muted: {bool(volume.GetMute())}")
    # print(f"- Volume level: {volume.GetMasterVolumeLevel()} dB")
    # print(f"- Volume range: {volume.GetVolumeRange()[0]} dB - {volume.GetVolumeRange()[1]} dB")
    # volume.SetMasterVolumeLevel(-20.0, None)
    # print(sessions)

    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER

    device = AudioUtilities.GetSpeakers()
    name = get_friendly_name(device)
    print(f"Device found: {name}")
    
    # now get the endpoint-volume interface
    interface = device.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
    )
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    
    print("Muted?:", "Yes" if volume.GetMute() else "No")
    print("Level (dB):", volume.GetMasterVolumeLevel())
    print("Range (dB):", volume.GetVolumeRange())
    
    print("Setting to -20 dB…")
    volume.SetMasterVolumeLevel(-1.0, None)
    print("New level:", volume.GetMasterVolumeLevel())


def test_per_app_recording():
    import wave
    from this_framework_that_i_made.audio_helpers.wasapi_per_app_loopback import PerAppLoopback

    if psutil is None:
        raise RuntimeError("psutil is required for test_per_app_recording(); install it with `pip install psutil`.")

    # Find the PID you want (example: first Spotify process with audio)
    target_name = "Spotify.exe"
    pid = next(p.info["pid"] for p in psutil.process_iter(["name", "pid"]) if p.info["name"] == target_name)

    with PerAppLoopback(pid=pid, include_tree=True, chunk_ms=10) as cap, \
        wave.open("spotify.wav", "wb") as wf:
        wf.setnchannels(cap.channels)
        wf.setsampwidth(2)             # int16
        wf.setframerate(cap.sample_rate)

        # record ~5 seconds
        bytes_needed = 5 * cap.sample_rate * cap.channels * 2
        written = 0
        for chunk in cap:
            wf.writeframes(chunk)
            written += len(chunk)
            if written >= bytes_needed:
                break

    print("Wrote spotify.wav")


def test_pyaudio_patch():
    # Spinner is a helper class that is in the same examples folder.
    # It is optional, you can safely delete the code associated with it.

    import pyaudiowpatch as pyaudio
    import time
    import wave

    DURATION = 5.0
    CHUNK_SIZE = 512

    filename = "loopback_record.wav"

    with pyaudio.PyAudio() as p:
        """
        Create PyAudio instance via context manager.
        Spinner is a helper class, for `pretty` output
        """
        try:
            # Get default WASAPI info
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("Looks like WASAPI is not available on the system. Exiting...")
            exit()
        
        # Get default WASAPI speakers
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in p.get_loopback_device_info_generator():
                """
                Try to find loopback device with same name(and [Loopback suffix]).
                Unfortunately, this is the most adequate way at the moment.
                """
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                print("Default loopback output device not found.\n\nRun `python -m pyaudiowpatch` to check available devices.\nExiting...\n")
                exit()
                
        print(f"Recording from: ({default_speakers['index']}){default_speakers['name']}")
        
        wave_file = wave.open(filename, 'wb')
        wave_file.setnchannels(default_speakers["maxInputChannels"])
        wave_file.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wave_file.setframerate(int(default_speakers["defaultSampleRate"]))
        
        def callback(in_data, frame_count, time_info, status):
            """Write frames and return PA flag"""
            wave_file.writeframes(in_data)
            return (in_data, pyaudio.paContinue)
        
        with p.open(format=pyaudio.paInt16,
                channels=default_speakers["maxInputChannels"],
                rate=int(default_speakers["defaultSampleRate"]),
                frames_per_buffer=CHUNK_SIZE,
                input=True,
                input_device_index=default_speakers["index"],
                stream_callback=callback
        ) as stream:
            """
            Opena PA stream via context manager.
            After leaving the context, everything will
            be correctly closed(Stream, PyAudio manager)            
            """
            print(f"The next {DURATION} seconds will be written to {filename}")
            time.sleep(DURATION) # Blocking execution while playing
        
        wave_file.close()


def test_PyAudioWrapper():
    from this_framework_that_i_made.audio import PyAudioWrapper
    p = PyAudioWrapper()
    groups = p.get_device_groups()
    print(p)


def test_processes():
    system = WindowsSystem()
    processes = system.processes_with_audio_controls
    process = next(p for p in processes if "zen" in (p.name or "").lower())
    
    while True:
        for p in processes:
            if p.pid == 0:
                continue
            controller = p.volume_controller
            if not controller.is_max_volume():
                controller.increment_volume()
            else:
                controller.set_min_volume()
            print(f"{p.name} {controller.get_volume()} {controller.get_range()}")
        time.sleep(.02)


def test_monitors():
    system = WindowsSystem()
    monitors = system.monitors
    print("\n".join(map(str, (m.as_dict() for m in monitors))))
    print(monitors)

    for screenshot in monitors[0].yield_content():
        print(screenshot)


def test_windows():
    system = WindowsSystem()
    print(system)

    windows = system.windows
    window = next(filter(lambda w: "Zen Browser".lower() in w.title.lower(), windows))

    for content in window.yield_audio_content():
        print(content)

    # for content in system.windows[0].yield_video_content(fps=10):
    #     print(content)


def test_app_audio():

    device_enumerator = PyMmDeviceEnumerator.create()
    print(device_enumerator)
    
    comms = device_enumerator.get_default_output_device(role=DeviceRole.E_COMMUNICATIONS)
    multimedia = device_enumerator.get_default_output_device(role=DeviceRole.E_MULTIMEDIA)
    
    comms_session_manager = comms.get_audio_session_manager_2()
    multimedia_session_manager = multimedia.get_audio_session_manager_2()

    devices = device_enumerator.get_devices()
    device = devices[0]
    property_store = device.open_property_store()
    print(property_store.as_dict())

    for device in devices:
        print(device)
        session_manager = device.get_audio_session_manager_2()
        print(session_manager)
        try:
            enumerator = session_manager.get_session_enumerator(device)
            sessions = enumerator.get_sessions2()
            if not sessions:
                print("  (no per-app sessions)")
                continue
            for session in sessions:
                details = {"state": session.get_state().name, "display": session.get_display_name()}
                try:
                    pid = session.get_process_id()
                except Exception:
                    pid = None
                details["pid"] = pid
                if psutil is not None and pid:
                    try:
                        details["process_name"] = psutil.Process(pid).name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        details["process_name"] = "n/a"
                print("  ", details)
        except Exception as e:
            print(f"  failed to enumerate sessions: {e}")
        print()

    default_output_device = device_enumerator.get_default_output_device()
    print(default_output_device)
    # session_manager = PyAudioSessionManager2.get_from_mm_device(default_output_device)
    # print(session_manager)


def test_session_registers():

    def register_everywhere():
        enumerator = PyMmDeviceEnumerator.create()
        devices = enumerator.get_devices(device_type=DeviceType.OUTPUT)

        callbacks = []             # keep references alive!
        managers = []

        for dev in devices:
            mgr = dev.get_audio_session_manager_2()
            callback = AudioSessionNotification(dev)   # keep a ref to this!
            mgr.register_session_notification(callback)

            print(f'registered notification on {tag}')
            callbacks.append(cb)
            managers.append((mgr, cb))

            # Optional: dump current sessions immediately
            try:
                enum = mgr.get_session_enumerator(dev)
                for ctrl in enum.get_sessions2():
                    print(f'    existing session: pid={ctrl.get_process_id()} display={ctrl.get_display_name()}')
            except Exception as exc:
                print(f'    (no existing sessions: {exc})')

        return managers  # stash so we can unregister later or keep alive

    comtypes.CoInitialize()
    registrations = register_everywhere()
    try:
        while True:
            time.sleep(0.5)    # you can do other work here
    finally:
        for mgr, cb in registrations:
            try:
                mgr.unregister_session_notification(cb)
            except Exception:
                pass
        comtypes.CoUninitialize()


def main():
    # test_audio_devices_and_endpoint()
    # test_runtime_env()
    # test_audio_capturing()
    # test_audio_utilities()
    # test_per_app_recording()
    # test_pyaudio_patch()
    # test_PyAudioWrapper()
    # test_processes()
    # test_monitors()
    # test_windows()
    # test_app_audio()
    test_session_registers()


if __name__ == "__main__":
    main()
