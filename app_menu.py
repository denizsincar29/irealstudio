"""
app_menu.py – Menu building and menu event handler mixin for the App class.

Extracted from main.py to reduce its size.
"""
import wx
from sound import get_output_devices, set_output_device, get_current_output_device
from recorder import AppState
from commands import (
    _CMD_FILE_NEW, _CMD_FILE_OPEN, _CMD_FILE_SAVE, _CMD_FILE_SAVE_AS,
    _CMD_FILE_EXPORT, _CMD_FILE_QR, _CMD_FILE_QUIT,
    _CMD_EDIT_UNDO, _CMD_EDIT_REDO, _CMD_EDIT_CUT, _CMD_EDIT_COPY, _CMD_EDIT_PASTE,
    _CMD_INSERT_CHORD, _CMD_EDIT_CHORD,
    _CMD_INSERT_SM_A, _CMD_INSERT_SM_B, _CMD_INSERT_SM_C,
    _CMD_INSERT_SM_D, _CMD_INSERT_SM_V, _CMD_INSERT_SM_I,
    _CMD_INSERT_SM_S, _CMD_INSERT_SM_Q, _CMD_INSERT_SM_F,
    _CMD_INSERT_VOLTA, _CMD_INSERT_NC, _CMD_INSERT_BASS, _CMD_TRANSPOSE,
    _CMD_RECORD_START, _CMD_RECORD_PLAY, _CMD_RECORD_STOP,
    _CMD_RECORD_MODE_OVERDUB, _CMD_RECORD_MODE_OVERWRITE, _CMD_RECORD_OVERWRITE_WHOLE,
    _CMD_SETTINGS_PROJECT, _CMD_SETTINGS_UPDATE,
    _CMD_CHORD_PLAY_OFF, _CMD_CHORD_PLAY_NAV, _CMD_CHORD_PLAY_PB, _CMD_CHORD_PLAY_BOTH,
    _CMD_METRO_SETTINGS,
    _CMD_MIDI_REFRESH, _CMD_MIDI_NONE, _CMD_MIDI_OUT_REFRESH, _CMD_MIDI_OUT_NONE,
    _CMD_SOUND_OUT_REFRESH, _CMD_SOUND_OUT_NONE, _CMD_SOUND_OUT_DEFAULT,
    _CMD_HELP_SHORTCUTS, _CMD_HELP_ABOUT,
    _LANG_BASE, _LANGUAGES,
    _MIDI_DEVICE_BASE, _MIDI_OUT_DEVICE_BASE, _SOUND_OUT_DEVICE_BASE,
    RECORDING_MODE_OVERDUB, RECORDING_MODE_OVERWRITE,
)
from i18n import _, ngettext, set_language, get_language


