import platform
import sys
import contextlib, queue, threading
import traceback
from typing import Callable, Iterator, Optional, Any

from this_framework_that_i_made.audio_helpers.audio_standards import (
    PcmBlock,
    PYAUDIO_SAMPLE_FORMAT,
    NUMPY_SAMPLE_FORMAT,
    SampleFormat,
)


try:
    import pythoncom
    _HAS_PYCOM = True
except Exception:
    _HAS_PYCOM = False


pyaudio = None
if platform.system() == "Windows":
    import pyaudiowpatch
    pyaudio = pyaudiowpatch
else:
    import pyaudio
    pyaudio = pyaudio


# @ensure_savable
# @dataclass(slots=True)
# class AudioMetadata(SavableObject):
#     rate: int  # Sampling rate
#     channels: int  # Number of channels
#     sample_format: SampleFormat  # Sampling size and format (See PortAudio Sample Format)
#     frames_per_buffer: int  # Specifies the number of frames per buffer (chunk size)


# @ensure_savable
# @dataclass(slots=True)
# class PyAudioMetadata(SavableObject):
#     is_input: bool = False  # Specifies whether this is an input stream. Defaults to False.
#     is_output: bool = False  # Specifies whether this is an output stream. Defaults to False.
#     input_device_index: int = None  # Index of Input Device to use. Unspecified (or None) uses default device. Ignored if input is False.
#     output_device_index: int = None  # Index of Output Device to use. Unspecified (or None) uses the default device. Ignored if output is False.
#     start: bool = True  # Start the stream running immediately. Defaults to True. In general, there is no reason to set this to False.
#     input_host_api_specific_stream_info: Any = None  # Specifies a host API specific stream information data structure for input. See PaMacCoreStreamInfo.
#     output_host_api_specific_stream_info: Any = None  # Specifies a host API specific stream information data structure for output. See PaMacCoreStreamInfo.
#     stream_callback: Any = None  # Specifies a callback function for non-blocking (callback) operation. Default is None, which indicates blocking operation (i.e., PyAudio.Stream.read() and PyAudio.Stream.write()). To use non-blocking operation, specify a callback that conforms to the following signature:


class PyAudioWrapper:

    """
    PyAudioWPatch is a fork of PyAudio, so I need to only use the base implemented methods in PyAudio to achieve what I'd like here
    
    """

    WASAPI_LOOPBACK_SUFFIX = " [Loopback]"

    @classmethod
    @contextlib.contextmanager
    def _with_pa(cls):
        # Use the globally-selected `pyaudio` (or `pyaudiowpatch` on Windows)
        pa = pyaudio.PyAudio()
        try:
            yield pa
        finally:
            pa.terminate()

    @classmethod
    def get_host_api_data(cls):
        with cls._with_pa() as pa:
            return [pa.get_host_api_info_by_index(i) for i in range(0, pa.get_host_api_count())]

    @classmethod
    def get_host_api_name_by_index(cls, index):
        with cls._with_pa() as pa:
            return pa.get_host_api_info_by_index(index)["name"]

    @classmethod
    def get_audio_endpoint_data(cls):
        with cls._with_pa() as pa:
            return [
                pa.get_device_info_by_host_api_device_index(host_api["index"], i)
                for host_api in cls.get_host_api_data()
                for i in range(host_api["deviceCount"])
            ]


@contextlib.contextmanager
def get_pcm_blocks(
    *,
    # For PyAudio open kwargs for input
    input_device_index: int = None,
    frames_per_buffer: int = 1024,
    sample_format: SampleFormat = SampleFormat.INT_16,
    rate: int = None,
    channels: int = None,
    input_host_api_specific_stream_info: Any = None,
    # Streaming behavior
    queue_size: int = 64,
    drop_oldest_on_full: bool = True,
    transform: Optional[Callable[[bytes, int, dict, int], Optional[bytes]]] = None,
) -> Iterator[Iterator[PcmBlock]]:
    """
    Generic PCM input stream helper for an AudioEndpoint.

    Yields an iterator of PcmBlock objects. Defaults are inferred from the
    provided `endpoint` when omitted (assumes input streaming).
    """

    pyaudio_format = PYAUDIO_SAMPLE_FORMAT[sample_format]
    dtype = NUMPY_SAMPLE_FORMAT[sample_format]

    q: "queue.Queue[Optional[PcmBlock]]" = queue.Queue(maxsize=max(1, queue_size))
    stop_evt = threading.Event()
    worker_exc: list[BaseException] = []
    SENTINEL = None

    def _worker():
        com_inited = False
        if _HAS_PYCOM:
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
                com_inited = True
            except Exception:
                pass

        pa = None
        stream = None
        try:
            pa = pyaudio.PyAudio()

            def _cb(in_data, frame_count, time_info, status):
                try:
                    payload = transform(in_data, frame_count, time_info, status) if transform else None
                    payload = payload if payload is not None else in_data
                    blk = PcmBlock(payload, dtype=dtype, channels=channels)
                    try:
                        q.put_nowait(blk)
                    except queue.Full:
                        if drop_oldest_on_full:
                            try:
                                _ = q.get_nowait()
                            except queue.Empty:
                                pass
                            try:
                                q.put_nowait(blk)
                            except queue.Full:
                                pass  # drop newest
                except Exception as e:
                    worker_exc.append(e)
                return (None, pyaudio.paContinue)

            start_immediately = True

            stream = pa.open(
                format=pyaudio_format,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=frames_per_buffer,
                stream_callback=_cb,
                start=start_immediately,
                input_host_api_specific_stream_info=input_host_api_specific_stream_info,
            )

            if not stream.is_active() and start_immediately:
                stream.start_stream()

            while not stop_evt.is_set() and stream.is_active():
                stop_evt.wait(0.05)

        except Exception as e:
            worker_exc.append(e)
        finally:
            try:
                if stream and stream.is_active():
                    stream.stop_stream()
            except Exception:
                pass
            try:
                if stream:
                    stream.close()
            except Exception:
                pass
            try:
                if pa:
                    pa.terminate()
            except Exception:
                pass
            if _HAS_PYCOM and com_inited:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            try:
                q.put_nowait(SENTINEL)
            except Exception:
                pass

            if worker_exc:
                traceback.print_exception(worker_exc[-1], file=sys.stderr)

    t = threading.Thread(target=_worker, name="PcmWorker", daemon=True)
    t.start()

    def _iter() -> Iterator[PcmBlock]:
        while True:
            blk = q.get()
            if blk is SENTINEL:
                if worker_exc:
                    raise worker_exc[-1]
                break
            yield blk

    try:
        yield _iter()
    finally:
        stop_evt.set()
        try:
            q.put_nowait(SENTINEL)
        except Exception:
            pass
        t.join(timeout=2.0)
