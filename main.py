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
  P             - Speak full position: section, ending, chord, bar, beat
  S + (a/b/c/d/v/i) - Add section mark at current measure
  V             - Add volta/ending mark at current measure
  / + (a-g)     - Add bass note to chord at cursor (slash chord)
  Delete/Backspace - Delete chord at current position
  Ctrl+S        - Save progression to JSON
  Ctrl+E        - Export to iReal Pro format (HTML file)
  Ctrl+L        - Speak last 5 log entries (MIDI errors, etc.)
  Escape        - Stop recording/playback
  Ctrl+Q        - Quit

All events are written to irealstudio.log in the working directory.

On Windows a native menu bar is available (use Alt to activate):
  File          - Save / Export to iReal Pro
  MIDI Device   - Select MIDI input port, refresh device list
  Settings      - Change BPM, Key, Style interactively
"""
import os
import sys
import time
import logging
import collections
import webbrowser
import wx
from pathlib import Path

from accessible_output3.outputs.auto import Auto
from pychord import find_chords_from_notes

from chords import (
    ChordProgression, TimeSignature, Position,
    SECTION_KEYS, NOTE_NAMES,
)
from sound import make_beep
from midi_handler import MidiHandler
from recorder import Recorder, AppState
from windows_menu import (
    create_menu,
    CMD_FILE_SAVE, CMD_FILE_EXPORT,
    CMD_MIDI_REFRESH, CMD_SETTINGS_BPM, CMD_SETTINGS_KEY, CMD_SETTINGS_STYLE,
    _MIDI_DEVICE_BASE, _index_from_id,
)
from dialogs import prompt_input

# ---------------------------------------------------------------------------
# Logging setup — writes timestamped records to irealstudio.log and keeps
# the last LOG_RING_SIZE messages in an in-memory ring for the in-app log display.
# ---------------------------------------------------------------------------
LOG_FILE = "irealstudio.log"
LOG_RING_SIZE = 100       # entries kept in the in-memory ring buffer
LOG_SPEAK_RECENT = 5      # entries spoken by Ctrl+L

_log_ring: collections.deque[str] = collections.deque(maxlen=LOG_RING_SIZE)


class _RingHandler(logging.Handler):
    """Push formatted records into the module-level ring buffer."""
    def emit(self, record: logging.LogRecord) -> None:
        _log_ring.append(self.format(record))


_app_logger = logging.getLogger('irealstudio')
_app_logger.setLevel(logging.DEBUG)

_file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
_file_handler.setFormatter(
    logging.Formatter('%(asctime)s %(levelname)-5s %(message)s',
                      datefmt='%H:%M:%S'))
_app_logger.addHandler(_file_handler)

_ring_handler = _RingHandler()
_ring_handler.setFormatter(logging.Formatter('%(levelname)-5s %(message)s'))
_app_logger.addHandler(_ring_handler)

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
# wxPython key-code → symbolic-name map (used by both keydown and keyup)
# ---------------------------------------------------------------------------
_WX_KEY_SYM: dict[int, str] = {
    wx.WXK_LEFT:    'left',
    wx.WXK_RIGHT:   'right',
    wx.WXK_HOME:    'home',
    wx.WXK_END:     'end',
    wx.WXK_ESCAPE:  'escape',
    wx.WXK_SPACE:   'space',
    wx.WXK_DELETE:  'delete',
    wx.WXK_BACK:    'backspace',
    ord('/'):       'slash',
}


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        self.speech = Auto()

        # Chord progression and cursor
        self.progression = ChordProgression(
            title=DEFAULT_TITLE,
            time_signature=DEFAULT_TIME_SIG,
            key=DEFAULT_KEY,
            style=DEFAULT_STYLE,
            bpm=DEFAULT_BPM,
        )
        self.cursor = Position(1, 1, self.progression.time_signature)

        # Key modifier tracking (for multi-key shortcuts)
        self.s_held = False
        self.slash_held = False

        # Recorder owns metronome/recording/playback state
        self._recorder = Recorder(
            speak=self.speak,
            tick_sound=make_beep(1200, 30),   # high downbeat click
            tock_sound=make_beep(800, 25),    # lower upbeat click
        )

        # MIDI handler owns port management and chord detection
        self._midi = MidiHandler(
            speak=self.speak,
            on_chord_released=self._on_chord_released,
            is_recording=lambda: self._recorder.state == AppState.RECORDING,
        )
        self._midi.init()

        # Native Windows menu bar (window handle installed in run())
        self._menu = create_menu()

        # wxPython frame and status labels (created in run())
        self._frame: wx.Frame | None = None
        self._status_labels: list[wx.StaticText] = []

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
    # MIDI chord callback
    # ------------------------------------------------------------------

    def _on_chord_released(self, notes: list[int], first_note_time: float) -> None:
        """Commit a detected chord to the progression during recording."""
        note_names = [NOTE_NAMES[n % 12] for n in notes]
        chords = find_chords_from_notes(note_names)
        if not chords:
            return
        chord = chords[0]

        elapsed = max(0.0, first_note_time - self._recorder.recording_start_time)
        bps = self.progression.bpm / 60.0
        beats_per_measure = self.progression.time_signature.numerator
        total_beat_0 = max(0, round(elapsed * bps))
        total_beat_0 += self.cursor.beat_from_start - 1
        measure = total_beat_0 // beats_per_measure + 1
        beat = total_beat_0 % beats_per_measure + 1

        # Discard chords in hidden (volta-repeated-body) range.
        if self.progression.is_in_hidden_range(measure):
            return

        self.progression.add_chord(chord, measure, beat)
        if measure > self.progression.total_measures:
            self.progression.total_measures = measure
        self.speak(f"{chord} at {measure} colon {beat}")

    # ------------------------------------------------------------------
    # MIDI device management
    # ------------------------------------------------------------------

    def _refresh_midi_devices(self) -> None:
        """Rebuild the MIDI Device menu from currently available ports."""
        names = self._midi.get_input_names()
        active: int | None = None
        for i, n in enumerate(names):
            if n == self._midi.midi_input_name:
                active = i
                break
        self._menu.refresh_devices(names, active)
        if names and active is None:
            self._midi.open_by_name(names[0])
            self._menu.refresh_devices(names, 0)

    def _refresh_menu_state(self) -> None:
        """Push current app state into the menu labels."""
        self._refresh_midi_devices()
        self._menu.update_settings_labels(
            self.progression.bpm,
            self.progression.key,
            self.progression.style,
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, direction: str, by_measure: bool = False) -> None:
        ts = self.progression.time_signature
        if by_measure:
            if direction == 'right':
                new_m = self.progression.navigate_right_from_measure(self.cursor.measure)
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
                            break
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
                    while (
                        new_pos.measure > 1
                        and max_iter > 0
                        and self.progression.is_in_hidden_range(new_pos.measure)
                    ):
                        new_m = self.progression.navigate_left_from_measure(new_pos.measure + 1)
                        if new_m >= new_pos.measure:
                            break
                        new_pos = Position(new_m, 1, ts)
                        max_iter -= 1
                    self.cursor = new_pos
        self._announce_position()

    def navigate_home(self) -> None:
        self.cursor = Position(1, 1, self.progression.time_signature)
        self._announce_position()

    def navigate_end(self) -> None:
        last_m = max(self.progression.last_measure(), 1)
        chords = self.progression.find_chords_in_measure(last_m)
        self.cursor = (
            chords[-1].position if chords
            else Position(last_m, 1, self.progression.time_signature)
        )
        self._announce_position()

    def _announce_position(self) -> None:
        """Speak a brief position: chord (if any) then 'bar N beat M'."""
        chords_here = self.progression.find_chords_at_position(self.cursor)
        chord_part = chords_here[0].chord_name() if chords_here else ""
        pos_part = f"bar {self.cursor.measure} beat {self.cursor.beat}"
        self.speak(f"{chord_part} {pos_part}".strip())

    def _announce_position_verbose(self) -> None:
        """Speak full context: section, ending, chord (if any), bar, beat."""
        parts: list[str] = []
        mark_names = {
            '*A': 'Section A', '*B': 'Section B', '*C': 'Section C',
            '*D': 'Section D', '*V': 'Verse', '*i': 'Intro',
        }
        sm = self.progression.get_section_mark(self.cursor.measure)
        if sm:
            parts.append(mark_names.get(sm, sm))
        for vb in self.progression.volta_brackets:
            if self.cursor.measure == vb.ending1_start:
                parts.append("ending 1")
            elif vb.is_complete() and self.cursor.measure == vb.ending2_start:
                parts.append("ending 2")
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            parts.append(chords_here[0].chord_name())
        parts.append(f"bar {self.cursor.measure} beat {self.cursor.beat}")
        self.speak(" ".join(parts))

    # ------------------------------------------------------------------
    # Editing helpers
    # ------------------------------------------------------------------

    def add_section_mark(self, letter: str) -> None:
        mark = SECTION_KEYS.get(letter.lower())
        if mark:
            self.progression.add_section_mark(self.cursor.measure, mark)
            names = {
                '*A': 'Section A', '*B': 'Section B', '*C': 'Section C',
                '*D': 'Section D', '*V': 'Verse', '*i': 'Intro',
            }
            self.speak(f"{names.get(mark, mark)} at measure {self.cursor.measure}")

    def add_bass_note(self, letter: str) -> None:
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

    def add_volta(self) -> None:
        msg = self.progression.add_volta_start(self.cursor.measure)
        self.speak(msg)

    def delete_at_cursor(self) -> None:
        self.progression.delete_chord_at(self.cursor)
        self.speak(f"Deleted at measure {self.cursor.measure} beat {self.cursor.beat}")

    # ------------------------------------------------------------------
    # Save / Export
    # ------------------------------------------------------------------

    def save_json(self) -> None:
        try:
            with open(SAVE_FILE, 'w') as f:
                f.write(self.progression.to_json())
            self.speak(f"Saved to {SAVE_FILE}")
        except Exception as e:
            self.speak(f"Save failed: {e}")

    def export_ireal(self) -> None:
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
    # Speech / logging
    # ------------------------------------------------------------------

    def speak(self, text: str) -> None:
        _app_logger.info(text)
        try:
            self.speech.output(text)
        except Exception:
            print(text)

    def _speak_recent_log(self) -> None:
        """Speak the last LOG_SPEAK_RECENT log entries (bound to Ctrl+L)."""
        recent = list(_log_ring)[-LOG_SPEAK_RECENT:]
        if recent:
            self.speak(". ".join(recent))
        else:
            self.speak("Log is empty")

    # ------------------------------------------------------------------
    # Menu command handler
    # ------------------------------------------------------------------

    def _handle_menu_command(self, cmd_id: int) -> None:
        """Dispatch a command from the native Win32 menu bar."""
        if cmd_id == CMD_FILE_SAVE:
            self.save_json()
        elif cmd_id == CMD_FILE_EXPORT:
            self.export_ireal()
        elif cmd_id == CMD_MIDI_REFRESH:
            self._refresh_midi_devices()
            self.speak("MIDI devices refreshed")
        elif cmd_id == CMD_SETTINGS_BPM:
            self._menu_change_bpm()
        elif cmd_id == CMD_SETTINGS_KEY:
            self._menu_change_key()
        elif cmd_id == CMD_SETTINGS_STYLE:
            self._menu_change_style()
        elif _MIDI_DEVICE_BASE <= cmd_id < _MIDI_DEVICE_BASE + 100:
            idx = _index_from_id(cmd_id)
            names = self._midi.get_input_names()
            if 0 <= idx < len(names):
                self._midi.open_by_name(names[idx])
                self._menu.refresh_devices(names, idx)
                self.speak(f"MIDI: {names[idx]}")

    def _menu_change_bpm(self) -> None:
        val = prompt_input("BPM", "Enter new BPM (40–240):",
                           str(self.progression.bpm), parent=self._frame)
        if val is not None:
            try:
                bpm = int(val)
                if 40 <= bpm <= 240:
                    self.progression.bpm = bpm
                    self._menu.update_settings_labels(
                        bpm, self.progression.key, self.progression.style)
                    self.speak(f"BPM set to {bpm}")
                else:
                    self.speak("BPM must be between 40 and 240")
            except ValueError:
                self.speak("Invalid BPM value")

    def _menu_change_key(self) -> None:
        from pyrealpro import KEY_SIGNATURES
        val = prompt_input("Key", "Enter key (e.g. C, Bb, F#-):",
                           self.progression.key, parent=self._frame)
        if val is not None:
            key = val.strip()
            if key in KEY_SIGNATURES:
                self.progression.key = key
                self._menu.update_settings_labels(
                    self.progression.bpm, key, self.progression.style)
                self.speak(f"Key set to {key}")
            else:
                self.speak(f"Unknown key: {key}")

    def _menu_change_style(self) -> None:
        from pyrealpro import STYLES_ALL
        val = prompt_input("Style",
                           "Enter style (e.g. Medium Swing, Bossa Nova):",
                           self.progression.style, parent=self._frame)
        if val is not None:
            style = val.strip()
            if style in STYLES_ALL:
                self.progression.style = style
                self._menu.update_settings_labels(
                    self.progression.bpm, self.progression.key, style)
                self.speak(f"Style set to {style}")
            else:
                self.speak(f"Unknown style: {style}")

    # ------------------------------------------------------------------
    # Main loop (wxPython)
    # ------------------------------------------------------------------

    def run(self) -> None:
        wx_app = wx.App(False)
        self._frame = wx.Frame(None, title="IReal Studio", size=(500, 140))
        self._frame.SetBackgroundColour(wx.Colour(30, 30, 30))
        panel = wx.Panel(self._frame)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._status_labels = []

        # Status labels (lines 0-3): title/key/bpm, cursor, chords, current chord
        for _ in range(4):
            lbl = wx.StaticText(panel, label="", style=wx.ST_NO_AUTORESIZE)
            lbl.SetForegroundColour(wx.Colour(200, 200, 200))
            sizer.Add(lbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            self._status_labels.append(lbl)

        # Line 4: last log entry, tinted as a footer
        log_lbl = wx.StaticText(panel, label="", style=wx.ST_NO_AUTORESIZE)
        log_lbl.SetForegroundColour(wx.Colour(136, 136, 136))
        sizer.Add(log_lbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self._status_labels.append(log_lbl)

        panel.SetSizer(sizer)

        for w in (self._frame, panel):
            w.Bind(wx.EVT_KEY_DOWN, self._on_keydown)
            w.Bind(wx.EVT_KEY_UP,   self._on_keyup)

        # Bind close event so cleanup runs whether the user presses X or Ctrl+Q
        self._frame.Bind(wx.EVT_CLOSE, self._on_close_window)

        # Install the native menu before showing so the window appears complete
        try:
            hwnd = self._get_hwnd()
            if hwnd:
                self._menu.install(hwnd)
                self._refresh_menu_state()
        except Exception:
            pass

        self._frame.Show()

        self._schedule_display_update()
        self._schedule_menu_poll()

        wx_app.MainLoop()

    def _get_hwnd(self) -> int:
        """Return the Win32 HWND of the wxPython frame, or 0."""
        if sys.platform != 'win32' or self._frame is None:
            return 0
        return self._frame.GetHandle()

    def _on_close_window(self, event: wx.CloseEvent) -> None:
        """Handle window close: clean up resources then allow destruction."""
        self._recorder.stop_all()
        self._menu.destroy()
        self._midi.close()
        self._frame = None
        event.Skip()

    def _on_quit(self) -> None:
        if self._frame is not None:
            self._frame.Close()

    # ------------------------------------------------------------------
    # Keyboard event handlers
    # ------------------------------------------------------------------

    def _on_keydown(self, event: wx.KeyEvent) -> None:
        ctrl = event.ControlDown()
        kc   = event.GetKeyCode()
        key  = _WX_KEY_SYM.get(kc) or (chr(kc).lower() if 32 <= kc < 127 else '')

        # Quit
        if ctrl and key == 'q':
            self._on_quit()

        # Escape – stop
        elif key == 'escape':
            self._recorder.stop_all()
            self.speak("Stopped")

        # R – record
        elif key == 'r' and not ctrl:
            if self._recorder.state == AppState.IDLE:
                self._recorder.start_recording(self.progression, self.cursor)
            else:
                self.speak("Already active")

        # Space – play / stop
        elif key == 'space':
            if ctrl:
                if self._recorder.state == AppState.PLAYING:
                    self._recorder.stop_all()
                    time.sleep(0.05)
                    if self._recorder.playback_stopped_at:
                        self.cursor = self._recorder.playback_stopped_at
                        self._announce_position()
            else:
                if self._recorder.state == AppState.IDLE:
                    self._recorder.start_playback(self.progression, self.cursor)
                elif self._recorder.state == AppState.PLAYING:
                    self._recorder.stop_all()

        # Navigation
        elif key == 'left' and not self.s_held:
            if self._recorder.state == AppState.IDLE:
                self.navigate('left', by_measure=ctrl)
        elif key == 'right' and not self.s_held:
            if self._recorder.state == AppState.IDLE:
                self.navigate('right', by_measure=ctrl)
        elif key == 'home' and ctrl:
            if self._recorder.state == AppState.IDLE:
                self.navigate_home()
        elif key == 'end' and ctrl:
            if self._recorder.state == AppState.IDLE:
                self.navigate_end()

        # Ctrl+S – save
        elif ctrl and key == 's':
            self.save_json()

        # Ctrl+E – export
        elif ctrl and key == 'e':
            self.export_ireal()

        # Ctrl+L – speak recent log entries
        elif ctrl and key == 'l':
            self._speak_recent_log()

        # Delete/Backspace
        elif key in ('delete', 'backspace'):
            if self._recorder.state == AppState.IDLE:
                self.delete_at_cursor()

        # S key held for section marks
        elif key == 's' and not ctrl:
            self.s_held = True

        # / held for slash chords
        elif key == 'slash':
            self.slash_held = True

        # P – verbose position (section, ending, chord, bar, beat)
        elif key == 'p' and not ctrl and not self.s_held:
            self._announce_position_verbose()

        # V key – volta (only when not using S modifier)
        elif key == 'v' and not ctrl and not self.s_held:
            self.add_volta()

        # Letter keys A-Z
        elif len(key) == 1 and key.isalpha():
            if self.s_held:
                self.add_section_mark(key)
                self.s_held = False
            elif self.slash_held:
                self.add_bass_note(key)
                self.slash_held = False

        event.Skip()

    def _on_keyup(self, event: wx.KeyEvent) -> None:
        kc  = event.GetKeyCode()
        key = _WX_KEY_SYM.get(kc) or (chr(kc).lower() if 32 <= kc < 127 else '')
        if key == 's':
            self.s_held = False
        elif key == 'slash':
            self.slash_held = False
        event.Skip()

    # ------------------------------------------------------------------
    # Periodic wxPython callbacks
    # ------------------------------------------------------------------

    def _schedule_display_update(self) -> None:
        if self._frame is None:
            return
        lines = [
            f"Title: {self.progression.title}  Key: {self.progression.key}  BPM: {self.progression.bpm}",
            f"Cursor: Measure {self.cursor.measure}, Beat {self.cursor.beat}   State: {self._recorder.state}",
            f"Chords: {len(self.progression)}  Measures: {self.progression.total_measures}",
            "",
            _log_ring[-1] if _log_ring else "",
        ]
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            lines[3] = f"Here: {chords_here[0].chord_name()}"
        for lbl, text in zip(self._status_labels, lines):
            lbl.SetLabel(text)
        wx.CallLater(50, self._schedule_display_update)

    def _schedule_menu_poll(self) -> None:
        if self._frame is None:
            return
        for _ in range(16):
            cmd = self._menu.poll()
            if cmd is None:
                break
            self._handle_menu_command(cmd)
        wx.CallLater(16, self._schedule_menu_poll)


if __name__ == '__main__':
    app = App()
    app.run()

