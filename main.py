from structure.systems import OperatingSystem, WindowsSystem


def main():
    # system = OperatingSystem()
    system = WindowsSystem()
    print(system)
    print("\n".join(map(str, system.get_windows_audio_devices())))

if __name__ == "__main__":
    main()
