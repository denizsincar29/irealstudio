"""Autoupdater for IReal Studio.

Checks the GitHub Releases API for a newer version and can automatically
download, extract and apply the update, then restart the application.
Works with both source installs and Nuitka-compiled executables; auto-install
is only available in compiled mode.

Usage (startup background check)::

    from updater import check_for_updates_async
    check_for_updates_async(on_update_found=my_callback)

Usage (manual / menu "Check for Updates")::

    from updater import check_for_updates_sync
    check_for_updates_sync(parent_window=frame, silent_if_current=False)
"""

from __future__ import annotations

import os
import sys
import shutil
import platform
import tempfile
import threading
import urllib.request
import urllib.error
import json
import logging
import zipfile
import tarfile
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Platform-specific asset helpers
# ---------------------------------------------------------------------------

def _get_platform_asset_name() -> str | None:
    """Return the expected release asset filename for the current platform."""
    system = platform.system()
    if system == 'Windows':
        return 'irealstudio-windows.zip'
    if system == 'Linux':
        return 'irealstudio-linux.tar.gz'
    if system == 'Darwin':
        return 'irealstudio-macos'
    return None


def _find_platform_asset(assets: list[dict]) -> dict | None:
    """Return the release asset dict matching the current platform, or None."""
    name = _get_platform_asset_name()
    if name is None:
        return None
    for asset in assets:
        if asset.get('name') == name:
            return asset
    return None


# ---------------------------------------------------------------------------
# Download / extract / apply helpers
# ---------------------------------------------------------------------------

def download_update(
    release_data: dict,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path | None:
    """Download the platform-specific release asset to a temporary directory.

    Parameters
    ----------
    release_data:
        The parsed JSON dict from :func:`fetch_latest_release`.
    progress_callback:
        Optional ``(downloaded_bytes, total_bytes)`` callback; called
        periodically during the download.  *total_bytes* may be 0 if the
        server does not send a Content-Length.

    Returns
    -------
    Path to the downloaded file, or *None* if no matching asset was found or
    the download failed.
    """
    asset = _find_platform_asset(release_data.get('assets', []))
    if asset is None:
        _logger.debug("No platform asset found in release.")
        return None

    download_url = asset['browser_download_url']
    asset_name = asset['name']
    total_size: int = asset.get('size', 0)

    tmp_dir = Path(tempfile.mkdtemp(prefix='irealstudio_update_'))
    dest = tmp_dir / asset_name
    try:
        req = urllib.request.Request(
            download_url,
            headers={'User-Agent': f'irealstudio/{VERSION}'},
        )
        downloaded = 0
        with urllib.request.urlopen(req, timeout=120) as resp, dest.open('wb') as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)
    except Exception as exc:
        _logger.error("Update download failed: %s", exc)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

    return dest


def extract_update(asset_path: Path) -> Path | None:
    """Extract a downloaded release asset and return the content directory.

    For archive formats (zip / tar.gz) the function extracts the archive
    and returns the single top-level directory inside it.  For a plain
    executable (macOS onefile) the file itself is returned.

    Returns *None* on failure.
    """
    try:
        name = asset_path.name
        extract_dir = asset_path.parent / 'extracted'
        extract_dir.mkdir(exist_ok=True)

        if name.endswith('.zip'):
            with zipfile.ZipFile(asset_path, 'r') as zf:
                zf.extractall(extract_dir)
        elif name.endswith('.tar.gz') or name.endswith('.tgz'):
            with tarfile.open(asset_path, 'r:gz') as tf:
                tf.extractall(extract_dir)
        else:
            # Treat as a single executable (macOS onefile).
            return asset_path

        # If the archive contained a single top-level directory, return that.
        contents = list(extract_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            return contents[0]
        return extract_dir
    except Exception as exc:
        _logger.error("Update extraction failed: %s", exc)
        return None


def apply_update_and_restart(new_content_dir: Path) -> None:
    """Replace the running installation with *new_content_dir* and restart.

    On **Windows**: cannot replace files that are in use, so a small batch
    script is written to a temp location, launched, and the app exits.  The
    script waits a few seconds, copies the new files over the installation
    directory, starts the application again, and deletes itself.

    On **Linux / macOS**: files are copied in-place and the process is
    replaced via :func:`os.execv`.

    This function only works when ``_IS_COMPILED`` is *True*.  Raises
    :class:`RuntimeError` otherwise.

    .. note::
        On Windows this function raises :class:`SystemExit` to let the
        caller exit the application so the batch script can run.
    """
    if not _IS_COMPILED:
        raise RuntimeError(
            "apply_update_and_restart is only supported in compiled mode."
        )

    current_exe = Path(sys.executable)
    current_dir = current_exe.parent
    system = platform.system()

    if system == 'Windows':
        # Build a batch script that waits for the process to exit, copies the
        # new files over, restarts the application, then deletes itself.
        import subprocess
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='_irealstudio_update.bat',
            delete=False, encoding='ascii',
        ) as bat_file:
            bat_path = bat_file.name
            bat_file.write(
                '@echo off\r\n'
                'timeout /t 3 /nobreak > nul\r\n'
                f'robocopy "{new_content_dir}" "{current_dir}"'
                ' /E /IS /IT /NFL /NDL /NJH /NJS /NC /NS\r\n'
                f'start "" "{current_exe}"\r\n'
                'del "%~f0"\r\n'
            )
        subprocess.Popen(  # noqa: S603
            ['cmd', '/c', bat_path],
            creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0),
            close_fds=True,
        )
        raise SystemExit(0)

    if system in ('Linux', 'Darwin'):
        if system == 'Darwin' and new_content_dir.is_file():
            # macOS onefile: replace the single binary.
            import stat
            # Capture original permissions before overwriting.
            orig_mode = current_exe.stat().st_mode
            shutil.copy2(new_content_dir, current_exe)
            current_exe.chmod(orig_mode | stat.S_IEXEC)
        else:
            # Copy new files over the current installation directory.
            for item in new_content_dir.iterdir():
                dst = current_dir / item.name
                if item.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
        os.execv(str(current_exe), [str(current_exe)] + sys.argv[1:])

    raise RuntimeError(f"Unsupported platform for auto-update: {system}")


