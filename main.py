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
    SECTION_KEYS, NOTE_NAMES, get_note_names_for_key,
)
from sound import make_beep, get_output_devices, set_output_device, get_current_output_device
from midi_handler import MidiHandler
from recorder import Recorder, AppState
from dialogs import (
    prompt_input, new_project_dialog, project_settings_dialog,
    insert_chord_dialog, BPM_MIN, BPM_MAX,
)

# ---------------------------------------------------------------------------
# Menu command IDs (used as wx.MenuItem IDs for direct EVT_MENU dispatch)
# ---------------------------------------------------------------------------
_CMD_FILE_SAVE      = 1001
_CMD_FILE_SAVE_AS   = 1003
_CMD_FILE_OPEN      = 1004
_CMD_FILE_EXPORT    = 1002
_CMD_FILE_QR        = 1005
_CMD_FILE_QUIT      = 1006
_CMD_MIDI_REFRESH     = 2001
_CMD_MIDI_NONE        = 2002   # placeholder shown when no devices are present
_CMD_MIDI_OUT_REFRESH = 2003
_CMD_MIDI_OUT_NONE    = 2004
_CMD_SOUND_OUT_REFRESH  = 2005
_CMD_SOUND_OUT_NONE     = 2006
_CMD_SOUND_OUT_DEFAULT  = 2007  # "System default" audio device
_CMD_SETTINGS_BPM       = 3001
_CMD_SETTINGS_KEY       = 3002
_CMD_SETTINGS_STYLE     = 3003
_CMD_SETTINGS_REC_BPM   = 3004
_CMD_SETTINGS_TITLE     = 3005
_CMD_SETTINGS_COMPOSER  = 3006
_CMD_SETTINGS_TIME_SIG  = 3007
_CMD_SETTINGS_PROJECT   = 3008  # "Project Settings…" (all-in-one dialog)
_CMD_EDIT_UNDO          = 4001
_CMD_EDIT_REDO          = 4002
_CMD_EDIT_CUT           = 4003
_CMD_EDIT_COPY          = 4004
_CMD_EDIT_PASTE         = 4005
_CMD_INSERT_CHORD       = 5001
_CMD_INSERT_SM_A        = 5010
_CMD_INSERT_SM_B        = 5011
_CMD_INSERT_SM_C        = 5012
_CMD_INSERT_SM_D        = 5013
_CMD_INSERT_SM_V        = 5014
_CMD_INSERT_SM_I        = 5015
_CMD_INSERT_VOLTA       = 5020
_CMD_INSERT_NC          = 5021
_CMD_INSERT_BASS        = 5023
_CMD_RECORD_START             = 6001
_CMD_RECORD_PLAY              = 6002
_CMD_RECORD_STOP              = 6003
_CMD_RECORD_MODE_OVERDUB      = 6010
_CMD_RECORD_MODE_OVERWRITE    = 6011
_CMD_RECORD_OVERWRITE_WHOLE   = 6012
_MIDI_DEVICE_BASE      = 2100  # IDs 2100..2199 → MIDI input device indices 0..99
_MIDI_OUT_DEVICE_BASE  = 2200  # IDs 2200..2299 → MIDI output device indices 0..99
_SOUND_OUT_DEVICE_BASE = 2300  # IDs 2300..2399 → audio output device indices 0..99

# Recording modes
RECORDING_MODE_OVERDUB    = 'overdub'
RECORDING_MODE_OVERWRITE  = 'overwrite'

# Maximum undo levels
_UNDO_MAX = 50

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


