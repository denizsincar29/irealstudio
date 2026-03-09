"""Audio synthesis and playback using sounddevice + numpy."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100


def make_beep(freq: int, duration_ms: int) -> np.ndarray:
    """Return a mono int16 numpy array containing a sine-wave beep."""
    num_samples = int(SAMPLE_RATE * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)


def play_sound(wave: np.ndarray) -> None:
    """Play *wave* asynchronously; silently ignore audio device errors."""
    try:
        sd.play(wave, samplerate=SAMPLE_RATE)
    except sd.PortAudioError:
        pass
