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


def set_language(lang: str | None = None) -> None:
    """Load the translation catalogue for *lang*.

    If *lang* is ``None`` the language is auto-detected from the environment
    variable ``IREALSTUDIO_LANG`` or the system locale.
    """
    global _translation

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
        return

    try:
        _translation = gettext.translation(
            _DOMAIN,
            localedir=str(_LOCALE_DIR),
            languages=[lang],
        )
        _logger.info("Loaded '%s' translation from %s", lang, _LOCALE_DIR)
    except FileNotFoundError:
        _logger.debug(
            "No '%s' translation found in %s; using English", lang, _LOCALE_DIR
        )
        _translation = gettext.NullTranslations()


def _(text: str) -> str:
    """Return the translated version of *text* for the active locale."""
    return _translation.gettext(text)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Return the singular or plural form of a translated string."""
    return _translation.ngettext(singular, plural, n)


# Auto-detect locale when the module is first imported.
set_language()
