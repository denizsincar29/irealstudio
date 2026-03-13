"""Metronome, recording, and playback logic."""

import time
import threading
from typing import Callable

import numpy as np

from chords import ChordProgression, Position
from sound import play_sound


class AppState:
    IDLE = 'idle'
    PRE_COUNT = 'precount'
    RECORDING = 'recording'
    PLAYING = 'playing'


class Recorder:
    """Runs the metronome pre-count, recording click track and playback threads."""

    def __init__(
        self,
        speak: Callable[[str], None],
        tick_sound: np.ndarray,
        tock_sound: np.ndarray,
    ) -> None:
        self._speak = speak
        self._tick = tick_sound
        self._tock = tock_sound

        self.state: str = AppState.IDLE
        self.recording_start_time: float = 0.0
        self.recording_bpm: int = 120

        self._metronome_stop = threading.Event()
        self._metronome_thread: threading.Thread | None = None

        self._playback_stop = threading.Event()
        self._playback_thread: threading.Thread | None = None
        self.playback_stopped_at: Position | None = None

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_recording(
        self,
        progression: ChordProgression,
        cursor: Position,
        recording_bpm: int | None = None,
    ) -> None:
        """Start a 2-measure pre-count then switch to RECORDING state.

        *recording_bpm* sets the metronome tempo used during recording.
        When ``None`` the progression's own BPM is used.  Passing a lower
        value lets the user record at a comfortable speed and then play back
        at the song's actual BPM.
        """
        self.stop_all()
        self.recording_bpm = recording_bpm if recording_bpm is not None else progression.bpm
        self.state = AppState.PRE_COUNT
        self._metronome_stop.clear()
        self._metronome_thread = threading.Thread(
            target=self._precount_and_record,
            args=(progression, cursor),
            daemon=True,
        )
        self._metronome_thread.start()

    def _precount_and_record(
        self, progression: ChordProgression, cursor: Position
    ) -> None:
        beats = progression.time_signature.numerator
        beat_names = ['One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight']
        interval = 60.0 / self.recording_bpm

        for _ in range(2):  # 2-measure pre-count
            for b in range(beats):
                if self._metronome_stop.is_set():
                    self.state = AppState.IDLE
                    return
                # Play the click first so the sound lands precisely on the beat;
                # speech follows asynchronously and is heard just after the click.
                play_sound(self._tick if b == 0 else self._tock)
                self._speak(beat_names[b] if b < len(beat_names) else str(b + 1))
                time.sleep(interval)

        if self._metronome_stop.is_set():
            self.state = AppState.IDLE
            return

        self.state = AppState.RECORDING
        self.recording_start_time = time.time()
        self._speak("Recording")

        # Position-tracking metronome: announces hidden ranges and ending 2.
        cursor_beat_offset = cursor.beat_from_start - 1  # 0-based beat offset at recording start
        beat_count = 0
        _announced_hidden = False
        _announced_ending2: set[int] = set()

        while not self._metronome_stop.is_set():
            abs_beat_0 = cursor_beat_offset + beat_count
            logical_measure = abs_beat_0 // beats + 1
            logical_beat = abs_beat_0 % beats + 1

            if logical_beat == 1:
                if progression.is_in_hidden_range(logical_measure):
                    if not _announced_hidden:
                        self._speak("Repeating, chords not recorded")
                        _announced_hidden = True
                else:
                    _announced_hidden = False
                    for vb in progression.volta_brackets:
                        if (
                            vb.is_complete()
                            and logical_measure == vb.ending2_start
                            and logical_measure not in _announced_ending2
                        ):
                            self._speak("Ending 2")
                            _announced_ending2.add(logical_measure)
                play_sound(self._tick)
            else:
                play_sound(self._tock)

            beat_count += 1
            time.sleep(interval)

        self.state = AppState.IDLE

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def start_playback(
        self, progression: ChordProgression, cursor: Position
    ) -> None:
        """Speak chords at metronome tempo starting from *cursor*."""
        if self.state != AppState.IDLE:
            return
        self.state = AppState.PLAYING
        self._playback_stop.clear()
        self.playback_stopped_at = None
        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(progression, cursor),
            daemon=True,
        )
        self._playback_thread.start()

    def _playback_loop(
        self, progression: ChordProgression, cursor: Position
    ) -> None:
        interval = 60.0 / progression.bpm
        beats = progression.time_signature.numerator
        cur = Position(cursor.measure, cursor.beat, progression.time_signature)

        last_m = max(progression.last_measure(), progression.total_measures, 1)
        for vb in progression.volta_brackets:
            if vb.is_complete():
                last_m = max(last_m, vb.ending2_start)

        while not self._playback_stop.is_set():
            chords_here = progression.find_chords_at_position(cur)
            if chords_here:
                self._speak(chords_here[0].chord_name())

            play_sound(self._tick if cur.beat == 1 else self._tock)

            self.playback_stopped_at = Position(
                cur.measure, cur.beat, progression.time_signature
            )

            time.sleep(interval)
            if self._playback_stop.is_set():
                break

            next_beat = cur.beat + 1
            if next_beat > beats:
                next_m = progression.navigate_right_from_measure(cur.measure)
                if next_m > last_m:
                    break
                cur = Position(next_m, 1, progression.time_signature)
            else:
                cur = Position(cur.measure, next_beat, progression.time_signature)

        self.state = AppState.IDLE

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def stop_all(self) -> None:
        """Stop both the metronome/recording and playback threads."""
        self._metronome_stop.set()
        self._playback_stop.set()
        self.state = AppState.IDLE
