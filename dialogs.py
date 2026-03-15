"""
dialogs.py - Modal input dialogs for IReal Studio.

On Windows native wx dialogs are used so that screen readers (NVDA, JAWS)
announce the dialogs correctly.  On non-Windows platforms the user is
prompted via stdout/stdin as a fallback.
"""

import sys
import time
import threading

from i18n import _
from app_settings import MAX_COMPENSATION_MS

_IS_WINDOWS = sys.platform == 'win32'

# BPM constraints — kept here so the dialog and main.py share one source.
BPM_MIN = 40
BPM_MAX = 240
_BPM_PREVIEW_BARS = 2   # bars of metronome played as a preview


def prompt_input(title: str, prompt: str, default: str = '',
                 parent=None) -> str | None:
    """
    Show a simple modal text-entry dialog.

    On Windows a ``wx.TextEntryDialog`` is used.  Pass the application's
    ``wx.Frame`` as *parent* so the dialog is properly anchored and accessible
    to screen readers.

    On non-Windows the user is prompted via stdout/stdin.

    Returns the entered string, or ``None`` if the user cancelled.
    """
    if not _IS_WINDOWS:
        print(f"{title}: {prompt} [{default}]", flush=True)
        try:
            value = input("> ").strip()
            return value if value else default
        except (KeyboardInterrupt, EOFError):
            return None

    try:
        import wx
        dlg = wx.TextEntryDialog(parent, prompt, caption=title, value=default)
        result = dlg.GetValue() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return result
    except Exception:
        return None


