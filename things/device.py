from __future__ import annotations
from abc import ABC

import sys
import logging

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


class CacherMixin(ABC):

    """
    A mixin that saves references to instances of every one of its subclasses.

    Here's the idea:
        The cache will be a dict of subclass to its instance. It won't be a list though, since what 
        happens if we want to reference a specific instance and instances are being deleted? All of
        the instances will be shifted. To avoid this, the cache will be a dict that appends instances
        with an incrementing integer key, but each new key will be: list(cache.keys())[-1] + 1.

        This is probably already a thing, but it sounds cool so I'm just going to make it. I might
        run into a problem when an object is "deleted", but the key's value reference still exists.
        Might be cool to look into the c pointer stuff if needed?

        Also, why the need for a cache? It makes more sense that instances should be easily referenced 
        by whatever context they're in. If you need a cache, you should probably pass in more things.

        But I guess if you're looking for a cache, here it is.
    """

    cache = {}  # Class-level attribute to store instances

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Call the parent class's constructor
        self.add_to_cache()  # Add the instance to the cache

    def add_to_cache(self):
        """ Add the instance to the cache. """
        cls = self.__class__  # Get the class of the instance
        if cls not in CacherMixin.cache:
            CacherMixin.cache[cls] = {}  # Initialize the cache for this class if it doesn't exist

        if len(curr_class_cache := CacherMixin.cache[cls]) == 0:
            curr_class_cache[0] = self
        else:
            curr_class_cache[list(curr_class_cache.keys())[-1] + 1] = self

    @classmethod
    def get_cache(cls):
        """ Get the cache for this class. """
        return CacherMixin.cache.get(cls, {})


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

    def __repr__(self):
        return f'{self.__class__.__name__}(name={self.name})'
