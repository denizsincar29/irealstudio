"""
app_io.py – File I/O, export, and static dialog methods mixin for the App class.

Extracted from main.py to reduce its size.
"""
import io
import logging
from pathlib import Path

import wx
import wx.adv

from chords import ChordProgression, TimeSignature, Position
from dialogs import (
    new_project_dialog, project_settings_dialog, insert_chord_dialog, prompt_input,
    BPM_MIN, BPM_MAX,
)
from recorder import AppState
from app_settings import (
    DEFAULT_BPM, DEFAULT_KEY, DEFAULT_STYLE, DEFAULT_TITLE, DEFAULT_TIME_SIG,
    SAVE_FILE, _safe_filename,
)
from i18n import _

_app_logger = logging.getLogger('irealstudio')

# Keyboard shortcuts reference (translated as a whole at runtime)
_KEYBOARD_SHORTCUTS_TEXT = """\
Keyboard Shortcuts – IReal Studio
==================================

Navigation
  Left / Right                    Move cursor one chord
  Shift+Left / Right              Extend selection by chord
  Alt+Left / Alt+Right            Move cursor one beat
  Shift+Alt+Left / Right          Extend selection by beat
  Ctrl+Left / Ctrl+Right          Move cursor one measure
  Shift+Ctrl+Left / Right         Extend selection by measure
  Ctrl+Alt+Left / Right           Move cursor to structural marker
  Shift+Ctrl+Alt+Left / Right     Extend selection to structural marker
  Ctrl+Home / Ctrl+End            Go to beginning / end

Playback & Recording
  R                     Start / stop recording
  Space                 Play chord on MIDI output (or play if no MIDI out)
  Ctrl+Space            Stop and jump to last position
  Escape                Stop recording or playback

Editing
  Delete / Backspace          Delete chord at cursor
  Ctrl+Delete / Ctrl+Backspace  Delete structural mark at cursor
                               (section mark, repeat bracket, N.C.)
  Ctrl+Z / Ctrl+Y       Undo / Redo
  Ctrl+X / Ctrl+C / Ctrl+V  Cut / Copy / Paste chord
  Ctrl+Return           Insert chord (dialog)
  F2                    Edit chord in place (dialog pre-filled with current chord)
  N                     Toggle No Chord (N.C.)
  Ctrl+T                Transpose (dialog)

Section Marks (Ctrl+Shift+letter)
  Ctrl+Shift+A/B/C/D    Section A / B / C / D
  Ctrl+Shift+V          Verse
  Ctrl+Shift+I          Intro
  Ctrl+Shift+S          Segno
  Ctrl+Shift+Q          Coda
  Ctrl+Shift+F          Fine (end mark)

Repeat Brackets & Volta
  [                     Mark repeat start
  ]                     Mark repeat end (then press V at volta beginning)
  V                     Add volta / ending bracket

Other
  / + (A–G)             Add bass note (slash chord)
  P                     Speak full position
  D                     Beat offset (debug)
  Ctrl+N                New project
  Ctrl+O                Open file
  Ctrl+S                Save
  Ctrl+E                Export to iReal Pro
  Ctrl+Shift+E          Show QR code
  Ctrl+L                Speak recent log entries
  F1                    Keyboard shortcuts
  Ctrl+Q                Quit
"""