def new_project_dialog(parent=None, defaults: dict | None = None) -> dict | None:
    """
    Show a 'New Project' dialog that collects title, composer, key, style and BPM.

    *defaults* is a dict with any of those keys; missing keys use built-in defaults.
    Returns a dict ``{'title', 'composer', 'key', 'style', 'bpm'}`` on OK,
    or ``None`` if the user cancelled.
    """
    _defaults: dict = defaults or {}
    # Text-entry fields (title, composer, bpm only — key and style get choices)
    text_fields = [
        ('title',    _('Title:'),    _defaults.get('title',    _('My Progression'))),
        ('composer', _('Composer:'), _defaults.get('composer', _('Unknown'))),
        ('bpm',      _('BPM:'),      str(_defaults.get('bpm',  120))),
    ]
    default_key   = _defaults.get('key',   'C')
    default_style = _defaults.get('style', 'Medium Swing')

    if not _IS_WINDOWS:
        result: dict = {}
        for key, label, default in text_fields:
            print(f"{label} [{default}]: ", end='', flush=True)
            try:
                val = input().strip()
                result[key] = val if val else default
            except (KeyboardInterrupt, EOFError):
                return None
        # Key: show numbered list
        from pyrealpro import KEY_SIGNATURES
        print("Key (enter number or name):")
        for idx, k in enumerate(KEY_SIGNATURES, 1):
            print(f"  {idx}: {k}")
        try:
            raw = input(f"[{default_key}]: ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                result['key'] = KEY_SIGNATURES[idx] if 0 <= idx < len(KEY_SIGNATURES) else default_key
            elif raw in KEY_SIGNATURES:
                result['key'] = raw
            else:
                result['key'] = default_key
        except (KeyboardInterrupt, EOFError):
            return None
        # Style: show numbered list
        from pyrealpro import STYLES_ALL
        print("Style (enter number or name):")
        for idx, s in enumerate(STYLES_ALL, 1):
            print(f"  {idx}: {s}")
        try:
            raw = input(f"[{default_style}]: ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                result['style'] = STYLES_ALL[idx] if 0 <= idx < len(STYLES_ALL) else default_style
            elif raw in STYLES_ALL:
                result['style'] = raw
            else:
                result['style'] = default_style
        except (KeyboardInterrupt, EOFError):
            return None
        return result

    try:
        import wx
        from pyrealpro import STYLES_ALL, KEY_SIGNATURES

        class _NewProjectDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title=_("New Project"),
                                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

                # Grid rows: text fields + key row + style row
                grid = wx.FlexGridSizer(rows=len(text_fields) + 2, cols=2, vgap=6, hgap=8)
                grid.AddGrowableCol(1, 1)
                self._ctrls: dict[str, wx.Control] = {}

                for key, label, default in text_fields:
                    grid.Add(wx.StaticText(self, label=label),
                             flag=wx.ALIGN_CENTER_VERTICAL)
                    ctrl = wx.TextCtrl(self, value=str(default))
                    self._ctrls[key] = ctrl
                    grid.Add(ctrl, flag=wx.EXPAND)

                # Key: wx.Choice with all valid iReal Pro key signatures
                grid.Add(wx.StaticText(self, label=_('Key:')),
                         flag=wx.ALIGN_CENTER_VERTICAL)
                key_choice = wx.Choice(self, choices=KEY_SIGNATURES)
                key_sel = KEY_SIGNATURES.index(default_key) if default_key in KEY_SIGNATURES else 0
                key_choice.SetSelection(key_sel)
                self._ctrls['key'] = key_choice
                grid.Add(key_choice, flag=wx.EXPAND)

                # Style: wx.Choice (accessible listbox-style dropdown)
                grid.Add(wx.StaticText(self, label=_('Style:')),
                         flag=wx.ALIGN_CENTER_VERTICAL)
                style_choice = wx.Choice(self, choices=STYLES_ALL)
                sel_idx = STYLES_ALL.index(default_style) if default_style in STYLES_ALL else 0
                style_choice.SetSelection(sel_idx)
                self._ctrls['style'] = style_choice
                grid.Add(style_choice, flag=wx.EXPAND)

                outer = wx.BoxSizer(wx.VERTICAL)
                outer.Add(grid, proportion=1,
                          flag=wx.EXPAND | wx.ALL, border=12)
                outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          border=12)
                self.SetSizerAndFit(outer)

                # BPM-specific state
                self._preview_stop: threading.Event | None = None
                self._tap_times: list[float] = []

                # Bind special key handling to the BPM field
                self._ctrls['bpm'].Bind(wx.EVT_KEY_DOWN, self._on_bpm_key)

                # Focus first field for screen readers
                list(self._ctrls.values())[0].SetFocus()

            # ----------------------------------------------------------
            # BPM helpers
            # ----------------------------------------------------------

            def _get_bpm(self) -> int:
                try:
                    return max(BPM_MIN, min(BPM_MAX, int(self._ctrls['bpm'].GetValue())))
                except ValueError:
                    return 120

            def _set_bpm(self, bpm: int) -> None:
                bpm = max(BPM_MIN, min(BPM_MAX, bpm))
                self._ctrls['bpm'].SetValue(str(bpm))

            def _on_bpm_key(self, event: wx.KeyEvent) -> None:
                key = event.GetKeyCode()
                if key == wx.WXK_UP:
                    step = 10 if event.ControlDown() else 1
                    self._set_bpm(self._get_bpm() + step)
                    self._preview_metronome()
                elif key == wx.WXK_DOWN:
                    step = 10 if event.ControlDown() else 1
                    self._set_bpm(self._get_bpm() - step)
                    self._preview_metronome()
                elif key == wx.WXK_SPACE:
                    self._tap_tempo()
                    # Consume the event so no space is typed into the field
                elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                    # Play a quick preview on Enter before confirming
                    self._preview_metronome()
                    event.Skip()
                else:
                    event.Skip()

            def _preview_metronome(self) -> None:
                """Play _BPM_PREVIEW_BARS bars of 4/4 metronome at the current BPM."""
                # Cancel any already-running preview
                if self._preview_stop is not None:
                    self._preview_stop.set()

                bpm = self._get_bpm()
                stop_ev = threading.Event()
                self._preview_stop = stop_ev
                interval = 60.0 / bpm
                total_beats = 4 * _BPM_PREVIEW_BARS

                def _run() -> None:
                    try:
                        from sound import make_beep, play_sound
                        tick = make_beep(1200, 30)
                        tock = make_beep(800, 25)
                    except Exception:
                        return
                    for i in range(total_beats):
                        if stop_ev.is_set():
                            break
                        play_sound(tick if i % 4 == 0 else tock)
                        time.sleep(interval)

                threading.Thread(target=_run, daemon=True).start()

            def _tap_tempo(self) -> None:
                """Record a tap; update BPM from average inter-tap interval."""
                now = time.monotonic()
                # Reset if the user paused more than 3 seconds between taps
                if self._tap_times and (now - self._tap_times[-1]) > 3.0:
                    self._tap_times.clear()
                self._tap_times.append(now)
                # Keep at most the 10 most recent taps
                if len(self._tap_times) > 10:
                    self._tap_times = self._tap_times[-10:]
                if len(self._tap_times) >= 2:
                    intervals = [
                        self._tap_times[i + 1] - self._tap_times[i]
                        for i in range(len(self._tap_times) - 1)
                    ]
                    avg = sum(intervals) / len(intervals)
                    self._set_bpm(round(60.0 / avg))
                    self._preview_metronome()

            def get_values(self) -> dict:
                result = {}
                for k, ctrl in self._ctrls.items():
                    if isinstance(ctrl, wx.Choice):
                        result[k] = ctrl.GetString(ctrl.GetSelection())
                    else:
                        result[k] = ctrl.GetValue()
                return result

        dlg = _NewProjectDlg(parent)
        result = dlg.get_values() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return result
    except Exception:
        return None


def project_settings_dialog(parent=None, defaults: dict | None = None) -> dict | None:
    """
    Show a 'Project Settings' dialog for an existing project.

    Like :func:`new_project_dialog` but also includes time signature and
    recording BPM fields so all project settings are editable in one place.

    *defaults* is a dict with any of ``title``, ``composer``, ``bpm``,
    ``recording_bpm``, ``key``, ``style``, ``time_signature`` (as a string,
    e.g. ``'4/4'``); missing keys use built-in defaults.

    Returns a dict with all those keys on OK, or ``None`` if cancelled.
    """
    _defaults: dict = defaults or {}
    text_fields = [
        ('title',         _('Title:'),           _defaults.get('title',         _('My Progression'))),
        ('composer',      _('Composer:'),        _defaults.get('composer',      _('Unknown'))),
        ('bpm',           _('BPM:'),             str(_defaults.get('bpm',       120))),
        ('recording_bpm', _('Recording BPM:'),   str(_defaults.get('recording_bpm', 120))),
        ('time_signature',_('Time Signature:'),  _defaults.get('time_signature', '4/4')),
    ]
    default_key   = _defaults.get('key',   'C')
    default_style = _defaults.get('style', 'Medium Swing')

    if not _IS_WINDOWS:
        result: dict = {}
        for key, label, default in text_fields:
            print(f"{label} [{default}]: ", end='', flush=True)
            try:
                val = input().strip()
                result[key] = val if val else default
            except (KeyboardInterrupt, EOFError):
                return None
        from pyrealpro import KEY_SIGNATURES
        print("Key (enter number or name):")
        for idx, k in enumerate(KEY_SIGNATURES, 1):
            print(f"  {idx}: {k}")
        try:
            raw = input(f"[{default_key}]: ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                result['key'] = KEY_SIGNATURES[idx] if 0 <= idx < len(KEY_SIGNATURES) else default_key
            elif raw in KEY_SIGNATURES:
                result['key'] = raw
            else:
                result['key'] = default_key
        except (KeyboardInterrupt, EOFError):
            return None
        from pyrealpro import STYLES_ALL
        print("Style (enter number or name):")
        for idx, s in enumerate(STYLES_ALL, 1):
            print(f"  {idx}: {s}")
        try:
            raw = input(f"[{default_style}]: ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                result['style'] = STYLES_ALL[idx] if 0 <= idx < len(STYLES_ALL) else default_style
            elif raw in STYLES_ALL:
                result['style'] = raw
            else:
                result['style'] = default_style
        except (KeyboardInterrupt, EOFError):
            return None
        return result

    try:
        import wx
        from pyrealpro import STYLES_ALL, KEY_SIGNATURES

        class _ProjectSettingsDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title=_("Project Settings"),
                                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

                grid = wx.FlexGridSizer(rows=len(text_fields) + 2, cols=2, vgap=6, hgap=8)
                grid.AddGrowableCol(1, 1)
                self._ctrls: dict[str, wx.Control] = {}

                for key, label, default in text_fields:
                    grid.Add(wx.StaticText(self, label=label),
                             flag=wx.ALIGN_CENTER_VERTICAL)
                    ctrl = wx.TextCtrl(self, value=str(default))
                    self._ctrls[key] = ctrl
                    grid.Add(ctrl, flag=wx.EXPAND)

                grid.Add(wx.StaticText(self, label=_('Key:')),
                         flag=wx.ALIGN_CENTER_VERTICAL)
                key_choice = wx.Choice(self, choices=KEY_SIGNATURES)
                key_sel = KEY_SIGNATURES.index(default_key) if default_key in KEY_SIGNATURES else 0
                key_choice.SetSelection(key_sel)
                self._ctrls['key'] = key_choice
                grid.Add(key_choice, flag=wx.EXPAND)

                grid.Add(wx.StaticText(self, label=_('Style:')),
                         flag=wx.ALIGN_CENTER_VERTICAL)
                style_choice = wx.Choice(self, choices=STYLES_ALL)
                sel_idx = STYLES_ALL.index(default_style) if default_style in STYLES_ALL else 0
                style_choice.SetSelection(sel_idx)
                self._ctrls['style'] = style_choice
                grid.Add(style_choice, flag=wx.EXPAND)

                outer = wx.BoxSizer(wx.VERTICAL)
                outer.Add(grid, proportion=1,
                          flag=wx.EXPAND | wx.ALL, border=12)
                outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          border=12)
                self.SetSizerAndFit(outer)

                self._preview_stop: threading.Event | None = None
                self._tap_times: list[float] = []
                self._ctrls['bpm'].Bind(wx.EVT_KEY_DOWN, self._on_bpm_key)
                if 'recording_bpm' in self._ctrls:
                    self._ctrls['recording_bpm'].Bind(wx.EVT_KEY_DOWN,
                                                       self._on_rec_bpm_key)
                list(self._ctrls.values())[0].SetFocus()

            def _get_bpm(self) -> int:
                try:
                    return max(BPM_MIN, min(BPM_MAX, int(self._ctrls['bpm'].GetValue())))
                except ValueError:
                    return 120

            def _set_bpm(self, bpm: int) -> None:
                bpm = max(BPM_MIN, min(BPM_MAX, bpm))
                self._ctrls['bpm'].SetValue(str(bpm))

            def _on_bpm_key(self, event: wx.KeyEvent) -> None:
                key = event.GetKeyCode()
                if key == wx.WXK_UP:
                    step = 10 if event.ControlDown() else 1
                    self._set_bpm(self._get_bpm() + step)
                    self._preview_metronome()
                elif key == wx.WXK_DOWN:
                    step = 10 if event.ControlDown() else 1
                    self._set_bpm(self._get_bpm() - step)
                    self._preview_metronome()
                elif key == wx.WXK_SPACE:
                    self._tap_tempo()
                elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                    self._preview_metronome()
                    event.Skip()
                else:
                    event.Skip()

            def _on_rec_bpm_key(self, event: wx.KeyEvent) -> None:
                key = event.GetKeyCode()
                if key in (wx.WXK_UP, wx.WXK_DOWN):
                    step = 10 if event.ControlDown() else 1
                    ctrl = self._ctrls['recording_bpm']
                    try:
                        val = max(BPM_MIN, min(BPM_MAX, int(ctrl.GetValue())))
                    except ValueError:
                        val = 120
                    val += step if key == wx.WXK_UP else -step
                    ctrl.SetValue(str(max(BPM_MIN, min(BPM_MAX, val))))
                else:
                    event.Skip()

            def _preview_metronome(self) -> None:
                if self._preview_stop is not None:
                    self._preview_stop.set()
                bpm = self._get_bpm()
                stop_ev = threading.Event()
                self._preview_stop = stop_ev
                interval = 60.0 / bpm
                total_beats = 4 * _BPM_PREVIEW_BARS

                def _run() -> None:
                    try:
                        from sound import make_beep, play_sound
                        tick = make_beep(1200, 30)
                        tock = make_beep(800, 25)
                    except Exception:
                        return
                    for i in range(total_beats):
                        if stop_ev.is_set():
                            break
                        play_sound(tick if i % 4 == 0 else tock)
                        time.sleep(interval)

                threading.Thread(target=_run, daemon=True).start()

            def _tap_tempo(self) -> None:
                now = time.monotonic()
                if self._tap_times and (now - self._tap_times[-1]) > 3.0:
                    self._tap_times.clear()
                self._tap_times.append(now)
                if len(self._tap_times) > 10:
                    self._tap_times = self._tap_times[-10:]
                if len(self._tap_times) >= 2:
                    intervals = [
                        self._tap_times[i + 1] - self._tap_times[i]
                        for i in range(len(self._tap_times) - 1)
                    ]
                    avg = sum(intervals) / len(intervals)
                    self._set_bpm(round(60.0 / avg))
                    self._preview_metronome()

            def get_values(self) -> dict:
                result = {}
                for k, ctrl in self._ctrls.items():
                    if isinstance(ctrl, wx.Choice):
                        result[k] = ctrl.GetString(ctrl.GetSelection())
                    else:
                        result[k] = ctrl.GetValue()
                return result

        dlg = _ProjectSettingsDlg(parent)
        result = dlg.get_values() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return result
    except Exception:
        return None


def insert_chord_dialog(parent=None, default: str = 'C') -> str | None:
    """
    Show a chord-entry dialog that lets the user type a chord name directly
    or build one from root + quality + alteration selectors.

    Returns the chord name string on OK (e.g. ``'Cmaj7'``, ``'Am7'``, ``'C7(b9#11)'``),
    or ``None`` if cancelled or invalid.
    """
    ROOTS = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F',
             'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B']
    QUALITIES = [
        '',       # major
        'm',      # minor
        '7',      # dominant 7
        'maj7',   # major 7
        'm7',     # minor 7
        'm7b5',   # half-diminished
        'dim',    # diminished
        'dim7',   # diminished 7
        'aug',    # augmented
        'sus4',   # sus4
        '7sus4',  # 7sus4
        'mM7',    # minor-major 7
        'add9',   # add9
        '6',      # major 6
        '6/9',    # 6/9
        'm6',     # minor 6
        '9',      # dominant 9
        'maj9',   # major 9
        'm9',     # minor 9
        '11',     # dominant 11
        '13',     # dominant 13
        'aug7',   # augmented dominant 7
    ]

    # Extensions permitted for each base quality.
    # An empty list means all alteration checkboxes are *disabled* for that quality
    # (they are always displayed in the dialog but greyed out when not applicable).
    _QUALITY_EXTENSIONS: dict[str, list[str]] = {
        '':      [],
        'm':     [],
        '7':     ['b9', '9', '#9', 'b5', '#11', 'b13', '13'],
        'maj7':  ['9', '#11', '13'],
        'm7':    ['9', '#11', '13'],
        'm7b5':  ['b9', '9'],
        'dim':   [],
        'dim7':  [],
        'aug':   [],
        'sus4':  [],
        '7sus4': ['b9', '13'],
        'mM7':   ['9'],
        'add9':  [],
        '6':     [],
        '6/9':   [],
        'm6':    [],
        '9':     ['b9', '#9', '#11', '13'],
        'maj9':  ['#11', '13'],
        'm9':    ['#11'],
        '11':    ['13'],
        '13':    [],
        'aug7':  [],
    }
    ALL_EXTS = ['b9', '9', '#9', 'b5', '#11', 'b13', '13']

    if not _IS_WINDOWS:
        print(f"Enter chord name [{default}]: ", end='', flush=True)
        try:
            val = input().strip()
            name = val if val else default
        except (KeyboardInterrupt, EOFError):
            return None
        if not name:
            return None
        try:
            from chords import Chord
            Chord(name)
            return name
        except Exception:
            return None

    try:
        import wx
        from chords import Chord

        class _InsertChordDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title=_("Insert Chord"),
                                 style=wx.DEFAULT_DIALOG_STYLE)
                self._updating = False  # guard against recursive updates

                sizer = wx.BoxSizer(wx.VERTICAL)

                # Row 1: chord name text entry
                row1 = wx.BoxSizer(wx.HORIZONTAL)
                row1.Add(wx.StaticText(self, label=_("Chord:")),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
                self._entry = wx.TextCtrl(self, value=default, size=(160, -1))
                row1.Add(self._entry, proportion=1)
                sizer.Add(row1, flag=wx.EXPAND | wx.ALL, border=12)

                # Row 2: root + quality selectors
                row2 = wx.BoxSizer(wx.HORIZONTAL)
                row2.Add(wx.StaticText(self, label=_("Root:")),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
                self._root = wx.Choice(self, choices=ROOTS)
                self._root.SetSelection(0)
                row2.Add(self._root, flag=wx.RIGHT, border=10)
                row2.Add(wx.StaticText(self, label=_("Quality:")),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
                self._quality = wx.Choice(self, choices=QUALITIES)
                self._quality.SetSelection(0)
                row2.Add(self._quality)
                sizer.Add(row2, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)

                # Row 3: alteration checkboxes
                ext_lbl = wx.StaticText(self, label=_("Alterations:"))
                sizer.Add(ext_lbl, flag=wx.LEFT | wx.RIGHT, border=12)
                ext_row = wx.BoxSizer(wx.HORIZONTAL)
                self._ext_checks: dict[str, wx.CheckBox] = {}
                for ext in ALL_EXTS:
                    cb = wx.CheckBox(self, label=ext)
                    self._ext_checks[ext] = cb
                    ext_row.Add(cb, flag=wx.RIGHT, border=6)
                    cb.Bind(wx.EVT_CHECKBOX, self._on_ext_changed)
                sizer.Add(ext_row, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=12)

                help_lbl = wx.StaticText(
                    self,
                    label=_("Type a chord name directly, or choose root/quality/alterations above.")
                )
                help_lbl.SetForegroundColour(wx.Colour(100, 100, 100))
                sizer.Add(help_lbl, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)

                sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)
                self.SetSizerAndFit(sizer)

                self._root.Bind(wx.EVT_CHOICE, self._on_selector_changed)
                self._quality.Bind(wx.EVT_CHOICE, self._on_selector_changed)
                self._update_ext_state()
                self._entry.SetFocus()

            def _build_name(self) -> str:
                """Build chord name from root + quality + selected extensions."""
                root = self._root.GetString(self._root.GetSelection())
                quality = self._quality.GetString(self._quality.GetSelection())
                active = [ext for ext in ALL_EXTS
                          if self._ext_checks[ext].IsEnabled()
                          and self._ext_checks[ext].GetValue()]
                if active:
                    return root + quality + '(' + ''.join(active) + ')'
                return root + quality

            def _update_ext_state(self) -> None:
                """Enable only the extensions that apply to the selected quality."""
                quality = self._quality.GetString(self._quality.GetSelection())
                allowed = _QUALITY_EXTENSIONS.get(quality, [])
                for ext, cb in self._ext_checks.items():
                    cb.Enable(ext in allowed)
                    if ext not in allowed:
                        cb.SetValue(False)

            def _on_selector_changed(self, _event):
                if self._updating:
                    return
                self._updating = True
                try:
                    self._update_ext_state()
                    self._entry.SetValue(self._build_name())
                finally:
                    self._updating = False

            def _on_ext_changed(self, _event):
                if self._updating:
                    return
                self._updating = True
                try:
                    self._entry.SetValue(self._build_name())
                finally:
                    self._updating = False

            def get_chord_name(self) -> str:
                return self._entry.GetValue().strip()

        dlg = _InsertChordDlg(parent)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None
        name = dlg.get_chord_name()
        dlg.Destroy()
        if not name:
            return None
        # Validate the chord name
        try:
            Chord(name)
            return name
        except Exception:
            return None
    except Exception:
        return None


def prompt_midi_metro_settings(
    parent=None,
    on_note: int = 91,
    off_note: int = 84,
    velocity: int = 48,
    channel: int = 0,
    duration_ms: int = 100,
    preview_fn=None,
) -> "tuple[int, int, int, int, int] | None":
    """Show a dialog for configuring MIDI metronome note numbers, channel, and duration.

    Parameters
    ----------
    preview_fn:
        Optional callable ``(note, velocity, channel, duration_ms) -> None``
        called immediately when the user changes any field, so they can hear
        the new value played on the connected MIDI output in real time.

    Returns ``(on_note, off_note, velocity, channel, duration_ms)`` on OK, or
    ``None`` if the user cancelled.  All values are clamped to valid ranges.
    """
    if not _IS_WINDOWS:
        print(_("MIDI Metronome Settings"))
        try:
            on_s   = input(f"  Downbeat MIDI note (0-127) [{on_note}]: ").strip()
            off_s  = input(f"  Upbeat MIDI note (0-127) [{off_note}]: ").strip()
            vel_s  = input(f"  Velocity (1-127) [{velocity}]: ").strip()
            ch_s   = input(f"  Channel (0-15) [{channel}]: ").strip()
            dur_s  = input(f"  Note length ms (10-2000) [{duration_ms}]: ").strip()
            on_note    = max(0,  min(127,  int(on_s   or on_note)))
            off_note   = max(0,  min(127,  int(off_s  or off_note)))
            velocity   = max(1,  min(127,  int(vel_s  or velocity)))
            channel    = max(0,  min(15,   int(ch_s   or channel)))
            duration_ms = max(10, min(2000, int(dur_s  or duration_ms)))
            return on_note, off_note, velocity, channel, duration_ms
        except (KeyboardInterrupt, EOFError, ValueError):
            return None

    try:
        import wx

        class _MidiMetroDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title=_("MIDI Metronome Settings"),
                                 style=wx.DEFAULT_DIALOG_STYLE)
                sizer = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
                sizer.AddGrowableCol(1, 1)

                def _row(label: str, min_val: int, max_val: int, initial: int) -> wx.SpinCtrl:
                    """Create a StaticText+SpinCtrl pair in that order.

                    Creating the StaticText first (lower z-order/creation index) and the
                    SpinCtrl immediately after is required for Windows UIA/MSAA to
                    associate the label with the control — the foundation for NVDA/JAWS
                    announcing the field name when the spinner receives focus.
                    """
                    sizer.Add(wx.StaticText(self, label=label),
                              flag=wx.ALIGN_CENTER_VERTICAL)
                    ctrl = wx.SpinCtrl(self, min=min_val, max=max_val, initial=initial)
                    sizer.Add(ctrl, flag=wx.EXPAND)
                    return ctrl

                self._on_note  = _row(_("Downbeat MIDI note (0-127):"),  0,   127, on_note)
                self._off_note = _row(_("Upbeat MIDI note (0-127):"),    0,   127, off_note)
                self._velocity = _row(_("Velocity (1-127):"),            1,   127, velocity)
                self._channel  = _row(_("Channel (0-15, 0=melodic):"),  0,    15, channel)
                self._duration = _row(_("Note length ms (10-2000):"),   10, 2000, duration_ms)

                # Live-preview: play the note immediately whenever any spin
                # value changes, so the user can hear the effect right away.
                if preview_fn is not None:
                    def _make_preview(note_ctrl):
                        def _on_spin(evt):
                            evt.Skip()
                            try:
                                note = note_ctrl.GetValue()
                                vel  = self._velocity.GetValue()
                                ch   = self._channel.GetValue()
                                dur  = self._duration.GetValue()
                                preview_fn(note, vel, ch, dur)
                            except Exception:
                                pass
                        return _on_spin

                    def _on_any_spin(evt):
                        evt.Skip()
                        try:
                            # Preview downbeat note when a non-note field changes.
                            note = self._on_note.GetValue()
                            vel  = self._velocity.GetValue()
                            ch   = self._channel.GetValue()
                            dur  = self._duration.GetValue()
                            preview_fn(note, vel, ch, dur)
                        except Exception:
                            pass

                    self._on_note.Bind(wx.EVT_SPINCTRL, _make_preview(self._on_note))
                    self._off_note.Bind(wx.EVT_SPINCTRL, _make_preview(self._off_note))
                    self._velocity.Bind(wx.EVT_SPINCTRL, _on_any_spin)
                    self._channel.Bind(wx.EVT_SPINCTRL,  _on_any_spin)
                    self._duration.Bind(wx.EVT_SPINCTRL, _on_any_spin)

                outer = wx.BoxSizer(wx.VERTICAL)
                outer.Add(sizer, flag=wx.EXPAND | wx.ALL, border=14)
                outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=14)
                self.SetSizerAndFit(outer)
                self._on_note.SetFocus()

            def get_values(self) -> "tuple[int, int, int, int, int]":
                return (
                    self._on_note.GetValue(),
                    self._off_note.GetValue(),
                    self._velocity.GetValue(),
                    self._channel.GetValue(),
                    self._duration.GetValue(),
                )

        dlg = _MidiMetroDlg(parent)
        result = dlg.get_values() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return result
    except Exception:
        return None


