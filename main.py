"""
IReal Studio – A blind-accessible chord progression recorder.

Module layout after refactoring:
  commands.py     – Menu command IDs, recording mode constants, key-sym map
  app_settings.py – Configuration constants and settings file helpers
  app_menu.py     – Menu building + menu event handler mixin (MenuMixin)
  app_keys.py     – Keyboard event handler mixin (KeysMixin)
  app_io.py       – File I/O, export and dialog mixin (IOMixin)
  main.py         – Logging setup, App core (navigation / editing / undo /
                    chord callbacks / display) and entry point

All events are written to irealstudio.log in the working directory.

File formats:
  .ips  – IReal Studio format (default)
"""
import sys
import time
import logging
import collections
import wx
import wx.adv
from pathlib import Path

from accessible_output3.outputs.auto import Auto

from chords import (
    ChordProgression, TimeSignature, Position, Chord,
    SECTION_KEYS, NOTE_NAMES, get_note_names_for_key,
    chord_name_to_spoken,
)
from sound import make_beep, get_output_devices, set_output_device, get_current_output_device
from midi_handler import MidiHandler
from recorder import Recorder, AppState
from dialogs import BPM_MIN, BPM_MAX
from i18n import _, set_language, get_language, ngettext

from commands import (
    RECORDING_MODE_OVERDUB, RECORDING_MODE_OVERWRITE, _UNDO_MAX,
)
from app_settings import (
    DEFAULT_BPM, DEFAULT_TITLE, DEFAULT_KEY, DEFAULT_STYLE, DEFAULT_TIME_SIG, SAVE_FILE,
    _load_app_settings, _save_settings_file,
)
from app_menu import MenuMixin
from app_keys import KeysMixin
from app_io import IOMixin

# ---------------------------------------------------------------------------
# Logging setup — writes timestamped records to irealstudio.log and keeps
# the last LOG_RING_SIZE messages in an in-memory ring for the in-app display.
# ---------------------------------------------------------------------------
LOG_FILE = "irealstudio.log"
LOG_RING_SIZE = 100       # entries kept in the in-memory ring buffer
LOG_SPEAK_RECENT = 5      # entries spoken by Ctrl+L