class IOMixin:
    """Mixin that provides file I/O, export, and static dialog methods."""

    # ------------------------------------------------------------------
    # Save / Export
    # ------------------------------------------------------------------

    def _save_to_path(self, path: Path) -> None:
        """Write the progression to *path* and update _current_file."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.progression.to_json())
        self._current_file = path
        self._is_dirty = False

    def save(self) -> None:
        """Save to the current file; prompt for a path if none is set yet."""
        if self._current_file is not None:
            try:
                self._save_to_path(self._current_file)
                self.speak(_("Saved to {name}").format(name=self._current_file.name))
            except Exception as e:
                self.speak(_("Save failed: {e}").format(e=e))
        else:
            self.save_as()

    def save_as(self) -> None:
        """Show a Save-As dialog; save as .ips."""
        if self._frame is not None:
            default_name = (
                self.progression.title.replace(' ', '_') + '.ips'
            )
            dlg = wx.FileDialog(
                self._frame,
                message=_("Save progression"),
                defaultFile=default_name,
                wildcard=_("IReal Studio files (*.ips)|*.ips|All files (*.*)|*.*"),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            if dlg.ShowModal() == wx.ID_OK:
                path = Path(dlg.GetPath())
                dlg.Destroy()
                try:
                    self._save_to_path(path)
                    self.speak(_("Saved to {name}").format(name=path.name))
                except Exception as e:
                    self.speak(_("Save failed: {e}").format(e=e))
            else:
                dlg.Destroy()
        else:
            # Fallback (no GUI)
            try:
                self._save_to_path(Path(SAVE_FILE))
                self.speak(_("Saved to {name}").format(name=SAVE_FILE))
            except Exception as e:
                self.speak(_("Save failed: {e}").format(e=e))

    def open_file(self) -> None:
        """Show an Open dialog and load the selected .ips file."""
        if self._frame is None:
            return
        dlg = wx.FileDialog(
            self._frame,
            message=_("Open progression"),
            wildcard=_("IReal Studio files (*.ips)|*.ips|All files (*.*)|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            path = Path(dlg.GetPath())
            dlg.Destroy()
            try:
                with open(path, encoding='utf-8') as f:
                    self.progression = ChordProgression.from_json(f.read())
                self._apply_loaded_progression(path)
                self.speak(_("Opened {title}").format(title=self.progression.title))
            except Exception as e:
                self.speak(_("Open failed: {e}").format(e=e))
        else:
            dlg.Destroy()

    def new_project(self) -> None:
        """Prompt to save unsaved changes, then show New Project dialog and reset state."""
        # Stop any active recording / playback before resetting state.
        if self._recorder.state != AppState.IDLE:
            self._recorder.stop_all()

        if self._is_dirty:
            dlg = wx.MessageDialog(
                self._frame,
                _("'{title}' has unsaved changes.\n\nSave before creating a new project?").format(
                    title=self.progression.title
                ),
                _("Unsaved Changes"),
                wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_WARNING,
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_CANCEL:
                return
            if result == wx.ID_YES:
                self.save()
                if self._is_dirty:
                    # User cancelled Save As dialog – abort
                    return

        data = new_project_dialog(
            parent=self._frame,
            defaults={
                'title':    DEFAULT_TITLE,
                'composer': '',
                'key':      DEFAULT_KEY,
                'style':    DEFAULT_STYLE,
                'bpm':      DEFAULT_BPM,
            },
        )
        if data is None:
            return

        self.progression = ChordProgression(
            title=DEFAULT_TITLE,
            time_signature=DEFAULT_TIME_SIG,
            key=DEFAULT_KEY,
            style=DEFAULT_STYLE,
            bpm=DEFAULT_BPM,
        )
        self.progression.title    = data.get('title',    DEFAULT_TITLE)
        self.progression.composer = data.get('composer', '')
        self.progression.key      = data.get('key',      DEFAULT_KEY)
        self.progression.style    = data.get('style',    DEFAULT_STYLE)
        try:
            bpm = int(data.get('bpm', DEFAULT_BPM))
            if BPM_MIN <= bpm <= BPM_MAX:
                self.progression.bpm = bpm
                self.recording_bpm   = bpm
            else:
                self.recording_bpm = self.progression.bpm
        except (ValueError, TypeError):
            self.recording_bpm = self.progression.bpm

        self.cursor = Position(1, 1, self.progression.time_signature)
        self._current_file = None
        self._is_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clear_selection()
        self.speak(_("New project: {title}").format(title=self.progression.title))

    def export_ireal(self) -> None:
        try:
            url = self.progression.to_ireal_url()
        except Exception as e:
            self.speak(_("Export failed: {e}").format(e=e))
            return
        html = (
            "<!DOCTYPE html>\n<html>\n<head><title>"
            + self.progression.title
            + "</title></head>\n<body>\n<p>Opening in iReal Pro...</p>\n<p><a href=\""
            + url + "\">" + self.progression.title + "</a></p>\n"
            + "<script>window.location.href = \"" + url + "\";</script>\n"
            + "</body>\n</html>"
        )
        default_name = _safe_filename(self.progression.title) + '.html'
        default_dir = (
            str(self._current_file.parent)
            if self._current_file is not None
            else str(Path.cwd())
        )
        if self._frame is not None:
            dlg = wx.FileDialog(
                self._frame,
                message=_("Export iReal Pro HTML"),
                defaultDir=default_dir,
                defaultFile=default_name,
                wildcard=_("HTML files (*.html)|*.html|All files (*.*)|*.*"),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            html_file = dlg.GetPath()
            dlg.Destroy()
        else:
            html_file = default_name
        try:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html)
            self.speak(_("Exported to {name}").format(name=Path(html_file).name))
        except Exception as e:
            self.speak(_("Export failed: {e}").format(e=e))

    def export_qr_code(self) -> None:
        """Generate a QR code for the iReal Pro URL and show it in a popup dialog."""
        try:
            import qrcode
        except ImportError:
            self.speak(_("QR code export requires the qrcode package (uv add qrcode)"))
            return
        try:
            url = self.progression.to_ireal_url()
            # Use the default PIL/Pillow factory which produces a PNG image
            img = qrcode.make(url)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
        except Exception as e:
            self.speak(_("QR code generation failed: {e}").format(e=e))
            return

        if self._frame is None:
            self.speak(_("QR code ready but no window to display it"))
            return

        bmp: wx.Bitmap | None = None
        try:
            wx_img = wx.Image(io.BytesIO(png_bytes), wx.BITMAP_TYPE_PNG)
            if not wx_img.IsOk():
                raise ValueError("wx.Image decode returned invalid image")
            wx_img.Rescale(320, 320, wx.IMAGE_QUALITY_HIGH)
            bmp = wx.Bitmap(wx_img)
            if not bmp.IsOk():
                raise ValueError("wx.Bitmap conversion failed")
        except Exception as exc:
            _app_logger.warning("QR image render failed: %s", exc)

        dlg = wx.Dialog(self._frame, title=_("QR Code – {title}").format(title=self.progression.title))
        sizer = wx.BoxSizer(wx.VERTICAL)
        if bmp is not None:
            sizer.Add(wx.StaticBitmap(dlg, bitmap=bmp), 0, wx.ALL | wx.ALIGN_CENTER, 10)
        hint_label = wx.StaticText(
            dlg,
            label=_("Scan this QR code with iReal Pro to import the chord chart."),
            style=wx.ALIGN_CENTER,
        )
        hint_label.SetMaxSize(wx.Size(320, -1))
        hint_label.Wrap(320)
        sizer.Add(hint_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_CENTER, 10)
        ok_btn = wx.Button(dlg, wx.ID_OK, _("OK"))
        ok_btn.SetDefault()
        sizer.Add(ok_btn, 0, wx.BOTTOM | wx.ALIGN_CENTER, 10)
        dlg.SetSizerAndFit(sizer)
        dlg.ShowModal()
        dlg.Destroy()

    # ------------------------------------------------------------------
    # Static dialogs
    # ------------------------------------------------------------------

    def _show_keyboard_shortcuts(self) -> None:
        """Show keyboard shortcuts in an accessible dialog."""
        text = _(_KEYBOARD_SHORTCUTS_TEXT)
        if self._frame is None:
            self.speak(text)
            return
        dlg = wx.Dialog(self._frame, title=_("Keyboard Shortcuts – IReal Studio"),
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        text_ctrl = wx.TextCtrl(
            dlg, value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=wx.Size(520, 400),
        )
        text_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL,
                                  wx.FONTWEIGHT_NORMAL))
        sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 8)
        ok_btn = wx.Button(dlg, wx.ID_OK, _("OK"))
        ok_btn.SetDefault()
        sizer.Add(ok_btn, 0, wx.BOTTOM | wx.ALIGN_CENTER, 8)
        dlg.SetSizer(sizer)
        dlg.Fit()
        self.speak(_("Keyboard shortcuts dialog opened. Press OK to close."))
        dlg.ShowModal()
        dlg.Destroy()

    def _show_about(self) -> None:
        """Show the About dialog."""
        from version import __version__
        info = wx.adv.AboutDialogInfo()
        info.SetName("IReal Studio")
        info.SetVersion(__version__)
        info.SetDescription(
            _("A blind-accessible chord progression recorder\n"
              "for musicians who use screen readers.\n\n"
              "Export chord charts to iReal Pro format.")
        )
        info.SetCopyright(_("(C) 2026 Deniz Sincar"))
        wx.adv.AboutBox(info, self._frame)

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
                ts = TimeSignature.from_string(ts_str)
                self.progression.time_signature = ts
                self.cursor = Position(
                    self.cursor.measure,
                    min(self.cursor.beat, ts.numerator),
                    ts,
                )
            except (ValueError, AttributeError):
                pass
        self._mark_dirty()
        self.speak(_("Settings updated: {title}").format(title=self.progression.title))

    def _insert_chord_from_menu(self) -> None:
        """Show Insert Chord dialog and add the chord at the cursor."""
        chords_here = self.progression.find_chords_at_position(self.cursor)
        current = chords_here[0].chord.name if chords_here else 'C'
        name = insert_chord_dialog(parent=self._frame, default=current)
        if name:
            self._push_undo()
            self.progression.add_chord_by_name(name, self.cursor.measure, self.cursor.beat)
            self._mark_dirty()
            self.speak(_("Inserted {name}").format(name=name))

    def _edit_chord_in_place(self) -> None:
        """Edit the chord at the cursor in place (F2).

        Opens the chord-entry dialog pre-filled with the current chord name.
        Does nothing (speaks an error) when no chord is present at the cursor.
        """
        chords_here = self.progression.find_chords_at_position(self.cursor)
        if not chords_here:
            self.speak(_("No chord to edit"))
            return
        item = chords_here[0]
        name = insert_chord_dialog(parent=self._frame, default=item.chord.name)
        if name and name != item.chord.name:
            self._push_undo()
            # Preserve the existing bass/slash note so F2 doesn't silently drop it.
            self.progression.add_chord_by_name(
                name, self.cursor.measure, self.cursor.beat,
                bass_note=item.bass_note,
            )
            self._mark_dirty()
            self.speak(_("Edited {name}").format(name=name))

    def _insert_bass_from_menu(self) -> None:
        """Show a prompt to enter a bass note for the chord at the cursor."""
        val = prompt_input(_("Bass Note"), _("Enter bass note (e.g. E, Bb):"), "",
                           parent=self._frame)
        if val is not None:
            self.add_bass_note(val.strip())

    # ------------------------------------------------------------------
    # Update checker
    # ------------------------------------------------------------------

    def _on_check_for_updates(self) -> None:
        """Menu handler for Settings → Check for Updates."""
        from updater import check_for_updates_sync
        check_for_updates_sync(parent_window=self._frame, silent_if_current=False)

    def _start_background_update_check(self) -> None:
        """Silently check for updates on startup; notify the user if one is found."""
        from updater import check_for_updates_async

        def _on_found(tag: str, url: str, release_data: dict) -> None:
            wx.CallAfter(self._notify_update_available, tag, url, release_data)

        check_for_updates_async(on_update_found=_on_found)

    def _notify_update_available(self, tag: str, url: str, release_data: dict) -> None:
        """Show a non-blocking update notification in the wx main thread.

        When running from source (not compiled), logs a debug message via
        speech instead of showing a dialog, to avoid interrupting development.
        In compiled mode, offers to download and install the update automatically.
        """
        from updater import is_compiled, can_auto_install, run_download_and_install
        if not is_compiled():
            self.speak(_("Debug: new update available: {tag}").format(tag=tag))
            return

        auto_install = can_auto_install(release_data)
        if auto_install:
            msg = _(
                "A new version of IReal Studio is available: {tag}\n\n"
                "Download and install the update now?"
            ).format(tag=tag)
        else:
            msg = _(
                "A new version of IReal Studio is available: {tag}\n\n"
                "Open the download page?"
            ).format(tag=tag)

        dlg = wx.MessageDialog(
            self._frame, msg, _("Update Available"),
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            if auto_install:
                run_download_and_install(self._frame, release_data)
            else:
                import webbrowser as _wb
                _wb.open(url)
        dlg.Destroy()
