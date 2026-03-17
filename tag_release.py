#!/usr/bin/env python3
"""Release tagger for IReal Studio.

Usage::

    uv run python tag_release.py [VERSION]

Behaviour is determined automatically from the current git branch:

* **main branch** – full interactive release.  If ``version.py`` already
  contains a version higher than the last git tag (prepared by a previous run
  on another branch), the release is finalised immediately (tag + push)
  without prompts.  Otherwise the user is prompted for a version (or VERSION
  is taken from the argument), ``version.py`` and ``changelog.md`` are
  updated, and everything is pushed.

* **any other branch** – draft-only release.  The version is taken from the
  argument (or interactively), ``news.md``, ``changelog.md``, and
  ``version.py`` are updated on disk but **not committed**.  Commit them
  manually (or let the Copilot agent commit via its report_progress step),
  then merge the branch into main and re-run to finalise.

**Workflow for Copilot / automation:**

1. Write human-readable release notes in ``news.md`` (no version header needed).
2. Run ``uv run python tag_release.py 0.2.1`` on the feature branch.
3. The script:
   - Validates the version and checks it is strictly higher than the last tag.
   - Bumps ``version.py`` to the new version.
   - Prepends ``## v0.2.1 - <today>`` to ``news.md`` if that header is not
     already present (the file content is otherwise untouched).
   - Updates ``changelog.md`` by prepending the versioned ``news.md`` block.
   - Commits ``version.py``, ``news.md``, and ``changelog.md`` (on main; on
     other branches the files are updated but not committed automatically).
4. After merging to main, run ``uv run python tag_release.py`` (no argument).
   The script detects that ``version.py`` is ahead of the last git tag and
   immediately creates and pushes the release tag — no further prompts.

Interactive steps (no VERSION argument, non-main branch):
1. Checks that there are no uncommitted or untracked changes.
2. Pulls the latest changes from origin.
3. Displays the last release tag and suggests next semver bumps (patch/minor/major).
4. Asks for a version number in ``x.x.x`` format (the ``v`` prefix is added
   automatically).
5. Validates the format.
6. Checks the tag does not already exist.
7. Checks the new version is strictly higher than the last tag.
8. Reads ``news.md`` for the release body (must be non-empty).
9. Updates ``news.md``, ``changelog.md``, and ``version.py``.
10. Updates ``news.md``, ``changelog.md``, and ``version.py`` on disk.
"""

import sys
import time
from datetime import date
from pathlib import Path

import git
import semver

# Sentinel representing "no prior release found".
_ZERO_VERSION = semver.Version(0, 0, 0)


def _check_clean_tree(repo: git.Repo) -> None:
    if repo.is_dirty(untracked_files=True):
        print("ERROR: There are uncommitted or untracked changes. Please commit or stash them first.")
        print(repo.git.status('--porcelain'))
        sys.exit(1)


def _parse_version(raw: str) -> semver.Version | None:
    """Parse ``x.y.z`` or ``vx.y.z`` → :class:`semver.Version`; return ``None`` if invalid."""
    raw = raw.strip()
    try:
        return semver.Version.parse(raw[1:] if raw[:1].lower() == 'v' else raw)
    except ValueError:
        return None


def _get_existing_tags(repo: git.Repo) -> list[str]:
    tags = []
    for t in repo.tags:
        tag_str = str(t)
        if _parse_version(tag_str) is not None:
            tags.append(tag_str)
    return tags


def _last_version_tag(tags: list[str]) -> semver.Version:
    best = _ZERO_VERSION
    for tag in tags:
        parsed = _parse_version(tag)
        if parsed is not None and parsed > best:
            best = parsed
    return best


def _read_version_py() -> semver.Version | None:
    """Read the current version from ``version.py``.

    Returns *None* if the file does not exist or the VERSION line cannot be
    parsed.
    """
    version_path = Path('version.py')
    if not version_path.exists():
        return None
    text = version_path.read_text(encoding='utf-8')
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('VERSION'):
            _, _, rhs = line.partition('=')
            return _parse_version(rhs.strip().strip('"').strip("'"))
    return None


