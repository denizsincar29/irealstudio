"""Audio synthesis and playback using sounddevice + numpy.

A persistent callback-based PortAudio output stream is kept open for the
entire lifetime of the process.  play_sound() simply enqueues a buffer into
a list that is mixed into the stream on every audio callback, eliminating
the ~200 ms warm-up latency caused by repeatedly calling sd.play().

Latency budget
--------------
* Block-size jitter: 0 – _BLOCK_SIZE/SAMPLE_RATE = ~23.2 ms (1024 frames)
* Hardware output buffer: requested 20 ms via ``latency=0.02``;
  PortAudio clamps to the device's achievable minimum on each platform
  (Windows WASAPI ≈ 10–20 ms shared, Linux ALSA ≈ 5–15 ms).
Total round-trip from play_sound() call to audible output: typically < 50 ms.
The audio compensation feature (default 60 ms) absorbs this latency.
"""

import threading
import numpy as np

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except Exception:
    _SD_AVAILABLE = False

SAMPLE_RATE = 44100

# Block size: 1024 frames → ~23.2 ms max callback scheduling jitter.
# 512 frames (~11.6 ms) still caused occasional xruns/crackles on some
# WASAPI and ALSA devices whose OS scheduler latency exceeds the callback
# interval.  1024 frames gives ~23 ms of headroom, which is comfortable
# even on heavily loaded Windows systems.  The dominant latency source is
# the hardware output buffer (latency=0.02), so the extra jitter is
# absorbed by the compensation feature (default 60 ms).
_BLOCK_SIZE = 1024

# Attack / release lengths in seconds for the metronome envelope.
_ATTACK_S  = 0.003   # 3 ms  — fast but click-free
_RELEASE_S = 0.015   # 15 ms — clean tail-off

# ---------------------------------------------------------------------------
# Persistent stream state
# ---------------------------------------------------------------------------

# List of (int16 buffer, current_read_position) tuples.
_pending: list[tuple[np.ndarray, int]] = []
_lock = threading.Lock()
_stream = None          # sd.OutputStream or None
_current_device: int | None = None  # None = PortAudio default


def _callback(outdata: np.ndarray, frames: int, time_info, status) -> None:
    """Audio callback: mix all pending buffers into *outdata*."""
    outdata[:] = 0.0
    with _lock:
        still_playing: list[tuple[np.ndarray, int]] = []
        for buf, pos in _pending:
            n = min(frames, len(buf) - pos)
            if n <= 0:
                continue
            outdata[:n, 0] += buf[pos:pos + n].astype(np.float32) / 32767.0
            new_pos = pos + n
            if new_pos < len(buf):
                still_playing.append((buf, new_pos))
        _pending[:] = still_playing
    np.clip(outdata, -1.0, 1.0, out=outdata)


def _open_stream(device: int | None = None) -> None:
    """(Re-)open the persistent output stream on *device* (None = default)."""
    global _stream, _current_device
    if not _SD_AVAILABLE:
        return
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
        _stream = None
    _current_device = device
    try:
        _stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
            callback=_callback,
            blocksize=_BLOCK_SIZE,
            device=device,
            # Request a 20 ms output buffer.  A smaller value (e.g. 5 ms)
            # forces WASAPI/ALSA to service the stream very frequently and
            # can cause xruns on systems with higher OS scheduler latency.
            # 20 ms is still well within the 60 ms audio compensation budget.
            latency=0.02,
        )
        _stream.start()
    except Exception:
        _stream = None


# Open the default stream once at import time.
_open_stream()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_beep(freq: int, duration_ms: int) -> np.ndarray:
    """Return a mono int16 sine-wave with a short attack/release envelope.

    The envelope avoids the flat "tut tut" quality of an unwindowed sine:
    the 3 ms linear attack prevents the onset click and the 15 ms cosine
    release (or whatever fits in the buffer) gives a natural decay.
    """
    num_samples = int(SAMPLE_RATE * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)

    # Build envelope
    attack_samples  = min(int(SAMPLE_RATE * _ATTACK_S), num_samples // 4)
    release_samples = min(int(SAMPLE_RATE * _RELEASE_S), num_samples // 2)

    envelope = np.ones(num_samples, dtype=np.float64)
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples)
    if release_samples > 0:
        # Cosine release curve feels more natural than linear
        envelope[-release_samples:] = 0.5 * (1.0 + np.cos(
            np.linspace(0.0, np.pi, release_samples)
        ))

    return (wave * envelope * 32767).astype(np.int16)


def play_sound(wave: np.ndarray) -> None:
    """Enqueue *wave* for immediate playback on the persistent stream.

    Returns immediately; the audio callback mixes the buffer into the
    hardware output on the next audio block (~23 ms at 1024 frames /
    44 100 Hz), avoiding the ~200 ms latency of sd.play().
    Falls back to sd.play() if the persistent stream is unavailable.
    """
    if _stream is not None and _stream.active:
        with _lock:
            _pending.append((wave, 0))
        return
    # Fallback: try to re-open the stream, then enqueue.
    _open_stream(_current_device)
    if _stream is not None and _stream.active:
        with _lock:
            _pending.append((wave, 0))
        return
    # Last resort: blocking sd.play()
    if _SD_AVAILABLE:
        try:
            sd.play(wave, samplerate=SAMPLE_RATE)
        except Exception:
            pass


def get_current_output_device() -> int | None:
    """Return the device_id of the currently active output stream.

    Returns ``None`` when the system default device is in use.
    """
    return _current_device


def get_output_devices() -> list[tuple[int, str]]:
    """Return ``[(device_id, name), ...]`` for all available output devices."""
    if not _SD_AVAILABLE:
        return []
    try:
        return [
            (i, d['name'])
            for i, d in enumerate(sd.query_devices())
            if d['max_output_channels'] > 0
        ]
    except Exception:
        return []


def set_output_device(device_id: int | None) -> bool:
    """Switch the persistent stream to *device_id* (None = system default).

    Returns True if the stream was (re-)opened successfully.
    """
    _open_stream(device_id)
    return _stream is not None
