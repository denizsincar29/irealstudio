"""
dialogs.py - Modal input dialogs for IReal Studio.

On Windows native wx dialogs are used so that screen readers (NVDA, JAWS)
announce the dialogs correctly.  On non-Windows platforms the user is
prompted via stdout/stdin as a fallback.
"""

import sys

_IS_WINDOWS = sys.platform == 'win32'


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
    fields = [
        ('title',    'Title:',    _defaults.get('title',    'My Progression')),
        ('composer', 'Composer:', _defaults.get('composer', 'Unknown')),
        ('key',      'Key:',      _defaults.get('key',      'C')),
        ('style',    'Style:',    _defaults.get('style',    'Medium Swing')),
        ('bpm',      'BPM:',      str(_defaults.get('bpm',  120))),
    ]

    if not _IS_WINDOWS:
        result: dict = {}
        for key, label, default in fields:
            print(f"{label} [{default}]: ", end='', flush=True)
            try:
                val = input().strip()
                result[key] = val if val else default
            except (KeyboardInterrupt, EOFError):
                return None
        return result

    try:
        import wx

        class _NewProjectDlg(wx.Dialog):
            def __init__(self, parent_wnd):
                super().__init__(parent_wnd, title="New Project",
                                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
                grid = wx.FlexGridSizer(rows=len(fields), cols=2, vgap=6, hgap=8)
                grid.AddGrowableCol(1, 1)
                self._ctrls: dict[str, wx.TextCtrl] = {}
                for key, label, default in fields:
                    grid.Add(wx.StaticText(self, label=label),
                             flag=wx.ALIGN_CENTER_VERTICAL)
                    ctrl = wx.TextCtrl(self, value=str(default))
                    self._ctrls[key] = ctrl
                    grid.Add(ctrl, flag=wx.EXPAND)
                outer = wx.BoxSizer(wx.VERTICAL)
                outer.Add(grid, proportion=1,
                          flag=wx.EXPAND | wx.ALL, border=12)
                outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          border=12)
                self.SetSizerAndFit(outer)
                # Focus first field for screen readers
                list(self._ctrls.values())[0].SetFocus()

            def get_values(self) -> dict:
                return {k: ctrl.GetValue() for k, ctrl in self._ctrls.items()}

        dlg = _NewProjectDlg(parent)
        result = dlg.get_values() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return result
    except Exception:
        return None
