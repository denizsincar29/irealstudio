"""
IReal Studio - A blind-accessible chord progression recorder.

Keyboard shortcuts:
  R             - Start recording (2-measure metronome pre-count, then record)
  Space         - Speak chord progression at metronome rhythm (playback)
  Ctrl+Space    - Stop playback, navigate to stopped position
  Left          - Move cursor left (to previous chord)
  Right         - Move cursor right (to next chord)
  Alt+Left      - Move cursor left one beat
  Alt+Right     - Move cursor right one beat
  Ctrl+Left     - Move cursor left one measure
  Ctrl+Right    - Move cursor right one measure
  Ctrl+Home     - Go to beginning of progression
  Ctrl+End      - Go to end of progression
  P             - Speak full position: section, ending, chord, bar, beat
  S + (a/b/c/d/v/i) - Add section mark at current measure
  V             - Add volta/ending mark at current measure
  / + (a-g)     - Add bass note to chord at cursor (slash chord)
  Delete/Backspace - Delete chord at current position
  Ctrl+O        - Open progression file (.ips or .json)
  Ctrl+S        - Save progression (to current file, or prompts if new)
  Ctrl+E        - Export to iReal Pro format (HTML file)
  Ctrl+L        - Speak last 5 log entries (MIDI errors, etc.)
  Escape        - Stop recording/playback
  Ctrl+Q        - Quit

All events are written to irealstudio.log in the working directory.

File formats:
  .ips  - IReal Studio format (default); same JSON content as .json
  .json - Legacy JSON format, still supported for reading and writing

On Windows the program can be registered as the default handler for .ips files
via "Open with" so that double-clicking a .ips file opens it in IReal Studio.

On Windows a native menu bar is available (use Alt to activate):
  File          - Open, Save, Save As, Export to iReal Pro
  MIDI Device   - Select MIDI input port, refresh device list
  Settings      - Change Title, Composer, Time Signature, BPM, Recording BPM,
                  Key, Style interactively
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

from chords import (
    ChordProgression, TimeSignature, Position, Chord,
    SECTION_KEYS, NOTE_NAMES,
)
from sound import make_beep
from midi_handler import MidiHandler
from recorder import Recorder, AppState
from dialogs import prompt_input, new_project_dialog, BPM_MIN, BPM_MAX

# ---------------------------------------------------------------------------
# Menu command IDs (used as wx.MenuItem IDs for direct EVT_MENU dispatch)
# ---------------------------------------------------------------------------
_CMD_FILE_SAVE      = 1001
_CMD_FILE_SAVE_AS   = 1003
_CMD_FILE_OPEN      = 1004
_CMD_FILE_EXPORT    = 1002
_CMD_MIDI_REFRESH   = 2001
_CMD_MIDI_NONE      = 2002   # placeholder shown when no devices are present
_CMD_SETTINGS_BPM       = 3001
_CMD_SETTINGS_KEY       = 3002
_CMD_SETTINGS_STYLE     = 3003
_CMD_SETTINGS_REC_BPM   = 3004
_CMD_SETTINGS_TITLE     = 3005
_CMD_SETTINGS_COMPOSER  = 3006
_CMD_SETTINGS_TIME_SIG  = 3007
_MIDI_DEVICE_BASE   = 2100   # IDs 2100..2199 → MIDI device indices 0..99

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
SAVE_FILE = "progression.ips"

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

        # Recording BPM (may differ from song BPM so user can record at a slower pace)
        self.recording_bpm: int = DEFAULT_BPM

        # Recorder owns metronome/recording/playback state
        self._recorder = Recorder(
            speak=self.speak,
            tick_sound=make_beep(1200, 10),   # short high downbeat click
            tock_sound=make_beep(800,   8),   # short lower upbeat click
        )

        # MIDI handler owns port management and chord detection
        self._midi = MidiHandler(
            speak=self.speak,
            on_chord_released=self._on_chord_released,
            is_recording=lambda: self._recorder.state == AppState.RECORDING,
        )
        self._midi.init()

        # wxPython frame, status labels, and menu handles (created in run())
        self._frame: wx.Frame | None = None
        self._status_labels: list[wx.StaticText] = []
        self._midi_menu: wx.Menu | None = None
        self._bpm_item:          wx.MenuItem | None = None
        self._rec_bpm_item:      wx.MenuItem | None = None
        self._key_item:          wx.MenuItem | None = None
        self._style_item:        wx.MenuItem | None = None
        self._title_item:        wx.MenuItem | None = None
        self._composer_item:     wx.MenuItem | None = None
        self._time_sig_item:     wx.MenuItem | None = None

        # Current open file path (None = unsaved / new project)
        self._current_file: Path | None = None

        # Load a file passed on the command line (e.g. via Windows "Open with")
        if len(sys.argv) > 1:
            cli_path = Path(sys.argv[1])
            if cli_path.exists():
                try:
                    with open(cli_path, encoding='utf-8') as f:
                        self.progression = ChordProgression.from_json(f.read())
                    self._current_file = cli_path
                    self._is_new_project = False
                    self.speak(f"Loaded {self.progression.title}")
                except Exception as e:
                    self._is_new_project = True
                    self.speak(f"Could not load {cli_path.name}: {e}")
            else:
                self._is_new_project = True
        # Load saved progression if it exists; otherwise flag for new-project dialog
        # Try .ips first, then fall back to legacy .json
        elif Path(SAVE_FILE).exists():
            try:
                with open(SAVE_FILE, encoding='utf-8') as f:
                    self.progression = ChordProgression.from_json(f.read())
                self._current_file = Path(SAVE_FILE)
                self._is_new_project = False
                self.speak(f"Loaded {self.progression.title}")
            except Exception as e:
                self._is_new_project = True
                self.speak(f"Could not load: {e}")
        elif Path("progression.json").exists():
            # Backward-compatibility: migrate from legacy JSON file
            try:
                with open("progression.json", encoding='utf-8') as f:
                    self.progression = ChordProgression.from_json(f.read())
                self._current_file = None  # will prompt Save As on next Ctrl+S
                self._is_new_project = False
                self.speak(f"Loaded {self.progression.title} (legacy JSON)")
            except Exception as e:
                self._is_new_project = True
                self.speak(f"Could not load: {e}")
        else:
            self._is_new_project = True

    # ------------------------------------------------------------------
    # MIDI chord callback
    # ------------------------------------------------------------------

    def _on_chord_released(self, notes: list[int], first_note_time: float) -> None:
        """Commit a detected chord to the progression during recording."""
        # Deduplicate pitch classes (same note in different octaves counts once),
        # preserving lowest-first order so the root is the first element.
        note_names = list(dict.fromkeys(NOTE_NAMES[n % 12] for n in notes))
        chord = Chord.from_notes(note_names)
        if chord is None:
            return

        elapsed = max(0.0, first_note_time - self._recorder.recording_start_time)
        bps = self._recorder.recording_bpm / 60.0
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
        """Rebuild the MIDI Device submenu with currently available ports."""
        if self._midi_menu is None:
            return
        names = self._midi.get_input_names()
        active: int | None = None
        for i, n in enumerate(names):
            if n == self._midi.midi_input_name:
                active = i
                break

        # Remove all device entries that sit above the separator
        count = self._midi_menu.GetMenuItemCount()
        # Last two items are always: separator + "Refresh devices"
        for _ in range(max(0, count - 2)):
            item = self._midi_menu.FindItemByPosition(0)
            self._midi_menu.Remove(item)

        if names:
            if active is None:
                self._midi.open_by_name(names[0])
                active = 0
            for idx, name in enumerate(names):
                item = wx.MenuItem(self._midi_menu, _MIDI_DEVICE_BASE + idx,
                                   name, kind=wx.ITEM_CHECK)
                self._midi_menu.Insert(idx, item)
                if idx == active:
                    item.Check(True)
        else:
            placeholder = wx.MenuItem(self._midi_menu, _CMD_MIDI_NONE,
                                      "No MIDI devices found")
            self._midi_menu.Insert(0, placeholder)
            placeholder.Enable(False)

    def _refresh_menu_state(self) -> None:
        """Push current app state into the menu labels."""
        self._refresh_midi_devices()
        self._update_settings_labels()

    def _update_settings_labels(self) -> None:
        """Update the Settings menu items to display current values."""
        if self._title_item:
            self._title_item.SetItemLabel(
                f"&Title: {self.progression.title}...")
        if self._composer_item:
            self._composer_item.SetItemLabel(
                f"C&omposer: {self.progression.composer}...")
        if self._time_sig_item:
            self._time_sig_item.SetItemLabel(
                f"T&ime Signature: {self.progression.time_signature}...")
        if self._bpm_item:
            self._bpm_item.SetItemLabel(
                f"&BPM: {self.progression.bpm}...")
        if self._rec_bpm_item:
            self._rec_bpm_item.SetItemLabel(
                f"&Recording BPM: {self.recording_bpm}...")
        if self._key_item:
            self._key_item.SetItemLabel(
                f"&Key: {self.progression.key}...")
        if self._style_item:
            self._style_item.SetItemLabel(
                f"&Style: {self.progression.style}...")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, direction: str, by_measure: bool = False, by_beat: bool = False) -> None:
        ts = self.progression.time_signature
        if by_measure:
            if direction == 'right':
                new_m = self.progression.navigate_right_from_measure(self.cursor.measure)
            else:
                new_m = self.progression.navigate_left_from_measure(self.cursor.measure)
            self.cursor = Position(new_m, 1, ts)
        elif by_beat:
            if direction == 'right':
                self.cursor = self.cursor + 1
            else:
                self.cursor = self.cursor - 1
        else:
            # Chord navigation: jump to nearest visible chord, skipping hidden ranges.
            if direction == 'right':
                nxt = self.progression.find_next_chord_to_right(self.cursor)
                if nxt and not self.progression.is_in_hidden_range(nxt.position.measure):
                    self.cursor = nxt.position
                elif nxt:
                    # Next chord is in a hidden range; skip past it and find first visible chord.
                    new_m = nxt.position.measure
                    for _ in range(1000):
                        if not self.progression.is_in_hidden_range(new_m):
                            break
                        new_m = self.progression.navigate_right_from_measure(new_m)
                    search = Position(max(new_m - 1, 1), ts.numerator, ts)
                    visible = self.progression.find_next_chord_to_right(search)
                    self.cursor = visible.position if visible else Position(new_m, 1, ts)
                # else: no chord to the right — stay put
            else:
                prv = self.progression.find_last_chord_to_left(self.cursor)
                if prv and not self.progression.is_in_hidden_range(prv.position.measure):
                    self.cursor = prv.position
                elif prv:
                    # Previous chord is in a hidden range; skip back past it and find last visible chord.
                    new_m = prv.position.measure
                    for _ in range(1000):
                        if not self.progression.is_in_hidden_range(new_m):
                            break
                        new_m = self.progression.navigate_left_from_measure(new_m)
                    search = Position(new_m + 1, 1, ts)
                    visible = self.progression.find_last_chord_to_left(search)
                    self.cursor = visible.position if visible else Position(new_m, 1, ts)
                # else: no chord to the left — stay put
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

    def _save_to_path(self, path: Path) -> None:
        """Write the progression as JSON/IPS to *path* and update _current_file."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.progression.to_json())
        self._current_file = path

    def save(self) -> None:
        """Save to the current file; prompt for a path if none is set yet."""
        if self._current_file is not None:
            try:
                self._save_to_path(self._current_file)
                self.speak(f"Saved to {self._current_file.name}")
            except Exception as e:
                self.speak(f"Save failed: {e}")
        else:
            self.save_as()

    def save_as(self) -> None:
        """Show a Save-As dialog; save as .ips by default, .json also accepted."""
        if self._frame is not None:
            default_name = (
                self.progression.title.replace(' ', '_') + '.ips'
            )
            dlg = wx.FileDialog(
                self._frame,
                message="Save progression",
                defaultFile=default_name,
                wildcard=(
                    "IReal Studio files (*.ips)|*.ips"
                    "|JSON files (*.json)|*.json"
                    "|All files (*.*)|*.*"
                ),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            if dlg.ShowModal() == wx.ID_OK:
                path = Path(dlg.GetPath())
                dlg.Destroy()
                try:
                    self._save_to_path(path)
                    self.speak(f"Saved to {path.name}")
                except Exception as e:
                    self.speak(f"Save failed: {e}")
            else:
                dlg.Destroy()
        else:
            # Fallback (no GUI)
            try:
                self._save_to_path(Path(SAVE_FILE))
                self.speak(f"Saved to {SAVE_FILE}")
            except Exception as e:
                self.speak(f"Save failed: {e}")

    # Backward-compatible alias kept for the Ctrl+S menu binding
    def save_json(self) -> None:
        self.save()

    def open_file(self) -> None:
        """Show an Open dialog and load the selected .ips or .json file."""
        if self._frame is None:
            return
        dlg = wx.FileDialog(
            self._frame,
            message="Open progression",
            wildcard=(
                "IReal Studio files (*.ips)|*.ips"
                "|JSON files (*.json)|*.json"
                "|All files (*.*)|*.*"
            ),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            path = Path(dlg.GetPath())
            dlg.Destroy()
            try:
                with open(path, encoding='utf-8') as f:
                    self.progression = ChordProgression.from_json(f.read())
                self._current_file = path
                self.cursor = Position(1, 1, self.progression.time_signature)
                self.speak(f"Opened {self.progression.title}")
            except Exception as e:
                self.speak(f"Open failed: {e}")
        else:
            dlg.Destroy()

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
            with open(html_file, 'w', encoding='utf-8') as f:
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
    # Menu event handlers (EVT_MENU — fired directly by wxPython)
    # ------------------------------------------------------------------

    def _on_menu_midi_refresh(self, _event: wx.CommandEvent) -> None:
        self._refresh_midi_devices()
        self.speak("MIDI devices refreshed")

    def _on_menu_midi_device(self, event: wx.CommandEvent) -> None:
        idx = event.GetId() - _MIDI_DEVICE_BASE
        names = self._midi.get_input_names()
        if 0 <= idx < len(names):
            self._midi.open_by_name(names[idx])
            self._refresh_midi_devices()
            self.speak(f"MIDI: {names[idx]}")

    def _menu_change_bpm(self) -> None:
        val = prompt_input(f"BPM", f"Enter new BPM ({BPM_MIN}–{BPM_MAX}):",
                           str(self.progression.bpm), parent=self._frame)
        if val is not None:
            try:
                bpm = int(val)
                if BPM_MIN <= bpm <= BPM_MAX:
                    self.progression.bpm = bpm
                    self._update_settings_labels()
                    self.speak(f"BPM set to {bpm}")
                else:
                    self.speak(f"BPM must be between {BPM_MIN} and {BPM_MAX}")
            except ValueError:
                self.speak("Invalid BPM value")

    def _menu_change_recording_bpm(self) -> None:
        val = prompt_input("Recording BPM",
                           f"Enter recording BPM ({BPM_MIN}–{BPM_MAX})\n"
                           "Record at a slower pace; playback uses the song BPM:",
                           str(self.recording_bpm), parent=self._frame)
        if val is not None:
            try:
                bpm = int(val)
                if BPM_MIN <= bpm <= BPM_MAX:
                    self.recording_bpm = bpm
                    self._update_settings_labels()
                    self.speak(f"Recording BPM set to {bpm}")
                else:
                    self.speak(f"BPM must be between {BPM_MIN} and {BPM_MAX}")
            except ValueError:
                self.speak("Invalid BPM value")

    def _menu_change_title(self) -> None:
        val = prompt_input("Title", "Enter song title:",
                           self.progression.title, parent=self._frame)
        if val is not None:
            self.progression.title = val.strip() or self.progression.title
            self._update_settings_labels()
            self.speak(f"Title set to {self.progression.title}")

    def _menu_change_composer(self) -> None:
        val = prompt_input("Composer", "Enter composer name:",
                           self.progression.composer, parent=self._frame)
        if val is not None:
            self.progression.composer = val.strip() or self.progression.composer
            self._update_settings_labels()
            self.speak(f"Composer set to {self.progression.composer}")

    def _menu_change_time_signature(self) -> None:
        val = prompt_input("Time Signature",
                           "Enter time signature (e.g. 4/4, 3/4, 6/8):",
                           str(self.progression.time_signature),
                           parent=self._frame)
        if val is not None:
            val = val.strip()
            try:
                ts = TimeSignature.from_string(val)
                if ts.numerator < 1 or ts.denominator < 1:
                    raise ValueError("numerator and denominator must be positive")
                self.progression.time_signature = ts
                # Update cursor to the same measure but clamp beat to valid range
                self.cursor = Position(
                    self.cursor.measure,
                    min(self.cursor.beat, ts.numerator),
                    ts,
                )
                self._update_settings_labels()
                self.speak(f"Time signature set to {ts}")
            except (ValueError, AttributeError):
                self.speak(f"Invalid time signature: {val}. Use format N/D (e.g. 4/4)")

    def _menu_change_key(self) -> None:
        from pyrealpro import KEY_SIGNATURES
        val = prompt_input("Key", "Enter key (e.g. C, Bb, F#-):",
                           self.progression.key, parent=self._frame)
        if val is not None:
            key = val.strip()
            if key in KEY_SIGNATURES:
                self.progression.key = key
                self._update_settings_labels()
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
                self._update_settings_labels()
                self.speak(f"Style set to {style}")
            else:
                self.speak(f"Unknown style: {style}")

    # ------------------------------------------------------------------
    # Main loop (wxPython)
    # ------------------------------------------------------------------

    def run(self) -> None:
        wx_app = wx.App(False)

        # --- New-project dialog (shown before the main window) ---
        if self._is_new_project:
            data = new_project_dialog(
                parent=None,
                defaults={
                    'title':    self.progression.title,
                    'composer': self.progression.composer,
                    'key':      self.progression.key,
                    'style':    self.progression.style,
                    'bpm':      self.progression.bpm,
                },
            )
            if data:
                self.progression.title    = data['title']
                self.progression.composer = data['composer']
                self.progression.key      = data['key']
                self.progression.style    = data['style']
                try:
                    bpm = int(data['bpm'])
                    if BPM_MIN <= bpm <= BPM_MAX:
                        self.progression.bpm = bpm
                        self.recording_bpm   = bpm   # default rec BPM = song BPM
                    else:
                        self.speak(
                            f"BPM {bpm} out of range ({BPM_MIN}–{BPM_MAX}); "
                            f"using {self.progression.bpm}")
                except ValueError:
                    self.speak(
                        f"Invalid BPM '{data['bpm']}'; "
                        f"using {self.progression.bpm}")
        self.speak(f"IReal Studio ready. {self.progression.title}. Press R to record.")

        self._frame = wx.Frame(None, title="IReal Studio", size=(500, 140))
        self._frame.SetBackgroundColour(wx.Colour(30, 30, 30))
        # style=0 removes wx.TAB_TRAVERSAL so navigation keys reach _on_keydown
        panel = wx.Panel(self._frame, style=0)
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

        # Build and attach the native wx.MenuBar
        self._build_menu_bar()
        self._refresh_menu_state()

        self._frame.Show()
        # Give keyboard focus to the panel so key events are received immediately
        panel.SetFocus()

        self._schedule_display_update()

        wx_app.MainLoop()

    def _build_menu_bar(self) -> None:
        """Create a wx.MenuBar and attach it to the frame with EVT_MENU bindings."""
        menu_bar = wx.MenuBar()

        # --- File ---
        file_menu = wx.Menu()
        file_menu.Append(_CMD_FILE_OPEN,   "&Open...\tCtrl+O")
        file_menu.Append(_CMD_FILE_SAVE,   "&Save\tCtrl+S")
        file_menu.Append(_CMD_FILE_SAVE_AS, "Save &As...")
        file_menu.AppendSeparator()
        file_menu.Append(_CMD_FILE_EXPORT, "&Export to iReal Pro\tCtrl+E")
        menu_bar.Append(file_menu, "&File")

        # --- MIDI Device (device items are populated by _refresh_midi_devices) ---
        self._midi_menu = wx.Menu()
        self._midi_menu.AppendSeparator()
        self._midi_menu.Append(_CMD_MIDI_REFRESH, "&Refresh devices")
        menu_bar.Append(self._midi_menu, "&MIDI Device")

        # --- Settings ---
        settings_menu = wx.Menu()
        self._title_item    = settings_menu.Append(
            _CMD_SETTINGS_TITLE,    f"&Title: {self.progression.title}...")
        self._composer_item = settings_menu.Append(
            _CMD_SETTINGS_COMPOSER, f"C&omposer: {self.progression.composer}...")
        self._time_sig_item = settings_menu.Append(
            _CMD_SETTINGS_TIME_SIG, f"T&ime Signature: {self.progression.time_signature}...")
        settings_menu.AppendSeparator()
        self._bpm_item      = settings_menu.Append(
            _CMD_SETTINGS_BPM,      f"&BPM: {self.progression.bpm}...")
        self._rec_bpm_item  = settings_menu.Append(
            _CMD_SETTINGS_REC_BPM,  f"&Recording BPM: {self.recording_bpm}...")
        self._key_item      = settings_menu.Append(
            _CMD_SETTINGS_KEY,      f"&Key: {self.progression.key}...")
        self._style_item    = settings_menu.Append(
            _CMD_SETTINGS_STYLE,    f"&Style: {self.progression.style}...")
        menu_bar.Append(settings_menu, "&Settings")

        self._frame.SetMenuBar(menu_bar)

        # Bind fixed-ID menu events
        self._frame.Bind(wx.EVT_MENU, lambda e: self.open_file(),
                         id=_CMD_FILE_OPEN)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.save(),
                         id=_CMD_FILE_SAVE)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.save_as(),
                         id=_CMD_FILE_SAVE_AS)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.export_ireal(),
                         id=_CMD_FILE_EXPORT)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_refresh,
                         id=_CMD_MIDI_REFRESH)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_title(),
                         id=_CMD_SETTINGS_TITLE)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_composer(),
                         id=_CMD_SETTINGS_COMPOSER)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_time_signature(),
                         id=_CMD_SETTINGS_TIME_SIG)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_bpm(),
                         id=_CMD_SETTINGS_BPM)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_recording_bpm(),
                         id=_CMD_SETTINGS_REC_BPM)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_key(),
                         id=_CMD_SETTINGS_KEY)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_change_style(),
                         id=_CMD_SETTINGS_STYLE)
        # Bind the entire MIDI device ID range once (no per-device rebinding needed)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_device,
                         id=_MIDI_DEVICE_BASE, id2=_MIDI_DEVICE_BASE + 99)

    def _on_close_window(self, event: wx.CloseEvent) -> None:
        """Handle window close: clean up resources then allow destruction."""
        self._recorder.stop_all()
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
        alt  = event.AltDown()
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
                self._recorder.start_recording(
                    self.progression, self.cursor,
                    recording_bpm=self.recording_bpm,
                )
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
        # Left/Right: chord navigation by default; Ctrl: by measure; Alt: by beat
        elif key == 'left' and not self.s_held:
            if self._recorder.state == AppState.IDLE:
                self.navigate('left', by_measure=ctrl, by_beat=alt)
        elif key == 'right' and not self.s_held:
            if self._recorder.state == AppState.IDLE:
                self.navigate('right', by_measure=ctrl, by_beat=alt)
        elif key == 'home' and ctrl:
            if self._recorder.state == AppState.IDLE:
                self.navigate_home()
        elif key == 'end' and ctrl:
            if self._recorder.state == AppState.IDLE:
                self.navigate_end()

        # Ctrl+O – open file
        elif ctrl and key == 'o':
            if self._recorder.state == AppState.IDLE:
                self.open_file()

        # Ctrl+S – save
        elif ctrl and key == 's':
            self.save()

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

        # D key – debug: speak beat offset during recording/pre-count/playback
        elif key == 'd' and not ctrl and not self.s_held:
            if self._recorder.state != AppState.IDLE:
                offset = self._recorder.beat_offset_ms()
                self.speak(f"Beat offset {offset:.0f} milliseconds")

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
    # Periodic wxPython callback
    # ------------------------------------------------------------------

    def _schedule_display_update(self) -> None:
        if self._frame is None:
            return
        bpm_info = f"BPM: {self.progression.bpm}"
        if self.recording_bpm != self.progression.bpm:
            bpm_info += f"  Rec BPM: {self.recording_bpm}"
        file_name = self._current_file.name if self._current_file else "[unsaved]"
        lines = [
            f"Title: {self.progression.title}  Key: {self.progression.key}  {bpm_info}  [{file_name}]",
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


if __name__ == '__main__':
    app = App()
    app.run()

