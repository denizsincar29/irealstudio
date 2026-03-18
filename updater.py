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
import webbrowser
from pathlib import Path
from typing import Callable

from version import VERSION
from i18n import _

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
_RELEASE_NOTES_PREVIEW_CHARS = 2000


def _news_md_path() -> Path:
    """Return the best-effort path to ``news.md`` for this runtime."""
    candidates = [
        Path(sys.executable).resolve().parent / 'news.md',
        Path(__file__).resolve().parent / 'news.md',
        Path.cwd() / 'news.md',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    _logger.warning("Release notes file not found in expected locations: %s", candidates)
    return candidates[0]


def open_release_notes_from_news() -> bool:
    """Render ``news.md`` to HTML and open it in the default browser.

    Returns ``True`` when a browser open was attempted successfully, otherwise
    ``False`` (missing file, markdown conversion failure, or browser failure).
    """
    news_path = _news_md_path()
    if not news_path.exists():
        _logger.warning("Release notes file not found: %s", news_path)
        return False
    try:
        import markdown  # uv dependency: Markdown

        # Best-effort cleanup of stale release-notes temp files from previous runs.
        for stale in Path(tempfile.gettempdir()).glob('*-irealstudio-release-notes.html'):
            try:
                stale.unlink()
            except OSError:
                pass

        md_text = news_path.read_text(encoding='utf-8')
        body_html = markdown.markdown(md_text)
        html_text = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>IReal Studio Release Notes</title>"
            "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;"
            "margin:2rem auto;padding:0 1rem;line-height:1.6}"
            "h1,h2,h3{line-height:1.3}pre{background:#f5f5f5;padding:0.75rem;"
            "overflow:auto;border-radius:4px}code{background:#f5f5f5;padding:0.1rem 0.25rem;"
            "border-radius:3px}</style></head><body>"
            f"{body_html}</body></html>"
        )
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='-irealstudio-release-notes.html',
            delete=False, encoding='utf-8',
        ) as f:
            f.write(html_text)
            html_path = Path(f.name)
        opened = webbrowser.open(html_path.as_uri())
        if not opened:
            _logger.warning("Browser reported failure opening release notes: %s", html_path)
            return False
        _logger.info("Release notes opened in browser: %s", html_path)
        return True
    except Exception as exc:
        _logger.warning("Could not open release notes: %s", exc)
        return False


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
        _logger.warning("No platform asset found in release.")
        return None

    download_url = asset['browser_download_url']
    asset_name = asset['name']
    total_size: int = asset.get('size', 0)

    tmp_dir = Path(tempfile.mkdtemp(prefix='irealstudio_update_'))
    dest = tmp_dir / asset_name
    _logger.info("Downloading update asset '%s' (%d bytes) to %s", asset_name, total_size, dest)
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

    _logger.info("Download complete: %d bytes written to %s", downloaded, dest)
    return dest


def _safe_extract_zip(zf: zipfile.ZipFile, extract_dir: Path) -> None:
    """Extract *zf* into *extract_dir*, rejecting path-traversal entries.

    Raises :class:`ValueError` if any member would be extracted outside
    *extract_dir*, has an absolute path, or points to a device file.
    """
    resolved_root = extract_dir.resolve()
    for member in zf.infolist():
        # Reject absolute paths and entries with any path-traversal component.
        if os.path.isabs(member.filename) or '..' in Path(member.filename).parts:
            raise ValueError(f"Unsafe zip entry rejected: {member.filename}")
        dest = (extract_dir / member.filename).resolve()
        try:
            dest.relative_to(resolved_root)
        except ValueError:
            raise ValueError(f"Unsafe zip entry rejected: {member.filename}")
        zf.extract(member, path=extract_dir)