class MenuMixin:
    """Mixin that provides menu building, device-submenu management, and menu event handlers."""

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
                                      _("No MIDI devices found"))
            self._midi_menu.Insert(0, placeholder)
            placeholder.Enable(False)

    def _refresh_menu_state(self) -> None:
        """Push current app state into the menu labels."""
        self._refresh_midi_devices()
        self._refresh_midi_out_devices()
        self._refresh_sound_out_devices()

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
                                      _("No MIDI output devices found"))
            self._midi_out_menu.Insert(0, placeholder)
            placeholder.Enable(False)

    def _refresh_sound_out_devices(self) -> None:
        """Rebuild the Sound Output submenu with available audio output devices."""
        if self._sound_out_menu is None:
            return
        devices = get_output_devices()  # list of (device_id, name)
        current_out = get_current_output_device()  # None = system default

        # Remove all device items (keep the trailing separator + "Refresh" = 2 items).
        count = self._sound_out_menu.GetMenuItemCount()
        for _i in range(max(0, count - 2)):
            item = self._sound_out_menu.FindItemByPosition(0)
            self._sound_out_menu.Remove(item)

        insert_pos = 0

        # Always offer a "System default" option at the top.
        default_item = wx.MenuItem(
            self._sound_out_menu, _CMD_SOUND_OUT_DEFAULT,
            _("System default"), kind=wx.ITEM_CHECK,
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
                                      _("No audio output devices found"))
            self._sound_out_menu.Insert(insert_pos, placeholder)
            placeholder.Enable(False)

    # ------------------------------------------------------------------
    # Menu event handlers (EVT_MENU — fired directly by wxPython)
    # ------------------------------------------------------------------

    def _on_menu_midi_refresh(self, _event: wx.CommandEvent) -> None:
        self._refresh_midi_devices()
        self.speak(_("MIDI devices refreshed"))

    def _on_menu_midi_device(self, event: wx.CommandEvent) -> None:
        idx = event.GetId() - _MIDI_DEVICE_BASE
        names = self._midi.get_input_names()
        if 0 <= idx < len(names):
            self._midi.open_by_name(names[idx])
            self._refresh_midi_devices()
            self.speak(_("MIDI input: {name}").format(name=names[idx]))
            self._save_app_settings()

    def _on_menu_midi_out_refresh(self, _event: wx.CommandEvent) -> None:
        self._refresh_midi_out_devices()
        self.speak(_("MIDI output devices refreshed"))

    def _on_menu_midi_out_device(self, event: wx.CommandEvent) -> None:
        idx = event.GetId() - _MIDI_OUT_DEVICE_BASE
        names = self._midi.get_output_names()
        if 0 <= idx < len(names):
            # Save the current compensation for the old output device before switching.
            old_name = self._midi.midi_output_name
            if old_name:
                self._midi_device_compensation[old_name] = self.midi_compensation_ms
            self._midi.open_output_by_name(names[idx])
            # Load per-device compensation for the new output device.
            new_name = names[idx]
            if new_name in self._midi_device_compensation:
                self.midi_compensation_ms = self._midi_device_compensation[new_name]
            self._sync_compensation_to_recorder()
            self._refresh_midi_out_devices()
            self.speak(_("MIDI output: {name}").format(name=new_name))
            self._save_app_settings()

    def _on_menu_sound_out_refresh(self, _event: wx.CommandEvent) -> None:
        self._refresh_sound_out_devices()
        self.speak(_("Sound output devices refreshed"))

    def _on_menu_sound_out_default(self, _event: wx.CommandEvent) -> None:
        set_output_device(None)
        self.speak(_("Sound output: system default"))
        self._refresh_sound_out_devices()
        self._save_app_settings()

    def _on_menu_sound_out_device(self, event: wx.CommandEvent) -> None:
        list_idx = event.GetId() - _SOUND_OUT_DEVICE_BASE
        devices = get_output_devices()
        if 0 <= list_idx < len(devices):
            dev_id, dev_name = devices[list_idx]
            if set_output_device(dev_id):
                self.speak(_("Sound output: {name}").format(name=dev_name))
            else:
                self.speak(_("Could not open: {name}").format(name=dev_name))
            self._refresh_sound_out_devices()
            self._save_app_settings()

    def _menu_record(self) -> None:
        if self._recorder.state == AppState.IDLE:
            if self.recording_mode == RECORDING_MODE_OVERWRITE:
                self._start_overwrite_session()
            self._seed_smart_metro()
            self._recorder.start_recording(
                self.progression, self.cursor,
                recording_bpm=self.recording_bpm,
            )
        else:
            self.speak(_("Already active"))

    def _menu_play(self) -> None:
        if self._recorder.state == AppState.IDLE:
            self._seed_smart_metro()
            self._recorder.start_playback(self.progression, self.cursor)
        elif self._recorder.state == AppState.PLAYING:
            self._recorder.stop_all()

    def _menu_stop(self) -> None:
        was_recording = self._recorder.state == AppState.RECORDING
        self._recorder.stop_all()
        if was_recording and self.recording_mode == RECORDING_MODE_OVERWRITE:
            self._apply_overwrite()
        self.speak(_("Stopped"))

    def _on_menu_language(self, event: wx.CommandEvent) -> None:
        """Handle a language radio-menu item click."""
        idx = event.GetId() - _LANG_BASE
        if 0 <= idx < len(_LANGUAGES):
            chosen_code = _LANGUAGES[idx][0]
            set_language(chosen_code)
            self._save_app_settings()
            self.speak(
                _("Language changed. Please restart IReal Studio for full effect.")
            )

    def _set_chord_play_mode(self, mode: str) -> None:
        """Set the chord playback mode and persist it."""
        self.chord_play_mode = mode
        # Update the radio item check state
        modes = ('off', 'navigation', 'playback', 'both')
        for item, m in zip(self._chord_play_items, modes):
            item.Check(m == mode)
        self._save_app_settings()
        labels = {
            'off':        _("Chord playback: off"),
            'navigation': _("Chord playback: during navigation"),
            'playback':   _("Chord playback: during playback"),
            'both':       _("Chord playback: both"),
        }
        self.speak(labels.get(mode, mode))

    def _sync_compensation_to_recorder(self) -> None:
        """Push the current compensation values from App attrs to the Recorder."""
        self._recorder.audio_compensation_ms = self.audio_compensation_ms
        self._recorder.midi_compensation_ms  = self.midi_compensation_ms

    def _open_metronome_settings(self) -> None:
        """Open the centralized Metronome Settings dialog."""
        from dialogs import prompt_metronome_settings
        from sound import play_sound

        def _preview(note: int, velocity: int, channel: int, duration_ms: int) -> None:
            """Play a single note through the MIDI output so the user can hear it."""
            try:
                self._midi.send_chord(
                    [note],
                    velocity=velocity,
                    duration=duration_ms / 1000.0,
                    channel=channel,
                )
            except Exception:
                pass

        def _audio_preview() -> None:
            """Play a single audio tick so it can be compared with the MIDI click."""
            try:
                play_sound(self._recorder.tick_sound)
            except Exception:
                pass

        result = prompt_metronome_settings(
            parent=self._frame,
            audio_compensation_ms=self.audio_compensation_ms,
            midi_metro_enabled=self.midi_metro_enabled,
            midi_metro_smart=self.midi_metro_smart,
            on_note=self.midi_metro_on_note,
            off_note=self.midi_metro_off_note,
            velocity=self.midi_metro_velocity,
            channel=self.midi_metro_channel,
            duration_ms=self.midi_metro_duration_ms,
            midi_compensation_ms=self.midi_compensation_ms,
            preview_fn=_preview if self._midi.midi_output is not None else None,
            audio_preview_fn=_audio_preview,
        )
        if result is not None:
            self.audio_compensation_ms  = result['audio_compensation_ms']
            self.midi_metro_enabled     = result['midi_metro_enabled']
            self.midi_metro_smart       = result['midi_metro_smart']
            self.midi_metro_on_note     = result['on_note']
            self.midi_metro_off_note    = result['off_note']
            self.midi_metro_velocity    = result['velocity']
            self.midi_metro_channel     = result['channel']
            self.midi_metro_duration_ms = result['duration_ms']
            self.midi_compensation_ms   = result['midi_compensation_ms']
            self._sync_compensation_to_recorder()
            self._save_app_settings()
            self.speak(_("Metronome settings saved"))

    def _on_transpose(self) -> None:
        """Show the Transpose dialog and apply transposition to the progression."""
        from dialogs import transpose_dialog
        result = transpose_dialog(parent=self._frame)
        if result is None:
            return
        raw_semitones = int(result.get('semitones', 0))
        if raw_semitones % 12 == 0:
            return
        semitone_abs = abs(raw_semitones) % 12
        semitones = semitone_abs if raw_semitones > 0 else -semitone_abs
        sel_items = self._chords_in_selection()
        self._push_undo()
        if sel_items:
            sel_positions = [item.position for item in sel_items]
            self.progression.transpose(semitones, positions=sel_positions)
            self.speak(
                ngettext(
                    "Transposed selection by {n} semitone",
                    "Transposed selection by {n} semitones",
                    abs(semitones),
                ).format(n=semitones)
            )
        else:
            self.progression.transpose(semitones)
            self.speak(
                ngettext(
                    "Transposed by {n} semitone, new key: {key}",
                    "Transposed by {n} semitones, new key: {key}",
                    abs(semitones),
                ).format(n=semitones, key=self.progression.key)
            )
        self._mark_dirty()
        self._schedule_display_update()

    # ------------------------------------------------------------------
    # Menu building
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        """Create a wx.MenuBar and attach it to the frame with EVT_MENU bindings."""
        current_lang = get_language()
        menu_bar = wx.MenuBar()

        # --- File ---
        file_menu = wx.Menu()
        file_menu.Append(_CMD_FILE_NEW,    _("&New Project") + "\tCtrl+N")
        file_menu.Append(_CMD_FILE_OPEN,   _("&Open...") + "\tCtrl+O")
        file_menu.Append(_CMD_FILE_SAVE,   _("&Save") + "\tCtrl+S")
        file_menu.Append(_CMD_FILE_SAVE_AS, _("Save &As..."))
        file_menu.AppendSeparator()
        file_menu.Append(_CMD_FILE_EXPORT, _("&Export to iReal Pro") + "\tCtrl+E")
        file_menu.Append(_CMD_FILE_QR,     _("Export &QR Code") + "\tCtrl+Shift+E")
        file_menu.AppendSeparator()
        file_menu.Append(_CMD_FILE_QUIT,   _("&Quit") + "\tCtrl+Q")
        menu_bar.Append(file_menu, _("&File"))

        # --- Edit ---
        edit_menu = wx.Menu()
        edit_menu.Append(_CMD_EDIT_UNDO,  _("&Undo") + "\tCtrl+Z")
        edit_menu.Append(_CMD_EDIT_REDO,  _("&Redo") + "\tCtrl+Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(_CMD_EDIT_CUT,   _("Cu&t") + "\tCtrl+X")
        edit_menu.Append(_CMD_EDIT_COPY,  _("&Copy") + "\tCtrl+C")
        edit_menu.Append(_CMD_EDIT_PASTE, _("&Paste") + "\tCtrl+V")
        edit_menu.AppendSeparator()
        edit_menu.Append(_CMD_TRANSPOSE,  _("&Transpose...") + "\tCtrl+T")
        menu_bar.Append(edit_menu, _("&Edit"))

        # --- Insert ---
        insert_menu = wx.Menu()
        insert_menu.Append(_CMD_INSERT_CHORD, _("&Add Chord...") + "\tCtrl+Return")
        insert_menu.Append(_CMD_EDIT_CHORD,   _("&Edit Chord...") + "\tF2")
        insert_menu.AppendSeparator()

        # Section marks sub-menu — Ctrl+Shift+letter shortcuts
        sm_menu = wx.Menu()
        sm_menu.Append(_CMD_INSERT_SM_A, _("&A (Section A)") + "\tCtrl+Shift+A")
        sm_menu.Append(_CMD_INSERT_SM_B, _("&B (Section B)") + "\tCtrl+Shift+B")
        sm_menu.Append(_CMD_INSERT_SM_C, _("&C (Section C)") + "\tCtrl+Shift+C")
        sm_menu.Append(_CMD_INSERT_SM_D, _("&D (Section D)") + "\tCtrl+Shift+D")
        sm_menu.Append(_CMD_INSERT_SM_V, _("&Verse") + "\tCtrl+Shift+V")
        sm_menu.Append(_CMD_INSERT_SM_I, _("&Intro") + "\tCtrl+Shift+I")
        sm_menu.Append(_CMD_INSERT_SM_S, _("&Segno") + "\tCtrl+Shift+S")
        sm_menu.Append(_CMD_INSERT_SM_Q, _("&Coda") + "\tCtrl+Shift+Q")
        # Fine (end mark) is commented out pending clarification of its iReal Pro semantics
        # sm_menu.Append(_CMD_INSERT_SM_F, _("&Fine (end mark)") + "\tCtrl+Shift+F")
        insert_menu.AppendSubMenu(sm_menu, _("&Section Mark"))

        insert_menu.Append(_CMD_INSERT_VOLTA, _("&Volta / Ending") + "\tV")
        insert_menu.AppendSeparator()
        insert_menu.Append(_CMD_INSERT_NC,     _("&No Chord (N.C.)"))
        insert_menu.Append(_CMD_INSERT_BASS,   _("&Bass Note...") + "\t/")
        menu_bar.Append(insert_menu, _("&Insert"))

        # --- Record & Playback ---
        rec_menu = wx.Menu()
        rec_menu.Append(_CMD_RECORD_START, _("&Record") + "\tR")
        rec_menu.Append(_CMD_RECORD_PLAY,  _("&Play") + "\tSpace")
        rec_menu.Append(_CMD_RECORD_STOP,  _("&Stop") + "\tEsc")
        rec_menu.AppendSeparator()
        self._overdub_item = rec_menu.AppendCheckItem(
            _CMD_RECORD_MODE_OVERDUB, _("&Overdub mode"))
        self._overdub_item.Check(self.recording_mode == RECORDING_MODE_OVERDUB)
        self._overwrite_item = rec_menu.AppendCheckItem(
            _CMD_RECORD_MODE_OVERWRITE, _("O&verwrite mode"))
        self._overwrite_item.Check(self.recording_mode == RECORDING_MODE_OVERWRITE)
        rec_menu.AppendSeparator()
        self._overwrite_whole_item = rec_menu.AppendCheckItem(
            _CMD_RECORD_OVERWRITE_WHOLE, _("Overwrite: &Whole measure"))
        self._overwrite_whole_item.Check(self.overwrite_whole_measure)
        self._overwrite_whole_item.Enable(
            self.recording_mode == RECORDING_MODE_OVERWRITE)
        menu_bar.Append(rec_menu, _("&Record"))

        # --- Settings ---
        settings_menu = wx.Menu()
        settings_menu.Append(_CMD_SETTINGS_PROJECT, _("&Project Settings...") + "\tCtrl+P")

        # Chord Playback mode sub-menu (radio items)
        settings_menu.AppendSeparator()
        chord_play_menu = wx.Menu()
        _chord_play_defs = [
            (_CMD_CHORD_PLAY_OFF,  _("&Off")),
            (_CMD_CHORD_PLAY_NAV,  _("During &Navigation")),
            (_CMD_CHORD_PLAY_PB,   _("During &Playback")),
            (_CMD_CHORD_PLAY_BOTH, _("&Both")),
        ]
        self._chord_play_items = []
        for cmd_id, label in _chord_play_defs:
            item = wx.MenuItem(chord_play_menu, cmd_id, label, kind=wx.ITEM_RADIO)
            chord_play_menu.Append(item)
            self._chord_play_items.append(item)
        # Set the currently-selected mode
        _mode_to_idx = {'off': 0, 'navigation': 1, 'playback': 2, 'both': 3}
        idx = _mode_to_idx.get(self.chord_play_mode, 0)
        self._chord_play_items[idx].Check(True)
        settings_menu.AppendSubMenu(chord_play_menu, _("Chord &Playback"))

        # Metronome Settings (replaces old MIDI metronome submenu)
        settings_menu.AppendSeparator()
        settings_menu.Append(_CMD_METRO_SETTINGS, _("&Metronome Settings..."))

        # Device sub-menus under Settings
        settings_menu.AppendSeparator()
        self._midi_menu = wx.Menu()
        self._midi_menu.AppendSeparator()
        self._midi_menu.Append(_CMD_MIDI_REFRESH, _("&Refresh devices"))
        settings_menu.AppendSubMenu(self._midi_menu, _("MIDI &Input Device"))

        self._midi_out_menu = wx.Menu()
        self._midi_out_menu.AppendSeparator()
        self._midi_out_menu.Append(_CMD_MIDI_OUT_REFRESH, _("&Refresh devices"))
        settings_menu.AppendSubMenu(self._midi_out_menu, _("MIDI &Output Device"))

        self._sound_out_menu = wx.Menu()
        self._sound_out_menu.AppendSeparator()
        self._sound_out_menu.Append(_CMD_SOUND_OUT_REFRESH, _("&Refresh devices"))
        settings_menu.AppendSubMenu(self._sound_out_menu, _("&Sound Output"))

        settings_menu.AppendSeparator()
        settings_menu.Append(_CMD_SETTINGS_UPDATE, _("Check for &Updates..."))

        # Language sub-menu (radio items, one per supported language)
        lang_menu = wx.Menu()
        for idx, (code, name) in enumerate(_LANGUAGES):
            item = wx.MenuItem(lang_menu, _LANG_BASE + idx, name, kind=wx.ITEM_RADIO)
            lang_menu.Append(item)
            if code == current_lang:
                item.Check(True)
        settings_menu.AppendSubMenu(lang_menu, _("&Language"))

        menu_bar.Append(settings_menu, _("&Settings"))

        # --- Help ---
        help_menu = wx.Menu()
        help_menu.Append(_CMD_HELP_SHORTCUTS, _("&Keyboard Shortcuts") + "\tF1")
        help_menu.AppendSeparator()
        help_menu.Append(_CMD_HELP_ABOUT, _("&About IReal Studio"))
        menu_bar.Append(help_menu, _("&Help"))

        self._frame.SetMenuBar(menu_bar)

        # Bind fixed-ID menu events
        self._frame.Bind(wx.EVT_MENU, lambda e: self.new_project(),
                         id=_CMD_FILE_NEW)
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
        self._frame.Bind(wx.EVT_MENU, lambda e: self._on_transpose(),
                         id=_CMD_TRANSPOSE)
        # Insert
        self._frame.Bind(wx.EVT_MENU, lambda e: self._insert_chord_from_menu(),
                         id=_CMD_INSERT_CHORD)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._edit_chord_in_place(),
                         id=_CMD_EDIT_CHORD)
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
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('s'),
                         id=_CMD_INSERT_SM_S)
        self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('q'),
                         id=_CMD_INSERT_SM_Q)
        # Fine binding commented out along with menu item
        # self._frame.Bind(wx.EVT_MENU, lambda e: self.add_section_mark('f'),
        #                  id=_CMD_INSERT_SM_F)
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
        self._frame.Bind(wx.EVT_MENU, lambda e: self._set_chord_play_mode('off'),
                         id=_CMD_CHORD_PLAY_OFF)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._set_chord_play_mode('navigation'),
                         id=_CMD_CHORD_PLAY_NAV)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._set_chord_play_mode('playback'),
                         id=_CMD_CHORD_PLAY_PB)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._set_chord_play_mode('both'),
                         id=_CMD_CHORD_PLAY_BOTH)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._open_metronome_settings(),
                         id=_CMD_METRO_SETTINGS)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._on_check_for_updates(),
                         id=_CMD_SETTINGS_UPDATE)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_language,
                         id=_LANG_BASE, id2=_LANG_BASE + len(_LANGUAGES) - 1)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_refresh,
                         id=_CMD_MIDI_REFRESH)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_out_refresh,
                         id=_CMD_MIDI_OUT_REFRESH)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_sound_out_refresh,
                         id=_CMD_SOUND_OUT_REFRESH)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_sound_out_default,
                         id=_CMD_SOUND_OUT_DEFAULT)
        # Bind entire device ID ranges (no per-device rebinding needed)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_device,
                         id=_MIDI_DEVICE_BASE, id2=_MIDI_DEVICE_BASE + 99)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_midi_out_device,
                         id=_MIDI_OUT_DEVICE_BASE, id2=_MIDI_OUT_DEVICE_BASE + 99)
        self._frame.Bind(wx.EVT_MENU, self._on_menu_sound_out_device,
                         id=_SOUND_OUT_DEVICE_BASE, id2=_SOUND_OUT_DEVICE_BASE + 99)
        # Help
        self._frame.Bind(wx.EVT_MENU, lambda e: self._show_keyboard_shortcuts(),
                         id=_CMD_HELP_SHORTCUTS)
        self._frame.Bind(wx.EVT_MENU, lambda e: self._show_about(),
                         id=_CMD_HELP_ABOUT)