# Default MIDI notes per channel role
_MIDI_DEFAULTS_MELODIC = (91, 84, 48)   # B6 / C6, velocity 48 — melodic metronome (ch 0-8, 10-15)
_MIDI_DEFAULTS_DRUMS   = (35, 42, 100)  # Acoustic Bass Drum (35) / Closed Hi-Hat (42), velocity 100 (ch 9)


def prompt_metronome_settings(
    parent=None,
    # Audio
    audio_compensation_ms: int = 60,
    # MIDI metro
    midi_metro_enabled: bool = False,
    midi_metro_smart: bool = False,
    on_note: int = 91,
    off_note: int = 84,
    velocity: int = 48,
    channel: int = 0,
    duration_ms: int = 100,
    midi_compensation_ms: int = 0,
    preview_fn=None,
    audio_preview_fn=None,
) -> "dict | None":
    """Show the centralized Metronome Settings dialog.

    Parameters
    ----------
    preview_fn:
        Optional callable ``(note, velocity, channel, duration_ms) -> None``
        for live MIDI preview when any MIDI field changes.
    audio_preview_fn:
        Optional callable ``() -> None`` that plays one audio tick so the
        user can compare it against the simultaneous MIDI preview and judge
        whether the audio compensation value is correct.  Called together
        with *preview_fn* (downbeat note) whenever the audio compensation
        spinner changes.

    Returns a dict with keys::

        audio_compensation_ms, midi_metro_enabled, midi_metro_smart,
        on_note, off_note, velocity, channel, duration_ms, midi_compensation_ms

    or ``None`` if the user cancelled.
    """
    if not _IS_WINDOWS:
        print(_("Metronome Settings"))
        try:
            aud_s = input(
                f"  Audio compensation ms (0-{MAX_COMPENSATION_MS}) [{audio_compensation_ms}]: "
            ).strip()
            audio_compensation_ms = max(0, min(MAX_COMPENSATION_MS, int(aud_s or audio_compensation_ms)))
            en_s = input(
                f"  Enable MIDI metronome (1/0) [{int(midi_metro_enabled)}]: "
            ).strip()
            midi_metro_enabled = bool(int(en_s or int(midi_metro_enabled)))
            sm_s = input(
                f"  Smart metronome (1/0) [{int(midi_metro_smart)}]: "
            ).strip()
            midi_metro_smart = bool(int(sm_s or int(midi_metro_smart)))
            on_s   = input(f"  Downbeat MIDI note (0-127) [{on_note}]: ").strip()
            off_s  = input(f"  Upbeat MIDI note (0-127) [{off_note}]: ").strip()
            vel_s  = input(f"  Velocity (1-127) [{velocity}]: ").strip()
            ch_s   = input(f"  Channel (0-15) [{channel}]: ").strip()
            dur_s  = input(f"  Note length ms (10-2000) [{duration_ms}]: ").strip()
            mid_s  = input(
                f"  MIDI compensation ms (0-{MAX_COMPENSATION_MS}) [{midi_compensation_ms}]: "
            ).strip()
            on_note    = max(0,   min(127,  int(on_s   or on_note)))
            off_note   = max(0,   min(127,  int(off_s  or off_note)))
            velocity   = max(1,   min(127,  int(vel_s  or velocity)))
            channel    = max(0,   min(15,   int(ch_s   or channel)))
            duration_ms = max(10, min(2000, int(dur_s  or duration_ms)))
            midi_compensation_ms = max(0, min(MAX_COMPENSATION_MS, int(mid_s or midi_compensation_ms)))
            return dict(
                audio_compensation_ms=audio_compensation_ms,
                midi_metro_enabled=midi_metro_enabled,
                midi_metro_smart=midi_metro_smart,
                on_note=on_note,
                off_note=off_note,
                velocity=velocity,
                channel=channel,
                duration_ms=duration_ms,
                midi_compensation_ms=midi_compensation_ms,
            )
        except (KeyboardInterrupt, EOFError, ValueError):
            return None

    try:
        import wx

        class _MetroDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title=_("Metronome Settings"),
                                 style=wx.DEFAULT_DIALOG_STYLE)

                # ----- helpers -----
                def _row(sizer, label: str, min_val: int, max_val: int,
                         initial: int) -> wx.SpinCtrl:
                    """StaticText must be created before its SpinCtrl for NVDA/JAWS."""
                    sizer.Add(wx.StaticText(self, label=label),
                              flag=wx.ALIGN_CENTER_VERTICAL)
                    ctrl = wx.SpinCtrl(self, min=min_val, max=max_val,
                                       initial=initial)
                    sizer.Add(ctrl, flag=wx.EXPAND)
                    return ctrl

                outer = wx.BoxSizer(wx.VERTICAL)

                # === Audio Metronome section ===
                outer.Add(
                    wx.StaticText(self, label=_("Audio Metronome")),
                    flag=wx.LEFT | wx.TOP, border=12,
                )
                audio_grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
                audio_grid.AddGrowableCol(1, 1)
                self._audio_comp = _row(
                    audio_grid,
                    _("Audio compensation (ms, 0-500):"),
                    0, MAX_COMPENSATION_MS, audio_compensation_ms,
                )
                outer.Add(audio_grid, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                          border=12)

                outer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.TOP | wx.BOTTOM,
                          border=8)

                # === MIDI Metronome section ===
                outer.Add(
                    wx.StaticText(self, label=_("MIDI Metronome")),
                    flag=wx.LEFT, border=12,
                )
                midi_sizer = wx.BoxSizer(wx.VERTICAL)

                # Enable / Smart checkboxes
                self._enable_cb = wx.CheckBox(self, label=_("Enable MIDI Metronome"))
                self._enable_cb.SetValue(midi_metro_enabled)
                self._smart_cb  = wx.CheckBox(self, label=_("Smart (chord-aware)"))
                self._smart_cb.SetValue(midi_metro_smart)
                midi_sizer.Add(self._enable_cb, flag=wx.LEFT | wx.TOP, border=4)
                midi_sizer.Add(self._smart_cb,  flag=wx.LEFT | wx.TOP, border=4)

                # Note / velocity / channel / duration grid
                midi_grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
                midi_grid.AddGrowableCol(1, 1)
                self._on_note  = _row(midi_grid,
                                      _("Downbeat MIDI note (0-127):"),
                                      0, 127, on_note)
                self._off_note = _row(midi_grid,
                                      _("Upbeat MIDI note (0-127):"),
                                      0, 127, off_note)
                self._velocity = _row(midi_grid,
                                      _("Velocity (1-127):"),
                                      1, 127, velocity)
                self._channel  = _row(midi_grid,
                                      _("Channel (0-15, 0=melodic):"),
                                      0, 15, channel)
                self._duration = _row(midi_grid,
                                      _("Note length ms (10-2000):"),
                                      10, 2000, duration_ms)
                self._midi_comp = _row(midi_grid,
                                       _("MIDI compensation (ms, 0-500):"),
                                       0, MAX_COMPENSATION_MS, midi_compensation_ms)
                midi_sizer.Add(midi_grid,
                               flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                               border=4)

                # Reset-to-defaults button (resets MIDI note/velocity fields only)
                self._reset_btn = wx.Button(self, label=_("Reset MIDI to defaults"))
                midi_sizer.Add(self._reset_btn, flag=wx.LEFT | wx.TOP, border=4)

                outer.Add(midi_sizer,
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          border=12)

                outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          border=14)
                self.SetSizerAndFit(outer)

                # ----- live preview bindings -----
                if preview_fn is not None:
                    def _make_preview(note_ctrl):
                        def _on_spin(evt):
                            evt.Skip()
                            try:
                                note = note_ctrl.GetValue()
                                vel  = self._velocity.GetValue()
                                ch   = self._channel.GetValue()
                                dur  = self._duration.GetValue()
                                preview_fn(note, vel, ch, dur)
                            except Exception:
                                pass
                        return _on_spin

                    def _on_any_spin(evt):
                        evt.Skip()
                        try:
                            note = self._on_note.GetValue()
                            vel  = self._velocity.GetValue()
                            ch   = self._channel.GetValue()
                            dur  = self._duration.GetValue()
                            preview_fn(note, vel, ch, dur)
                        except Exception:
                            pass

                    self._on_note.Bind(wx.EVT_SPINCTRL, _make_preview(self._on_note))
                    self._off_note.Bind(wx.EVT_SPINCTRL, _make_preview(self._off_note))
                    self._velocity.Bind(wx.EVT_SPINCTRL, _on_any_spin)
                    self._channel.Bind(wx.EVT_SPINCTRL,  _on_any_spin)
                    self._duration.Bind(wx.EVT_SPINCTRL, _on_any_spin)

                # Audio compensation preview: fire audio tick immediately, then
                # delay the MIDI ding by comp_ms so the gap demonstrates what
                # the compensation corrects.  The user adjusts comp_ms until
                # the ding appears to land on the tick.
                _midi_cancel: list[threading.Event] = [threading.Event()]

                def _on_audio_comp_spin(evt):
                    evt.Skip()
                    # Cancel any pending MIDI ding from a previous spin event.
                    _midi_cancel[0].set()
                    cancel = threading.Event()
                    _midi_cancel[0] = cancel

                    comp_ms = self._audio_comp.GetValue()
                    try:
                        if audio_preview_fn is not None:
                            audio_preview_fn()
                    except Exception:
                        pass
                    if preview_fn is not None:
                        note = self._on_note.GetValue()
                        vel  = self._velocity.GetValue()
                        ch   = self._channel.GetValue()
                        dur  = self._duration.GetValue()

                        def _fire_midi():
                            if comp_ms > 0 and cancel.wait(comp_ms / 1000.0):
                                return  # cancelled by a newer spin event
                            try:
                                preview_fn(note, vel, ch, dur)
                            except Exception:
                                pass

                        threading.Thread(target=_fire_midi, daemon=True).start()
                self._audio_comp.Bind(wx.EVT_SPINCTRL, _on_audio_comp_spin)

                # ----- reset button -----
                self._reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)

                self._audio_comp.SetFocus()

            def _on_reset(self, _evt) -> None:
                """Reset MIDI note/velocity fields to channel-appropriate defaults."""
                ch = self._channel.GetValue()
                if ch == 9:
                    on_n, off_n, vel = _MIDI_DEFAULTS_DRUMS
                else:
                    on_n, off_n, vel = _MIDI_DEFAULTS_MELODIC
                self._on_note.SetValue(on_n)
                self._off_note.SetValue(off_n)
                self._velocity.SetValue(vel)

            def get_values(self) -> dict:
                return dict(
                    audio_compensation_ms=self._audio_comp.GetValue(),
                    midi_metro_enabled=self._enable_cb.GetValue(),
                    midi_metro_smart=self._smart_cb.GetValue(),
                    on_note=self._on_note.GetValue(),
                    off_note=self._off_note.GetValue(),
                    velocity=self._velocity.GetValue(),
                    channel=self._channel.GetValue(),
                    duration_ms=self._duration.GetValue(),
                    midi_compensation_ms=self._midi_comp.GetValue(),
                )

        dlg = _MetroDlg(parent)
        result = dlg.get_values() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return result
    except Exception:
        return None