_log_ring: collections.deque = collections.deque(maxlen=LOG_RING_SIZE)


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
# Main application class
# ---------------------------------------------------------------------------
class App(MenuMixin, KeysMixin, IOMixin):
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
        self.slash_held = False

        # Recording BPM (may differ from song BPM for a slower practice pace)
        self.recording_bpm: int = DEFAULT_BPM

        # Recording mode: overdub (replace chord at same position) or
        # overwrite (at stop, delete old chords in recorded range)
        self.recording_mode: str = RECORDING_MODE_OVERDUB
        self.overwrite_whole_measure: bool = False
        self._overwrite_start: Position | None = None
        self._overwrite_recorded: set = set()  # set of (measure, beat) pairs

        # Undo / redo stacks (JSON snapshots of the progression)
        self._undo_stack: list = []
        self._redo_stack: list = []

        # Clipboard (chord name string for cut/copy/paste)
        self._clipboard: str | None = None

        # Selection state: anchor + active end (both Positions or None)
        self._sel_anchor: Position | None = None
        self._sel_active: Position | None = None

        # Unsaved-changes tracking
        self._is_dirty: bool = False

        # Tracks whether a progression was loaded at startup (used for welcome message)
        self._loaded_at_startup: bool = False

        # Menu items that may need to be checked/unchecked at runtime
        self._overdub_item = None
        self._overwrite_item = None
        self._overwrite_whole_item = None

        # Recorder owns metronome/recording/playback state
        self._recorder = Recorder(
            speak=self.speak,
            tick_sound=make_beep(1200, 10),
            tock_sound=make_beep(800,   8),
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
        self._apply_saved_settings()

        # wxPython frame, status labels, and menu handles (created in run())
        self._frame = None
        self._status_labels: list = []
        self._midi_menu = None
        self._midi_out_menu = None
        self._sound_out_menu = None

        # Current open file path (None = unsaved / new project)
        self._current_file: Path | None = None

        # Load a file passed on the command line (e.g. via Windows "Open with")
        if len(sys.argv) > 1:
            cli_path = Path(sys.argv[1])
            if cli_path.exists():
                try:
                    with open(cli_path, encoding='utf-8') as f:
                        self.progression = ChordProgression.from_json(f.read())
                    self._apply_loaded_progression(cli_path)
                    self._loaded_at_startup = True
                    self.speak(_('Loaded {title}').format(title=self.progression.title))
                except Exception as e:
                    self.speak(_('Could not load {name}: {e}').format(name=cli_path.name, e=e))
        # Auto-load the last saved project file so the user's work is restored.
        elif Path(SAVE_FILE).exists():
            try:
                with open(SAVE_FILE, encoding='utf-8') as f:
                    self.progression = ChordProgression.from_json(f.read())
                self._apply_loaded_progression(Path(SAVE_FILE))
                self._loaded_at_startup = True
                self.speak(_('Loaded {title}').format(title=self.progression.title))
            except Exception as e:
                self.speak(_('Could not load {name}: {e}').format(name=SAVE_FILE, e=e))

    # ------------------------------------------------------------------
    # Progression loading helpers
    # ------------------------------------------------------------------

    def _apply_loaded_progression(self, path: Path | None) -> None:
        """Reset all dependent app state after ``self.progression`` has been replaced.

        Called from every load path (startup auto-load, CLI load, and
        interactive open) so that the cursor, undo/redo stacks, selection,
        recording BPM and dirty flag all reflect the freshly loaded progression.
        """
        self._current_file = path
        self._is_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.cursor = Position(1, 1, self.progression.time_signature)
        self.recording_bpm = self.progression.bpm
        self._clear_selection()

    # ------------------------------------------------------------------
    # MIDI chord callbacks
    # ------------------------------------------------------------------

    def _on_chord_released(self, notes: list, first_note_time: float) -> None:
        """Commit a detected chord to the progression during recording."""
        # Deduplicate pitch classes, preserving lowest-first order.
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

        if self.progression.is_in_hidden_range(measure):
            return

        self._push_undo()
        self.progression.add_chord(chord, measure, beat)
        if measure > self.progression.total_measures:
            self.progression.total_measures = measure
        if self.recording_mode == RECORDING_MODE_OVERWRITE:
            self._overwrite_recorded.add((measure, beat))
        self._mark_dirty()
        self.speak(chord_name_to_spoken(chord.name))

    def _on_chord_preview(self, notes: list) -> None:
        """Speak the recognized chord name when played outside recording."""
        note_names = list(dict.fromkeys(
            get_note_names_for_key(self.progression.key)[n % 12] for n in notes
        ))
        chord = Chord.from_notes(note_names)
        if chord is not None:
            self.speak(chord_name_to_spoken(chord.name))

    def _on_nc_pedal(self) -> None:
        """Toggle N.C. on current measure via the soft pedal (IDLE only)."""
        if self._recorder.state != AppState.IDLE:
            return
        self.toggle_no_chord()

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def _push_undo(self) -> None:
        snapshot = self.progression.to_json()
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > _UNDO_MAX:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _mark_dirty(self) -> None:
        self._is_dirty = True

    def undo(self) -> None:
        if not self._undo_stack:
            self.speak(_('Nothing to undo'))
            return
        self._redo_stack.append(self.progression.to_json())
        snapshot = self._undo_stack.pop()
        self.progression = ChordProgression.from_json(snapshot)
        self.cursor = Position(
            min(self.cursor.measure, max(self.progression.last_measure(), 1)),
            1, self.progression.time_signature,
        )
        self._mark_dirty()
        self.speak(_('Undo'))

    def redo(self) -> None:
        if not self._redo_stack:
            self.speak(_('Nothing to redo'))
            return
        self._undo_stack.append(self.progression.to_json())
        snapshot = self._redo_stack.pop()
        self.progression = ChordProgression.from_json(snapshot)
        self._mark_dirty()
        self.speak(_('Redo'))

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def copy_chord(self) -> None:
        chords = self.progression.find_chords_at_position(self.cursor)
        if chords:
            self._clipboard = chords[0].chord.name
            self.speak(_('Copied {name}').format(name=chords[0].chord.name))
        else:
            self.speak(_('No chord at cursor'))

    def cut_chord(self) -> None:
        chords = self.progression.find_chords_at_position(self.cursor)
        if chords:
            self._clipboard = chords[0].chord.name
            self._push_undo()
            self.progression.delete_chord_at(self.cursor)
            self._mark_dirty()
            self.speak(_('Cut {name}').format(name=self._clipboard))
        else:
            self.speak(_('No chord at cursor'))

    def paste_chord(self) -> None:
        if self._clipboard is None:
            self.speak(_('Clipboard is empty'))
            return
        self._push_undo()
        self.progression.add_chord_by_name(
            self._clipboard,
            self.cursor.measure, self.cursor.beat,
        )
        self._mark_dirty()
        self.speak(_('Pasted {name}').format(name=self._clipboard))

    # ------------------------------------------------------------------
    # No-chord insertion
    # ------------------------------------------------------------------

    def toggle_no_chord(self) -> None:
        m = self.cursor.measure
        if self.progression.is_no_chord(m):
            self._push_undo()
            self.progression.remove_no_chord(m)
            self._mark_dirty()
            self.speak(_('N.C. removed at measure {m}').format(m=m))
        else:
            self._push_undo()
            self.progression.add_no_chord(m)
            self._mark_dirty()
            self.speak(_('N.C. at measure {m}').format(m=m))

    # ------------------------------------------------------------------
    # Overwrite mode helpers
    # ------------------------------------------------------------------

    def _start_overwrite_session(self) -> None:
        self._overwrite_start = Position(
            self.cursor.measure, self.cursor.beat,
            self.progression.time_signature,
        )
        self._overwrite_recorded.clear()

    def _apply_overwrite(self) -> None:
        """Delete old chords in the recorded range not replaced by new ones."""
        if not self._overwrite_start or not self._overwrite_recorded:
            self._overwrite_start = None
            self._overwrite_recorded.clear()
            return

        ts = self.progression.time_signature
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
    # App settings persistence (MIDI / audio device selection)
    # ------------------------------------------------------------------

    def _apply_saved_settings(self) -> None:
        """Restore MIDI, audio device selections and language from the config file."""
        settings = _load_app_settings()
        if not settings:
            return

        saved_lang = settings.get('language', '')
        if saved_lang:
            set_language(saved_lang)

        midi_in = settings.get('midi_input_device', '')
        if midi_in:
            names = self._midi.get_input_names()
            if midi_in in names:
                self._midi.open_by_name(midi_in)
            else:
                _app_logger.warning("Saved MIDI input '%s' not found", midi_in)

        midi_out = settings.get('midi_output_device', '')
        if midi_out:
            names = self._midi.get_output_names()
            if midi_out in names:
                self._midi.open_output_by_name(midi_out)
            else:
                _app_logger.warning("Saved MIDI output '%s' not found", midi_out)

        audio_name = settings.get('audio_output_device_name', '')
        if audio_name:
            devices = get_output_devices()
            for dev_id, dev_name in devices:
                if dev_name == audio_name:
                    set_output_device(dev_id)
                    break
            else:
                _app_logger.warning("Saved audio output '%s' not found", audio_name)

    def _save_app_settings(self) -> None:
        """Persist current device selections and language to the config file."""
        current_out = get_current_output_device()
        audio_name = ''
        if current_out is not None:
            for dev_id, dev_name in get_output_devices():
                if dev_id == current_out:
                    audio_name = dev_name
                    break
        settings = {
            'language': get_language(),
            'midi_input_device': self._midi.midi_input_name,
            'midi_output_device': self._midi.midi_output_name,
            'audio_output_device_name': audio_name,
        }
        _save_settings_file(settings)

    # ------------------------------------------------------------------
    # Selection helpers (Shift+Left/Right)
    # ------------------------------------------------------------------

    def _clear_selection(self) -> None:
        self._sel_anchor = None
        self._sel_active = None

    def _extend_selection(self, direction: str) -> None:
        if self._sel_anchor is None:
            self._sel_anchor = self.cursor
        if direction == 'right':
            nxt = self.progression.find_next_chord_to_right(self.cursor)
            if nxt and not self.progression.is_in_hidden_range(nxt.position.measure):
                self.cursor = nxt.position
                self._sel_active = self.cursor
        else:
            prv = self.progression.find_last_chord_to_left(self.cursor)
            if prv and not self.progression.is_in_hidden_range(prv.position.measure):
                self.cursor = prv.position
                self._sel_active = self.cursor
        self._announce_selection()

    def _announce_selection(self) -> None:
        chords_sel = self._chords_in_selection()
        chords_here = self.progression.find_chords_at_position(self.cursor)
        chord_part = chords_here[0].chord_name_spoken() if chords_here else ''
        n = len(chords_sel)
        count_part = ngettext('{n} chord selected', '{n} chords selected', n).format(n=n)
        self.speak(f'{chord_part} {count_part}'.strip())

    def _selected_range(self):
        if self._sel_anchor is None or self._sel_active is None:
            return None
        start = min(self._sel_anchor, self._sel_active)
        end   = max(self._sel_anchor, self._sel_active)
        return start, end

    def _chords_in_selection(self) -> list:
        rng = self._selected_range()
        if rng is None:
            return []
        start, end = rng
        return [item for item in self.progression.items
                if start <= item.position <= end]

    def _select_all(self) -> None:
        items = self.progression.items
        if not items:
            self.speak(_('No chords to select'))
            return
        self._sel_anchor = items[0].position
        self._sel_active = items[-1].position
        self.cursor = self._sel_active
        n = len(items)
        self.speak(ngettext('All {n} chord selected', 'All {n} chords selected', n).format(n=n))

    def _copy_selection(self) -> None:
        chords = self._chords_in_selection()
        if not chords:
            self.speak(_('No chords selected'))
            return
        self._clipboard = chords[0].chord.name
        self.speak(_('Copied {name}').format(name=chords[0].chord_name_spoken()))

    def _cut_selection(self) -> None:
        chords = self._chords_in_selection()
        if not chords:
            self.speak(_('No chords selected'))
            return
        self._clipboard = chords[0].chord.name
        self._push_undo()
        for item in chords:
            self.progression.delete_chord_at(item.position)
        self._mark_dirty()
        self._clear_selection()
        n = len(chords)
        self.speak(ngettext('Cut {n} chord', 'Cut {n} chords', n).format(n=n))

    def _delete_selection(self) -> None:
        chords = self._chords_in_selection()
        if not chords:
            self._clear_selection()
            self.speak(_('No chords in selection'))
            return
        anchor = self._sel_anchor
        active = self._sel_active
        if anchor is None or active is None:
            return
        start = min(anchor, active)
        prev_item = self.progression.find_last_chord_to_left(start)
        self._push_undo()
        for item in chords:
            self.progression.delete_chord_at(item.position)
        self._mark_dirty()
        self._clear_selection()
        if prev_item:
            self.cursor = prev_item.position
        else:
            self.cursor = Position(1, 1, self.progression.time_signature)
        n = len(chords)
        self.speak(ngettext('Deleted {n} chord', 'Deleted {n} chords', n).format(n=n))
        self._announce_position()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, direction: str, by_measure: bool = False, by_beat: bool = False) -> None:
        ts = self.progression.time_signature
        old_measure = self.cursor.measure
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
            if direction == 'right':
                nxt = self.progression.find_next_chord_to_right(self.cursor)
                if nxt and not self.progression.is_in_hidden_range(nxt.position.measure):
                    self.cursor = nxt.position
                elif nxt:
                    new_m = nxt.position.measure
                    for _ in range(1000):
                        if not self.progression.is_in_hidden_range(new_m):
                            break
                        new_m = self.progression.navigate_right_from_measure(new_m)
                    search = Position(max(new_m - 1, 1), ts.numerator, ts)
                    visible = self.progression.find_next_chord_to_right(search)
                    self.cursor = visible.position if visible else Position(new_m, 1, ts)
            else:
                prv = self.progression.find_last_chord_to_left(self.cursor)
                if prv and not self.progression.is_in_hidden_range(prv.position.measure):
                    self.cursor = prv.position
                elif prv:
                    new_m = prv.position.measure
                    for _ in range(1000):
                        if not self.progression.is_in_hidden_range(new_m):
                            break
                        new_m = self.progression.navigate_left_from_measure(new_m)
                    search = Position(new_m + 1, 1, ts)
                    visible = self.progression.find_last_chord_to_left(search)
                    self.cursor = visible.position if visible else Position(new_m, 1, ts)
        new_measure = self.cursor.measure
        if new_measure != old_measure:
            old_section = self.progression.get_section_at_measure(old_measure)
            new_section = self.progression.get_section_at_measure(new_measure)
            self._announce_position(announce_section=new_section != old_section)
        else:
            self._announce_position(announce_section=False)

    def navigate_home(self) -> None:
        self.cursor = Position(1, 1, self.progression.time_signature)
        self._announce_position(announce_section=True)

    def navigate_end(self) -> None:
        last_m = max(self.progression.last_measure(), 1)
        chords = self.progression.find_chords_in_measure(last_m)
        self.cursor = (
            chords[-1].position if chords
            else Position(last_m, 1, self.progression.time_signature)
        )
        self._announce_position(announce_section=True)

    # ------------------------------------------------------------------
    # Position announcement
    # ------------------------------------------------------------------

    def _section_name(self, mark: str) -> str:
        names = {
            '*A': _('Section A'), '*B': _('Section B'), '*C': _('Section C'),
            '*D': _('Section D'), '*V': _('Verse'), '*i': _('Intro'),
        }
        return names.get(mark, mark)

    def _announce_position(self, announce_section: bool = False) -> None:
        parts: list = []
        if announce_section:
            sm = self.progression.get_section_at_measure(self.cursor.measure)
            if sm:
                parts.append(self._section_name(sm))
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            parts.append(chords_here[0].chord_name_spoken())
        parts.append(_('bar {m} beat {b}').format(m=self.cursor.measure, b=self.cursor.beat))
        self.speak(' '.join(parts))

    def _announce_position_verbose(self) -> None:
        parts: list = []
        sm = self.progression.get_section_mark(self.cursor.measure)
        if sm:
            parts.append(self._section_name(sm))
        for vb in self.progression.volta_brackets:
            if self.cursor.measure == vb.ending1_start:
                parts.append(_('ending 1'))
            elif vb.is_complete() and self.cursor.measure == vb.ending2_start:
                parts.append(_('ending 2'))
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            parts.append(chords_here[0].chord_name_spoken())
        parts.append(_('bar {m} beat {b}').format(m=self.cursor.measure, b=self.cursor.beat))
        self.speak(' '.join(parts))

    # ------------------------------------------------------------------
    # Editing helpers
    # ------------------------------------------------------------------

    def add_section_mark(self, letter: str) -> None:
        mark = SECTION_KEYS.get(letter.lower())
        if mark:
            self._push_undo()
            self.progression.add_section_mark(self.cursor.measure, mark)
            self._mark_dirty()
            self.speak(_('{section} at measure {m}').format(
                section=self._section_name(mark), m=self.cursor.measure))

    def add_bass_note(self, letter: str) -> None:
        note = letter.upper()
        if note not in NOTE_NAMES:
            self.speak(_('Invalid note'))
            return
        chords = self.progression.find_chords_at_position(self.cursor)
        if not chords:
            item = self.progression.find_last_chord_to_left(self.cursor)
            if not item:
                self.speak(_('No chord to modify'))
                return
            target = item
        else:
            target = chords[0]
        self._push_undo()
        target.bass_note = note
        self._mark_dirty()
        self.speak(target.chord_name_spoken())

    def add_volta(self) -> None:
        self._push_undo()
        msg = self.progression.add_volta_start(self.cursor.measure)
        self._mark_dirty()
        self.speak(msg)

    def delete_at_cursor(self) -> None:
        """Delete the chord, section mark, or volta bracket at the cursor."""
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            prev_item = self.progression.find_last_chord_to_left(self.cursor)
            self._push_undo()
            self.progression.delete_chord_at(self.cursor)
            self._mark_dirty()
            if prev_item:
                self.cursor = prev_item.position
            else:
                self.cursor = Position(1, 1, self.progression.time_signature)
            self.speak(_('Deleted'))
            self._announce_position()
        else:
            m = self.cursor.measure
            deleted = []
            if self.progression.get_section_mark(m):
                self._push_undo()
                self.progression.remove_section_mark(m)
                self._mark_dirty()
                deleted.append(_('section mark'))
            vbs_to_remove = [
                vb for vb in self.progression.volta_brackets
                if vb.repeat_start == m or vb.ending1_start == m
                or (vb.is_complete() and vb.ending2_start == m)
            ]
            if vbs_to_remove:
                if not deleted:
                    self._push_undo()
                for vb in vbs_to_remove:
                    self.progression.volta_brackets.remove(vb)
                self._mark_dirty()
                deleted.append(_('repeat bracket'))
            if self.progression.is_no_chord(m):
                if not deleted:
                    self._push_undo()
                self.progression.remove_no_chord(m)
                self._mark_dirty()
                deleted.append(_('N.C.'))
            if deleted:
                self.speak(_('Deleted {items} at measure {m}').format(
                    items=', '.join(deleted), m=m))
            else:
                self.speak(_('Nothing to delete at measure {m} beat {b}').format(
                    m=m, b=self.cursor.beat))

    def delete_structural_at_cursor(self) -> None:
        """Delete section marks, repeat brackets, and N.C. at the current measure.

        Unlike delete_at_cursor, ignores any chord so structural marks can be
        removed even when a chord occupies the same beat. Bound to Ctrl+Delete.
        """
        m = self.cursor.measure
        deleted: list = []
        if self.progression.get_section_mark(m):
            self._push_undo()
            self.progression.remove_section_mark(m)
            self._mark_dirty()
            deleted.append(_('section mark'))
        vbs_to_remove = [
            vb for vb in self.progression.volta_brackets
            if vb.repeat_start == m or vb.ending1_start == m
            or (vb.is_complete() and vb.ending2_start == m)
        ]
        if vbs_to_remove:
            if not deleted:
                self._push_undo()
            for vb in vbs_to_remove:
                self.progression.volta_brackets.remove(vb)
            self._mark_dirty()
            deleted.append(_('repeat bracket'))
        if self.progression.is_no_chord(m):
            if not deleted:
                self._push_undo()
            self.progression.remove_no_chord(m)
            self._mark_dirty()
            deleted.append(_('N.C.'))
        if deleted:
            self.speak(_('Deleted {items} at measure {m}').format(
                items=', '.join(deleted), m=m))
        else:
            self.speak(_('Nothing to delete at measure {m} beat {b}').format(
                m=m, b=self.cursor.beat))

    # ------------------------------------------------------------------
    # Recording mode toggles
    # ------------------------------------------------------------------

    def _toggle_recording_mode(self, mode: str) -> None:
        self.recording_mode = mode
        if self._overdub_item:
            self._overdub_item.Check(mode == RECORDING_MODE_OVERDUB)
        if self._overwrite_item:
            self._overwrite_item.Check(mode == RECORDING_MODE_OVERWRITE)
        if self._overwrite_whole_item:
            self._overwrite_whole_item.Enable(mode == RECORDING_MODE_OVERWRITE)
        mode_labels = {
            RECORDING_MODE_OVERDUB:    _('overdub'),
            RECORDING_MODE_OVERWRITE:  _('overwrite'),
        }
        self.speak(_('Recording mode: {mode}').format(
            mode=mode_labels.get(mode, mode)))

    def _toggle_overwrite_whole(self) -> None:
        self.overwrite_whole_measure = not self.overwrite_whole_measure
        if self._overwrite_whole_item:
            self._overwrite_whole_item.Check(self.overwrite_whole_measure)
        label = _('whole measure') if self.overwrite_whole_measure else _('stop at last chord')
        self.speak(_('Overwrite: {label}').format(label=label))

    # ------------------------------------------------------------------
    # Speech and log
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
            self.speak('. '.join(recent))
        else:
            self.speak(_('Log is empty'))

    # ------------------------------------------------------------------
    # Main loop (wxPython)
    # ------------------------------------------------------------------

    def run(self) -> None:
        wx_app = wx.App(False)

        if self._loaded_at_startup:
            self.speak(_('IReal Studio ready. {title}. Press R to record.').format(
                title=self.progression.title))
        else:
            self.speak(_('IReal Studio ready. Press Ctrl+N for a new project or Ctrl+O to open a file.'))

        self._frame = wx.Frame(None, title="IReal Studio", size=(500, 140))
        self._frame.SetBackgroundColour(wx.Colour(30, 30, 30))
        # style=0 removes wx.TAB_TRAVERSAL so navigation keys reach _on_keydown
        panel = wx.Panel(self._frame, style=0)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._status_labels = []

        # Status labels (lines 0-3): title/key/bpm, cursor, chords, current chord
        for _i in range(4):
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

        self._frame.Bind(wx.EVT_CLOSE, self._on_close_window)

        self._build_menu_bar()
        self._refresh_menu_state()

        self._frame.Show()
        panel.SetFocus()

        self._schedule_display_update()
        self._start_background_update_check()

        wx_app.MainLoop()

    def _on_close_window(self, event) -> None:
        """Handle window close: prompt to save unsaved changes, then clean up."""
        if self._is_dirty:
            dlg = wx.MessageDialog(
                self._frame,
                _("\'{title}\' has unsaved changes.\n\nSave before closing?").format(
                    title=self.progression.title
                ),
                _('Unsaved Changes'),
                wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_WARNING,
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_CANCEL:
                event.Veto()
                return
            if result == wx.ID_YES:
                if self._current_file is not None:
                    try:
                        self._save_to_path(self._current_file)
                    except Exception as e:
                        wx.MessageBox(_('Save failed: {e}').format(e=e), _('Error'),
                                      wx.OK | wx.ICON_ERROR, self._frame)
                        event.Veto()
                        return
                else:
                    try:
                        self.save_as()
                    except Exception as e:
                        wx.MessageBox(_('Save failed: {e}').format(e=e), _('Error'),
                                      wx.OK | wx.ICON_ERROR, self._frame)
                        event.Veto()
                        return
                    if self._is_dirty:
                        event.Veto()
                        return
        self._recorder.stop_all()
        self._midi.close()
        self._frame = None
        event.Skip()

    def _on_quit(self) -> None:
        if self._frame is not None:
            self._frame.Close()

    # ------------------------------------------------------------------
    # Periodic wxPython display-update callback
    # ------------------------------------------------------------------

    def _schedule_display_update(self) -> None:
        if self._frame is None:
            return
        bpm_info = f"{_('BPM:')} {self.progression.bpm}"
        if self.recording_bpm != self.progression.bpm:
            bpm_info += f"  {_('Rec BPM')}: {self.recording_bpm}"
        dirty_marker = "*" if self._is_dirty else ""
        file_name = (self._current_file.name if self._current_file else _('[unsaved]')) + dirty_marker
        _state_labels = {
            AppState.IDLE:      _('idle'),
            AppState.PRE_COUNT: _('precount'),
            AppState.RECORDING: _('recording'),
            AppState.PLAYING:   _('playing'),
        }
        state_label = _state_labels.get(self._recorder.state, self._recorder.state)
        mode_labels = {
            RECORDING_MODE_OVERDUB:    _('overdub'),
            RECORDING_MODE_OVERWRITE:  _('overwrite'),
        }
        rec_mode_label = mode_labels.get(self.recording_mode, self.recording_mode)
        rec_mode_info = (
            f" [{rec_mode_label}"
            + (" " + _('whole') if self.overwrite_whole_measure and self.recording_mode == RECORDING_MODE_OVERWRITE else "")
            + "]"
        )
        lines = [
            f"{_('Title')}: {self.progression.title}  {_('Key')}: {self.progression.key}  {bpm_info}  [{file_name}]",
            f"{_('Cursor')}: {_('Measure')} {self.cursor.measure}, {_('Beat')} {self.cursor.beat}   {_('State')}: {state_label}{rec_mode_info}",
            f"{_('Chords')}: {len(self.progression)}  {_('Measures')}: {self.progression.total_measures}",
            "",
            _log_ring[-1] if _log_ring else "",
        ]
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if chords_here:
            lines[3] = f"{_('Here')}: {chords_here[0].chord_name()}"
        elif self.progression.is_no_chord(self.cursor.measure):
            lines[3] = f"{_('Here')}: N.C."
        if self._sel_anchor is not None and self._sel_active is not None:
            n = len(self._chords_in_selection())
            lines[3] += "  [" + _('SEL:') + " " + ngettext('{n} chord', '{n} chords', n).format(n=n) + "]"
        for lbl, text in zip(self._status_labels, lines):
            lbl.SetLabel(text)
        wx.CallLater(50, self._schedule_display_update)


if __name__ == '__main__':
    app = App()
    app.run()
