# mux.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Iterator, Any, Optional, Tuple, Dict
import threading, queue, contextlib, inspect

"""
“Mux” is short for multiplexer.

In hardware, a multiplexer picks one of many inputs and presents it on one output
(an N→1 device). In software, people use “mux” loosely for anything that merges
multiple input streams into a single output stream.
"""

@dataclass
class Source:
    """
    name: label emitted with each event
    yielder: callable returning an iterator/generator that yields events
    args/kwargs: optional args to pass to yielder
    start/stop: optional callables to prep/cleanup the source
    """
    name: str
    yielder: Callable[..., Iterator[Any]]
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    start: Optional[Callable[[], None]] = None
    stop: Optional[Callable[[], None]] = None


def yield_from_sources(
    *sources: Source,
    pump_timeout: float = 0.25,   # passed to yielders that accept `timeout=`
    queue_maxsize: int = 0,
) -> Iterator[Tuple[str, Any]]:
    """
    Merge events from multiple generator methods into a single iterator.
    Yields (source_name, event). Cleanly stops all pumps when the consumer breaks.
    """
    q: "queue.Queue[Tuple[str, Any]]" = queue.Queue(maxsize=queue_maxsize)
    stop_evt = threading.Event()
    threads: list[threading.Thread] = []

    def _pump(src: Source):
        # Call yielder, injecting timeout if it is supported
        kwargs = dict(src.kwargs)
        try:
            sig = inspect.signature(src.yielder)
            if "timeout" in sig.parameters and "timeout" not in kwargs:
                kwargs["timeout"] = pump_timeout
        except (ValueError, TypeError):
            pass  # builtins or C-callables without signatures

        try:
            if src.start:
                src.start()

            for item in src.yielder(*src.args, **kwargs):
                if stop_evt.is_set():
                    break
                q.put((src.name, item))
        except Exception as e:
            # surface errors as a special event; you can also log here
            q.put((f"{src.name}.__error__", e))
        finally:
            if src.stop:
                with contextlib.suppress(Exception):
                    src.stop()

    # Spin up pumps
    for s in sources:
        t = threading.Thread(target=_pump, args=(s,), daemon=True)
        t.start()
        threads.append(t)

    # The iterator that the caller will consume
    try:
        while True:
            yield q.get()
    finally:
        # Consumer broke out: signal pumps to stop and join threads
        stop_evt.set()
        for s in sources:
            if s.stop:
                with contextlib.suppress(Exception):
                    s.stop()
        for t in threads:
            if t.is_alive():
                t.join(timeout=pump_timeout + 0.5)
