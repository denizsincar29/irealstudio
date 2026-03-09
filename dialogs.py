"""
dialogs.py - Modal input dialogs for IReal Studio.

On Windows a native ``wx.TextEntryDialog`` is used so that screen readers
(NVDA, JAWS) announce the dialog correctly.  On non-Windows platforms the
user is prompted via stdout/stdin as a fallback.
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
