"""Autoupdater for IReal Studio.

Checks the GitHub Releases API for a newer version and notifies the user.
Works with both source installs and Nuitka-compiled executables.

Usage (startup background check)::

    from updater import check_for_updates_async
    check_for_updates_async(on_update_found=my_callback)

Usage (manual / menu "Check for Updates")::

    from updater import check_for_updates_sync
    check_for_updates_sync(parent_window=frame, silent_if_current=False)
"""

from __future__ import annotations

import threading
import urllib.request
import urllib.error
import json
import logging
from typing import Callable

from version import VERSION

# True when running inside a Nuitka-compiled binary, False when running from source.
try:
    _IS_COMPILED: bool = bool(__compiled__)  # injected by Nuitka at compile time  # noqa: F821
except NameError:
    _IS_COMPILED = False

_logger = logging.getLogger('irealstudio')

_GITHUB_API_URL = (
    'https://api.github.com/repos/denizsincar29/irealstudio/releases/latest'
)
_RELEASES_PAGE = 'https://github.com/denizsincar29/irealstudio/releases/latest'


def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse a version tag like ``v1.2.3`` or ``1.2.3`` into a tuple of ints."""
    tag = tag.lstrip('vV')
    try:
        return tuple(int(x) for x in tag.split('.'))
    except ValueError:
        return (0,)


def _current_version() -> tuple[int, ...]:
    return _parse_version(VERSION)


def fetch_latest_release() -> dict | None:
    """Fetch the latest release info from GitHub.

    Returns the parsed JSON dict on success, or *None* on any error.
    """
    try:
        req = urllib.request.Request(
            _GITHUB_API_URL,
            headers={
                'User-Agent': f'irealstudio/{VERSION}',
                'Accept': 'application/vnd.github+json',
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        _logger.debug("Update check failed: %s", exc)
        return None


def check_for_updates_async(
    on_update_found: Callable[[str, str], None] | None = None,
    on_up_to_date: Callable[[], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
    """Start a daemon thread to check for updates without blocking the UI.

    Parameters
    ----------
    on_update_found:
        Called with ``(latest_tag, release_url)`` when a newer version is
        available.  The callback is invoked from the background thread; use
        ``wx.CallAfter`` inside the callback to update the UI.
    on_up_to_date:
        Called (no arguments) when the current version is already the latest.
    on_error:
        Called with an error message string if the check fails.
    """
    def _worker() -> None:
        data = fetch_latest_release()
        if data is None:
            if on_error:
                on_error("Could not reach GitHub to check for updates.")
            return
        tag = data.get('tag_name', '')
        if not tag:
            msg = data.get('message', 'GitHub API did not return a release tag.')
            _logger.debug("Update check: unexpected response: %s", msg)
            if on_error:
                on_error(f"Update check failed: {msg}")
            return
        latest = _parse_version(tag)
        current = _current_version()
        if latest > current:
            url = data.get('html_url', _RELEASES_PAGE)
            if on_update_found:
                on_update_found(tag, url)
        else:
            if on_up_to_date:
                on_up_to_date()

    t = threading.Thread(target=_worker, daemon=True, name='updater')
    t.start()


def check_for_updates_sync(
    parent_window=None,
    silent_if_current: bool = True,
) -> None:
    """Check for updates and show a wx dialog with the result.

    This function fetches the release info **synchronously** (blocking).
    Call it from the UI thread only after the user explicitly requests a check
    (e.g. via the "Check for Updates" menu item).

    Parameters
    ----------
    parent_window:
        The wx.Window to use as the dialog parent (may be None).
    silent_if_current:
        When *True* (default), no dialog is shown if the app is already
        up-to-date.  Set to *False* to always show a result dialog.
    """
    import wx
    import webbrowser

    data = fetch_latest_release()
    if data is None:
        wx.MessageBox(
            "Could not reach GitHub. Please check your internet connection.",
            "Update Check Failed",
            wx.OK | wx.ICON_WARNING,
            parent_window,
        )
        return

    tag = data.get('tag_name', '')
    if not tag:
        api_msg = data.get('message', 'GitHub API did not return a release tag.')
        wx.MessageBox(
            f"Update check failed: {api_msg}",
            "Update Check Failed",
            wx.OK | wx.ICON_WARNING,
            parent_window,
        )
        return
    latest = _parse_version(tag)
    current = _current_version()

    if latest > current:
        url = data.get('html_url', _RELEASES_PAGE)
        body = data.get('body', '').strip()
        message = (
            f"A new version is available: {tag}\n"
            f"(current: v{VERSION})\n\n"
        )
        if body:
            # Show at most 400 chars of release notes
            message += body[:400] + ('…' if len(body) > 400 else '') + '\n\n'
        message += "Open the releases page to download?"
        dlg = wx.MessageDialog(
            parent_window,
            message,
            "Update Available",
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            webbrowser.open(url)
        dlg.Destroy()
    else:
        if not silent_if_current:
            wx.MessageBox(
                f"You are running the latest version (v{VERSION}).",
                "No Updates Found",
                wx.OK | wx.ICON_INFORMATION,
                parent_window,
            )
