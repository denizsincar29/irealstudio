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
from pathlib import Path

from accessible_output3.outputs.auto import Auto

from chords import (
    ChordProgression, Position, Chord,
    SECTION_KEYS, NOTE_NAMES, get_note_names_for_key,
    chord_name_to_spoken, voice_chord_midi,
)
from sound import make_beep, get_output_devices, set_output_device, get_current_output_device
from midi_handler import MidiHandler
from recorder import Recorder, AppState
from i18n import _, set_language, get_language, ngettext

from commands import (
    RECORDING_MODE_OVERDUB, RECORDING_MODE_OVERWRITE, _UNDO_MAX,
)
from app_settings import (
    DEFAULT_BPM, DEFAULT_TITLE, DEFAULT_KEY, DEFAULT_STYLE, DEFAULT_TIME_SIG, SAVE_FILE,
    _load_app_settings, _save_settings_file,
    MIDI_METRO_ON_NOTE, MIDI_METRO_OFF_NOTE, MIDI_METRO_VELOCITY, MIDI_METRO_CHANNEL,
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
# Chord grid visualization panel
# ---------------------------------------------------------------------------
class ChordGridPanel(wx.Panel):
    """Visual chord grid showing the progression on a 2-D grid of measures.

    * Each row shows ``MEASURES_PER_ROW`` measures left-to-right.
    * The cursor measure/beat is highlighted in blue.
    * The current selection range is highlighted in teal.
    * The playback position (during playback) is highlighted in red.
    * Mouse left-click moves the cursor; click-and-drag extends the selection.
    * Section markers (A, B, …) are drawn in amber on the measure where they start.
    """

    CELL_W: int = 140       # pixels wide per measure cell
    CELL_H: int = 60        # pixels tall per measure cell
    MEASURES_PER_ROW: int = 4

    # ---- colour palette ---------------------------------------------------
    _BG        = wx.Colour(30,  30,  30)
    _GRID      = wx.Colour(60,  60,  60)
    _TEXT      = wx.Colour(200, 200, 200)
    _MNUM      = wx.Colour(90,  90,  90)    # measure number
    _CURSOR    = wx.Colour(0,   80,  170)   # cursor cell bg
    _SEL       = wx.Colour(0,   90,  80)    # selection bg
    _PLAY      = wx.Colour(140, 0,   0)     # playback beat bg
    _SECTION   = wx.Colour(255, 200, 0)     # section marker text
    _NC        = wx.Colour(120, 120, 120)   # N.C. text
    _BEAT_LINE = wx.Colour(65,  65,  65)    # vertical beat separator

    def __init__(self, parent: wx.Window, app) -> None:
        super().__init__(parent, style=0)
        self._app = app
        self._mouse_drag = False
        self.SetBackgroundColour(self._BG)
        self.SetMinSize((-1, self.CELL_H * 4))
        self.Bind(wx.EVT_PAINT,       self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN,   self._on_mouse_down)
        self.Bind(wx.EVT_MOTION,      self._on_mouse_move)
        self.Bind(wx.EVT_LEFT_UP,     self._on_mouse_up)
        self.Bind(wx.EVT_SIZE,        lambda _e: self.Refresh())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _total_measures(self) -> int:
        prog = self._app.progression
        return max(prog.last_measure(), prog.total_measures, 1)

    def _pos_from_xy(self, mx: int, my: int):
        """Return a ``Position`` from pixel coords, or ``None`` if out of range."""
        from chords import Position as _Pos
        ts = self._app.progression.time_signature
        beats = ts.numerator
        col  = mx // self.CELL_W
        row  = my // self.CELL_H
        if col >= self.MEASURES_PER_ROW or col < 0 or row < 0:
            return None
        measure = row * self.MEASURES_PER_ROW + col + 1
        if measure > self._total_measures():
            return None
        beat_w = self.CELL_W / beats
        beat = max(1, min(beats, int((mx % self.CELL_W) / beat_w) + 1))
        return _Pos(measure, beat, ts)

    def _cell_rect(self, measure: int) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) pixel rect for a given 1-based measure number."""
        idx = measure - 1
        col = idx % self.MEASURES_PER_ROW
        row = idx // self.MEASURES_PER_ROW
        return (col * self.CELL_W, row * self.CELL_H, self.CELL_W, self.CELL_H)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def _on_paint(self, _event) -> None:
        dc = wx.PaintDC(self)
        dc.SetBackground(wx.Brush(self._BG))
        dc.Clear()

        app    = self._app
        prog   = app.progression
        cursor = app.cursor
        beats  = prog.time_signature.numerator
        total  = self._total_measures()

        # Build fast-lookup: measure → list of (beat, chord_name) or None for N.C.
        by_measure: dict[int, list[tuple[int, str | None]]] = {}
        for item in prog.items:
            m = item.position.measure
            name = None if getattr(item.chord, 'is_no_chord', False) else item.chord.name
            by_measure.setdefault(m, []).append((item.position.beat, name))

        # Selection range
        sel_range = app._selected_range()

        # Playback / recording beat
        play_pos = app._recorder.playback_stopped_at if app._recorder.state == 'playing' else None

        # Font for chord names
        font_chord = wx.Font(11, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_small = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        font_sec   = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)

        # Collect section marks
        section_marks: dict[int, str] = {}
        for sm in prog.section_marks:
            section_marks[sm.measure] = sm.name

        for m in range(1, total + 1):
            x, y, w, h = self._cell_rect(m)

            # --- background colour ---
            if play_pos and play_pos.measure == m:
                dc.SetBrush(wx.Brush(self._PLAY))
                dc.SetPen(wx.Pen(self._PLAY))
            elif cursor.measure == m:
                dc.SetBrush(wx.Brush(self._CURSOR))
                dc.SetPen(wx.Pen(self._CURSOR))
            elif sel_range and sel_range[0].measure <= m <= sel_range[1].measure:
                dc.SetBrush(wx.Brush(self._SEL))
                dc.SetPen(wx.Pen(self._SEL))
            else:
                dc.SetBrush(wx.Brush(self._BG))
                dc.SetPen(wx.Pen(self._BG))
            dc.DrawRectangle(x, y, w, h)

            # --- playback beat strip ---
            if play_pos and play_pos.measure == m:
                beat_w_px = w / beats
                bx = x + int((play_pos.beat - 1) * beat_w_px)
                dc.SetBrush(wx.Brush(wx.Colour(200, 30, 30)))
                dc.SetPen(wx.Pen(wx.Colour(200, 30, 30)))
                dc.DrawRectangle(bx, y, max(2, int(beat_w_px)), h)

            # --- cursor beat strip ---
            if cursor.measure == m:
                beat_w_px = w / beats
                bx = x + int((cursor.beat - 1) * beat_w_px)
                dc.SetBrush(wx.Brush(wx.Colour(80, 150, 255)))
                dc.SetPen(wx.Pen(wx.Colour(80, 150, 255)))
                dc.DrawRectangle(bx, y, max(2, int(beat_w_px)), h)

            # --- beat separator lines ---
            dc.SetPen(wx.Pen(self._BEAT_LINE))
            beat_w_px = w / beats
            for b in range(1, beats):
                bx = x + int(b * beat_w_px)
                dc.DrawLine(bx, y, bx, y + h)

            # --- grid border ---
            dc.SetPen(wx.Pen(self._GRID))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(x, y, w, h)

            # --- measure number (dim, top-right) ---
            dc.SetFont(font_small)
            dc.SetTextForeground(self._MNUM)
            mnum_str = str(m)
            tw, th = dc.GetTextExtent(mnum_str)
            dc.DrawText(mnum_str, x + w - tw - 3, y + 2)

            # --- section marker (amber, top-left) ---
            if m in section_marks:
                dc.SetFont(font_sec)
                dc.SetTextForeground(self._SECTION)
                dc.DrawText(section_marks[m], x + 3, y + 2)

            # --- chord names ---
            dc.SetFont(font_chord)
            chords_in_m = by_measure.get(m, [])
            if chords_in_m:
                beat_w_px = w / beats
                for beat, name in sorted(chords_in_m):
                    bx = x + int((beat - 1) * beat_w_px) + 4
                    if name is None:
                        dc.SetTextForeground(self._NC)
                        dc.DrawText("N.C.", bx, y + h // 2 - 8)
                    else:
                        dc.SetTextForeground(self._TEXT)
                        dc.DrawText(name, bx, y + h // 2 - 8)

        # Required virtual size so scroll bars appear if the grid is tall
        rows = max(1, (total + self.MEASURES_PER_ROW - 1) // self.MEASURES_PER_ROW)
        self.SetVirtualSize(self.MEASURES_PER_ROW * self.CELL_W, rows * self.CELL_H)

    # ------------------------------------------------------------------
    # Mouse events → cursor / selection
    # ------------------------------------------------------------------

    def _on_mouse_down(self, event: wx.MouseEvent) -> None:
        pos = self._pos_from_xy(event.GetX(), event.GetY())
        if pos is None:
            return
        self._mouse_drag = True
        self.CaptureMouse()
        self._app._clear_selection()
        self._app.cursor = pos
        self.Refresh()
        # Give keyboard focus back to the main input panel so key events still work.
        # Search the frame's direct children for a plain wx.Panel that is not this grid.
        if self._app._frame is not None:
            focused = False
            for child in self._app._frame.GetChildren():
                if isinstance(child, wx.Panel) and child is not self:
                    child.SetFocus()
                    focused = True
                    break
            if not focused:
                # Fallback: focus the frame itself so key events are not lost.
                self._app._frame.SetFocus()

    def _on_mouse_move(self, event: wx.MouseEvent) -> None:
        if not self._mouse_drag or not event.LeftIsDown():
            return
        pos = self._pos_from_xy(event.GetX(), event.GetY())
        if pos is None:
            return
        if self._app._sel_anchor is None:
            self._app._sel_anchor = self._app.cursor
        self._app._sel_active = pos
        self._app.cursor = pos
        self.Refresh()

    def _on_mouse_up(self, _event: wx.MouseEvent) -> None:
        if self._mouse_drag:
            self._mouse_drag = False
            if self.HasCapture():
                self.ReleaseMouse()


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
        self._overwrite_recorded: set[tuple[int, int]] = set()  # set of (measure, beat) pairs

        # Undo / redo stacks (JSON snapshots of the progression)
        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []

        # Clipboard (chord name string for cut/copy/paste)
        self._clipboard: str | None = None

        # Selection state: anchor + active end (both Positions or None)
        self._sel_anchor: Position | None = None
        self._sel_active: Position | None = None

        # MIDI chord voicing: last root MIDI note played (for voice leading)
        self._last_chord_root_midi: int | None = None

        # When to automatically play the chord on the MIDI output:
        # 'off' | 'navigation' | 'playback' | 'both'
        self.chord_play_mode: str = 'off'

        # MIDI metronome settings
        self.midi_metro_enabled: bool = False
        self.midi_metro_on_note: int = MIDI_METRO_ON_NOTE
        self.midi_metro_off_note: int = MIDI_METRO_OFF_NOTE
        self.midi_metro_velocity: int = MIDI_METRO_VELOCITY
        self.midi_metro_channel: int = MIDI_METRO_CHANNEL

        # Unsaved-changes tracking
        self._is_dirty: bool = False

        # Tracks whether a progression was loaded at startup (used for welcome message)
        self._loaded_at_startup: bool = False

        # Menu items that may need to be checked/unchecked at runtime
        self._overdub_item = None
        self._overwrite_item = None
        self._overwrite_whole_item = None
        self._chord_play_items: list = []  # radio items for chord playback mode

        # MIDI handler owns port management and chord detection (must be created
        # before Recorder so that _midi is available in _make_beat_callback).
        self._midi = MidiHandler(
            speak=self.speak,
            on_chord_released=self._on_chord_released,
            is_recording=lambda: self._recorder.state == AppState.RECORDING,
            on_chord_preview=self._on_chord_preview,
            on_nc_pedal=self._on_nc_pedal,
        )

        # Recorder owns metronome/recording/playback state
        self._recorder = Recorder(
            speak=self.speak,
            tick_sound=make_beep(1200, 10),
            tock_sound=make_beep(800,   8),
            on_playback_chord=self._on_playback_chord_midi,
            on_beat=self._midi_metro_beat,
        )

        self._midi.init()
        self._apply_saved_settings()

        # wxPython frame, status labels, and menu handles (created in run())
        self._frame = None
        self._status_labels: list = []
        self._midi_menu = None
        self._midi_out_menu = None
        self._sound_out_menu = None
        self._midi_metro_toggle_item = None
        self._chord_grid: ChordGridPanel | None = None

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

    def _on_chord_released(self, notes: list[int], first_note_time: float) -> None:
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

    def _on_chord_preview(self, notes: list[int]) -> None:
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

    def _midi_metro_beat(self, is_downbeat: bool) -> None:
        """MIDI metronome callback — fires on every beat from Recorder.

        When ``midi_metro_enabled`` is ``True`` and a MIDI output port is open,
        sends a short note-on/note-off pair on the configured percussion channel
        so external MIDI devices or a DAW can play the metronome sound.
        When disabled, falls back to the built-in audio beep by returning
        without doing anything (the Recorder will then call play_sound itself
        because *on_beat* is set; so we must pass through to audio when MIDI is
        not active).
        """
        if not self.midi_metro_enabled or self._midi.midi_output is None:
            # Fall back to audio click
            from sound import play_sound
            play_sound(self._recorder.tick_sound if is_downbeat else self._recorder.tock_sound)
            return
        note = self.midi_metro_on_note if is_downbeat else self.midi_metro_off_note
        try:
            import mido
            ch = max(0, min(15, self.midi_metro_channel))
            vel = max(1, min(127, self.midi_metro_velocity))
            self._midi.midi_output.send(mido.Message(
                'note_on', note=note, velocity=vel, channel=ch,
            ))
            # Schedule note-off after 50 ms so the note does not sustain.
            # Use a daemon timer so it does not block process shutdown.
            import threading
            def _note_off():
                try:
                    self._midi.midi_output.send(mido.Message(
                        'note_off', note=note, velocity=0, channel=ch,
                    ))
                except Exception:
                    pass
            t = threading.Timer(0.05, _note_off)
            t.daemon = True
            t.start()
        except Exception:
            _app_logger.debug("MIDI metro beat failed", exc_info=True)

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

        # Chord playback mode: support old 'play_chord_on_nav' bool for back-compat.
        # Old format: play_chord_on_nav=True → treated as chord_play_mode='navigation'.
        if 'chord_play_mode' in settings:
            mode = settings['chord_play_mode']
            if mode in ('off', 'navigation', 'playback', 'both'):
                self.chord_play_mode = mode
        elif settings.get('play_chord_on_nav', False):
            self.chord_play_mode = 'navigation'

        # MIDI metronome settings
        if 'midi_metro_enabled' in settings:
            self.midi_metro_enabled = bool(settings['midi_metro_enabled'])
        if 'midi_metro_on_note' in settings:
            self.midi_metro_on_note = int(settings['midi_metro_on_note'])
        if 'midi_metro_off_note' in settings:
            self.midi_metro_off_note = int(settings['midi_metro_off_note'])
        if 'midi_metro_velocity' in settings:
            self.midi_metro_velocity = int(settings['midi_metro_velocity'])
        if 'midi_metro_channel' in settings:
            self.midi_metro_channel = int(settings['midi_metro_channel'])

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
            'chord_play_mode': self.chord_play_mode,
            'midi_metro_enabled': self.midi_metro_enabled,
            'midi_metro_on_note': self.midi_metro_on_note,
            'midi_metro_off_note': self.midi_metro_off_note,
            'midi_metro_velocity': self.midi_metro_velocity,
            'midi_metro_channel': self.midi_metro_channel,
        }
        _save_settings_file(settings)

    # ------------------------------------------------------------------
    # Selection helpers (Shift+Left/Right)
    # ------------------------------------------------------------------

    def _clear_selection(self) -> None:
        self._sel_anchor = None
        self._sel_active = None

    def _extend_selection(self, direction: str,
                           by_measure: bool = False,
                           by_beat: bool = False,
                           structural: bool = False) -> None:
        ts = self.progression.time_signature
        if self._sel_anchor is None:
            self._sel_anchor = self.cursor
        if structural:
            if direction == 'right':
                new_m = self.progression.navigate_next_structural(self.cursor.measure)
            else:
                new_m = self.progression.navigate_prev_structural(self.cursor.measure)
            self.cursor = Position(new_m, 1, ts)
        elif by_measure:
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
        self._maybe_play_chord_on_nav()

    def navigate_home(self) -> None:
        self.cursor = Position(1, 1, self.progression.time_signature)
        self._announce_position(announce_section=True)
        self._maybe_play_chord_on_nav()

    def navigate_end(self) -> None:
        last_m = max(self.progression.last_measure(), 1)
        chords = self.progression.find_chords_in_measure(last_m)
        self.cursor = (
            chords[-1].position if chords
            else Position(last_m, 1, self.progression.time_signature)
        )
        self._announce_position(announce_section=True)
        self._maybe_play_chord_on_nav()

    def navigate_structural(self, direction: str) -> None:
        """Move the cursor to the next/previous structural marker."""
        ts = self.progression.time_signature
        old_measure = self.cursor.measure
        if direction == 'right':
            new_m = self.progression.navigate_next_structural(self.cursor.measure)
        else:
            new_m = self.progression.navigate_prev_structural(self.cursor.measure)
        self.cursor = Position(new_m, 1, ts)
        new_measure = self.cursor.measure
        old_section = self.progression.get_section_at_measure(old_measure)
        new_section = self.progression.get_section_at_measure(new_measure)
        self._announce_position(announce_section=new_section != old_section)
        self._maybe_play_chord_on_nav()

    def _maybe_play_chord_on_nav(self) -> None:
        """Play the chord at the cursor on MIDI output when navigation mode is active."""
        if self.chord_play_mode in ('navigation', 'both') and self._midi.midi_output is not None:
            self.play_current_chord_midi()

    def _on_playback_chord_midi(self, chord_name: str) -> None:
        """Callback invoked by Recorder each beat to play a chord during playback."""
        if self.chord_play_mode not in ('playback', 'both'):
            return
        if self._midi.midi_output is None:
            return
        notes, root_midi = voice_chord_midi(chord_name, self._last_chord_root_midi)
        if notes:
            self._last_chord_root_midi = root_midi
            self._midi.send_chord(notes)

    def play_current_chord_midi(self) -> None:
        """Play the chord at the current cursor position on the MIDI output.

        Uses the voicing algorithm from ``voice_chord_midi()`` and updates
        ``_last_chord_root_midi`` for voice-leading continuity.
        """
        chords = self.progression.find_chords_at_position(self.cursor)
        if not chords:
            return
        item = chords[0]
        chord_name = item.chord.name
        notes, root_midi = voice_chord_midi(chord_name, self._last_chord_root_midi)
        if notes:
            self._last_chord_root_midi = root_midi
            self._midi.send_chord(notes)

    # ------------------------------------------------------------------
    # Position announcement
    # ------------------------------------------------------------------

    def _section_name(self, mark: str) -> str:
        names = {
            '*A': _('Section A'), '*B': _('Section B'), '*C': _('Section C'),
            '*D': _('Section D'), '*V': _('Verse'), '*i': _('Intro'),
            'S':  _('Segno'), 'Q': _('Coda'), 'f': _('Fine'),  # 'f' is the iReal Pro standard for Fine
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
        removed even when a chord occupies the same beat. Bound to Ctrl+Delete / Ctrl+Backspace.
        """
        m = self.cursor.measure
        deleted: list[str] = []
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

        self._frame = wx.Frame(None, title="IReal Studio", size=(580, 420))
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

        # Chord grid visual panel
        self._chord_grid = ChordGridPanel(panel, self)
        sizer.Add(self._chord_grid, 1, wx.EXPAND | wx.TOP, 4)

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
        # Refresh the chord grid whenever any state changes
        if self._chord_grid is not None:
            self._chord_grid.Refresh()
        wx.CallLater(50, self._schedule_display_update)


if __name__ == '__main__':
    app = App()
    app.run()
