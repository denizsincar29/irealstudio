"""Audio synthesis and playback using sounddevice + numpy.

A persistent callback-based PortAudio output stream is kept open for the
entire lifetime of the process.  play_sound() simply enqueues a buffer into
a list that is mixed into the stream on every audio callback.

DAC-time scheduling
-------------------
Each pending item may carry an optional *target_dac_time* (a PortAudio stream
time value).  When provided, the callback places the first sample of the sound
at the exact output-buffer offset that will be heard at that stream time,
giving **sample-accurate scheduling** and eliminating block-size jitter
entirely.  Without a target the sound is played as soon as possible.

To convert a ``time.monotonic()`` deadline to a stream time, call
``play_sound(wave, target_monotonic=T)``; the module tracks the
monotonic→stream offset measured right after the stream opens.

Latency budget (with DAC scheduling)
-------------------------------------
* Block-size jitter: eliminated — samples land at the exact target offset.
* Hardware output buffer: requested 20 ms via ``latency=0.02``;
  PortAudio clamps to the device's achievable minimum on each platform
  (Windows WASAPI ≈ 10–20 ms shared, Linux ALSA ≈ 5–15 ms).
* Total latency from play_sound() to audible output: ≈ hardware latency only.
  The audio compensation feature should be set to match the device's hardware
  latency (query via ``get_stream_hardware_latency()``).
"""

import time as _time
import threading
import numpy as np

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except Exception:
    _SD_AVAILABLE = False

SAMPLE_RATE = 44100

# Block size: 256 frames → ~5.8 ms max callback scheduling jitter.
# With DAC-time scheduling this jitter no longer affects perceived timing
# (samples are placed at the exact target offset within each buffer), but a
# smaller block size still reduces the worst-case queue depth and makes the
# stream more responsive to device changes.  256 is stable on modern
# WASAPI/ALSA/CoreAudio setups while avoiding the xruns seen with 128.
_BLOCK_SIZE = 256

# Attack / release lengths in seconds for the metronome envelope.
_ATTACK_S  = 0.003   # 3 ms  — fast but click-free
_RELEASE_S = 0.015   # 15 ms — clean tail-off

# ---------------------------------------------------------------------------
# Persistent stream state
# ---------------------------------------------------------------------------

# Each item is (int16 buffer, current_read_position, target_dac_time | None).
# target_dac_time, when not None, is a PortAudio stream time (seconds) at
# which the first sample of the buffer should be heard.  None means "play
# as soon as possible".
_pending: list[tuple[np.ndarray, int, float | None]] = []
_lock = threading.Lock()
_stream = None          # sd.OutputStream or None
_current_device: int | None = None  # None = PortAudio default

# Offset used to convert time.monotonic() values into PortAudio stream time:
#   stream_time = monotonic_time - _mono_to_stream_offset
# Measured right after the stream is started to minimise clock skew.
_mono_to_stream_offset: float = 0.0


def _callback(outdata: np.ndarray, frames: int, time_info, status) -> None:
    """Audio callback: mix all pending buffers into *outdata*.

    Each pending item may carry an optional *target_dac_time*.  When present,
    the sample is placed at the exact offset within the output buffer that
    corresponds to that DAC time, achieving sample-accurate scheduling.
    Items scheduled for a future buffer are kept in the queue unchanged.
    Items that are late (target is before the current buffer's start) begin
    at sample 0 of the current buffer (best-effort recovery).
    """
    outdata[:] = 0.0
    dac_time: float = time_info.output_buffer_dac_time  # stream time of buffer[0]
    with _lock:
        still_playing: list[tuple[np.ndarray, int, float | None]] = []
        for buf, pos, target_dac in _pending:
            if target_dac is not None:
                # Number of samples from now until the target playback point.
                sample_start = round((target_dac - dac_time) * SAMPLE_RATE)
                if sample_start >= frames:
                    # Target is in a future buffer — keep waiting.
                    still_playing.append((buf, pos, target_dac))
                    continue
                if sample_start < 0:
                    # We are late: skip the samples that should have already
                    # played (advance pos by abs(sample_start)) and start
                    # immediately at the current buffer head.
                    # Note: pos - sample_start == pos + abs(sample_start) because
                    # sample_start is negative here.
                    pos = pos - sample_start  # advance past the missed samples
                    if pos >= len(buf):
                        # The entire buffer is in the past — drop it.
                        continue
                    sample_start = 0
                # Fall through with sample_start in [0, frames).
            else:
                sample_start = 0

            n = min(frames - sample_start, len(buf) - pos)
            if n > 0:
                outdata[sample_start:sample_start + n, 0] += (
                    buf[pos:pos + n].astype(np.float32) / 32767.0
                )
                pos += n
            if pos < len(buf):
                # Buffer has remaining samples; continue next callback at pos,
                # no longer needs DAC targeting (already started playing).
                still_playing.append((buf, pos, None))
        _pending[:] = still_playing
    np.clip(outdata, -1.0, 1.0, out=outdata)


