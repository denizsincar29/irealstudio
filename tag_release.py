#!/usr/bin/env python3
"""Release tagger for IReal Studio.

Usage::

    uv run python tag_release.py            # interactive full release
    uv run python tag_release.py prepare    # agent: prepare draft (no tag/push)
    uv run python tag_release.py auto       # human: finalize draft (tag + push)

Interactive full release:
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

``prepare`` mode (for automated agents / Copilot):
  Same steps 1–10 as above, then saves ``.release_draft.json`` with the
  version and changelog, and commits all four files.  Does NOT create a
  git tag or push anything.  Run ``auto`` afterwards to finalize.

``auto`` mode (for the human, after the agent ran ``prepare``):
  1. Checks clean working tree and pulls latest.
  2. Reads ``.release_draft.json`` written by ``prepare``.
  3. Creates an annotated git tag from the stored version.
  4. Deletes ``.release_draft.json`` and commits the removal.
  5. Pushes the commit and the tag.
"""

import json
import sys
import re
import time
from datetime import date
from pathlib import Path

import git

# Temporary file used to hand off prepared release data from ``prepare`` to ``auto``.
_DRAFT_FILE = Path('.release_draft.json')


def _check_clean_tree(repo: git.Repo) -> None:
    if repo.is_dirty(untracked_files=True):
        print("ERROR: There are uncommitted or untracked changes. Please commit or stash them first.")
        print(repo.git.status('--porcelain'))
        sys.exit(1)


def _parse_version(raw: str) -> tuple[int, ...] | None:
    """Parse ``x.y.z`` or ``vx.y.z`` → ``(x, y, z)``; return None if invalid."""
    m = re.fullmatch(r'[Vv]?(\d+)\.(\d+)\.(\d+)', raw.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _get_existing_tags(repo: git.Repo) -> list[str]:
    tags = []
    for t in repo.tags:
        tag_str = str(t)
        if re.match(r'v\d+\.\d+\.\d+$', tag_str):
            tags.append(tag_str)
    return tags


def _last_version_tag(tags: list[str]) -> tuple[int, ...]:
    best: tuple[int, ...] = (0, 0, 0)
    for tag in tags:
        parsed = _parse_version(tag)
        if parsed and parsed > best:
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
    except git.GitCommandError as exc:
        print(f"ERROR: git pull failed: {exc}")
        sys.exit(1)


def _suggest_next_versions(last: tuple[int, ...]) -> dict[str, str]:
    """Return a dict of bump type → suggested version string."""
    major, minor, patch = last
    return {
        'patch': f'{major}.{minor}.{patch + 1}',
        'minor': f'{major}.{minor + 1}.0',
        'major': f'{major + 1}.0.0',
    }


def _save_draft(version_tag: str, changelog: str) -> None:
    """Persist release data to *_DRAFT_FILE* so ``auto`` can read it later."""
    _DRAFT_FILE.write_text(
        json.dumps({'version': version_tag, 'changelog': changelog}, indent=2),
        encoding='utf-8',
    )
    print(f"Saved release draft to {_DRAFT_FILE}")


def _load_draft() -> tuple[str, str]:
    """Load the draft written by ``prepare``.  Exits with an error if missing."""
    if not _DRAFT_FILE.exists():
        print(
            f"ERROR: No release draft found ({_DRAFT_FILE}).\n"
            "Run 'uv run tag_release.py prepare' first."
        )
        sys.exit(1)
    data = json.loads(_DRAFT_FILE.read_text(encoding='utf-8'))
    return data['version'], data['changelog']


def _prompt_version(existing_tags: list[str], last: tuple[int, ...]) -> tuple[str, tuple[int, ...]]:
    """Interactively prompt for a valid, new-enough version.

    Returns ``(version_tag, parsed)`` where *version_tag* is normalised to
    lowercase ``v`` prefix.
    """
    last_str = 'v{}.{}.{}'.format(*last) if last != (0, 0, 0) else '(none)'
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
        version_tag = 'v{}.{}.{}'.format(*parsed)
        if version_tag in existing_tags:
            print(f"ERROR: Tag '{version_tag}' already exists.")
            sys.exit(1)
        if parsed <= last:
            print(
                f"ERROR: Version {version_tag} is not higher than the last tag "
                f"{'v{}.{}.{}'.format(*last)}."
            )
            sys.exit(1)
        return version_tag, parsed


def prepare() -> None:
    """Prepare a release draft (agent / Copilot mode).

    Writes release files and a draft JSON, commits them, but does NOT tag or push.
    A human then runs ``auto`` to finalize.
    """
    repo = git.Repo('.')
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
    _save_draft(version_tag, changelog)

    repo.index.add(['news.md', 'changelog.md', 'version.py', str(_DRAFT_FILE)])
    repo.index.commit(f'chore: prepare release {version_tag}')
    print(f"Committed release draft for {version_tag}.")
    print("Run 'uv run tag_release.py auto' to tag and push.")


def auto() -> None:
    """Finalize a release prepared by ``prepare`` (human mode).

    Reads ``.release_draft.json`` written by ``prepare``, creates the annotated
    git tag, removes the draft file, and pushes everything to origin.
    """
    repo = git.Repo('.')
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
        print(
            f"ERROR: Version {version_tag} is not higher than the last tag "
            f"{'v{}.{}.{}'.format(*last)}."
        )
        sys.exit(1)

    # Create the annotated tag
    repo.create_tag(version_tag, message=f'Release {version_tag}')
    print(f"Created tag {version_tag}")

    # Remove the draft file and commit
    _DRAFT_FILE.unlink()
    repo.index.remove([str(_DRAFT_FILE)])
    repo.index.commit(f'chore: finalize release {version_tag}')
    print("Removed draft and committed.")

    # Push commit and tag
    print("Pushing commit and tag…")
    origin = repo.remotes.origin
    origin.push()
    origin.push(version_tag)
    print(f"Done! Release {version_tag} is on its way.")


def main() -> None:
    """Interactive full release (default when no subcommand is given)."""
    repo = git.Repo('.')
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

    # Commit news.md, changelog.md and version.py
    repo.index.add(['news.md', 'changelog.md', 'version.py'])
    repo.index.commit(f'chore: release {version_tag}')
    print(f"Committed release notes for {version_tag}")

    # Create annotated tag
    repo.create_tag(version_tag, message=f'Release {version_tag}')
    print(f"Created tag {version_tag}")

    # Push commit and tag
    print("Pushing commit and tag…")
    origin = repo.remotes.origin
    origin.push()
    origin.push(version_tag)
    print(f"Done! Release {version_tag} is on its way.")


if __name__ == '__main__':
    _COMMANDS = {'prepare': prepare, 'auto': auto}
    _cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if _cmd in _COMMANDS:
        _COMMANDS[_cmd]()
    elif _cmd is None:
        main()
    else:
        print(
            f"ERROR: Unknown command '{_cmd}'.\n"
            "Valid commands: prepare, auto (or no argument for interactive release)."
        )
        sys.exit(1)
