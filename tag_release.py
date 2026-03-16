#!/usr/bin/env python3
"""Release tagger for IReal Studio.

Usage::

    uv run python tag_release.py            # full release or draft, depending on branch

Behaviour is determined automatically from the current git branch:

* **main branch** – full interactive release.  If ``.release_draft.json``
  exists (written by a previous run on another branch), the draft is
  finalised immediately (tag + push) without prompts.  Otherwise the user
  is prompted for a version and changelog, the files are committed, the tag
  is created, and everything is pushed.

* **any other branch** – draft-only release.  The user is prompted for a
  version and changelog; ``news.md``, ``changelog.md``, ``version.py`` and
  ``.release_draft.json`` are committed, but NO tag or push happens.  Merge
  the branch into main and re-run to finalise.

Interactive full release steps:
1. Checks that there are no uncommitted or untracked changes.
2. Pulls the latest changes from origin.
3. Displays the last release tag and suggests next semver bumps (patch/minor/major).
4. Asks for a version number in ``x.x.x`` format (the ``v`` prefix is added
   automatically).
5. Validates the format.
6. Checks the tag does not already exist.
7. Checks the new version is strictly higher than the last tag.
8. Collects a multiline changelog entry (press Enter twice quickly to finish).
9. Writes ``news.md`` (current release) and updates ``changelog.md`` (history).
10. Updates ``version.py`` with the new version number.
11. Commits ``news.md``, ``changelog.md``, and ``version.py``.
12. Creates and pushes the git tag.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import git
import semver

# Temporary file used to hand off prepared release data to a main-branch run.
_DRAFT_FILE = Path('.release_draft.json')

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


def _write_news(version: str, changelog: str) -> None:
    today = date.today().isoformat()
    new_block = f"## {version} - {today}\n\n{changelog}\n"

    # news.md: current release only — overwritten each time so the CI workflow
    # can read the whole file as the release body without any parsing.
    news_path = Path('news.md')
    news_path.write_text(f"# {version} Release Notes\n\n{new_block}", encoding='utf-8')
    print(f"Wrote news.md for {version}")

    # changelog.md: cumulative history — prepend the new block.
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
    print(f"Updated changelog.md for {version}")


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


def _suggest_next_versions(last: semver.Version) -> dict[str, str]:
    """Return a dict of bump type → suggested version string."""
    return {
        'patch': str(last.bump_patch()),
        'minor': str(last.bump_minor()),
        'major': str(last.bump_major()),
    }


def _save_draft(version_tag: str, changelog: str) -> None:
    """Persist release data to *_DRAFT_FILE* so a main-branch run can read it later."""
    _DRAFT_FILE.write_text(
        json.dumps({'version': version_tag, 'changelog': changelog}, indent=2),
        encoding='utf-8',
    )
    print(f"Saved release draft to {_DRAFT_FILE}")


def _load_draft() -> tuple[str, str]:
    """Load the draft written by a non-main-branch run.  Exits with an error if missing."""
    if not _DRAFT_FILE.exists():
        print(
            f"ERROR: No release draft found ({_DRAFT_FILE}).\n"
            "Run tag_release.py on a non-main branch first."
        )
        sys.exit(1)
    data = json.loads(_DRAFT_FILE.read_text(encoding='utf-8'))
    return data['version'], data['changelog']


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


def main() -> None:
    """Entry point: behaviour is determined automatically from the current branch.

    * **main branch** – full release (interactive or finalise existing draft).
    * **any other branch** – draft-only (commit files; no tag or push).
    """
    repo = git.Repo('.')
    try:
        branch = repo.active_branch.name
    except TypeError:
        print("ERROR: HEAD is detached. Please check out a branch before releasing.")
        sys.exit(1)

    on_main = branch == 'main'

    # On main: if a draft from a previous branch run exists, finalise it now.
    if on_main and _DRAFT_FILE.exists():
        print(f"Found release draft ({_DRAFT_FILE}). Finalizing…")
        _check_clean_tree(repo)
        _pull_latest(repo)

        version_tag, _ = _load_draft()
        parsed = _parse_version(version_tag)

        existing_tags = _get_existing_tags(repo)
        if version_tag in existing_tags:
            print(f"ERROR: Tag '{version_tag}' already exists.")
            sys.exit(1)
        last = _last_version_tag(existing_tags)
        if parsed is not None and parsed <= last:
            print(f"ERROR: Version {version_tag} is not higher than the last tag v{last}.")
            sys.exit(1)

        repo.create_tag(version_tag, message=f'Release {version_tag}')
        print(f"Created tag {version_tag}")

        _DRAFT_FILE.unlink()
        repo.index.remove([str(_DRAFT_FILE)])
        repo.index.commit(f'chore: finalize release {version_tag}')
        print("Removed draft and committed.")

        print("Pushing commit and tag…")
        origin = repo.remotes.origin
        origin.push()
        origin.push(version_tag)
        print(f"Done! Release {version_tag} is on its way.")
        return

    # Interactive release preparation
    _check_clean_tree(repo)
    _pull_latest(repo)

    existing_tags = _get_existing_tags(repo)
    last = _last_version_tag(existing_tags)
    version_tag, _ = _prompt_version(existing_tags, last)

    changelog = _read_multiline_changelog()
    if not changelog.strip():
        print("ERROR: Changelog cannot be empty.")
        sys.exit(1)

    _write_news(version_tag, changelog)
    _update_version_py(version_tag)

    if on_main:
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
        # Draft only: commit files but no tag or push
        _save_draft(version_tag, changelog)
        repo.index.add(['news.md', 'changelog.md', 'version.py', str(_DRAFT_FILE)])
        repo.index.commit(f'chore: prepare release {version_tag}')
        print(f"Committed release draft for {version_tag}.")
        print(f"Note: not on main branch (current: {branch!r}). No tag or push.")
        print("Merge/switch to main and re-run to finalize.")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        print(
            f"ERROR: Unknown argument '{sys.argv[1]}'.\n"
            "This script takes no arguments; branch is detected automatically."
        )
        sys.exit(1)
    main()

