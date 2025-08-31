from collections import defaultdict
from dataclasses import fields, is_dataclass
from typing import Any


class staticproperty(property):
    def __get__(self, obj, objtype=None):
        return self.fget()


def group_by_name(objects):
    groups = defaultdict(list)
    for obj in objects:
        groups[obj.name].append(obj)
    return groups


def _is_self_dataclass_class(cls) -> bool:
    """True if `cls` is decorated with @dataclass itself (not just inheriting)."""
    return (
        is_dataclass(cls)
        and ("__dataclass_fields__" in cls.__dict__ or "__dataclass_params__" in cls.__dict__)
    )


def ensure_savable(cls):
    """Validate that a class is a dataclass (itself) or defines as_dict()."""
    if not (_is_self_dataclass_class(cls) or hasattr(cls, "as_dict")):
        raise TypeError(f"{cls.__name__} must be a dataclass or define as_dict()")
    return cls


class SavableObject:

    def _pretty(self, obj: Any, indent: int = 0) -> str:
        pad = " " * indent
        # Only treat as dataclass if the object's class is itself a dataclass
        if is_dataclass(obj) and _is_self_dataclass_class(type(obj)):
            # Pretty print nested dataclasses too
            cls = obj.__class__.__name__
            inner = []
            for f in fields(obj):
                v = getattr(obj, f.name)
                inner.append(f"{pad}  {f.name} = {self._pretty(v, indent + 2)}")
            return f"{cls}(\n" + ",\n".join(inner) + f"\n{pad})"
        elif isinstance(obj, (list, tuple, set)):
            open_, close_ = ("[", "]") if isinstance(obj, list) else ("(", ")") if isinstance(obj, tuple) else ("{", "}")
            if not obj:
                return f"{open_}{close_}"
            items = [self._pretty(v, indent + 2) for v in obj]
            inner = ",\n".join((" " * (indent + 2)) + s for s in items)
            return f"{open_}\n{inner}\n{pad}{close_}"
        elif isinstance(obj, dict):
            if not obj:
                return "{}"
            inner = []
            for k, v in obj.items():
                inner.append(f"{pad}  {k!r}: {self._pretty(v, indent + 2)}")
            return "{\n" + ",\n".join(inner) + f"\n{pad}}}"
        elif isinstance(obj, SavableObject) and hasattr(obj, 'as_dict') and callable(getattr(obj, 'as_dict', None)):
            d = obj.as_dict()
            inner = []
            for k, v in d.items():
                inner.append(f"{pad}  {k} = {self._pretty(v, indent + 2)}")
            return f"{obj.__class__.__name__}(\n" + ",\n".join(inner) + f"\n{pad})"
        else:
            # Fallback scalar formatting
            return repr(obj)

    def __str__(self) -> str:
        # Assumes self is a dataclass
        return self._pretty(self, 0)
