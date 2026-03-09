"""Audio synthesis and playback using sounddevice + numpy."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100

# Attack / release lengths in seconds for the metronome envelope.
_ATTACK_S  = 0.003   # 3 ms  — fast but click-free
_RELEASE_S = 0.015   # 15 ms — clean tail-off


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
    """Play *wave* asynchronously; silently ignore audio device errors."""
    try:
        sd.play(wave, samplerate=SAMPLE_RATE)
    except sd.PortAudioError:
        pass