def _safe_extract_tar(tf: tarfile.TarFile, extract_dir: Path) -> None:
    """Extract *tf* into *extract_dir*, rejecting unsafe members.

    Raises :class:`ValueError` for path-traversal entries, absolute paths,
    symlinks pointing outside the extract directory, and device/block files.
    """
    resolved_root = extract_dir.resolve()
    for member in tf.getmembers():
        if member.issym() or member.islnk():
            raise ValueError(f"Symlink/hardlink in archive rejected: {member.name}")
        if member.isdev():
            raise ValueError(f"Device file in archive rejected: {member.name}")
        if os.path.isabs(member.name) or '..' in Path(member.name).parts:
            raise ValueError(f"Unsafe tar entry rejected: {member.name}")
        dest = (extract_dir / member.name).resolve()
        try:
            dest.relative_to(resolved_root)
        except ValueError:
            raise ValueError(f"Unsafe tar entry rejected: {member.name}")
    tf.extractall(extract_dir)  # All members validated above


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
        _logger.info("Extracting update asset '%s' to %s", name, extract_dir)

        if name.endswith('.zip'):
            with zipfile.ZipFile(asset_path, 'r') as zf:
                _safe_extract_zip(zf, extract_dir)
        elif name.endswith('.tar.gz') or name.endswith('.tgz'):
            with tarfile.open(asset_path, 'r:gz') as tf:
                _safe_extract_tar(tf, extract_dir)
        else:
            # Treat as a single executable (macOS onefile).
            _logger.info("Asset is a single executable; no extraction needed.")
            return asset_path

        # If the archive contained a single top-level directory, return that.
        contents = list(extract_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            _logger.info("Extraction complete; content directory: %s", contents[0])
            return contents[0]
        _logger.info("Extraction complete; content directory: %s", extract_dir)
        return extract_dir
    except Exception as exc:
        _logger.error("Update extraction failed: %s", exc)
        return None


def apply_update_and_restart(
    new_content_dir: Path,
    cleanup_dir: Path | None = None,
) -> None:
    """Replace the running installation with *new_content_dir* and restart.

    On **Windows**: cannot replace files that are in use, so a small
    batch script is written to a temp location, launched, and the app
    exits.  The script waits for the current process to exit, copies the new
    files over the installation directory, starts the application again, and
    deletes both the temp script and the temp download directory.  All steps
    are logged to ``irealstudio.log``.

    On **Linux / macOS**: new files are staged to a sibling directory first.
    If staging succeeds the old directory is backed up and the staging
    directory is renamed in its place (atomic on same filesystem).  On any
    error the backup is restored.  The process is then replaced via
    :func:`os.execv`.

    Parameters
    ----------
    new_content_dir:
        Directory (or file, for macOS onefile) containing the new build.
    cleanup_dir:
        Optional temp directory to remove after a successful apply (before
        exec on POSIX, or via the helper script on Windows).

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

    _logger.info(
        "Applying update: system=%s, src=%s, dst=%s",
        system, new_content_dir, current_dir,
    )

    if system == 'Windows':
        # Write a batch script that:
        #   1. Waits for this process to exit
        #   2. Copies the new files over the installation directory
        #   3. Starts the application
        #   4. Cleans up the temp download dir and itself
        import subprocess
        pid = os.getpid()

        # Use the system ANSI/OEM codepage so cmd.exe can read paths that
        # contain non-ASCII characters (e.g. from a user profile directory).
        # 'mbcs' resolves to the current Windows ANSI codepage at runtime.
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='_irealstudio_update.bat',
            delete=False, encoding='mbcs',
        ) as bat_file:
            bat_path = bat_file.name
            # Batch quoting: wrap paths in double quotes; no special escaping
            # needed for the characters that appear in typical Windows paths.
            src = str(new_content_dir)
            dst = str(current_dir)
            exe = str(current_exe)
            lines = [
                '@echo off\r\n',
                # Wait until the main process exits.
                f':waitloop\r\n',
                f'tasklist /FI "PID eq {pid}" 2>nul | find /I " {pid} " >nul\r\n',
                f'if not errorlevel 1 (\r\n',
                f'    timeout /t 1 /nobreak >nul\r\n',
                f'    goto waitloop\r\n',
                f')\r\n',
                # Brief pause after process exit to let file locks / AV scanners
                # release handles before robocopy starts.
                f'timeout /t 2 /nobreak >nul\r\n',
                # robocopy exit codes 0-7 indicate success (8+ = error).
                f'robocopy "{src}" "{dst}" /E /IS /IT /NFL /NDL /NJH /NJS /NC /NS >nul 2>&1\r\n',
                f'if %errorlevel% leq 7 (\r\n',
                f'    start "" "{exe}" "--releasenotes"\r\n',
            ]
            if cleanup_dir:
                # Only remove the temp download dir on a successful copy.
                lines.append(f'    rmdir /s /q "{cleanup_dir}"\r\n')
            lines += [
                f')\r\n',
                # Spawn a separate cmd process to delete the script file so
                # the running batch file can be removed while it is still active.
                f'start /b cmd /c del /f /q "%~f0"\r\n',
            ]
            bat_file.write(''.join(lines))

        _logger.info("Launching update helper script: %s", bat_path)
        subprocess.Popen(  # noqa: S603
            ['cmd', '/c', bat_path],
            creationflags=getattr(subprocess, 'DETACHED_PROCESS', 8)
            | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200),
            close_fds=True,
        )
        raise SystemExit(0)

    if system in ('Linux', 'Darwin'):
        if system == 'Darwin' and new_content_dir.is_file():
            # macOS onefile: replace the single binary in-place.
            import stat
            _logger.info("macOS onefile update: replacing %s", current_exe)
            orig_mode = current_exe.stat().st_mode
            shutil.copy2(new_content_dir, current_exe)
            current_exe.chmod(orig_mode | stat.S_IEXEC)
        else:
            # Stage new content into a sibling directory, then atomically swap
            # with the current installation directory.  Keep a backup of the
            # old directory for rollback.
            staging_dir = current_dir.parent / f'.{current_dir.name}.new'
            backup_dir = current_dir.parent / f'.{current_dir.name}.bak'

            _logger.info(
                "Staging update: %s -> %s (backup: %s)",
                new_content_dir, staging_dir, backup_dir,
            )

            # Remove stale staging/backup dirs from a previous aborted update.
            for _d in (staging_dir, backup_dir):
                if _d.exists():
                    shutil.rmtree(_d)

            # Copy new content to staging — any failure here leaves the
            # running installation untouched.
            shutil.copytree(new_content_dir, staging_dir)

            # Swap: back up the current dir then move staging into place.
            # Both rename calls operate within the same parent directory so
            # they are atomic on any POSIX filesystem.
            try:
                current_dir.rename(backup_dir)
                try:
                    staging_dir.rename(current_dir)
                except Exception:
                    # Move the backup back to restore the original state.
                    backup_dir.rename(current_dir)
                    raise
            except Exception:
                # Clean up staging dir if it was not moved.
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                _logger.error("Update staging/swap failed; installation restored.")
                raise

            # Success — remove the backup.
            shutil.rmtree(backup_dir, ignore_errors=True)
            _logger.info("Update staged successfully; restarting application.")

        # Clean up the temp download directory before exec.
        if cleanup_dir and cleanup_dir.exists():
            shutil.rmtree(cleanup_dir, ignore_errors=True)

        _logger.info("Restarting via os.execv: %s", current_exe)
        # Flush and close all log handlers so the restart entry reaches the
        # file before os.execv replaces the process image.
        logging.shutdown()
        restart_args = (
            [str(current_exe)]
            + [a for a in sys.argv[1:] if a != '--releasenotes']
            + ['--releasenotes']
        )
        os.execv(str(current_exe), restart_args)

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
            _logger.warning("Update check: could not reach GitHub.")
            if on_error:
                on_error(_("Could not reach GitHub to check for updates."))
            return
        tag = data.get('tag_name', '')
        if not tag:
            msg = data.get('message', _('GitHub API did not return a release tag.'))
            _logger.warning("Update check: unexpected response: %s", msg)
            if on_error:
                on_error(_("Update check failed: {msg}").format(msg=msg))
            return
        latest = _parse_version(tag)
        current = _current_version()
        if latest > current:
            _logger.info("Update available: %s (current: %s)", tag, VERSION)
            url = data.get('html_url', _RELEASES_PAGE)
            if on_update_found:
                on_update_found(tag, url, data)
        else:
            _logger.info("Already up to date (v%s).", VERSION)
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
            _("Could not reach GitHub. Please check your internet connection."),
            _("Update Check Failed"),
            wx.OK | wx.ICON_WARNING,
            parent_window,
        )
        return

    tag = data.get('tag_name', '')
    if not tag:
        api_msg = data.get('message', _('GitHub API did not return a release tag.'))
        wx.MessageBox(
            _("Update check failed: {msg}").format(msg=api_msg),
            _("Update Check Failed"),
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
            _("A new version is available: {tag}\n(current: v{current})\n\n")
            .format(tag=tag, current=VERSION)
        )
        if body:
            message += (
                body[:_RELEASE_NOTES_PREVIEW_CHARS]
                + ('…' if len(body) > _RELEASE_NOTES_PREVIEW_CHARS else '')
                + '\n\n'
            )

        can_auto_install_flag = can_auto_install(data)

        if can_auto_install_flag:
            message += _("Download and install the update now?")
        else:
            message += _("Open the releases page to download?")

        dlg = wx.MessageDialog(
            parent_window,
            message,
            _("Update Available"),
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            if can_auto_install_flag:
                run_download_and_install(parent_window, data)
            else:
                webbrowser.open(url)
        dlg.Destroy()
    else:
        if not silent_if_current:
            wx.MessageBox(
                _("You are running the latest version (v{version}).").format(version=VERSION),
                _("No Updates Found"),
                wx.OK | wx.ICON_INFORMATION,
                parent_window,
            )


def _run_download_and_install(parent_window, release_data: dict) -> None:
    """Download and install an update, showing a wx progress dialog.

    Called from the UI thread.  The download runs in a background thread while
    a progress dialog is displayed.  On completion the update is applied and
    the app restarts (or the user is informed of the failure).

    The temporary download directory is always cleaned up on failure; on
    success it is removed by :func:`apply_update_and_restart` (before exec on
    POSIX, or by the helper script on Windows).
    """
    import wx

    tag = release_data.get('tag_name', _('new version'))
    asset = _find_platform_asset(release_data.get('assets', []))
    total_size: int = asset.get('size', 0) if asset else 0

    progress = wx.ProgressDialog(
        _("Downloading Update"),
        _("Downloading {tag}...").format(tag=tag),
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
            err_msg = result['error'] or _('no asset found')
            _logger.error("Update download failed: %s", err_msg)
            wx.MessageBox(
                _("Download failed: {error}").format(error=err_msg),
                _("Update Failed"),
                wx.OK | wx.ICON_ERROR,
                parent_window,
            )
            return
        tmp_dir = asset_path.parent
        # Extract
        new_dir = extract_update(asset_path)
        if new_dir is None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            wx.MessageBox(
                _("Failed to extract the downloaded update."),
                _("Update Failed"),
                wx.OK | wx.ICON_ERROR,
                parent_window,
            )
            return
        # Notify the user that the update is about to be applied.
        wx.MessageBox(
            _("The update has been downloaded and will now be applied.\n"
              "The application will restart automatically."),
            _("Applying Update"),
            wx.OK | wx.ICON_INFORMATION,
            parent_window,
        )
        _logger.info("User acknowledged restart; applying update now.")
        # Apply and restart; pass tmp_dir so it is cleaned up after apply.
        try:
            apply_update_and_restart(new_dir, cleanup_dir=tmp_dir)
        except SystemExit:
            # On Windows, apply_update_and_restart raises SystemExit(0) after
            # launching the helper script.  Shut down the wx main loop cleanly
            # before letting SystemExit propagate so that all wx resources are
            # properly released and the helper script can overwrite the files.
            app = wx.GetApp()
            if app is not None:
                app.ExitMainLoop()
            raise
        except Exception as exc:
            _logger.error("Failed to apply update: %s", exc)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            wx.MessageBox(
                _("Failed to apply update: {error}").format(error=exc),
                _("Update Failed"),
                wx.OK | wx.ICON_ERROR,
                parent_window,
            )

    threading.Thread(target=_worker, daemon=True, name='updater-dl').start()


# ---------------------------------------------------------------------------
# Public convenience API (used by app_io and other callers)
# ---------------------------------------------------------------------------

def is_compiled() -> bool:
    """Return *True* when running inside a Nuitka-compiled binary."""
    return _IS_COMPILED


def can_auto_install(release_data: dict) -> bool:
    """Return *True* if the current platform has a downloadable asset in *release_data*."""
    return _IS_COMPILED and _find_platform_asset(release_data.get('assets', [])) is not None


def run_download_and_install(parent_window, release_data: dict) -> None:
    """Public entry point: download and install *release_data* with a progress dialog.

    Equivalent to the internal :func:`_run_download_and_install` but stable
    across refactors.  Safe to call from any module.
    """
    _run_download_and_install(parent_window, release_data)