def _read_multiline_changelog() -> str:
    """Read multiline input; pressing Enter twice within 1 second ends input."""
    print("Enter changelog (press Enter twice quickly to finish):")
    lines: list[str] = []
    last_enter_time = 0.0
    while True:
        try:
            line = input()
        except EOFError:
            break
        now = time.time()
        if line == '' and (now - last_enter_time) < 1.0:
            break
        last_enter_time = now
        lines.append(line)
    # Strip trailing blank line if any
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def _update_version_py(version_tag: str) -> None:
    """Write the new version string into ``version.py``.

    ``version_tag`` may be prefixed with a lowercase or uppercase ``v``
    (e.g. ``'v1.2.3'`` or ``'1.2.3'``); the prefix is stripped automatically.
    Both ``VERSION`` and ``__version__`` are written so that all existing
    import patterns continue to work.
    """
    ver_str = version_tag.removeprefix('v').removeprefix('V')
    version_path = Path('version.py')
    version_path.write_text(
        '"""Single source of truth for the application version.\n\n'
        'The release workflow and autoupdater both read this module.\n'
        '"""\n\n'
        f'VERSION = "{ver_str}"\n'
        f'__version__ = VERSION\n',
        encoding='utf-8',
    )
    print(f"Updated version.py → VERSION = \"{ver_str}\"")


def _read_news_md() -> str:
    """Read ``news.md`` and return its content.

    Exits with an error if the file does not exist or is empty.
    """
    news_path = Path('news.md')
    if not news_path.exists():
        print("ERROR: news.md does not exist. Write release notes there first.")
        sys.exit(1)
    content = news_path.read_text(encoding='utf-8').strip()
    if not content:
        print("ERROR: news.md is empty. Write release notes there first.")
        sys.exit(1)
    return content


def _ensure_news_header(version_tag: str, content: str) -> str:
    """Ensure ``news.md`` starts with the correct ``## vX.Y.Z - DATE`` header.

    *content* is the already-read text of ``news.md`` (from :func:`_read_news_md`).

    * If the first non-empty line is any markdown heading (starts with ``#``),
      the heading must contain *version_tag*.  If it does, the file is left
      untouched.  If it contains a different version, the script exits with an
      error — the user must clear ``news.md`` or remove the existing header
      before running this script for a new version.
    * If no heading is present, ``## vX.Y.Z - DATE`` is prepended and the file
      is rewritten.

    Returns the (possibly updated) full content of ``news.md``.
    """
    first_line = next((ln for ln in content.splitlines() if ln.strip()), '')
    if first_line.startswith('#'):
        if version_tag in first_line:
            # Correct version header already present — leave news.md as-is
            return content
        print(
            f"ERROR: news.md already has a version header that does not match {version_tag}:\n"
            f"  {first_line}\n"
            "Clear news.md or remove the existing header before running this script."
        )
        sys.exit(1)
    today = date.today().isoformat()
    header = f'## {version_tag} - {today}'
    updated = f'{header}\n\n{content}'
    Path('news.md').write_text(updated, encoding='utf-8')
    print(f"Prepended version header to news.md")
    return updated


def _update_changelog(version_tag: str, news_content: str) -> None:
    """Prepend the versioned ``news.md`` block to ``changelog.md``.

    *news_content* is the (already-headed) full text of ``news.md``.
    The version+timestamp header is sourced from ``news.md`` itself so
    ``changelog.md`` never diverges from it.
    """
    # The block appended to changelog is the full news_content (stripped).
    new_block = news_content.strip() + '\n'

    changelog_path = Path('changelog.md')
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding='utf-8')
        if existing.startswith('# Changelog'):
            header, _, rest = existing.partition('\n')
            accumulated = header + '\n\n' + new_block + '\n' + rest.lstrip('\n')
        else:
            accumulated = '# Changelog\n\n' + new_block + '\n' + existing.lstrip('\n')
    else:
        accumulated = '# Changelog\n\n' + new_block
    changelog_path.write_text(accumulated, encoding='utf-8')
    print(f"Updated changelog.md for {version_tag}")


