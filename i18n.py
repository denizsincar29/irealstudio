"""
i18n.py – Localization support for IReal Studio.

Usage::

    from i18n import _  # noqa: F401

The ``_()`` function translates a string to the current locale.  If no
translation catalogue is found, it falls back to the original (English) string.

The locale is determined by the following priority:
  1. ``IREALSTUDIO_LANG`` environment variable (e.g. ``ru``, ``en``)
  2. The system locale (``locale.getlocale()``)
  3. Falls back to English if no catalogue is available.
"""

import gettext
import logging
import os
from pathlib import Path

_logger = logging.getLogger('irealstudio')

# Directory containing per-language sub-directories:
#   locales/<lang>/LC_MESSAGES/irealstudio.mo
_LOCALE_DIR = Path(__file__).parent / 'locales'
_DOMAIN = 'irealstudio'

# Active translation object (NullTranslations = passthrough)
_translation: gettext.NullTranslations = gettext.NullTranslations()

# Currently active language code (None = English / no translation loaded)
_current_lang: str | None = None


def _compile_po_if_stale(lang: str) -> None:
    """Recompile the ``.po`` file to ``.mo`` when the source is newer.

    This is a convenience for developers who edit translation files directly.
    It silently skips if ``msgfmt`` is not found on PATH.
    """
    import shutil
    po_path = _LOCALE_DIR / lang / 'LC_MESSAGES' / f'{_DOMAIN}.po'
    mo_path = _LOCALE_DIR / lang / 'LC_MESSAGES' / f'{_DOMAIN}.mo'
    if not po_path.exists():
        return
    if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
        return
    msgfmt_bin = shutil.which('msgfmt')
    if msgfmt_bin is None:
        _logger.debug("msgfmt not found; cannot recompile '%s' translation", lang)
        return
    import subprocess
    try:
        subprocess.run(
            [msgfmt_bin, str(po_path), '-o', str(mo_path)],
            check=True,
            capture_output=True,
        )
        _logger.info("Recompiled '%s' translation catalogue", lang)
    except subprocess.CalledProcessError as exc:
        _logger.debug("Could not recompile '%s' .mo: %s", lang, exc)


def set_language(lang: str | None = None) -> None:
    """Load the translation catalogue for *lang*.

    If *lang* is ``None`` the language is auto-detected from the environment
    variable ``IREALSTUDIO_LANG`` or the system locale.

    When running from a source checkout and the ``.po`` file is newer than the
    compiled ``.mo``, the catalogue is recompiled automatically (requires
    ``msgfmt`` on PATH; silently skipped otherwise).
    """
    global _translation, _current_lang

    if lang is None:
        lang = os.environ.get('IREALSTUDIO_LANG')

    if lang is None:
        try:
            import locale as _locale
            loc = _locale.getlocale()[0]  # e.g. 'ru_RU' or None
            if loc:
                lang = loc.split('_')[0]  # e.g. 'ru'
        except Exception:
            pass

    if lang is None or lang == 'en':
        _translation = gettext.NullTranslations()
        _current_lang = 'en'
        return

    _compile_po_if_stale(lang)

    try:
        _translation = gettext.translation(
            _DOMAIN,
            localedir=str(_LOCALE_DIR),
            languages=[lang],
        )
        _current_lang = lang
        _logger.info("Loaded '%s' translation from %s", lang, _LOCALE_DIR)
    except FileNotFoundError:
        _logger.debug(
            "No '%s' translation found in %s; using English", lang, _LOCALE_DIR
        )
        _translation = gettext.NullTranslations()
        _current_lang = 'en'


def get_language() -> str:
    """Return the currently active language code (e.g. ``'en'``, ``'ru'``)."""
    return _current_lang or 'en'


def _(text: str) -> str:
    """Return the translated version of *text* for the active locale."""
    return _translation.gettext(text)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Return the singular or plural form of a translated string."""
    return _translation.ngettext(singular, plural, n)


# Auto-detect locale when the module is first imported.
set_language()
