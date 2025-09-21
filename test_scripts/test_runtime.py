import time
from this_framework_that_i_made.python import PythonRuntimeEnv
from this_framework_that_i_made.systems import WindowsSystem



def test_runtime_env():
    runtime_env = PythonRuntimeEnv()

    print(runtime_env)
    for d in runtime_env.distributions:
        print(d)


def test_processes():
    system = WindowsSystem()
    processes = system.processes_with_audio_controls
    process = next(p for p in processes if "zen" in (p.name or "").lower())
    print(process)
    
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


def main():
    # test_runtime_env()
    test_processes()


if __name__ == "__main__":
    main()