def _pull_latest(repo: git.Repo) -> None:
    """Pull the latest changes from origin for the current branch."""
    try:
        origin = repo.remotes.origin
        branch = repo.active_branch.name
        print(f"Pulling latest changes from origin/{branch}…")
        origin.pull(branch)
        print("Up to date.")
    except TypeError:
        # active_branch raises TypeError in detached-HEAD state; callers should
        # have already guarded against this, but be safe.
        print("ERROR: HEAD is detached. Please check out a branch before releasing.")
        sys.exit(1)
    except git.GitCommandError as exc:
        print(f"ERROR: git pull failed: {exc}")
        sys.exit(1)


def _resolve_version(
    existing_tags: list[str],
    last: semver.Version,
    version_arg: str | None,
) -> str:
    """Validate and return a ``vX.Y.Z`` version tag.

    Uses *version_arg* when provided; otherwise interactively prompts the user.
    Exits on invalid input, duplicate tag, or version not strictly higher than
    *last*.
    """
    if version_arg is not None:
        parsed = _parse_version(version_arg)
        if parsed is None:
            print(f"ERROR: Invalid version '{version_arg}'. Use x.y.z (e.g. 1.2.3).")
            sys.exit(1)
        version_tag = f'v{parsed}'
        if version_tag in existing_tags:
            print(f"ERROR: Tag '{version_tag}' already exists.")
            sys.exit(1)
        if parsed <= last:
            print(f"ERROR: Version {version_tag} is not higher than the last tag v{last}.")
            sys.exit(1)
        print(f"Using version {version_tag}")
        return version_tag
    version_tag, _ = _prompt_version(existing_tags, last)
    return version_tag


def _suggest_next_versions(last: semver.Version) -> dict[str, str]:
    """Return a dict of bump type → suggested version string."""
    return {
        'patch': str(last.bump_patch()),
        'minor': str(last.bump_minor()),
        'major': str(last.bump_major()),
    }


def _prompt_version(existing_tags: list[str], last: semver.Version) -> tuple[str, semver.Version]:
    """Interactively prompt for a valid, new-enough version.

    Returns ``(version_tag, parsed)`` where *version_tag* is normalised to
    lowercase ``v`` prefix.
    """
    last_str = f'v{last}' if last != _ZERO_VERSION else '(none)'
    suggestions = _suggest_next_versions(last)
    print(f"Last release: {last_str}")
    print(
        f"  Suggested bumps:  patch → {suggestions['patch']}"
        f"  |  minor → {suggestions['minor']}"
        f"  |  major → {suggestions['major']}"
    )
    while True:
        raw = input("Enter version (e.g. 1.0.0): ").strip()
        if not raw:
            print("Cancelled.")
            sys.exit(0)
        parsed = _parse_version(raw)
        if parsed is None:
            print(f"  Invalid format '{raw}'. Use x.y.z (e.g. 1.2.3).")
            continue
        version_tag = f'v{parsed}'
        if version_tag in existing_tags:
            print(f"ERROR: Tag '{version_tag}' already exists.")
            sys.exit(1)
        if parsed <= last:
            print(
                f"ERROR: Version {version_tag} is not higher than the last tag v{last}."
            )
            sys.exit(1)
        return version_tag, parsed