# ---------------------------------------------------------------------------
# Async / sync public API
# ---------------------------------------------------------------------------

def check_for_updates_async(
    on_update_found: Callable[[str, str, dict], None] | None = None,
    on_up_to_date: Callable[[], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
    """Start a daemon thread to check for updates without blocking the UI.

    Parameters
    ----------
    on_update_found:
        Called with ``(latest_tag, release_url, release_data)`` when a newer
        version is available.  The callback is invoked from the background
        thread; use ``wx.CallAfter`` inside the callback to update the UI.
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
                on_update_found(tag, url, data)
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

    When a newer version is available and the app is running in compiled mode,
    the user is offered the choice to download and install the update
    automatically.  In source mode, a browser link is opened instead.

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

        can_auto_install = _IS_COMPILED and _find_platform_asset(
            data.get('assets', [])
        ) is not None

        if can_auto_install:
            message += "Download and install the update now?"
        else:
            message += "Open the releases page to download?"

        dlg = wx.MessageDialog(
            parent_window,
            message,
            "Update Available",
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            if can_auto_install:
                _run_download_and_install(parent_window, data)
            else:
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


def _run_download_and_install(parent_window, release_data: dict) -> None:
    """Download and install an update, showing a wx progress dialog.

    Called from the UI thread.  The download runs in a background thread while
    a progress dialog is displayed.  On completion the update is applied and
    the app restarts (or the user is informed of the failure).
    """
    import wx

    tag = release_data.get('tag_name', 'new version')
    asset = _find_platform_asset(release_data.get('assets', []))
    total_size: int = asset.get('size', 0) if asset else 0

    progress = wx.ProgressDialog(
        "Downloading Update",
        f"Downloading {tag}…",
        maximum=max(total_size, 1),
        parent=parent_window,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME,
    )

    result: dict = {'asset_path': None, 'error': None}

    def _on_progress(downloaded: int, total: int) -> None:
        nonlocal total_size
        if total > 0 and total != total_size:
            total_size = total
            wx.CallAfter(progress.SetRange, total_size)
        wx.CallAfter(progress.Update, min(downloaded, max(total_size, 1)))

    def _worker() -> None:
        try:
            path = download_update(release_data, progress_callback=_on_progress)
            result['asset_path'] = path
        except Exception as exc:
            result['error'] = str(exc)
        finally:
            wx.CallAfter(_on_download_done)

    def _on_download_done() -> None:
        progress.Destroy()
        asset_path: Path | None = result['asset_path']
        if result['error'] or asset_path is None:
            wx.MessageBox(
                f"Download failed: {result['error'] or 'no asset found'}",
                "Update Failed",
                wx.OK | wx.ICON_ERROR,
                parent_window,
            )
            return
        # Extract
        new_dir = extract_update(asset_path)
        if new_dir is None:
            wx.MessageBox(
                "Failed to extract the downloaded update.",
                "Update Failed",
                wx.OK | wx.ICON_ERROR,
                parent_window,
            )
            return
        # Apply and restart
        try:
            apply_update_and_restart(new_dir)
        except SystemExit:
            raise
        except Exception as exc:
            wx.MessageBox(
                f"Failed to apply update: {exc}",
                "Update Failed",
                wx.OK | wx.ICON_ERROR,
                parent_window,
            )

    threading.Thread(target=_worker, daemon=True, name='updater-dl').start()
