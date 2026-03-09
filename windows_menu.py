"""
windows_menu.py - Native Win32 menu bar for the IReal Studio window.

On non-Windows platforms this module exposes only stubs so the rest of the
code can always import and call it safely.

Menu layout
-----------
File
  Save          (Ctrl+S)
  Export iReal  (Ctrl+E)

MIDI Device
  <device 0>
  <device 1>
  ...
  ──────────────
  Refresh devices

Settings
  BPM: <current>...
  Key: <current>...
  Style: <current>...
"""

import sys
import queue
import threading

_IS_WINDOWS = sys.platform == 'win32'

# Menu-command ID constants
CMD_FILE_SAVE    = 1001
CMD_FILE_EXPORT  = 1002
CMD_MIDI_REFRESH = 2001
CMD_SETTINGS_BPM   = 3001
CMD_SETTINGS_KEY   = 3002
CMD_SETTINGS_STYLE = 3003
_MIDI_DEVICE_BASE  = 2100   # IDs 2100..2199 are MIDI device 0..99


def _device_id(index: int) -> int:
    return _MIDI_DEVICE_BASE + index


def _index_from_id(cmd_id: int) -> int:
    return cmd_id - _MIDI_DEVICE_BASE


# ---------------------------------------------------------------------------
# Stub for non-Windows
# ---------------------------------------------------------------------------