def _prepare_release_files(version_tag: str) -> None:
    """Update ``news.md``, ``changelog.md``, and ``version.py`` for *version_tag*.

    1. Reads the current content of ``news.md`` (which must be non-empty).
    2. Prepends ``## vX.Y.Z - DATE`` to ``news.md`` if that header is absent.
    3. Prepends the versioned block to ``changelog.md``.
    4. Writes the new version into ``version.py``.
    """
    news_content = _read_news_md()
    news_content = _ensure_news_header(version_tag, news_content)
    _update_changelog(version_tag, news_content)
    _update_version_py(version_tag)


def main(version_arg: str | None = None) -> None:
    """Entry point: behaviour is determined automatically from the current branch.

    * **main branch** – full release (interactive, or finalize if version.py is
      already ahead of the last tag).
    * **any other branch** – draft-only (update files on disk; no commit, tag, or push).

    Parameters
    ----------
    version_arg:
        Version string provided via CLI (e.g. ``"0.1.7"``).  Skips the
        interactive version prompt when supplied.  The changelog is always
        read from ``news.md``; there is no CLI argument for it.
    """
    repo = git.Repo('.')
    try:
        branch = repo.active_branch.name
    except TypeError:
        print("ERROR: HEAD is detached. Please check out a branch before releasing.")
        sys.exit(1)

    on_main = branch == 'main'

    _check_clean_tree(repo)
    _pull_latest(repo)

    existing_tags = _get_existing_tags(repo)
    last = _last_version_tag(existing_tags)

    if on_main:
        # On main: if version.py is already ahead of the last tag, a draft was
        # prepared on another branch.  Finalise it immediately without prompts.
        current_version = _read_version_py()
        if current_version is not None and current_version > last:
            version_tag = f'v{current_version}'
            print(
                f"Found version.py ({version_tag}) ahead of last tag (v{last}). "
                "Finalizing release…"
            )
            if version_tag in existing_tags:
                print(f"ERROR: Tag '{version_tag}' already exists.")
                sys.exit(1)

            repo.create_tag(version_tag, message=f'Release {version_tag}')
            print(f"Created tag {version_tag}")

            print("Pushing tag…")
            origin = repo.remotes.origin
            origin.push(version_tag)
            print(f"Done! Release {version_tag} is on its way.")
            return

        # No prepared draft: interactive/non-interactive release flow.
        version_tag = _resolve_version(existing_tags, last, version_arg)
        _prepare_release_files(version_tag)

        # Full release: commit, tag, push
        repo.index.add(['news.md', 'changelog.md', 'version.py'])
        repo.index.commit(f'chore: release {version_tag}')
        print(f"Committed release notes for {version_tag}")

        repo.create_tag(version_tag, message=f'Release {version_tag}')
        print(f"Created tag {version_tag}")

        print("Pushing commit and tag…")
        origin = repo.remotes.origin
        origin.push()
        origin.push(version_tag)
        print(f"Done! Release {version_tag} is on its way.")

    else:
        # Non-main branch: draft-only flow.
        version_tag = _resolve_version(existing_tags, last, version_arg)
        _prepare_release_files(version_tag)

        # Draft only: files are updated but NOT committed here.
        # Commit them manually (e.g. via `git add` + `git commit`) or let the
        # Copilot agent commit them via its report_progress step.
        print(f"Release draft prepared for {version_tag}.")
        print(f"  Updated: news.md, changelog.md, version.py")
        print(f"Note: not on main branch (current: {branch!r}). No commit, tag, or push.")
        print("Commit the changed files, merge to main, and re-run to finalize.")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Tag a release for IReal Studio.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Release notes are always read from news.md.\n'
            'Write your release notes there before running this script.\n\n'
            'Branch behaviour is detected automatically:\n'
            '  main branch   → full release (commit + tag + push)\n'
            '  other branch  → draft only (commit; no tag or push)\n'
        ),
    )
    parser.add_argument(
        'version',
        nargs='?',
        help='Version to release (e.g. 0.1.7).  Omit for interactive prompt.',
    )
    args = parser.parse_args()
    main(version_arg=args.version)

