from __future__ import annotations
import contextlib
import asyncio, time
from dataclasses import dataclass
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Optional,
    TypeVar,
)

T = TypeVar("T")
U = TypeVar("U")


def now_ns() -> int:  # shared clock; replace with media clock when needed
    return time.time_ns()


@dataclass(frozen=True)
class TimeStamp:
    pts_ns: int

    @staticmethod
    def now():
        return now_ns()


class Stream(Generic[T]):
    """One standard stream type: async iterable of (value, timestamp)."""

    def __init__(self, agen_factory: Callable[[], AsyncIterator[tuple[T, TimeStamp]]]):
        self._agen_factory = agen_factory

    def __aiter__(self) -> AsyncIterator[tuple[T, TimeStamp]]:
        return self._agen_factory()

    # ---------- Constructors ----------

    @staticmethod
    def from_async_iter(source: AsyncIterator[T]) -> "Stream[T]":
        async def agen():
            async for item in source:
                yield (item, TimeStamp.now())

        return Stream(agen)

    @staticmethod
    def from_iterable(iterable: Iterable[T]) -> "Stream[T]":
        async def agen():
            for item in iterable:
                yield (item, TimeStamp.now())
                await asyncio.sleep(0)  # yield to loop

        return Stream(agen)

    @staticmethod
    def from_poll(
        poll_fn: Callable[[], Awaitable[T] | T], interval: float, jitter: float = 0.0
    ) -> "Stream[T]":
        """Turn a snapshot (pull) into a stream by polling."""

        async def agen():
            try:
                while True:
                    v = poll_fn()
                    if asyncio.iscoroutine(v):
                        v = await v  # type: ignore
                    yield (v, TimeStamp.now())
                    if jitter:
                        await asyncio.sleep(
                            interval
                            + (jitter * (2 * asyncio.get_running_loop().time() % 1 - 1))
                        )
                    else:
                        await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return

        return Stream(agen)

    @staticmethod
    def from_callback(
        register: Callable[[Callable[[T], None]], Any],
        unregister: Optional[Callable[[Any], None]] = None,
        *,
        maxsize: int = 256,
        overflow: str = "block",
    ) -> "Stream[T]":
        """
        Adapt a push/event API (callback) to a stream.
        overflow='block'|'drop'|'latest'
        """
        assert overflow in ("block", "drop", "latest")

        async def agen():
            q: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
            token_holder = {}

            def emit(item: T):
                # Runs in the producer's thread/loop; choose overflow policy
                if overflow == "block":
                    # Block using thread-safe future so back-pressure propagates
                    fut = asyncio.run_coroutine_threadsafe(
                        q.put(item), asyncio.get_running_loop()
                    )
                    fut.result()
                elif overflow == "drop":
                    try:
                        q.put_nowait(item)
                    except asyncio.QueueFull:
                        pass
                else:  # latest
                    while True:
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    try:
                        q.put_nowait(item)
                    except asyncio.QueueFull:
                        pass

            token = register(emit)
            token_holder["t"] = token

            try:
                while True:
                    item = await q.get()
                    yield (item, TimeStamp.now())
            except asyncio.CancelledError:
                return
            finally:
                if unregister:
                    try:
                        unregister(token_holder["t"])
                    except Exception:
                        pass

        return Stream(agen)

    @staticmethod
    def from_process(
        cmd: list[str], *, decode: str = "utf-8", line_buffered: bool = True
    ) -> "Stream[str]":
        """Stdout lines from a subprocess become a stream."""

        async def agen():
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            assert proc.stdout is not None
            try:
                if line_buffered:
                    async for raw in proc.stdout:
                        yield (
                            raw.decode(decode, errors="replace").rstrip("\n"),
                            TimeStamp.now(),
                        )
                else:
                    while b := await proc.stdout.read(4096):
                        yield (b.decode(decode, errors="replace"), TimeStamp.now())
            finally:
                with contextlib.suppress(ProcessLookupError):
                    if proc.returncode is None:
                        proc.terminate()

        return Stream(agen)

    # ---------- Operators (return new streams) ----------

    def map(self, fn: Callable[[T], U]) -> "Stream[U]":
        async def agen():
            async for v, ts in self:
                yield (fn(v), ts)

        return Stream(agen)

    def filter(self, pred: Callable[[T], bool]) -> "Stream[T]":
        async def agen():
            async for v, ts in self:
                if pred(v):
                    yield (v, ts)

        return Stream(agen)

    def buffer(self, n: int) -> "Stream[list[T]]":
        async def agen():
            buf: list[T] = []
            async for v, ts in self:
                buf.append(v)
                if len(buf) >= n:
                    yield (buf[:], ts)
                    buf.clear()

        return Stream(agen)

    @staticmethod
    def merge(*streams: "Stream[T]") -> "Stream[T]":
        async def agen():
            q: asyncio.Queue[tuple[T, TimeStamp]] = asyncio.Queue()
            tasks = []

            async def pump(s: Stream[T]):
                async for v in s:
                    await q.put(v)

            for s in streams:
                tasks.append(asyncio.create_task(pump(s)))
            done = 0
            try:
                while done < len(tasks):
                    try:
                        yield await q.get()
                    except asyncio.CancelledError:
                        break
            finally:
                for t in tasks:
                    t.cancel()

        return Stream(agen)

    # ---------- Sinks ----------

    async def for_each(self, fn: Callable[[T, TimeStamp], Awaitable[None] | None]) -> None:
        async for v, ts in self:
            r = fn(v, ts)
            if asyncio.iscoroutine(r):
                await r  # type: ignore
