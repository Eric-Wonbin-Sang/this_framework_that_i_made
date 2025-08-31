from this_framework_that_i_made.python import PythonRuntimeEnv
from this_framework_that_i_made.systems import WindowsSystem
from this_framework_that_i_made.audio import HostApi


def main():
    # runtime_env = PythonRuntimeEnv()
    # print(runtime_env)

    # system = OperatingSystem()
    system = WindowsSystem()
    # print(system)
    # print("\n".join(map(str, system.get_windows_audio_devices())))
    # print("\n".join(map(str, system.audio_system.default_endpoints)))

    print("\n".join(map(str, system.audio_system.default_input_endpoints)))
    print("-" * 100)
    print("\n".join(map(str, system.audio_system.default_output_endpoints)))

    print("done")


if __name__ == "__main__":
    main()
