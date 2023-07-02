from __future__ import annotations

import logging


class Device:

    logger = logging.getLogger(__name__)

    cache = {}  # this caches every audio device child instance as an audio device object. Might want to change. TODO

    def __init__(self, name):
        self.name = name
        if self.name not in self.cache:
            self.cache[self.name] = self

    @classmethod
    def get_available_device_names(cls):
        return list(cls.cache.keys())

    @classmethod
    def get_all_devices(cls):
        raise Exception(f"{cls.__name__} base method called, should be a child's method.")

    @classmethod
    def get_default_device(cls):
        raise Exception(f"{cls.__name__} base method called, should be a child's method.")

    @classmethod
    def populate_cache(cls):
        cls.cache = {m.name: m for m in cls.get_all_devices()}

    @classmethod
    def print_cache(cls):
        print(f"{cls.__name__}(")
        print("\n".join([f"\t{k}: {v}" for k, v in cls.cache.items()]))
        print(")")

    @classmethod
    def search_for(cls, target_name) -> Device:
        target_device = None
        for name, device in cls.cache.items():
            if target_name.lower() in name.lower():
                if target_device is None:
                    target_device = device
                else:
                    cls.logger.warning(
                        f"Found multiple devices that could be found with name {target_device}, consider refining name"
                    )
                    break
        return target_device