class _MenuStub:
    """No-op menu manager used on non-Windows platforms."""

    def install(self, hwnd) -> None:  # noqa: D401
        pass

    def refresh_devices(self, device_names: list[str], active_index: int | None) -> None:
        pass

    def update_settings_labels(self, bpm: int, key: str, style: str) -> None:
        pass

    def poll(self) -> int | None:  # noqa: D401
        """Return the next pending menu command ID, or None."""
        return None

    def destroy(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Windows implementation
# ---------------------------------------------------------------------------

if _IS_WINDOWS:
    import ctypes
    import ctypes.wintypes as wt

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    WM_COMMAND    = 0x0111
    WM_DESTROY    = 0x0002
    MF_STRING     = 0x0000
    MF_SEPARATOR  = 0x0800
    MF_POPUP      = 0x0010
    MF_GRAYED     = 0x0001
    MF_CHECKED    = 0x0008
    MF_UNCHECKED  = 0x0000
    MFT_SEPARATOR = 0x0800
    MFS_CHECKED   = 0x0008

    GWLP_WNDPROC  = -4
    # On 64-bit Windows SetWindowLongPtr must be used; on 32-bit SetWindowLong
    # is the same function alias.
    try:
        _SetWindowLongPtr = _user32.SetWindowLongPtrW
        _GetWindowLongPtr = _user32.GetWindowLongPtrW
        _CallWindowProc   = _user32.CallWindowProcW
    except AttributeError:          # 32-bit fallback
        _SetWindowLongPtr = _user32.SetWindowLongW
        _GetWindowLongPtr = _user32.GetWindowLongW
        _CallWindowProc   = _user32.CallWindowProcW

    _WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

    class WindowsMenu:
        """Attaches a native Win32 menu bar to the application window."""

        def __init__(self):
            self._hwnd: int = 0
            self._menu_bar: int = 0
            self._midi_menu: int = 0
            self._settings_menu: int = 0
            self._file_menu: int = 0
            self._orig_wndproc: int = 0
            self._wndproc_ref = None   # keep reference alive
            self._cmd_queue: queue.SimpleQueue[int] = queue.SimpleQueue()
            self._device_names: list[str] = []
            self._active_device: int | None = None

        # ----------------------------------------------------------------
        # Public API
        # ----------------------------------------------------------------

        def install(self, hwnd: int) -> None:
            """Attach the menu bar to *hwnd* (the application window handle)."""
            self._hwnd = hwnd
            self._menu_bar   = _user32.CreateMenu()
            self._file_menu  = _user32.CreatePopupMenu()
            self._midi_menu  = _user32.CreatePopupMenu()
            self._settings_menu = _user32.CreatePopupMenu()

            # File menu
            _user32.AppendMenuW(self._file_menu, MF_STRING, CMD_FILE_SAVE,   "&Save\tCtrl+S")
            _user32.AppendMenuW(self._file_menu, MF_STRING, CMD_FILE_EXPORT, "&Export to iReal Pro\tCtrl+E")

            # MIDI menu (populated by refresh_devices)
            _user32.AppendMenuW(self._midi_menu, MF_STRING | MF_GRAYED,
                                CMD_MIDI_REFRESH, "No MIDI devices found")
            _user32.AppendMenuW(self._midi_menu, MF_SEPARATOR, 0, None)
            _user32.AppendMenuW(self._midi_menu, MF_STRING,
                                CMD_MIDI_REFRESH, "&Refresh devices")

            # Settings menu
            _user32.AppendMenuW(self._settings_menu, MF_STRING,
                                CMD_SETTINGS_BPM,   "&BPM...")
            _user32.AppendMenuW(self._settings_menu, MF_STRING,
                                CMD_SETTINGS_KEY,   "&Key...")
            _user32.AppendMenuW(self._settings_menu, MF_STRING,
                                CMD_SETTINGS_STYLE, "&Style...")

            # Top-level menu bar
            _user32.AppendMenuW(self._menu_bar, MF_POPUP,
                                self._file_menu,  "&File")
            _user32.AppendMenuW(self._menu_bar, MF_POPUP,
                                self._midi_menu,  "&MIDI Device")
            _user32.AppendMenuW(self._menu_bar, MF_POPUP,
                                self._settings_menu, "&Settings")

            _user32.SetMenu(hwnd, self._menu_bar)

            # Subclass the window so we can catch WM_COMMAND
            self._wndproc_ref = _WNDPROC(self._wndproc)
            self._orig_wndproc = _SetWindowLongPtr(
                hwnd, GWLP_WNDPROC,
                ctypes.cast(self._wndproc_ref, ctypes.c_void_p).value)

        def refresh_devices(self, device_names: list[str],
                            active_index: int | None) -> None:
            """Rebuild the MIDI Device menu with the given port names."""
            if not self._midi_menu:
                return
            self._device_names = list(device_names)
            self._active_device = active_index

            # Remove all items except the separator and Refresh at bottom
            count = _user32.GetMenuItemCount(self._midi_menu)
            # Keep last 2 items (separator + Refresh)
            for _ in range(max(0, count - 2)):
                _user32.RemoveMenu(self._midi_menu, 0, 0x00000400)  # MF_BYPOSITION

            if device_names:
                # Insert device items before separator
                for i, name in enumerate(device_names):
                    flags = MF_STRING
                    if i == active_index:
                        flags |= MF_CHECKED
                    _user32.InsertMenuW(self._midi_menu, 0, 0x00000400 | flags,
                                        _device_id(i), name)
            else:
                _user32.InsertMenuW(self._midi_menu, 0,
                                    0x00000400 | MF_STRING | MF_GRAYED,
                                    CMD_MIDI_REFRESH, "No MIDI devices found")

            _user32.DrawMenuBar(self._hwnd)

        def update_settings_labels(self, bpm: int, key: str, style: str) -> None:
            """Update the Settings menu item labels to show current values."""
            if not self._settings_menu:
                return
            _user32.ModifyMenuW(self._settings_menu, CMD_SETTINGS_BPM,
                                0x00000000 | MF_STRING,    # MF_BYCOMMAND
                                CMD_SETTINGS_BPM, f"&BPM: {bpm}...")
            _user32.ModifyMenuW(self._settings_menu, CMD_SETTINGS_KEY,
                                0x00000000 | MF_STRING,
                                CMD_SETTINGS_KEY, f"&Key: {key}...")
            _user32.ModifyMenuW(self._settings_menu, CMD_SETTINGS_STYLE,
                                0x00000000 | MF_STRING,
                                CMD_SETTINGS_STYLE, f"&Style: {style}...")
            _user32.DrawMenuBar(self._hwnd)

        def poll(self) -> int | None:
            """Return the next pending menu command ID, or None if empty."""
            try:
                return self._cmd_queue.get_nowait()
            except queue.Empty:
                return None

        def destroy(self) -> None:
            if self._hwnd and self._orig_wndproc:
                _SetWindowLongPtr(self._hwnd, GWLP_WNDPROC, self._orig_wndproc)
            if self._menu_bar:
                _user32.DestroyMenu(self._menu_bar)
            self._hwnd = 0
            self._menu_bar = 0

        # ----------------------------------------------------------------
        # Internal
        # ----------------------------------------------------------------

        def _wndproc(self, hwnd: int, msg: int,
                     wparam: int, lparam: int) -> int:
            if msg == WM_COMMAND:
                cmd_id = wparam & 0xFFFF
                self._cmd_queue.put(cmd_id)
            return _CallWindowProc(self._orig_wndproc, hwnd, msg, wparam, lparam)

    def create_menu() -> WindowsMenu:
        """Create a WindowsMenu for the current platform."""
        return WindowsMenu()

else:
    def create_menu() -> _MenuStub:  # type: ignore[misc]
        """Create a no-op menu stub on non-Windows platforms."""
        return _MenuStub()



