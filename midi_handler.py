"""MIDI input handling and chord detection."""

import logging
import time
import threading
from typing import Callable

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False

_logger = logging.getLogger('irealstudio')


class MidiHandler:
    """Manages a MIDI input port and detects chord note events."""

    def __init__(
        self,
        speak: Callable[[str], None],
        on_chord_released: Callable[[list[int], float], None],
        is_recording: Callable[[], bool],
    ) -> None:
        """
        Parameters
        ----------
        speak:
            Callable used to announce messages to the user.
        on_chord_released:
            Called with ``(notes, first_note_time)`` when all held keys are
            released.  ``notes`` is a list of MIDI note numbers; ``first_note_time``
            is the ``time.time()`` value of the first key press in the chord.
        is_recording:
            Returns True when the app is in the RECORDING state so that the
            handler only commits chords during active recording.
        """
        self._speak = speak
        self._on_chord_released = on_chord_released
        self._is_recording = is_recording

        self.midi_input = None
        self.midi_input_name: str = ''
        self._stop_event = threading.Event()

        self._held_notes: dict[int, float] = {}
        self._chord_first_note_time: float = 0.0
        self._chord_notes: list[int] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Auto-connect to the first available MIDI input port."""
        if not MIDO_AVAILABLE:
            self._speak("MIDI not available: install mido and python-rtmidi")
            return
        try:
            names = mido.get_input_names()
        except Exception as e:
            self._speak(f"MIDI init error: {e}")
            return
        if not names:
            self._speak("No MIDI input devices found")
            return
        count = len(names)
        self._speak(f"MIDI: {count} device{'s' if count != 1 else ''} found")
        self.open_by_name(names[0])

    def open_by_name(self, name: str) -> None:
        """Close any open port and open *name*."""
        self._stop_event.set()
        if self.midi_input is not None:
            try:
                self.midi_input.close()
            except Exception:
                pass
            self.midi_input = None
        # Give the reader thread a moment to notice the stop event.
        time.sleep(0.02)
        self._stop_event.clear()
        try:
            self.midi_input = mido.open_input(name)
            self.midi_input_name = name
            threading.Thread(target=self._loop, daemon=True).start()
            self._speak(f"MIDI connected: {name}")
        except Exception as e:
            self.midi_input_name = ''
            self._speak(f"MIDI open failed: {e}")

    def get_input_names(self) -> list[str]:
        """Return available MIDI input port names (empty list if unavailable)."""
        if not MIDO_AVAILABLE:
            return []
        try:
            return mido.get_input_names()
        except Exception as e:
            _logger.error("MIDI list error: %s", e)
            self._speak(f"MIDI list error: {e}")
            return []

    def close(self) -> None:
        """Signal the reader thread to stop and close the port."""
        _logger.debug("Closing MIDI port: %s", self.midi_input_name)
        self._stop_event.set()
        if self.midi_input is not None:
            try:
                self.midi_input.close()
            except Exception:
                pass
            self.midi_input = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        _logger.debug("MIDI reader thread started for: %s", self.midi_input_name)
        while not self._stop_event.is_set():
            if self.midi_input is None:
                break
            try:
                for msg in self.midi_input.iter_pending():
                    self._handle(msg)
            except Exception as e:
                _logger.error("MIDI read error: %s", e)
                break
            time.sleep(0.005)
        _logger.debug("MIDI reader thread stopped")

    def _handle(self, msg) -> None:
        if not self._is_recording():
            return
        note_on = msg.type == 'note_on' and msg.velocity > 0
        note_off = msg.type == 'note_off' or (
            msg.type == 'note_on' and msg.velocity == 0
        )

        if note_on:
            if not self._held_notes:
                self._chord_first_note_time = time.time()
            self._held_notes[msg.note] = time.time()
            if msg.note not in self._chord_notes:
                self._chord_notes.append(msg.note)
        elif note_off:
            self._held_notes.pop(msg.note, None)
            if not self._held_notes and self._chord_notes:
                notes = list(self._chord_notes)
                first_time = self._chord_first_note_time
                self._chord_notes = []
                self._on_chord_released(notes, first_time)
