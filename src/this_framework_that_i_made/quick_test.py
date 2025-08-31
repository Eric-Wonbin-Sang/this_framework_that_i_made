from this_framework_that_i_made.python import PythonRuntimeEnv
from this_framework_that_i_made.systems import WindowsSystem


def main():
    # system = OperatingSystem()
    system = WindowsSystem()
    print(system)
    print("\n".join(map(str, system.get_windows_audio_devices())))

    runtime_env = PythonRuntimeEnv()
    print(runtime_env)

if __name__ == "__main__":
    main()
