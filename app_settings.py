"""
app_settings.py – Application-level configuration constants and helpers for
loading and saving the per-user settings file.
"""
import sys
import os
import json
import logging
import re
from pathlib import Path

from chords import TimeSignature

# ---------------------------------------------------------------------------
# Default project settings
# ---------------------------------------------------------------------------
DEFAULT_BPM = 120
DEFAULT_TITLE = "My Progression"
DEFAULT_KEY = "C"
DEFAULT_STYLE = "Medium Swing"
DEFAULT_TIME_SIG = TimeSignature(4, 4)
SAVE_FILE = "progression.ips"

# ---------------------------------------------------------------------------
# MIDI metronome defaults
# ---------------------------------------------------------------------------
# Default notes for non-percussion channel use (channel 1, 0-indexed as 0).
# Notes 91 (B6) and 84 (C6) were chosen by the project author as a pleasant
# two-tone melodic metronome pair with a clear pitch contrast between downbeat
# and upbeat.  Velocity 48 gives a medium-soft click on most instruments.
MIDI_METRO_ON_NOTE: int = 91    # B6 — downbeat
MIDI_METRO_OFF_NOTE: int = 84   # C6 — upbeat
MIDI_METRO_VELOCITY: int = 48
MIDI_METRO_CHANNEL: int = 0     # channel 1 (0-indexed) — melodic (not percussion)
MIDI_METRO_DURATION_MS: int = 100  # note-on duration in milliseconds
MIDI_METRO_SMART: bool = True   # chord-aware smart metronome mode enabled by default


def _get_settings_path() -> Path:
    """Return the path to the per-user app settings file."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return base / 'irealstudio' / 'settings.json'


def _load_app_settings() -> dict:
    """Load saved app settings; return an empty dict on any error."""
    path = _get_settings_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings_file(settings: dict) -> None:
    """Persist *settings* to the user config directory."""
    path = _get_settings_path()
    _logger = logging.getLogger('irealstudio')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except Exception as exc:
        _logger.error("Could not save app settings: %s", exc)


def _safe_filename(title: str) -> str:
    """Return a filesystem-safe version of *title* suitable for use as a base filename."""
    safe = re.sub(r'[\\/:*?"<>|]', '', title)   # strip Windows-forbidden chars + slashes
    safe = safe.replace(' ', '_')
    safe = safe.strip('._')                       # leading/trailing dots/underscores
    return safe or 'export'
