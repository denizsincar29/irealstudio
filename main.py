"""
IReal Studio - A blind-accessible chord progression recorder.

Keyboard shortcuts:
  R             - Start recording (2-measure metronome pre-count, then record)
  Space         - Speak chord progression at metronome rhythm (playback)
  Ctrl+Space    - Stop playback, navigate to stopped position
  Left          - Move cursor left (to previous chord)
  Right         - Move cursor right (to next chord)
  Ctrl+Left     - Move cursor left one measure
  Ctrl+Right    - Move cursor right one measure
  Ctrl+Home     - Go to beginning of progression
  Ctrl+End      - Go to end of progression
  S + (a/b/c/d/v/i) - Add section mark at current measure
  V             - Add volta/ending mark at current measure
  / + (a-g)     - Add bass note to chord at cursor (slash chord)
  Delete/Backspace - Delete chord at current position
  Ctrl+S        - Save progression to JSON
  Ctrl+E        - Export to iReal Pro format (HTML file)
  Escape        - Stop recording/playback
  Ctrl+Q        - Quit
"""
import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

import pygame
from accessible_output3.outputs.auto import Auto
from pychord import find_chords_from_notes

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False

from chords import (
    ChordProgression, TimeSignature, Position,
    SECTION_KEYS, NOTE_NAMES,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_BPM = 120
DEFAULT_TITLE = "My Progression"
DEFAULT_KEY = "C"
DEFAULT_STYLE = "Medium Swing"
DEFAULT_TIME_SIG = TimeSignature(4, 4)
SAVE_FILE = "progression.json"


# ---------------------------------------------------------------------------
# App state constants
# ---------------------------------------------------------------------------
class AppState:
    IDLE = 'idle'
    PRE_COUNT = 'precount'
    RECORDING = 'recording'
    PLAYING = 'playing'


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)

        self.speech = Auto()
        self.state = AppState.IDLE

        # Chord progression
        self.progression = ChordProgression(
            title=DEFAULT_TITLE,
            time_signature=DEFAULT_TIME_SIG,
            key=DEFAULT_KEY,
            style=DEFAULT_STYLE,
            bpm=DEFAULT_BPM,
        )

        # Cursor position
        self.cursor = Position(1, 1, self.progression.time_signature)

        # Recording state
        self.recording_start_time: float = 0.0
        self.held_notes: dict = {}          # midi_note -> press time
        self.chord_first_note_time: float = 0.0
        self.recording_chord_notes: list = []

        # Metronome/recording thread
        self.metronome_stop_event = threading.Event()
        self.metronome_thread = None

        # Playback thread
        self.playback_stop_event = threading.Event()
        self.playback_thread = None
        self.playback_stopped_at = None

        # Key modifier tracking
        self.s_held = False
        self.slash_held = False

        # MIDI
        self.midi_input = None
        self.midi_stop_event = threading.Event()
        self._init_midi()

        # Pygame display
        self.screen = pygame.display.set_mode((500, 110))
        pygame.display.set_caption("IReal Studio")
        self.clock = pygame.time.Clock()

        # Sounds
        self.tick_sound = self._make_beep(880, 60)
        self.tock_sound = self._make_beep(440, 60)

        # Load saved progression if it exists
        if Path(SAVE_FILE).exists():
            try:
                with open(SAVE_FILE) as f:
                    self.progression = ChordProgression.from_json(f.read())
                self.speak(f"Loaded {self.progression.title}")
            except Exception as e:
                self.speak(f"Could not load: {e}")
        else:
            self.speak("IReal Studio ready. Press R to record.")

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    def _make_beep(self, freq: int, duration_ms: int) -> pygame.mixer.Sound:
        import math
        import array as arr
        sample_rate = 44100
        num_samples = int(sample_rate * duration_ms / 1000)
        wave = arr.array('h', [
            int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
            for i in range(num_samples)
        ])
        return pygame.sndarray.make_sound(wave)

    # ------------------------------------------------------------------
    # MIDI
    # ------------------------------------------------------------------

    def _init_midi(self):
        if not MIDO_AVAILABLE:
            return
        try:
            names = mido.get_input_names()
            if names:
                self.midi_input = mido.open_input(names[0])
                t = threading.Thread(target=self._midi_loop, daemon=True)
                t.start()
        except Exception:
            pass

    def _midi_loop(self):
        while not self.midi_stop_event.is_set():
            if self.midi_input is None:
                break
            try:
                for msg in self.midi_input.iter_pending():
                    self._handle_midi(msg)
            except Exception:
                pass
            time.sleep(0.005)

    def _handle_midi(self, msg):
        if self.state != AppState.RECORDING:
            return
        note_on = (msg.type == 'note_on' and msg.velocity > 0)
        note_off = (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0)

        if note_on:
            if not self.held_notes:
                self.chord_first_note_time = time.time()
            self.held_notes[msg.note] = time.time()
            if msg.note not in self.recording_chord_notes:
                self.recording_chord_notes.append(msg.note)
        elif note_off:
            self.held_notes.pop(msg.note, None)
            if not self.held_notes and self.recording_chord_notes:
                self._commit_chord()
                self.recording_chord_notes = []

    def _commit_chord(self):
        if not self.recording_chord_notes:
            return
        notes = [NOTE_NAMES[n % 12] for n in self.recording_chord_notes]
        chords = find_chords_from_notes(notes)
        if not chords:
            return
        chord = chords[0]

        elapsed = max(0.0, self.chord_first_note_time - self.recording_start_time)
        bps = self.progression.bpm / 60.0
        beats_per_measure = self.progression.time_signature.numerator
        total_beat_0 = max(0, round(elapsed * bps))  # 0-based
        # Offset by cursor's starting beat
        total_beat_0 += self.cursor.beat_from_start - 1
        measure = total_beat_0 // beats_per_measure + 1
        beat = total_beat_0 % beats_per_measure + 1

        # Discard chords that fall in the hidden (repeated-body) range so that
        # the user does not accidentally overwrite clean chords while playing
        # through the repeated section before reaching ending 2.
        if self.progression.is_in_hidden_range(measure):
            return

        self.progression.add_chord(chord, measure, beat)
        if measure > self.progression.total_measures:
            self.progression.total_measures = measure
        self.speak(f"{chord} at {measure} colon {beat}")

    # ------------------------------------------------------------------
    # Metronome & recording
    # ------------------------------------------------------------------

    def _beat_interval(self) -> float:
        return 60.0 / self.progression.bpm

    def start_recording(self):
        self.stop_all()
        self.state = AppState.PRE_COUNT
        self.metronome_stop_event.clear()
        self.metronome_thread = threading.Thread(
            target=self._precount_and_record, daemon=True)
        self.metronome_thread.start()

    def _precount_and_record(self):
        beats = self.progression.time_signature.numerator
        beat_names = ['One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight']
        interval = self._beat_interval()

        for _ in range(2):           # 2 measure pre-count
            for b in range(beats):
                if self.metronome_stop_event.is_set():
                    self.state = AppState.IDLE
                    return
                name = beat_names[b] if b < len(beat_names) else str(b + 1)
                self.speak(name)
                if b == 0:
                    self.tick_sound.play()
                else:
                    self.tock_sound.play()
                time.sleep(interval)

        if self.metronome_stop_event.is_set():
            self.state = AppState.IDLE
            return

        self.state = AppState.RECORDING
        self.recording_start_time = time.time()
        self.held_notes.clear()
        self.recording_chord_notes.clear()
        self.speak("Recording")

        # Position-tracking metronome: tracks the logical measure/beat so it
        # can announce when we enter a hidden (repeated-body) range or reach
        # ending 2.  The click pattern stays at a steady tempo throughout.
        beats = self.progression.time_signature.numerator
        cursor_beat_0 = self.cursor.beat_from_start - 1  # 0-based offset
        beat_count = 0
        _announced_hidden = False
        _announced_ending2: set[int] = set()

        while not self.metronome_stop_event.is_set():
            # Logical 0-based beat position from beginning of progression
            abs_beat_0 = cursor_beat_0 + beat_count
            logical_measure = abs_beat_0 // beats + 1
            logical_beat_in_measure = abs_beat_0 % beats + 1

            # --- Announcements at beat 1 of each measure ---
            if logical_beat_in_measure == 1:
                if self.progression.is_in_hidden_range(logical_measure):
                    if not _announced_hidden:
                        self.speak("Repeating, chords not recorded")
                        _announced_hidden = True
                else:
                    _announced_hidden = False
                    # Announce arrival at ending 2
                    for vb in self.progression.volta_brackets:
                        if (vb.is_complete()
                                and logical_measure == vb.ending2_start
                                and logical_measure not in _announced_ending2):
                            self.speak("Ending 2")
                            _announced_ending2.add(logical_measure)
                self.tick_sound.play()
            else:
                self.tock_sound.play()

            beat_count += 1
            time.sleep(interval)

        self.state = AppState.IDLE

    def stop_all(self):
        self.metronome_stop_event.set()
        self.playback_stop_event.set()
        self.state = AppState.IDLE

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def start_playback(self):
        if self.state != AppState.IDLE:
            return
        self.state = AppState.PLAYING
        self.playback_stop_event.clear()
        self.playback_stopped_at = None
        self.playback_thread = threading.Thread(
            target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def _playback_loop(self):
        interval = self._beat_interval()
        beats = self.progression.time_signature.numerator
        cur = Position(self.cursor.measure, self.cursor.beat,
                       self.progression.time_signature)
        # Determine the true final measure, including anything past hidden ranges
        last_m = max(self.progression.last_measure(), self.progression.total_measures, 1)
        # Also check the end of any volta brackets
        for vb in self.progression.volta_brackets:
            if vb.is_complete():
                last_m = max(last_m, vb.ending2_start)

        while not self.playback_stop_event.is_set():
            chords_here = self.progression.find_chords_at_position(cur)
            if chords_here:
                self.speak(chords_here[0].chord_name())

            if cur.beat == 1:
                self.tick_sound.play()
            else:
                self.tock_sound.play()

            self.playback_stopped_at = Position(
                cur.measure, cur.beat, self.progression.time_signature)

            time.sleep(interval)
            if self.playback_stop_event.is_set():
                break

            next_beat = cur.beat + 1
            if next_beat > beats:
                next_m = self.progression.navigate_right_from_measure(cur.measure)
                if next_m > last_m:
                    break
                cur = Position(next_m, 1, self.progression.time_signature)
            else:
                cur = Position(cur.measure, next_beat, self.progression.time_signature)

        self.state = AppState.IDLE

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, direction: str, by_measure: bool = False):
        ts = self.progression.time_signature
        if by_measure:
            if direction == 'right':
                new_m = self.progression.navigate_right_from_measure(self.cursor.measure)
                self.cursor = Position(new_m, 1, ts)
            else:
                new_m = self.progression.navigate_left_from_measure(self.cursor.measure)
                self.cursor = Position(new_m, 1, ts)
        else:
            if direction == 'right':
                nxt = self.progression.find_next_chord_to_right(self.cursor)
                if nxt and not self.progression.is_in_hidden_range(nxt.position.measure):
                    self.cursor = nxt.position
                else:
                    new_pos = self.cursor + 1
                    max_iter = 1000
                    while max_iter > 0 and self.progression.is_in_hidden_range(new_pos.measure):
                        new_m = self.progression.navigate_right_from_measure(new_pos.measure - 1)
                        if new_m <= new_pos.measure:
                            break  # no forward progress, stop
                        new_pos = Position(new_m, 1, ts)
                        max_iter -= 1
                    self.cursor = new_pos
            else:
                prv = self.progression.find_last_chord_to_left(self.cursor)
                if prv and not self.progression.is_in_hidden_range(prv.position.measure):
                    self.cursor = prv.position
                else:
                    new_pos = self.cursor - 1
                    max_iter = 1000
                    while new_pos.measure > 1 and max_iter > 0 and self.progression.is_in_hidden_range(new_pos.measure):
                        new_m = self.progression.navigate_left_from_measure(new_pos.measure + 1)
                        if new_m >= new_pos.measure:
                            break  # no backward progress, stop
                        new_pos = Position(new_m, 1, ts)
                        max_iter -= 1
                    self.cursor = new_pos

        self._announce_position()

    def navigate_home(self):
        self.cursor = Position(1, 1, self.progression.time_signature)
        self._announce_position()

    def navigate_end(self):
        last_m = max(self.progression.last_measure(), 1)
        chords = self.progression.find_chords_in_measure(last_m)
        self.cursor = chords[-1].position if chords else Position(last_m, 1, self.progression.time_signature)
        self._announce_position()

    def _announce_position(self):
        parts = []
        sm = self.progression.get_section_mark(self.cursor.measure)
        if sm:
            mark_names = {'*A': 'Section A', '*B': 'Section B', '*C': 'Section C',
                          '*D': 'Section D', '*V': 'Verse', '*i': 'Intro'}
            parts.append(mark_names.get(sm, sm))

        for vb in self.progression.volta_brackets:
            if self.cursor.measure == vb.ending1_start:
                parts.append("Ending 1")
            elif vb.is_complete() and self.cursor.measure == vb.ending2_start:
                parts.append("Ending 2")

        chords_here = self.progression.find_chords_at_position(self.cursor)
        parts.append(chords_here[0].chord_name() if chords_here else "Empty")
        parts.append(f"Measure {self.cursor.measure} beat {self.cursor.beat}")
        self.speak(", ".join(parts))

    # ------------------------------------------------------------------
    # Section marks / slash chords / volta
    # ------------------------------------------------------------------

    def add_section_mark(self, letter: str):
        mark = SECTION_KEYS.get(letter.lower())
        if mark:
            self.progression.add_section_mark(self.cursor.measure, mark)
            names = {'*A': 'Section A', '*B': 'Section B', '*C': 'Section C',
                     '*D': 'Section D', '*V': 'Verse', '*i': 'Intro'}
            self.speak(f"{names.get(mark, mark)} at measure {self.cursor.measure}")

    def add_bass_note(self, letter: str):
        note = letter.upper()
        if note not in NOTE_NAMES:
            self.speak("Invalid note")
            return
        chords = self.progression.find_chords_at_position(self.cursor)
        if not chords:
            item = self.progression.find_last_chord_to_left(self.cursor)
            if not item:
                self.speak("No chord to modify")
                return
            target = item
        else:
            target = chords[0]
        target.bass_note = note
        self.speak(target.chord_name())

    def add_volta(self):
        msg = self.progression.add_volta_start(self.cursor.measure)
        self.speak(msg)

    def delete_at_cursor(self):
        self.progression.delete_chord_at(self.cursor)
        self.speak(f"Deleted at measure {self.cursor.measure} beat {self.cursor.beat}")

    # ------------------------------------------------------------------
    # Save / Export
    # ------------------------------------------------------------------

    def save_json(self):
        try:
            with open(SAVE_FILE, 'w') as f:
                f.write(self.progression.to_json())
            self.speak(f"Saved to {SAVE_FILE}")
        except Exception as e:
            self.speak(f"Save failed: {e}")

    def export_ireal(self):
        try:
            url = self.progression.to_ireal_url()
            html_file = self.progression.title.replace(' ', '_') + '.html'
            html = (
                "<!DOCTYPE html>\n<html>\n<head><title>"
                + self.progression.title
                + "</title></head>\n<body>\n<p>Opening in iReal Pro...</p>\n<p><a href=\""
                + url + "\">" + self.progression.title + "</a></p>\n"
                + "<script>window.location.href = \"" + url + "\";</script>\n"
                + "</body>\n</html>"
            )
            with open(html_file, 'w') as f:
                f.write(html)
            self.speak(f"Exported to {html_file}")
            try:
                webbrowser.open('file://' + os.path.abspath(html_file))
            except Exception:
                pass
        except Exception as e:
            self.speak(f"Export failed: {e}")

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    def speak(self, text: str):
        try:
            self.speech.output(text)
        except Exception:
            print(text)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        font = pygame.font.SysFont(None, 20)
        running = True

        while running:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    ctrl = bool(event.mod & pygame.KMOD_CTRL)

                    # Quit
                    if ctrl and event.key == pygame.K_q:
                        running = False

                    # Escape – stop
                    elif event.key == pygame.K_ESCAPE:
                        self.stop_all()
                        self.speak("Stopped")

                    # R – record
                    elif event.key == pygame.K_r and not ctrl:
                        if self.state == AppState.IDLE:
                            self.start_recording()
                        else:
                            self.speak("Already active")

                    # Space – play / stop
                    elif event.key == pygame.K_SPACE:
                        if ctrl:
                            if self.state == AppState.PLAYING:
                                self.stop_all()
                                time.sleep(0.05)
                                if self.playback_stopped_at:
                                    self.cursor = self.playback_stopped_at
                                    self._announce_position()
                        else:
                            if self.state == AppState.IDLE:
                                self.start_playback()
                            elif self.state == AppState.PLAYING:
                                self.stop_all()

                    # Navigation
                    elif event.key == pygame.K_LEFT and not self.s_held:
                        if self.state == AppState.IDLE:
                            self.navigate('left', by_measure=ctrl)
                    elif event.key == pygame.K_RIGHT and not self.s_held:
                        if self.state == AppState.IDLE:
                            self.navigate('right', by_measure=ctrl)
                    elif event.key == pygame.K_HOME and ctrl:
                        if self.state == AppState.IDLE:
                            self.navigate_home()
                    elif event.key == pygame.K_END and ctrl:
                        if self.state == AppState.IDLE:
                            self.navigate_end()

                    # Ctrl+S – save
                    elif ctrl and event.key == pygame.K_s:
                        self.save_json()

                    # Ctrl+E – export
                    elif ctrl and event.key == pygame.K_e:
                        self.export_ireal()

                    # Delete/Backspace
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        if self.state == AppState.IDLE:
                            self.delete_at_cursor()

                    # S key held for section marks
                    elif event.key == pygame.K_s and not ctrl:
                        self.s_held = True

                    # / held for slash chords
                    elif event.key == pygame.K_SLASH:
                        self.slash_held = True

                    # V key – volta (only when not using S modifier)
                    elif event.key == pygame.K_v and not ctrl and not self.s_held:
                        self.add_volta()

                    # Letter keys A-Z
                    elif pygame.K_a <= event.key <= pygame.K_z:
                        letter = chr(event.key)
                        if self.s_held:
                            self.add_section_mark(letter)
                            self.s_held = False
                        elif self.slash_held:
                            self.add_bass_note(letter)
                            self.slash_held = False

                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_s:
                        self.s_held = False
                    elif event.key == pygame.K_SLASH:
                        self.slash_held = False

            # Draw status
            self.screen.fill((30, 30, 30))
            lines = [
                f"Title: {self.progression.title}  Key: {self.progression.key}  BPM: {self.progression.bpm}",
                f"Cursor: Measure {self.cursor.measure}, Beat {self.cursor.beat}   State: {self.state}",
                f"Chords: {len(self.progression)}  Measures: {self.progression.total_measures}",
            ]
            chords_here = self.progression.find_chords_at_position(self.cursor)
            if chords_here:
                lines.append(f"Here: {chords_here[0].chord_name()}")
            for i, line in enumerate(lines):
                surf = font.render(line, True, (200, 200, 200))
                self.screen.blit(surf, (8, 8 + i * 22))
            pygame.display.flip()

        self.stop_all()
        self.midi_stop_event.set()
        if self.midi_input:
            try:
                self.midi_input.close()
            except Exception:
                pass
        pygame.quit()


if __name__ == '__main__':
    app = App()
    app.run()