def _safe_filename(title: str) -> str:
    """Return a filesystem-safe version of *title* suitable for use as a base filename."""
    import re
    safe = re.sub(r'[\\/:*?"<>|]', '', title)   # strip Windows-forbidden chars + slashes
    safe = safe.replace(' ', '_')
    safe = safe.strip('._')                       # leading/trailing dots/underscores
    return safe or 'export'

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

        # Recording mode: overdub (replace chord at same position) or
        # overwrite (at stop, delete old chords in recorded range)
        self.recording_mode: str = RECORDING_MODE_OVERDUB
        self.overwrite_whole_measure: bool = False
        self._overwrite_start: Position | None = None
        self._overwrite_recorded: set[tuple[int, int]] = set()  # (measure, beat) pairs

        # Undo / redo stacks (JSON snapshots of the progression)
        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []

        # Clipboard (chord name string for cut/copy/paste)
        self._clipboard: str | None = None

        # Menu items that may need to be checked/unchecked at runtime
        self._overdub_item:          wx.MenuItem | None = None
        self._overwrite_item:        wx.MenuItem | None = None
        self._overwrite_whole_item:  wx.MenuItem | None = None

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
            on_chord_preview=self._on_chord_preview,
            on_nc_pedal=self._on_nc_pedal,
        )
        self._midi.init()

        # wxPython frame, status labels, and menu handles (created in run())
        self._frame: wx.Frame | None = None
        self._status_labels: list[wx.StaticText] = []
        self._midi_menu: wx.Menu | None = None
        self._midi_out_menu: wx.Menu | None = None
        self._sound_out_menu: wx.Menu | None = None
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
        note_names = list(dict.fromkeys(
            get_note_names_for_key(self.progression.key)[n % 12] for n in notes
        ))
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

        self._push_undo()
        self.progression.add_chord(chord, measure, beat)
        if measure > self.progression.total_measures:
            self.progression.total_measures = measure
        if self.recording_mode == RECORDING_MODE_OVERWRITE:
            self._overwrite_recorded.add((measure, beat))
        self.speak(chord.name)

    def _on_chord_preview(self, notes: list[int]) -> None:
        """Speak the recognized chord name when a chord is played outside recording."""
        note_names = list(dict.fromkeys(
            get_note_names_for_key(self.progression.key)[n % 12] for n in notes
        ))
        chord = Chord.from_notes(note_names)
        if chord is not None:
            self.speak(chord.name)

    def _on_nc_pedal(self) -> None:
        """Called when the left (soft) pedal is pressed: toggle N.C. on current measure.

        Gated to IDLE state — during recording or playback the pedal has no
        effect because the cursor doesn't reflect the live recording position.
        """
        if self._recorder.state != AppState.IDLE:
            return
        self.toggle_no_chord()

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def _push_undo(self) -> None:
        """Snapshot the current progression onto the undo stack."""
        snapshot = self.progression.to_json()
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > _UNDO_MAX:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> None:
        if not self._undo_stack:
            self.speak("Nothing to undo")
            return
        self._redo_stack.append(self.progression.to_json())
        snapshot = self._undo_stack.pop()
        self.progression = ChordProgression.from_json(snapshot)
        self.cursor = Position(
            min(self.cursor.measure, max(self.progression.last_measure(), 1)),
            1, self.progression.time_signature,
        )
        self.speak("Undo")

    def redo(self) -> None:
        if not self._redo_stack:
            self.speak("Nothing to redo")
            return
        self._undo_stack.append(self.progression.to_json())
        snapshot = self._redo_stack.pop()
        self.progression = ChordProgression.from_json(snapshot)
        self.speak("Redo")

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def copy_chord(self) -> None:
        chords = self.progression.find_chords_at_position(self.cursor)
        if chords:
            self._clipboard = chords[0].chord.name
            self.speak(f"Copied {chords[0].chord.name}")
        else:
            self.speak("No chord at cursor")

    def cut_chord(self) -> None:
        chords = self.progression.find_chords_at_position(self.cursor)
        if chords:
            self._clipboard = chords[0].chord.name
            self._push_undo()
            self.progression.delete_chord_at(self.cursor)
            self.speak(f"Cut {self._clipboard}")
        else:
            self.speak("No chord at cursor")

    def paste_chord(self) -> None:
        if self._clipboard is None:
            self.speak("Clipboard is empty")
            return
        self._push_undo()
        self.progression.add_chord_by_name(
            self._clipboard,
            self.cursor.measure, self.cursor.beat,
        )
        self.speak(f"Pasted {self._clipboard}")

    # ------------------------------------------------------------------
    # No-chord insertion
    # ------------------------------------------------------------------

    def toggle_no_chord(self) -> None:
        """Toggle the N.C. (no chord) mark on the measure at the cursor."""
        m = self.cursor.measure
        if self.progression.is_no_chord(m):
            self._push_undo()
            self.progression.remove_no_chord(m)
            self.speak(f"N.C. removed at measure {m}")
        else:
            self._push_undo()
            self.progression.add_no_chord(m)
            self.speak(f"N.C. at measure {m}")

    # ------------------------------------------------------------------
    # Overwrite mode helpers
    # ------------------------------------------------------------------

    def _start_overwrite_session(self) -> None:
        """Called when recording starts in OVERWRITE mode."""
        self._overwrite_start = Position(
            self.cursor.measure, self.cursor.beat,
            self.progression.time_signature,
        )
        self._overwrite_recorded.clear()

    def _apply_overwrite(self) -> None:
        """
        After recording stops in OVERWRITE mode, delete old chords in the
        recorded range that weren't replaced by new ones.
        """
        if not self._overwrite_start or not self._overwrite_recorded:
            self._overwrite_start = None
            self._overwrite_recorded.clear()
            return

        ts = self.progression.time_signature
        beats = ts.numerator
        recorded_positions = {
            Position(m, b, ts) for m, b in self._overwrite_recorded
        }
        last_rec = max(recorded_positions)

        if self.overwrite_whole_measure:
            start_m = self._overwrite_start.measure
            end_m   = last_rec.measure
            to_del = [
                item for item in self.progression.items
                if start_m <= item.position.measure <= end_m
                and item.position not in recorded_positions
            ]
        else:
            to_del = [
                item for item in self.progression.items
                if self._overwrite_start <= item.position <= last_rec
                and item.position not in recorded_positions
            ]

        if to_del:
            self._push_undo()
            for item in to_del:
                self.progression.delete_chord_at(item.position)
        self._overwrite_start = None
        self._overwrite_recorded.clear()

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
        self._refresh_midi_out_devices()
        self._refresh_sound_out_devices()
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
            self._push_undo()
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
        self._push_undo()
        target.bass_note = note
        self.speak(target.chord_name())

    def add_volta(self) -> None:
        self._push_undo()
        msg = self.progression.add_volta_start(self.cursor.measure)
        self.speak(msg)

    def delete_at_cursor(self) -> None:
        self._push_undo()
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
            html_file = _safe_filename(self.progression.title) + '.html'
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
                webbrowser.open(Path(html_file).resolve().as_uri())
            except Exception:
                pass
        except Exception as e:
            self.speak(f"Export failed: {e}")

    def export_qr_code(self) -> None:
        """Generate a QR code SVG for the iReal Pro URL and open it in the browser."""
        try:
            import qrcode
            import qrcode.image.svg as qr_svg
        except ImportError:
            self.speak("QR code export requires the qrcode package (uv add qrcode)")
            return
        try:
            url = self.progression.to_ireal_url()
            factory = qr_svg.SvgFillImage
            img = qrcode.make(url, image_factory=factory)
            qr_file = _safe_filename(self.progression.title) + '_qrcode.svg'
            with open(qr_file, 'wb') as f:
                img.save(f)
            self.speak(f"QR code exported to {qr_file}")
            try:
                webbrowser.open(Path(qr_file).resolve().as_uri())
            except Exception:
                pass
        except Exception as e:
            self.speak(f"QR code export failed: {e}")

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

    def _refresh_midi_out_devices(self) -> None:
        """Rebuild the MIDI Output submenu with currently available output ports."""
        if self._midi_out_menu is None:
            return
        names = self._midi.get_output_names()
        active: int | None = None
        for i, n in enumerate(names):
            if n == self._midi.midi_output_name:
                active = i
                break

        count = self._midi_out_menu.GetMenuItemCount()
        for _ in range(max(0, count - 2)):
            item = self._midi_out_menu.FindItemByPosition(0)
            self._midi_out_menu.Remove(item)

        if names:
            for idx, name in enumerate(names):
                item = wx.MenuItem(self._midi_out_menu, _MIDI_OUT_DEVICE_BASE + idx,
                                   name, kind=wx.ITEM_CHECK)
                self._midi_out_menu.Insert(idx, item)
                if idx == active:
                    item.Check(True)
        else:
            placeholder = wx.MenuItem(self._midi_out_menu, _CMD_MIDI_OUT_NONE,
                                      "No MIDI output devices found")
            self._midi_out_menu.Insert(0, placeholder)
            placeholder.Enable(False)

    def _on_menu_midi_out_refresh(self, _event: wx.CommandEvent) -> None:
        self._refresh_midi_out_devices()
        self.speak("MIDI output devices refreshed")

    def _on_menu_midi_out_device(self, event: wx.CommandEvent) -> None:
        idx = event.GetId() - _MIDI_OUT_DEVICE_BASE
        names = self._midi.get_output_names()
        if 0 <= idx < len(names):
            self._midi.open_output_by_name(names[idx])
            self._refresh_midi_out_devices()

    def _refresh_sound_out_devices(self) -> None:
        """Rebuild the Sound Output submenu with available audio output devices."""
        if self._sound_out_menu is None:
            return
        devices = get_output_devices()  # list of (device_id, name)
        current_out = get_current_output_device()  # None = system default

        # Remove all device items (keep the trailing separator + "Refresh" = 2 items).
        count = self._sound_out_menu.GetMenuItemCount()
        for _ in range(max(0, count - 2)):
            item = self._sound_out_menu.FindItemByPosition(0)
            self._sound_out_menu.Remove(item)

        insert_pos = 0

        # Always offer a "System default" option at the top.
        default_item = wx.MenuItem(
            self._sound_out_menu, _CMD_SOUND_OUT_DEFAULT,
            "System default", kind=wx.ITEM_CHECK,
        )
        self._sound_out_menu.Insert(insert_pos, default_item)
        if current_out is None:
            default_item.Check(True)
        insert_pos += 1

        if devices:
            for list_idx, (dev_id, dev_name) in enumerate(devices):
                item = wx.MenuItem(
                    self._sound_out_menu, _SOUND_OUT_DEVICE_BASE + list_idx,
                    dev_name, kind=wx.ITEM_CHECK,
                )
                self._sound_out_menu.Insert(insert_pos, item)
                if dev_id == current_out:
                    item.Check(True)
                insert_pos += 1
        else:
            placeholder = wx.MenuItem(self._sound_out_menu, _CMD_SOUND_OUT_NONE,
                                      "No audio output devices found")
            self._sound_out_menu.Insert(insert_pos, placeholder)
            placeholder.Enable(False)

    def _on_menu_sound_out_refresh(self, _event: wx.CommandEvent) -> None:
        self._refresh_sound_out_devices()
        self.speak("Sound output devices refreshed")

    def _on_menu_sound_out_default(self, _event: wx.CommandEvent) -> None:
        set_output_device(None)
        self.speak("Sound output: system default")
        self._refresh_sound_out_devices()

    def _on_menu_sound_out_device(self, event: wx.CommandEvent) -> None:
        list_idx = event.GetId() - _SOUND_OUT_DEVICE_BASE
        devices = get_output_devices()
        if 0 <= list_idx < len(devices):
            dev_id, dev_name = devices[list_idx]
            if set_output_device(dev_id):
                self.speak(f"Sound output: {dev_name}")
            else:
                self.speak(f"Could not open: {dev_name}")
            self._refresh_sound_out_devices()

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
        current = self.progression.key
        sel_idx = KEY_SIGNATURES.index(current) if current in KEY_SIGNATURES else 0
        dlg = wx.SingleChoiceDialog(
            self._frame, "Select key signature:", "Key",
            KEY_SIGNATURES,
        )
        dlg.SetSelection(sel_idx)
        if dlg.ShowModal() == wx.ID_OK:
            key = dlg.GetStringSelection()
            self.progression.key = key
            self._update_settings_labels()
            self.speak(f"Key set to {key}")
        dlg.Destroy()

    def _menu_change_style(self) -> None:
        from pyrealpro import STYLES_ALL
        current = self.progression.style
        sel_idx = STYLES_ALL.index(current) if current in STYLES_ALL else 0
        dlg = wx.SingleChoiceDialog(
            self._frame, "Select a style:", "Style",
            STYLES_ALL,
        )
        dlg.SetSelection(sel_idx)
        if dlg.ShowModal() == wx.ID_OK:
            style = dlg.GetStringSelection()
            self.progression.style = style
            self._update_settings_labels()
            self.speak(f"Style set to {style}")
        dlg.Destroy()

    def _open_project_settings(self) -> None:
        """Open the all-in-one Project Settings dialog."""
        data = project_settings_dialog(
            parent=self._frame,
            defaults={
                'title':         self.progression.title,
                'composer':      self.progression.composer,
                'bpm':           self.progression.bpm,
                'recording_bpm': self.recording_bpm,
                'key':           self.progression.key,
                'style':         self.progression.style,
                'time_signature': str(self.progression.time_signature),
            },
        )
        if data is None:
            return
        changed = False
        if data.get('title', '').strip() and data['title'].strip() != self.progression.title:
            changed = True
        if data.get('composer', '').strip() and data['composer'].strip() != self.progression.composer:
            changed = True
        if data.get('key') and data['key'] != self.progression.key:
            changed = True
        if data.get('style') and data['style'] != self.progression.style:
            changed = True
        try:
            bpm = int(data.get('bpm', self.progression.bpm))
            if BPM_MIN <= bpm <= BPM_MAX and bpm != self.progression.bpm:
                changed = True
        except (ValueError, TypeError):
            pass
        try:
            rec_bpm = int(data.get('recording_bpm', self.recording_bpm))
            if BPM_MIN <= rec_bpm <= BPM_MAX and rec_bpm != self.recording_bpm:
                changed = True
        except (ValueError, TypeError):
            pass
        ts_str = data.get('time_signature', '')
        if ts_str and ts_str != str(self.progression.time_signature):
            changed = True
        if not changed:
            return
        self._push_undo()
        if data.get('title', '').strip():
            self.progression.title = data['title'].strip()
        if data.get('composer', '').strip():
            self.progression.composer = data['composer'].strip()
        if data.get('key'):
            self.progression.key = data['key']
        if data.get('style'):
            self.progression.style = data['style']
        try:
            bpm = int(data.get('bpm', self.progression.bpm))
            if BPM_MIN <= bpm <= BPM_MAX:
                self.progression.bpm = bpm
        except (ValueError, TypeError):
            pass
        try:
            rec_bpm = int(data.get('recording_bpm', self.recording_bpm))
            if BPM_MIN <= rec_bpm <= BPM_MAX:
                self.recording_bpm = rec_bpm
        except (ValueError, TypeError):
            pass
        if ts_str:
            try:
                from chords import TimeSignature
                ts = TimeSignature.from_string(ts_str)
                self.progression.time_signature = ts
                self.cursor = Position(
                    self.cursor.measure,
                    min(self.cursor.beat, ts.numerator),
                    ts,
                )
            except (ValueError, AttributeError):
                pass
        self._update_settings_labels()
        self.speak(f"Settings updated: {self.progression.title}")

    def _insert_chord_from_menu(self) -> None:
        """Show Insert Chord dialog and add the chord at the cursor."""
        chords_here = self.progression.find_chords_at_position(self.cursor)
        current = chords_here[0].chord.name if chords_here else 'C'
        name = insert_chord_dialog(parent=self._frame, default=current)
        if name:
            self._push_undo()
            self.progression.add_chord_by_name(name, self.cursor.measure, self.cursor.beat)
            self.speak(f"Inserted {name}")

    def _insert_bass_from_menu(self) -> None:
        """Show a prompt to enter a bass note for the chord at the cursor."""
        val = prompt_input("Bass Note", "Enter bass note (e.g. E, Bb):", "",
                           parent=self._frame)
        if val is not None:
            self.add_bass_note(val.strip())

    def _toggle_recording_mode(self, mode: str) -> None:
        self.recording_mode = mode
        if self._overdub_item:
            self._overdub_item.Check(mode == RECORDING_MODE_OVERDUB)
        if self._overwrite_item:
            self._overwrite_item.Check(mode == RECORDING_MODE_OVERWRITE)
        if self._overwrite_whole_item:
            self._overwrite_whole_item.Enable(mode == RECORDING_MODE_OVERWRITE)
        self.speak(f"Recording mode: {mode}")

    def _toggle_overwrite_whole(self) -> None:
        self.overwrite_whole_measure = not self.overwrite_whole_measure
        if self._overwrite_whole_item:
            self._overwrite_whole_item.Check(self.overwrite_whole_measure)
        label = "whole measure" if self.overwrite_whole_measure else "stop at last chord"
        self.speak(f"Overwrite: {label}")

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
        file_menu.Append(_CMD_FILE_QR,     "Export &QR Code\tCtrl+Shift+E")
        file_menu.AppendSeparator()
        file_menu.Append(_CMD_FILE_QUIT,   "&Quit\tCtrl+Q")
        menu_bar.Append(file_menu, "&File")

        # --- Edit ---
        edit_menu = wx.Menu()
        edit_menu.Append(_CMD_EDIT_UNDO,  "&Undo\tCtrl+Z")
        edit_menu.Append(_CMD_EDIT_REDO,  "&Redo\tCtrl+Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(_CMD_EDIT_CUT,   "Cu&t\tCtrl+X")
        edit_menu.Append(_CMD_EDIT_COPY,  "&Copy\tCtrl+C")
        edit_menu.Append(_CMD_EDIT_PASTE, "&Paste\tCtrl+V")
        menu_bar.Append(edit_menu, "&Edit")

        # --- Insert ---
        insert_menu = wx.Menu()
        insert_menu.Append(_CMD_INSERT_CHORD, "&Add Chord...\tCtrl+Return")
        insert_menu.AppendSeparator()

        # Section marks sub-menu
        sm_menu = wx.Menu()
        sm_menu.Append(_CMD_INSERT_SM_A, "&A (Section A)\tS+A")
        sm_menu.Append(_CMD_INSERT_SM_B, "&B (Section B)\tS+B")
        sm_menu.Append(_CMD_INSERT_SM_C, "&C (Section C)\tS+C")
        sm_menu.Append(_CMD_INSERT_SM_D, "&D (Section D)\tS+D")
        sm_menu.Append(_CMD_INSERT_SM_V, "&Verse\tS+V")
        sm_menu.Append(_CMD_INSERT_SM_I, "&Intro\tS+I")
        insert_menu.AppendSubMenu(sm_menu, "&Section Mark")

        insert_menu.Append(_CMD_INSERT_VOLTA, "&Volta / Ending\tV")
        insert_menu.AppendSeparator()
        insert_menu.Append(_CMD_INSERT_NC,     "&No Chord (N.C.)")
        insert_menu.Append(_CMD_INSERT_BASS,   "&Bass Note...\t/")
        menu_bar.Append(insert_menu, "&Insert")

        # --- Record & Playback ---
        rec_menu = wx.Menu()
        rec_menu.Append(_CMD_RECORD_START, "&Record\tR")
        rec_menu.Append(_CMD_RECORD_PLAY,  "&Play\tSpace")
        rec_menu.Append(_CMD_RECORD_STOP,  "&Stop\tEsc")
        rec_menu.AppendSeparator()
        self._overdub_item = rec_menu.AppendCheckItem(
            _CMD_RECORD_MODE_OVERDUB, "&Overdub mode")
        self._overdub_item.Check(self.recording_mode == RECORDING_MODE_OVERDUB)
        self._overwrite_item = rec_menu.AppendCheckItem(
            _CMD_RECORD_MODE_OVERWRITE, "O&verwrite mode")
        self._overwrite_item.Check(self.recording_mode == RECORDING_MODE_OVERWRITE)
        rec_menu.AppendSeparator()
        self._overwrite_whole_item = rec_menu.AppendCheckItem(
            _CMD_RECORD_OVERWRITE_WHOLE, "Overwrite: &Whole measure")
        self._overwrite_whole_item.Check(self.overwrite_whole_measure)
        self._overwrite_whole_item.Enable(
            self.recording_mode == RECORDING_MODE_OVERWRITE)
        menu_bar.Append(rec_menu, "&Record")

        # --- Settings ---
        settings_menu = wx.Menu()
        settings_menu.Append(_CMD_SETTINGS_PROJECT, "&Project Settings...\tCtrl+P")
        settings_menu.AppendSeparator()
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

        # Device sub-menus under Settings
        settings_menu.AppendSeparator()
        self._midi_menu = wx.Menu()
        self._midi_menu.AppendSeparator()
        self._midi_menu.Append(_CMD_MIDI_REFRESH, "&Refresh devices")
        settings_menu.AppendSubMenu(self._midi_menu, "MIDI &Input Device")

        self._midi_out_menu = wx.Menu()
        self._midi_out_menu.AppendSeparator()
        self._midi_out_menu.Append(_CMD_MIDI_OUT_REFRESH, "&Refresh devices")
        settings_menu.AppendSubMenu(self._midi_out_menu, "MIDI &Output Device")

        self._sound_out_menu = wx.Menu()
        self._sound_out_menu.AppendSeparator()
        self._sound_out_menu.Append(_CMD_SOUND_OUT_REFRESH, "&Refresh devices")
        settings_menu.AppendSubMenu(self._sound_out_menu, "&Sound Output")

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
        self._frame.Bind(wx.EVT_MENU, lambda e: self.export_qr_code(),
                         id=_CMD_FILE_QR)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._on_quit(),
                         id=_CMD_FILE_QUIT)
        # Edit
        self._frame.Bind(wx.EVT_MENU, lambda e: self.undo(),
                         id=_CMD_EDIT_UNDO)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.redo(),
                         id=_CMD_EDIT_REDO)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.cut_chord(),
                         id=_CMD_EDIT_CUT)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.copy_chord(),
                         id=_CMD_EDIT_COPY)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.paste_chord(),
                         id=_CMD_EDIT_PASTE)
        # Insert
        self._frame.Bind(wx.EVT_MENU, lambda e: self._insert_chord_from_menu(),
                         id=_CMD_INSERT_CHORD)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('a'),
                         id=_CMD_INSERT_SM_A)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('b'),
                         id=_CMD_INSERT_SM_B)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('c'),
                         id=_CMD_INSERT_SM_C)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('d'),
                         id=_CMD_INSERT_SM_D)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('v'),
                         id=_CMD_INSERT_SM_V)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('i'),
                         id=_CMD_INSERT_SM_I)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_volta(),
                         id=_CMD_INSERT_VOLTA)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.toggle_no_chord(),
                         id=_CMD_INSERT_NC)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._insert_bass_from_menu(),
                         id=_CMD_INSERT_BASS)
        # Record
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_record(),
                         id=_CMD_RECORD_START)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_play(),
                         id=_CMD_RECORD_PLAY)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._menu_stop(),
                         id=_CMD_RECORD_STOP)
        self._frame.Bind(wx.EVT_MENU,
                         lambda e: self._toggle_recording_mode(RECORDING_MODE_OVERDUB),
                         id=_CMD_RECORD_MODE_OVERDUB)
        self._frame.Bind(wx.EVT_MENU,
                         lambda e: self._toggle_recording_mode(RECORDING_MODE_OVERWRITE),
                         id=_CMD_RECORD_MODE_OVERWRITE)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._toggle_overwrite_whole(),
                         id=_CMD_RECORD_OVERWRITE_WHOLE)
        # Settings
        self._frame.Bind(wx.EVT_MENU, lambda e: self._open_project_settings(),
                         id=_CMD_SETTINGS_PROJECT)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_refresh,
                         id=_CMD_MIDI_REFRESH)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_out_refresh,
                         id=_CMD_MIDI_OUT_REFRESH)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_sound_out_refresh,
                         id=_CMD_SOUND_OUT_REFRESH)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_sound_out_default,
                         id=_CMD_SOUND_OUT_DEFAULT)
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
        # Bind entire device ID ranges (no per-device rebinding needed)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_device,
                         id=_MIDI_DEVICE_BASE, id2=_MIDI_DEVICE_BASE + 99)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_out_device,
                         id=_MIDI_OUT_DEVICE_BASE, id2=_MIDI_OUT_DEVICE_BASE + 99)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_sound_out_device,
                         id=_SOUND_OUT_DEVICE_BASE, id2=_SOUND_OUT_DEVICE_BASE + 99)

    def _menu_record(self) -> None:
        if self._recorder.state == AppState.IDLE:
            if self.recording_mode == RECORDING_MODE_OVERWRITE:
                self._start_overwrite_session()
            self._recorder.start_recording(
                self.progression, self.cursor,
                recording_bpm=self.recording_bpm,
            )
        else:
            self.speak("Already active")

    def _menu_play(self) -> None:
        if self._recorder.state == AppState.IDLE:
            self._recorder.start_playback(self.progression, self.cursor)
        elif self._recorder.state == AppState.PLAYING:
            self._recorder.stop_all()

    def _menu_stop(self) -> None:
        was_recording = self._recorder.state == AppState.RECORDING
        self._recorder.stop_all()
        if was_recording and self.recording_mode == RECORDING_MODE_OVERWRITE:
            self._apply_overwrite()
        self.speak("Stopped")

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
            was_recording = self._recorder.state == AppState.RECORDING
            self._recorder.stop_all()
            if was_recording and self.recording_mode == RECORDING_MODE_OVERWRITE:
                self._apply_overwrite()
            self.speak("Stopped")

        # R – record
        elif key == 'r' and not ctrl:
            if self._recorder.state == AppState.IDLE:
                if self.recording_mode == RECORDING_MODE_OVERWRITE:
                    self._start_overwrite_session()
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

        # Ctrl+E – export iReal Pro HTML
        elif ctrl and key == 'e' and not event.ShiftDown():
            self.export_ireal()

        # Ctrl+Shift+E – export QR code
        elif ctrl and key == 'e' and event.ShiftDown():
            self.export_qr_code()

        # Ctrl+Z – undo
        elif ctrl and key == 'z':
            self.undo()

        # Ctrl+Y – redo
        elif ctrl and key == 'y':
            self.redo()

        # Ctrl+C – copy chord
        elif ctrl and key == 'c':
            self.copy_chord()

        # Ctrl+X – cut chord
        elif ctrl and key == 'x':
            self.cut_chord()

        # Ctrl+V – paste chord
        elif ctrl and key == 'v':
            self.paste_chord()

        # Ctrl+L – speak recent log entries
        elif ctrl and key == 'l':
            self._speak_recent_log()

        # Ctrl+P – project settings
        elif ctrl and key == 'p':
            if self._recorder.state == AppState.IDLE:
                self._open_project_settings()

        # Ctrl+Return – insert chord dialog
        elif ctrl and kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if self._recorder.state == AppState.IDLE:
                self._insert_chord_from_menu()

        # Delete/Backspace
        elif key in ('delete', 'backspace'):
            if self._recorder.state == AppState.IDLE:
                self.delete_at_cursor()

        # N – toggle no chord
        elif key == 'n' and not ctrl and not self.s_held and not self.slash_held:
            if self._recorder.state == AppState.IDLE:
                self.toggle_no_chord()

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
        rec_mode_info = (
            f" [{self.recording_mode}"
            + (" whole" if self.overwrite_whole_measure and self.recording_mode == RECORDING_MODE_OVERWRITE else "")
            + "]"
        )
        lines = [
            f"Title: {self.progression.title}  Key: {self.progression.key}  {bpm_info}  [{file_name}]",
            f"Cursor: Measure {self.cursor.measure}, Beat {self.cursor.beat}   State: {self._recorder.state}{rec_mode_info}",
            f"Chords: {len(self.progression)}  Measures: {self.progression.total_measures}",
            "",
            _log_ring[-1] if _log_ring else "",
        ]
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            lines[3] = f"Here: {chords_here[0].chord_name()}"
        elif self.progression.is_no_chord(self.cursor.measure):
            lines[3] = "Here: N.C."
        for lbl, text in zip(self._status_labels, lines):
            lbl.SetLabel(text)
        wx.CallLater(50, self._schedule_display_update)


if __name__ == '__main__':
    app = App()
    app.run()

