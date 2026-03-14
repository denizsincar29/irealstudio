#!/usr/bin/env python3
"""Release tagger for IReal Studio.

Usage::

    uv run python tag_release.py

The script:
1. Checks that there are no uncommitted changes.
2. Asks for a version number in ``Vx.x.x`` format.
3. Validates the format.
4. Checks the tag does not already exist.
5. Checks the new version is strictly higher than the last tag.
6. Collects a multiline changelog entry (press Enter twice quickly to finish).
7. Writes ``news.md`` with the version, date, and changelog.
8. Commits ``news.md``.
9. Creates and pushes the git tag.
"""

import subprocess
import sys
import re
import time
from datetime import date
from pathlib import Path


def _run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )


def _check_clean_tree() -> None:
    result = _run(['git', 'status', '--porcelain'])
    if result.returncode != 0:
        print("ERROR: Could not check git status.")
        sys.exit(1)
    if result.stdout.strip():
        print("ERROR: There are uncommitted changes. Please commit or stash them first.")
        print(result.stdout)
        sys.exit(1)


def _parse_version(tag: str) -> tuple[int, ...] | None:
    """Parse ``Vx.y.z`` → ``(x, y, z)``; return None if invalid."""
    m = re.fullmatch(r'[Vv](\d+)\.(\d+)\.(\d+)', tag.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _get_existing_tags() -> list[str]:
    result = _run(['git', 'tag', '--list', 'v*', '--sort=-version:refname'])
    if result.returncode != 0:
        return []
    return [t for t in result.stdout.splitlines() if t.strip()]


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


def _write_news(version: str, changelog: str) -> None:
    today = date.today().isoformat()
    new_block = f"## {version} - {today}\n\n{changelog}\n"
    news_path = Path('news.md')
    if news_path.exists():
        existing = news_path.read_text(encoding='utf-8')
        # Insert the new block after the top-level "# News" header if present,
        # otherwise simply prepend it.
        if existing.startswith('# News'):
            header, _, rest = existing.partition('\n')
            content = header + '\n\n' + new_block + '\n' + rest.lstrip('\n')
        else:
            content = '# News\n\n' + new_block + '\n' + existing.lstrip('\n')
    else:
        content = '# News\n\n' + new_block
    news_path.write_text(content, encoding='utf-8')
    print(f"Wrote news.md for {version}")


def main() -> None:
    _check_clean_tree()

    # Ask for version
    while True:
        raw = input("Enter version (e.g. v1.0.0): ").strip()
        if not raw:
            print("Cancelled.")
            sys.exit(0)
        parsed = _parse_version(raw)
        if parsed is None:
            print(f"  Invalid format '{raw}'. Use Vx.y.z (e.g. v1.2.3).")
            continue
        # Normalise to lowercase 'v'
        version_tag = 'v{}.{}.{}'.format(*parsed)
        break

    existing_tags = _get_existing_tags()

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

    # Commit news.md
    _run(['git', 'add', 'news.md'], capture=False)
    result = _run(['git', 'commit', '-m', f'chore: release {version_tag}'])
    if result.returncode != 0:
        print("ERROR: git commit failed.")
        print(result.stderr)
        sys.exit(1)
    print(f"Committed news.md for {version_tag}")

    # Create annotated tag
    result = _run(['git', 'tag', '-a', version_tag, '-m', f'Release {version_tag}'])
    if result.returncode != 0:
        print("ERROR: git tag failed.")
        print(result.stderr)
        sys.exit(1)
    print(f"Created tag {version_tag}")

    # Push commit and tag
    print("Pushing commit and tag…")
    _run(['git', 'push'], capture=False)
    _run(['git', 'push', 'origin', version_tag], capture=False)
    print(f"Done! Release {version_tag} is on its way.")


if __name__ == '__main__':
    main()
