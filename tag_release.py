#!/usr/bin/env python3
"""Release tagger for IReal Studio.

Usage::

    uv run python tag_release.py

The script:
1. Checks that there are no uncommitted or untracked changes.
2. Asks for a version number in ``x.x.x`` format (the ``v`` prefix is added
   automatically).
3. Validates the format.
4. Checks the tag does not already exist.
5. Checks the new version is strictly higher than the last tag.
6. Collects a multiline changelog entry (press Enter twice quickly to finish).
7. Writes ``news.md`` (current release) and updates ``changelog.md`` (history).
8. Updates ``version.py`` with the new version number.
9. Commits ``news.md``, ``changelog.md``, and ``version.py``.
10. Creates and pushes the git tag.
"""

import sys
import re
import time
from datetime import date
from pathlib import Path

import git


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

    ``version_tag`` should be the normalised tag without a leading ``v``,
    e.g. ``'1.2.3'``.
    """
    ver_str = version_tag.removeprefix('v').removeprefix('V')
    version_path = Path('version.py')
    version_path.write_text(
        '"""Single source of truth for the application version.\n\n'
        'The release workflow and autoupdater both read this module.\n'
        '"""\n\n'
        f'VERSION = "{ver_str}"\n',
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


def main() -> None:
    repo = git.Repo('.')
    _check_clean_tree(repo)

    # Ask for version (user does NOT need to type the 'v' prefix)
    while True:
        raw = input("Enter version (e.g. 1.0.0): ").strip()
        if not raw:
            print("Cancelled.")
            sys.exit(0)
        parsed = _parse_version(raw)
        if parsed is None:
            print(f"  Invalid format '{raw}'. Use x.y.z (e.g. 1.2.3).")
            continue
        # Always normalise to lowercase 'v' prefix
        version_tag = 'v{}.{}.{}'.format(*parsed)
        break

    existing_tags = _get_existing_tags(repo)

    # Check tag doesn't already exist
    if version_tag in existing_tags:
        print(f"ERROR: Tag '{version_tag}' already exists.")
        sys.exit(1)

    # Check version is higher than the last tag
    last = _last_version_tag(existing_tags)
    if parsed <= last:
        last_str = 'v{}.{}.{}'.format(*last)
        print(
            f"ERROR: Version {version_tag} is not higher than the last tag {last_str}."
        )
        sys.exit(1)

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
    main()
