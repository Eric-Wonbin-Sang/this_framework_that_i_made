from this_framework_that_i_made.python import PythonRuntimeEnv
from this_framework_that_i_made.systems import WindowsSystem
from this_framework_that_i_made.audio import AudioDeviceStreamer, HostApi

import soundcard

mics = soundcard.default_microphone()
speakers = soundcard.all_speakers()


def main():
    # runtime_env = PythonRuntimeEnv()
    # print(runtime_env)

    # system = OperatingSystem()
    system = WindowsSystem()
    print(system)
    # print("\n".join(map(str, system.get_windows_audio_devices())))

    print("audio tests", "-" * 100)
    print("\n".join(map(str, system.audio_system.default_input_endpoints)))
    print("-" * 100)
    print("\n".join(map(str, system.audio_system.default_output_endpoints)))

    print("done")

    # audio_device = system.audio_system.default_input_devices[0]
    audio_devices = system.audio_system.default_output_devices
    audio_device = audio_devices[2]

    with AudioDeviceStreamer(audio_device, sample_rate=48_000, channels=2, encoding="i16", block_ms=20, as_bytes=True) as streamer:
        for payload in streamer.stream():
            print(payload)


if __name__ == "__main__":
    main()
