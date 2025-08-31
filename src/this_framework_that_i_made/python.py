from dataclasses import dataclass
import importlib.metadata
import platform
from typing import Any, Dict, List

from .generics import SavableObject, ensure_savable


@ensure_savable
@dataclass
class Distribution(SavableObject):
    metadata: Dict  # TODO: sloppy, redo
    name: str
    requires: str
    version: str

    @classmethod
    def create_instance(cls, metadata):
        return cls(
            metadata=metadata,
            name=metadata.name,
            requires=metadata.requires,
            version=metadata.version,
        )

    def __str__(self):
        name = self.name
        requires = self.requires
        version = self.version
        return f"{self.__class__.__name__}({name=}, {requires=}, {version=})"


@ensure_savable
@dataclass
class PythonRuntimeEnv(SavableObject):

    python_version: str = platform.python_build()
    distributions: List[Any] = None

    def __post_init__(self):
        self.distributions = self._get_distributions()

    @staticmethod
    def _get_distributions():
        return [Distribution.create_instance(metadata) for metadata in importlib.metadata.distributions()]
