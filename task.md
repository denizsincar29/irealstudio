# Task
Make a python app for blind that writes chord progressions by metronomed recording, allows to edit them and save to json and ireal pro format.

## features
- Press R to start recording. The metronome will start pre-counting 2 measures along with speech (One two...).
- The timestamp of each chord is recorded on first note-on, and the chord is identified on last note-off. It is quantized automatically in the chords.py module.
- Rehearsal marks / other metadata must be also included in the ChordProgression object, and saved to json and ireal pro format.
- Press ctrl+left/right to navigate between measures, left/right between chords.
- Adding inversion to a chord by holding slash key and pressing the note key (a-g) / typing "/"+(Gb)...
- Add section marks by holding S key and pressing A, B... and all ireal supported rehearsal marks.
- Save the chord progression to json format by pressing Ctrl+S.
- Export to ireal pro html format by pressing Ctrl+E.
- Press space to speak out the chord progression by the metronome rhythm. Ctrl+space to stop and navigate to the beat where it stopped.
- Playing and recording is done from the position of the cursor. Press ctrl+home to navigate to the beginning of the progression, ctrl+end to navigate to the end.
- repeat / ending variations. Explained in the next section.

## Repeats and endings
Let's asume we have an AABA 32 measure song, where first A is nearly the same as B, but last 2 measures are different.
Usually in IRealPro we mark that as a repeat with 2 endings. So we have something like this:
- repeat start.
- section a: first 6 measures
- ending 1: measures 7-8
- section A (refered as a2)- ending 2 without writing the first 6 measures again.

In the app, the first A section has 8 measures, and on the start of 7th measure you press V key (volta), and the 7 and 8th measures are marked as ending 1.
When you press right key from the 8th measure, you will navigate to the second ending (measure 15), and 6 measures of the second A is hidden from the user and from ireal pro export. Well, they are not hidden in the ChordProgression object, just there are no chords in the second A's first x measures, but the navigation must skip them when detected ending marks.
Ireal pro export must not write | x | x | x | x for the before ending2 measures, it must follow the pyrealpro rules / features for that.

## Pyrealpro library is used for ireal pro export
Pyrealpro library is used for ireal pro export
Uv package manager is used for dependency management for python. Use uv add <dependency> to add dependencies, and uv run <script> to run the app. The app should be runnable by uv run main.py command.

---

## Future task: migrate GUI from tkinter to wxPython

### Why

`tkinter` dialogs (`simpledialog.askstring`) are not reliably announced by
screen readers (NVDA, JAWS) on Windows.  wxPython widgets are built on
native Win32 controls and are fully accessible out of the box.

### Scope

Replace every `tkinter` import with a wxPython equivalent.  The audio
engine (`sound.py`), MIDI handler (`midi_handler.py`), recording/playback
logic (`recorder.py`), and all data-model files are **not** affected.

### Steps

1. **Add dependency**

   ```
   uv add wxPython
   ```

2. **`main.py` — swap the event loop and window**

   ```python
   # Remove
   import tkinter as tk

   # Add
   import wx
   ```

   Replace `App.run()`:
   ```python
   def run(self) -> None:
       wx_app = wx.App(False)
       self._frame = wx.Frame(None, title="IReal Studio", size=(500, 140))
       self._frame.SetBackgroundColour(wx.Colour(30, 30, 30))
       panel = wx.Panel(self._frame)
       sizer = wx.BoxSizer(wx.VERTICAL)
       self._status_labels = []
       for _ in range(4):
           lbl = wx.StaticText(panel, label="", style=wx.ST_NO_AUTORESIZE)
           lbl.SetForegroundColour(wx.Colour(200, 200, 200))
           sizer.Add(lbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
       panel.SetSizer(sizer)
       for w in (self._frame, panel):
           w.Bind(wx.EVT_KEY_DOWN, self._on_keydown)
           w.Bind(wx.EVT_KEY_UP,   self._on_keyup)
       self._frame.Show()
       try:
           hwnd = self._get_hwnd()
           if hwnd:
               self._menu.install(hwnd)
               self._refresh_menu_state()
       except Exception:
           pass
       self._schedule_display_update()
       self._schedule_menu_poll()
       wx_app.MainLoop()
       self._recorder.stop_all()
       self._menu.destroy()
       self._midi.close()
   ```

   Replace `_get_hwnd()` (no `GetParent` trick needed):
   ```python
   def _get_hwnd(self) -> int:
       if sys.platform != 'win32':
           return 0
       return self._frame.GetHandle()
   ```

   Replace `_on_keydown()` / `_on_keyup()` signatures:
   ```python
   def _on_keydown(self, event: wx.KeyEvent) -> None:
       ctrl = event.ControlDown()
       kc   = event.GetKeyCode()
       # wx uses integer key codes; map to the existing string-based checks:
       _WX_SYM = {
           wx.WXK_LEFT: 'left', wx.WXK_RIGHT: 'right',
           wx.WXK_HOME: 'home', wx.WXK_END: 'end',
           wx.WXK_ESCAPE: 'escape', wx.WXK_SPACE: 'space',
           wx.WXK_DELETE: 'delete', wx.WXK_BACK: 'backspace',
       }
       key = _WX_SYM.get(kc) or (chr(kc).lower() if 32 <= kc < 127 else '')
       # … rest of the existing handler body, unchanged …
       event.Skip()
   ```

   Replace periodic callbacks (`root.after` → `wx.CallLater`):
   ```python
   def _schedule_display_update(self) -> None:
       lines = [...]
       for lbl, text in zip(self._status_labels, lines):
           lbl.SetLabel(text)
       wx.CallLater(50, self._schedule_display_update)

   def _schedule_menu_poll(self) -> None:
       for _ in range(16):
           cmd = self._menu.poll()
           if cmd is None:
               break
           self._handle_menu_command(cmd)
       wx.CallLater(16, self._schedule_menu_poll)
   ```

   Replace `_on_quit()`:
   ```python
   def _on_quit(self) -> None:
       if self._frame:
           self._frame.Close()
   ```

3. **`windows_menu.py` — replace `simpledialog` with `wx.TextEntryDialog`**

   ```python
   def prompt_input(title: str, prompt: str, default: str = '',
                    parent=None) -> str | None:
       if not _IS_WINDOWS:
           # stdin fallback unchanged
           ...
       import wx
       dlg = wx.TextEntryDialog(parent, prompt, caption=title, value=default)
       result = dlg.GetValue() if dlg.ShowModal() == wx.ID_OK else None
       dlg.Destroy()
       return result
   ```

   In `main.py` the three `_menu_change_*` callers already pass
   `parent=self.root`; rename that argument to `parent=self._frame`.

### Notes

* `wx.StaticText` is announced by NVDA/JAWS.  If labels must be
  individually focusable, use `wx.TextCtrl(style=wx.TE_READONLY)`.
* Test with NVDA 2024.x as the AT baseline.
* The `WindowsMenu` ctypes implementation is unchanged; only `_get_hwnd`
  needs updating (above).