def _open_stream(device: int | None = None) -> None:
    """(Re-)open the persistent output stream on *device* (None = default)."""
    global _stream, _current_device, _mono_to_stream_offset
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
            # 20 ms is still well within the default 60 ms audio compensation
            # budget; with DAC-time scheduling the hardware latency is
            # compensated automatically when the caller passes target_monotonic.
            latency=0.02,
        )
        _stream.start()
        # Calibrate the monotonic→stream-time offset immediately after the
        # stream starts.  We bracket the Pa_GetStreamTime() call with two
        # monotonic readings and use their midpoint to minimise clock-read skew.
        # Note: time.monotonic() and the PortAudio stream clock are independent;
        # over very long sessions (many hours) clock drift between the two may
        # accumulate to a few milliseconds.  This is negligible for metronome
        # use but users running the application for many hours without stopping
        # may observe slightly increasing click offset.  Recalling
        # set_output_device() resets the calibration if needed.
        t_before = _time.monotonic()
        t_stream = _stream.time
        t_after  = _time.monotonic()
        _mono_to_stream_offset = (t_before + t_after) * 0.5 - t_stream
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


def play_sound(wave: np.ndarray, target_monotonic: float | None = None) -> None:
    """Enqueue *wave* for playback on the persistent stream.

    Returns immediately; the audio callback mixes the buffer into the
    hardware output on the next audio block, avoiding the ~200 ms latency
    of sd.play().

    Parameters
    ----------
    wave:
        Mono int16 array to play.
    target_monotonic:
        Optional ``time.monotonic()`` value at which the *first* sample of
        *wave* should be heard through the speakers.  When provided the
        callback uses DAC-time scheduling to place the sample at the exact
        output-buffer offset corresponding to this moment, eliminating
        block-size jitter.  When ``None`` the sound plays as soon as the
        next callback fires (legacy behaviour).

    Falls back to sd.play() if the persistent stream is unavailable.
    """
    target_dac: float | None = None
    if target_monotonic is not None:
        # Convert monotonic time to PortAudio stream time.
        target_dac = target_monotonic - _mono_to_stream_offset

    if _stream is not None and _stream.active:
        with _lock:
            _pending.append((wave, 0, target_dac))
        return
    # Fallback: try to re-open the stream, then enqueue.
    _open_stream(_current_device)
    if _stream is not None and _stream.active:
        with _lock:
            _pending.append((wave, 0, target_dac))
        return
    # Last resort: blocking sd.play()
    if _SD_AVAILABLE:
        try:
            sd.play(wave, samplerate=SAMPLE_RATE)
        except Exception:
            pass


def get_stream_hardware_latency() -> float:
    """Return the hardware output latency (seconds) of the active stream.

    This is the PortAudio-reported output latency — the delay between when
    the callback fills a buffer and when the first sample of that buffer is
    audible.  Use this value as the audio metronome compensation when you
    want the click to be heard exactly on the logical beat time.

    Returns 0.02 (the requested latency) when the stream is not open.
    """
    if _stream is not None:
        try:
            return _stream.latency
        except Exception:
            pass
    return 0.02


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
