"""
dialogs.py - Modal input dialogs for IReal Studio.

On Windows native wx dialogs are used so that screen readers (NVDA, JAWS)
announce the dialogs correctly.  On non-Windows platforms the user is
prompted via stdout/stdin as a fallback.
"""

import sys
import time
import threading

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
        ('title',    'Title:',    _defaults.get('title',    'My Progression')),
        ('composer', 'Composer:', _defaults.get('composer', 'Unknown')),
        ('bpm',      'BPM:',      str(_defaults.get('bpm',  120))),
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
            else:
                result['key'] = raw if raw else default_key
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
            else:
                result['style'] = raw if raw else default_style
        except (KeyboardInterrupt, EOFError):
            return None
        return result

    try:
        import wx
        from pyrealpro import STYLES_ALL, KEY_SIGNATURES

        class _NewProjectDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title="New Project",
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
                grid.Add(wx.StaticText(self, label='Key:'),
                         flag=wx.ALIGN_CENTER_VERTICAL)
                key_choice = wx.Choice(self, choices=KEY_SIGNATURES)
                key_sel = KEY_SIGNATURES.index(default_key) if default_key in KEY_SIGNATURES else 0
                key_choice.SetSelection(key_sel)
                self._ctrls['key'] = key_choice
                grid.Add(key_choice, flag=wx.EXPAND)

                # Style: wx.Choice (accessible listbox-style dropdown)
                grid.Add(wx.StaticText(self, label='Style:'),
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
