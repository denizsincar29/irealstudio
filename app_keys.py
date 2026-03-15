"""
app_keys.py – Keyboard event handler mixin for the App class.

Provides _on_keydown and _on_keyup, extracted from main.py to keep it lean.
"""
import wx
from recorder import AppState
from commands import (
    RECORDING_MODE_OVERDUB, RECORDING_MODE_OVERWRITE, _WX_KEY_SYM,
)
from i18n import _


class KeysMixin:
    """Mixin that provides wxPython keyboard event handlers."""

    # ------------------------------------------------------------------
    # Keyboard event handlers
    # ------------------------------------------------------------------

    def _on_keydown(self, event: wx.KeyEvent) -> None:
        ctrl  = event.ControlDown()
        alt   = event.AltDown()
        shift = event.ShiftDown()
        kc    = event.GetKeyCode()
        key   = _WX_KEY_SYM.get(kc) or (chr(kc).lower() if 32 <= kc < 127 else '')

        # Quit
        if ctrl and key == 'q':
            self._on_quit()

        # Escape – stop recording/playback; also clear selection
        elif key == 'escape':
            self._clear_selection()
            was_recording = self._recorder.state == AppState.RECORDING
            self._recorder.stop_all()
            if was_recording and self.recording_mode == RECORDING_MODE_OVERWRITE:
                self._apply_overwrite()
            self.speak(_("Stopped"))

        # R – record (start if idle, stop if recording/pre-count/playing)
        elif key == 'r' and not ctrl and not shift:
            if self._recorder.state == AppState.IDLE:
                if self.recording_mode == RECORDING_MODE_OVERWRITE:
                    self._start_overwrite_session()
                self._seed_smart_metro()
                self._recorder.start_recording(
                    self.progression, self.cursor,
                    recording_bpm=self.recording_bpm,
                )
            elif self._recorder.state in (AppState.RECORDING, AppState.PRE_COUNT):
                self._recorder.stop_all()
                if self.recording_mode == RECORDING_MODE_OVERWRITE:
                    self._apply_overwrite()
                self.speak(_("Stopped"))
            else:
                self._recorder.stop_all()
                self.speak(_("Stopped"))

        # Space – play/stop playback; also previews the current chord on MIDI
        # output when "play chord when navigating" is enabled.
        elif key == 'space':
            if ctrl:
                if self._recorder.state == AppState.PLAYING:
                    import time
                    self._recorder.stop_all()
                    time.sleep(0.05)
                    if self._recorder.playback_stopped_at:
                        self.cursor = self._recorder.playback_stopped_at
                        self._announce_position()
            else:
                if self._recorder.state == AppState.IDLE:
                    # Preview chord on MIDI output when navigation mode is active.
                    if self._midi.midi_output is not None and self.chord_play_mode in ('navigation', 'both'):
                        self.play_current_chord_midi()
                    self._seed_smart_metro()
                    self._recorder.start_playback(self.progression, self.cursor)
                elif self._recorder.state in (AppState.RECORDING, AppState.PRE_COUNT):
                    self._recorder.stop_all()
                    if self.recording_mode == RECORDING_MODE_OVERWRITE:
                        self._apply_overwrite()
                    self.speak(_("Stopped"))
                elif self._recorder.state == AppState.PLAYING:
                    self._recorder.stop_all()

        # Navigation – Left/Right
        # Shift+Left/Right: extend selection by chord
        # Ctrl+Left/Right: by measure; Alt+Left/Right: by beat
        # Ctrl+Alt+Left/Right: by structural marker
        # Shift+Ctrl/Alt/Ctrl+Alt variants: extend selection accordingly
        elif key == 'left':
            if self._recorder.state == AppState.IDLE:
                if shift and ctrl and alt:
                    self._extend_selection('left', structural=True)
                elif shift and ctrl and not alt:
                    self._extend_selection('left', by_measure=True)
                elif shift and alt and not ctrl:
                    self._extend_selection('left', by_beat=True)
                elif shift and not ctrl and not alt:
                    self._extend_selection('left')
                elif ctrl and alt and not shift:
                    self._clear_selection()
                    self.navigate_structural('left')
                else:
                    self._clear_selection()
                    self.navigate('left', by_measure=ctrl, by_beat=alt)
        elif key == 'right':
            if self._recorder.state == AppState.IDLE:
                if shift and ctrl and alt:
                    self._extend_selection('right', structural=True)
                elif shift and ctrl and not alt:
                    self._extend_selection('right', by_measure=True)
                elif shift and alt and not ctrl:
                    self._extend_selection('right', by_beat=True)
                elif shift and not ctrl and not alt:
                    self._extend_selection('right')
                elif ctrl and alt and not shift:
                    self._clear_selection()
                    self.navigate_structural('right')
                else:
                    self._clear_selection()
                    self.navigate('right', by_measure=ctrl, by_beat=alt)
        elif key == 'home' and ctrl:
            if self._recorder.state == AppState.IDLE:
                self._clear_selection()
                self.navigate_home()
        elif key == 'end' and ctrl:
            if self._recorder.state == AppState.IDLE:
                self._clear_selection()
                self.navigate_end()

        # Ctrl+N – new project
        elif ctrl and key == 'n' and not shift:
            if self._recorder.state == AppState.IDLE:
                self.new_project()

        # Ctrl+O – open file
        elif ctrl and key == 'o' and not shift:
            if self._recorder.state == AppState.IDLE:
                self.open_file()

        # Ctrl+S – save
        elif ctrl and key == 's' and not shift:
            self.save()

        # Ctrl+E – export iReal Pro HTML
        elif ctrl and key == 'e' and not shift:
            self.export_ireal()

        # Ctrl+Shift+E – export QR code
        elif ctrl and shift and key == 'e':
            self.export_qr_code()

        # Ctrl+Z – undo
        elif ctrl and key == 'z' and not shift:
            self.undo()

        # Ctrl+Y – redo
        elif ctrl and key == 'y' and not shift:
            self.redo()

        # Ctrl+A – select all chords
        elif ctrl and key == 'a' and not shift:
            if self._recorder.state == AppState.IDLE:
                self._select_all()

        # Ctrl+C – copy chord (or selection)
        elif ctrl and key == 'c' and not shift:
            if self._selected_range() is not None:
                self._copy_selection()
            else:
                self.copy_chord()

        # Ctrl+X – cut chord (or selection)
        elif ctrl and key == 'x' and not shift:
            if self._selected_range() is not None:
                self._cut_selection()
            else:
                self.cut_chord()

        # Ctrl+V – paste chord
        elif ctrl and key == 'v' and not shift:
            self.paste_chord()

        # Ctrl+L – speak recent log entries
        elif ctrl and key == 'l' and not shift:
            self._speak_recent_log()

        # Ctrl+P – project settings
        elif ctrl and key == 'p' and not shift:
            if self._recorder.state == AppState.IDLE:
                self._open_project_settings()

        # Ctrl+Return – insert chord dialog
        elif ctrl and kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if self._recorder.state == AppState.IDLE:
                self._insert_chord_from_menu()

        # Ctrl+Shift+A/B/C/D/V/I/S/Q/F – section marks
        elif ctrl and shift and len(key) == 1 and key in 'abcdvisqf':
            if self._recorder.state == AppState.IDLE:
                self.add_section_mark(key)

        # Delete/Backspace – delete selection or chord at cursor
        # Ctrl+Delete / Ctrl+Backspace – delete structural marks (section mark,
        #   repeat bracket, N.C.) at the current measure regardless of whether
        #   a chord is present
        elif key in ('delete', 'backspace'):
            if self._recorder.state == AppState.IDLE:
                if ctrl and key in ('delete', 'backspace'):
                    self.delete_structural_at_cursor()
                elif self._selected_range() is not None:
                    self._delete_selection()
                else:
                    self.delete_at_cursor()

        # N – toggle no chord
        elif key == 'n' and not ctrl and not shift and not self.slash_held:
            if self._recorder.state == AppState.IDLE:
                self.toggle_no_chord()

        # / held for slash chords
        elif key == 'slash':
            self.slash_held = True

        # P – verbose position (section, ending, chord, bar, beat)
        elif key == 'p' and not ctrl and not shift:
            self._announce_position_verbose()

        # V key – volta
        elif key == 'v' and not ctrl and not shift:
            self.add_volta()

        # D key – debug: speak beat offset during recording/pre-count/playback
        elif key == 'd' and not ctrl and not shift:
            if self._recorder.state != AppState.IDLE:
                offset = self._recorder.beat_offset_ms()
                self.speak(_("Beat offset {offset:.0f} milliseconds").format(offset=offset))

        # Letter keys for slash-chord bass note (plain alpha only)
        elif len(key) == 1 and key.isalpha() and not ctrl and not shift:
            if self.slash_held:
                self.add_bass_note(key)
                self.slash_held = False

        # F1 – keyboard shortcuts help
        elif kc == wx.WXK_F1 and not ctrl and not shift:
            self._show_keyboard_shortcuts()

        event.Skip()

    def _on_keyup(self, event: wx.KeyEvent) -> None:
        kc  = event.GetKeyCode()
        key = _WX_KEY_SYM.get(kc) or (chr(kc).lower() if 32 <= kc < 127 else '')
        if key == 'slash':
            self.slash_held = False
        event.Skip()
