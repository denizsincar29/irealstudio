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
        use_midi_compensation: "Callable[[], bool] | None" = None,
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
        use_midi_compensation:
            Optional zero-argument callable that returns ``True`` when the MIDI
            metronome is actually active (MIDI output open, MIDI metro enabled)
            and ``False`` when the click falls back to audio.  Used to pick the
            correct latency compensation value at the start of each session.
            Defaults to always returning ``False`` (audio compensation).
        """
        self._speak = speak
        self._tick = tick_sound
        self._tock = tock_sound
        self._on_playback_chord = on_playback_chord
        self._on_beat = on_beat
        self._use_midi_compensation: "Callable[[], bool]" = (
            use_midi_compensation if use_midi_compensation is not None else (lambda: False)
        )

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

    def _click(
        self,
        is_downbeat: bool,
        chords: "list | None" = None,
        target_time: float | None = None,
    ) -> None:
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
        target_time:
            Optional ``time.monotonic()`` value at which the *first* sample of
            the click should be audible.  Passed through to
            :func:`~sound.play_sound` for DAC-time scheduling when the audio
            metronome is active.  Ignored when an *on_beat* callback handles
            the click (MIDI metronome path).
        """
        if self._on_beat is not None:
            try:
                self._on_beat(is_downbeat, chords)
                return
            except Exception:
                _logger.error("on_beat callback raised — falling back to audio", exc_info=True)
        play_sound(self._tick if is_downbeat else self._tock, target_monotonic=target_time)

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

    def _get_clamped_compensation(self, interval: float) -> float:
        """Return the effective latency compensation in seconds for *interval*-length beats.

        Selects MIDI or audio compensation based on whether the MIDI metronome
        is currently active (via ``_use_midi_compensation``), then clamps the
        result to less than one full beat interval so that
        ``next_beat_time`` stays monotonically increasing even at extreme
        compensation values.
        """
        raw_s = (
            self._midi_compensation_ms if self._use_midi_compensation()
            else self._audio_compensation_ms
        ) / 1000.0
        return min(raw_s, interval * 0.9)

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
        # listener/device exactly on the beat.
        comp_s = self._get_clamped_compensation(interval)

        # Use time.monotonic() throughout so beat scheduling is immune to
        # wall-clock adjustments (NTP, manual time changes, etc.).
        #
        # With audio metronome: set t0 comp_s into the future so that beat 1
        # fires comp_s early (just like beats 2+) and its sound is heard at
        # exactly t0.  With MIDI metronome comp_s is typically 0, so t0 equals
        # the current time and the first beat fires immediately.
        t0 = time.monotonic() + comp_s
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
            # Use the logical beat time (when the sound will be heard) so that
            # beat_offset_ms() reports a meaningful phase value.
            beat_logical = t0 + i * interval
            self._last_beat_time = beat_logical
            # Play the click first so the sound lands precisely on the beat;
            # speech follows asynchronously and is heard just after the click.
            # Pass beat_logical for DAC-time scheduling (audio path only).
            self._click(b == 0, target_time=beat_logical)

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

            # Logical time when this recording beat should be heard.
            beat_logical = self.recording_start_time + beat_count * interval
            self._last_beat_time = beat_logical

            if logical_beat == 1:
                if progression.is_in_virtual_range(logical_measure):
                    # Repeating section: announce once and play back the chords
                    # from the resolved primary position so the MIDI smart
                    # metronome and chord-playback callback remain active.
                    if not _announced_hidden:
                        self._speak("Repeating, chords not recorded")
                        _announced_hidden = True
                    primary_m = progression.resolve_virtual_measure(logical_measure)
                    chords_here = progression.find_chords_at_position(
                        Position(primary_m, 1, progression.time_signature))
                    self._click(True, chords_here if chords_here else None,
                                target_time=beat_logical)
                    if chords_here:
                        self._speak(chords_here[0].chord_name_spoken())
                    if chords_here and self._on_playback_chord is not None:
                        try:
                            self._on_playback_chord(chords_here[0].chord.name)
                        except Exception:
                            _logger.error("on_playback_chord callback raised", exc_info=True)
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
                    self._click(True, target_time=beat_logical)
            else:
                if progression.is_in_virtual_range(logical_measure):
                    # Off-beat in virtual territory: pass resolved chords to
                    # the MIDI smart metronome callback.
                    primary_m = progression.resolve_virtual_measure(logical_measure)
                    chords_here = progression.find_chords_at_position(
                        Position(primary_m, logical_beat, progression.time_signature))
                    self._click(False, chords_here if chords_here else None,
                                target_time=beat_logical)
                else:
                    self._click(False, target_time=beat_logical)

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
                # Include the full virtual territory (hidden body + ending 2 or
                # all plain-repeat copies) in the playback range.
                last_m = max(last_m, vb.after_repeat_measure() - 1)

        # Latency compensation (see _precount_and_record for rationale).
        comp_s = self._get_clamped_compensation(interval)
        # True when audio (not MIDI) compensation is in use, meaning the click
        # fires comp_s before the logical beat and the chord call must be
        # delayed by the same amount so both are heard simultaneously.
        use_audio_comp = not self._use_midi_compensation()

        # Anchor the beat grid to an absolute timeline so processing overhead
        # (chord lookup, speak, play_sound enqueue) does not accumulate and
        # drift the metronome — same pattern used in _precount_and_record.
        #
        # Setting t0 = now + comp_s makes the *logical* beat-1 time equal to
        # t0 so that beat 1 fires comp_s early (same as beats 2+).
        t0 = time.monotonic() + comp_s
        beat_count = 0

        while not self._playback_stop.is_set():
            # Logical time at which this beat is meant to be heard.
            beat_logical = t0 + beat_count * interval

            # Record the logical beat time for beat_offset_ms() queries.
            self._last_beat_time = beat_logical

            # Resolve virtual measures (hidden body / plain repeat copies) to
            # their stored primary counterpart so chords are looked up correctly.
            real_m = progression.resolve_virtual_measure(cur.measure)
            lookup_cur = (cur if real_m == cur.measure
                          else Position(real_m, cur.beat, progression.time_signature))
            chords_here = progression.find_chords_at_position(lookup_cur)
            if chords_here:
                self._speak(chords_here[0].chord_name_spoken())

            # Fire the click.  For the audio path, pass beat_logical so that
            # DAC-time scheduling places the sample exactly at that moment —
            # the click fires comp_s *before* beat_logical in code time but
            # the sound arrives at beat_logical.  For the MIDI path target_time
            # is ignored and the callback fires immediately (comp_s early in
            # code time, heard ≈ beat_logical after MIDI driver latency).
            self._click(cur.beat == 1, chords_here if chords_here else None,
                        target_time=beat_logical)

            # Fire the MIDI chord accompaniment at the logical beat time.
            # When audio compensation is active the click was fired comp_s early
            # (in code time) and the MIDI chord must be delayed by the same
            # amount so both are heard simultaneously.
            if chords_here and self._on_playback_chord is not None:
                if use_audio_comp and comp_s > 0:
                    # Wait until the logical beat time before sending the chord,
                    # but wake immediately if playback is stopped.
                    chord_wait = beat_logical - time.monotonic()
                    if chord_wait > 0:
                        self._playback_stop.wait(timeout=chord_wait)
                    if self._playback_stop.is_set():
                        break
                try:
                    self._on_playback_chord(chords_here[0].chord.name)
                except Exception:
                    _logger.error("on_playback_chord callback raised", exc_info=True)

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
        # _last_beat_time is the logical (future) beat time; clamp to 0 so
        # callers never see a negative elapsed value during the lead-in window.
        return max(0.0, (time.monotonic() - self._last_beat_time) * 1000.0)

    def stop_all(self) -> None:
        """Stop both the metronome/recording and playback threads."""
        self._metronome_stop.set()
        self._playback_stop.set()
        self.state = AppState.IDLE
