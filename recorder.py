"""Metronome, recording, and playback logic."""

import logging
import time
import threading
from typing import Callable

import numpy as np

from chords import ChordProgression, Position
from sound import play_sound
from app_settings import MAX_COMPENSATION_MS

_logger = logging.getLogger('irealstudio')


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
        on_playback_chord: Callable[[str], None] | None = None,
        on_beat: "Callable[[bool, list | None], None] | None" = None,
    ) -> None:
        """
        Parameters
        ----------
        speak:
            Callable used to announce messages to the user.
        tick_sound:
            Audio sample for beat 1 (downbeat) used when no MIDI metronome is
            configured (i.e. *on_beat* is ``None``).
        tock_sound:
            Audio sample for beats 2-N (upbeats) used without MIDI metronome.
        on_playback_chord:
            Optional callback called with the chord name on every playback beat.
        on_beat:
            Optional callback called on every metronome beat.  Signature:
            ``on_beat(is_downbeat: bool, chords: list | None) -> None``.
            ``is_downbeat`` is ``True`` for beat 1, ``False`` for all other
            beats.  ``chords`` is the list of :class:`~chords.Chord` objects
            active at the current measure during playback, or ``None`` during
            precount/recording or when no chord data is available.
            When provided this callback is called *instead of* the built-in
            audio beep, allowing the caller to drive a MIDI metronome.
        """
        self._speak = speak
        self._tick = tick_sound
        self._tock = tock_sound
        self._on_playback_chord = on_playback_chord
        self._on_beat = on_beat

        self.state: str = AppState.IDLE
        self.recording_start_time: float = 0.0
        self.recording_bpm: int = 120

        self._metronome_stop = threading.Event()
        self._metronome_thread: threading.Thread | None = None

        self._playback_stop = threading.Event()
        self._playback_thread: threading.Thread | None = None
        self.playback_stopped_at: Position | None = None

        # Beat-timing debug: updated each beat (monotonic time) so the UI can
        # query the offset since the last beat fired.
        self._last_beat_time: float | None = None

        # Latency compensation: fire the click this many ms before the logical
        # beat time so the sound reaches the listener on-beat.
        # Audio metronome default: 60 ms (PortAudio + OS audio stack latency).
        # MIDI metronome default: 0 ms (MIDI driver latency is typically < 1 ms).
        self._audio_compensation_ms: int = 60
        self._midi_compensation_ms: int = 0

    def _click(self, is_downbeat: bool, chords: "list | None" = None) -> None:
        """Fire a metronome click for one beat.

        If an *on_beat* callback was provided at construction time it is called
        instead of the built-in audio beep so the caller can drive a MIDI
        metronome.  Otherwise the appropriate audio sample is played.

        Parameters
        ----------
        is_downbeat:
            True when this beat is beat 1 (downbeat), False otherwise.
        chords:
            List of ``ProgressionItem`` objects at the current position, or
            ``None`` when no chord data is available (precount / recording).
        """
        if self._on_beat is not None:
            try:
                self._on_beat(is_downbeat, chords)
                return
            except Exception:
                _logger.error("on_beat callback raised — falling back to audio", exc_info=True)
        play_sound(self._tick if is_downbeat else self._tock)

    @property
    def tick_sound(self) -> "np.ndarray":
        """Audio sample used for the downbeat click."""
        return self._tick

    @property
    def tock_sound(self) -> "np.ndarray":
        """Audio sample used for non-downbeat clicks."""
        return self._tock

    @property
    def audio_compensation_ms(self) -> int:
        """Milliseconds to fire the audio click before the logical beat time."""
        return self._audio_compensation_ms

    @audio_compensation_ms.setter
    def audio_compensation_ms(self, value: int) -> None:
        self._audio_compensation_ms = max(0, min(MAX_COMPENSATION_MS, int(value)))

    @property
    def midi_compensation_ms(self) -> int:
        """Milliseconds to fire the MIDI beat callback before the logical beat time."""
        return self._midi_compensation_ms

    @midi_compensation_ms.setter
    def midi_compensation_ms(self, value: int) -> None:
        self._midi_compensation_ms = max(0, min(MAX_COMPENSATION_MS, int(value)))

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
        denom = progression.time_signature.denominator
        beat_names = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight']
        interval = 60.0 / self.recording_bpm

        # Latency compensation: fire the click this many seconds before the
        # logical beat time so that the sound (or MIDI event) arrives at the
        # listener/device exactly on the beat.  The compensation is determined
        # by whether a MIDI on_beat callback or the built-in audio beep is used.
        comp_s = (
            self._midi_compensation_ms if self._on_beat is not None
            else self._audio_compensation_ms
        ) / 1000.0

        # Use time.monotonic() throughout so beat scheduling is immune to
        # wall-clock adjustments (NTP, manual time changes, etc.).
        t0 = time.monotonic()
        total_precount_beats = 2 * beats

        # Jazz 4/4 mode: first measure gives a sparse "one … two …" cue;
        # second measure gives the full "one two three four" count-in.
        jazz_mode = (beats == 4 and denom == 4)

        # While loop (instead of for) so we can skip missed beats when the
        # system falls behind by more than one interval.
        i = 0
        while i < total_precount_beats:
            if self._metronome_stop.is_set():
                self.state = AppState.IDLE
                return
            b = i % beats
            measure_idx = i // beats   # 0 = first precount measure, 1 = second

            # Record when this beat fires for debug offset queries.
            self._last_beat_time = time.monotonic()
            # Play the click first so the sound lands precisely on the beat;
            # speech follows asynchronously and is heard just after the click.
            self._click(b == 0)

            if jazz_mode and measure_idx == 0:
                # First 4/4 precount measure: speak "one" on beat 1 and
                # "two" on beat 3; stay silent on beats 2 and 4.
                if b == 0:
                    self._speak('one')
                elif b == 2:
                    self._speak('two')
            else:
                # Second precount measure (or non-4/4): full count.
                self._speak(beat_names[b] if b < len(beat_names) else str(b + 1))

            # Sleep until comp_s before the next logical beat so the click
            # sound/MIDI event arrives on time after hardware latency.
            next_beat_time = t0 + (i + 1) * interval - comp_s
            sleep_time = next_beat_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
                i += 1
            elif sleep_time > -interval:
                # Slightly behind (within one interval); proceed normally.
                if sleep_time < -0.01:
                    _logger.debug(
                        "Pre-count beat %d ran %.1f ms over budget", i, -sleep_time * 1000
                    )
                i += 1
            else:
                # More than one beat behind; skip missed beats to avoid
                # rapid-fire catch-up clicks.
                missed = int(-sleep_time / interval)
                _logger.debug(
                    "Pre-count: skipping %d beat(s) due to %.1f ms lag",
                    missed, -sleep_time * 1000,
                )
                i += missed + 1

        if self._metronome_stop.is_set():
            self.state = AppState.IDLE
            return

        # recording_start_time is the *logical* beat time (without compensation)
        # so that chord positions computed from elapsed time are correct.
        self.recording_start_time = t0 + total_precount_beats * interval
        self.state = AppState.RECORDING
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

            # Record when this beat fires for debug offset queries.
            self._last_beat_time = time.monotonic()

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
                self._click(True)
            else:
                self._click(False)

            beat_count += 1
            # Fire the click comp_s before the logical beat time so the sound
            # arrives on time.  recording_start_time itself is the logical time,
            # so chord position calculations remain unaffected.
            next_beat_time = self.recording_start_time + beat_count * interval - comp_s
            sleep_time = next_beat_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time > -interval:
                # Slightly behind; proceed without sleeping.
                if sleep_time < -0.01:
                    _logger.debug(
                        "Recording beat %d ran %.1f ms over budget", beat_count, -sleep_time * 1000
                    )
            else:
                # More than one beat behind; skip missed beats to avoid
                # rapid-fire catch-up clicks.
                missed = int(-sleep_time / interval)
                _logger.debug(
                    "Recording metronome: skipping %d beat(s) due to %.1f ms lag",
                    missed, -sleep_time * 1000,
                )
                beat_count += missed

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

        # Latency compensation (see _precount_and_record for rationale).
        comp_s = (
            self._midi_compensation_ms if self._on_beat is not None
            else self._audio_compensation_ms
        ) / 1000.0

        # Anchor the beat grid to an absolute timeline so processing overhead
        # (chord lookup, speak, play_sound enqueue) does not accumulate and
        # drift the metronome — same pattern used in _precount_and_record.
        t0 = time.monotonic()
        beat_count = 0

        while not self._playback_stop.is_set():
            # Record when this beat fires for debug offset queries.
            self._last_beat_time = time.monotonic()

            chords_here = progression.find_chords_at_position(cur)
            if chords_here:
                self._speak(chords_here[0].chord_name_spoken())
                if self._on_playback_chord is not None:
                    try:
                        self._on_playback_chord(chords_here[0].chord.name)
                    except Exception:
                        _logger.error("on_playback_chord callback raised", exc_info=True)

            # Pass current chord list so the on_beat callback can apply
            # chord-aware note selection (smart metronome mode).
            self._click(cur.beat == 1, chords_here if chords_here else None)

            self.playback_stopped_at = Position(
                cur.measure, cur.beat, progression.time_signature
            )

            # Sleep until comp_s before the next logical beat so the click
            # sound/MIDI event arrives on time.
            beat_count += 1
            next_beat_time = t0 + beat_count * interval - comp_s
            sleep_time = next_beat_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.01:
                _logger.debug(
                    "Playback beat %d ran %.1f ms over budget",
                    beat_count, -sleep_time * 1000,
                )

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

    def beat_offset_ms(self) -> float:
        """
        Return the time elapsed (in milliseconds) since the last metronome beat fired.

        This is a phase metric: it tells you how far into the current beat interval
        the query was made.  A small value means the beat just fired; a large value
        means the query was made well after the beat.  Returns 0.0 when no beat has
        been recorded yet.
        """
        if self._last_beat_time is None:
            return 0.0
        return (time.monotonic() - self._last_beat_time) * 1000.0

    def stop_all(self) -> None:
        """Stop both the metronome/recording and playback threads."""
        self._metronome_stop.set()
        self._playback_stop.set()
        self.state = AppState.IDLE
