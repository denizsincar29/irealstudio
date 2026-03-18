# IReal Studio — Copilot Coding Agent Instructions

## What This Repository Does

IReal Studio is a **blind-accessible chord progression recorder** for musicians who use screen readers. It allows users to build chord progressions with a MIDI keyboard, navigate them by ear, and export them to [iReal Pro](https://irealpro.com/). Primary target is Windows with NVDA/JAWS; also runs on Linux/macOS.

## Project At a Glance

- **Language:** Python 3.13+ (type hints, dataclasses, `match` statements)
- **GUI:** wxPython 4.2+
- **Audio:** sounddevice (PortAudio), mido + python-rtmidi (MIDI)
- **Accessibility:** accessible-output3 (screen reader speech)
- **Packaging:** Nuitka standalone build (not onefile on Windows/Linux; onefile on macOS)
- **Dependency manager:** [uv](https://github.com/astral-sh/uv) — **always use `uv` instead of pip**

## Key Source Files

| File | Role |
|------|------|
| `chords.py` | Core data model: `ChordProgression`, `VoltaBracket`, `Position`, `Chord`, iReal URL export, navigation helpers |
| `main.py` | App core: `App` class, navigation, editing, undo/redo, display, entry point |
| `recorder.py` | Metronome loop, MIDI recording, playback loop, `Recorder`/`AppState` |
| `sound.py` | Audio output, `make_beep`, PortAudio scheduling |
| `midi_handler.py` | MIDI input/output, `MidiHandler` |
| `app_keys.py` | `KeysMixin` — all keyboard shortcuts |
| `app_menu.py` | `MenuMixin` — menu building + handlers |
| `app_io.py` | `IOMixin` — file I/O, export, QR code, dialogs |
| `app_settings.py` | Constants and settings file helpers |
| `commands.py` | Menu command IDs, recording mode constants |
| `dialogs.py` | All wx dialog classes (chord entry, project settings, etc.) |
| `i18n.py` | `_()`, `ngettext()`, `set_language()` wrappers |
| `tag_release.py` | Release tagging script (version bump → commit → tag → push) |
| `version.py` | Single source of truth: `VERSION = "x.y.z"` |
| `updater.py` | Auto-update checker (GitHub Releases API) |
| `locales/ru/LC_MESSAGES/irealstudio.po` | Russian translations (compile to `.mo` after editing) |

## Environment Setup

```bash
# Copilot setup usually installs uv automatically.
# Check first and only install when `uv` is missing.
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux/macOS
# Windows (PowerShell): if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { irm https://astral.sh/uv/install.ps1 | iex }
# Fallback: python -m pip install uv

# Install all dependencies (including dev)
uv sync

# Run the application (requires a display on Linux: set DISPLAY or use Xvfb)
uv run main.py
```

**Python version:** pinned in `.python-version` (currently 3.13). `uv sync` installs it automatically.

## Running Tests

```bash
# Run the full test suite (fast, ~0.03 s, no display needed)
python3 -m unittest tests.test_ireal_export -q

# Or via uv:
uv run python -m unittest tests.test_ireal_export -q
```

Tests live in `tests/test_ireal_export.py` and test only `chords.py` (no GUI, no audio). Always run tests after changes to `chords.py` or navigation logic.

## Linting

No dedicated linter is configured. The codebase uses standard Python style. Do not introduce external linters.

## Building

```bash
# Windows (produces irealstudio-windows/ standalone directory):
compile.bat

# Linux (produces irealstudio-linux/ standalone directory):
bash compile.sh

# macOS (produces irealstudio.bin onefile):
bash compile.sh   # detects platform automatically
```

Nuitka defaults are in `pyproject.toml` under `[tool.nuitka]`. Notable requirements:
- `--include-module=mido.backends.rtmidi` (dynamic string import, missed by static analysis)
- `accessible_output3` DLLs bundled via `--include-data-dir` resolved at build time
- `locales` directory must be included: `locales=locales`

CI builds are triggered on `v*` tag pushes via `.github/workflows/release.yml`.

## Releasing

Copilot **must only** edit `news.md`. **Do not** run `tag_release.py`. **Do not** edit `changelog.md` or `version.py`.

The user will run `tag_release.py` manually to finalize the release.

- `news.md` is used as the GitHub Release body by the CI workflow — keep it up to date with human-readable release notes (plain bullet points).

## Translations (Russian)

After editing `locales/ru/LC_MESSAGES/irealstudio.po`, recompile the binary:

```python
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
with open('locales/ru/LC_MESSAGES/irealstudio.po', 'rb') as f:
    catalog = read_po(f)
with open('locales/ru/LC_MESSAGES/irealstudio.mo', 'wb') as f:
    write_mo(f, catalog)
```

(`msgfmt` is not available in CI; use Babel instead.)

## Architecture Notes

- **Virtual measures:** Repeated bodies are "virtual" — not stored in `ChordProgression.items`. `resolve_virtual_measure(m)` maps a virtual bar to its primary counterpart. `is_in_virtual_range(m)` tests membership. Navigation inside virtual territory must resolve to primary before finding chords, then map back using `cursor.measure - primary_m` as the offset.
- **VoltaBracket:** `is_repeat_only()` → plain `{ }` repeat (no N1/N2 endings). `is_complete()` → has all required fields set. `hidden_range()` → `(ending1_end+1, ending2_start-1)`.
- **Position:** `(measure, beat, time_signature)`. Comparison is by `(measure, beat)`. `Position + 1` / `- 1` advance/retreat one beat, wrapping across measures.
- **Logging:** Writes to `irealstudio.log` in the working directory. Format: `%H:%M:%S level message`.
- **Settings:** Persisted as JSON in the platform app-data directory; loaded by `_load_app_settings()`.

## CI / GitHub Actions

- **`.github/workflows/release.yml`** — triggered by `v*` tags; builds Windows + Linux (+ optional macOS) with Nuitka; creates a GitHub Release using `news.md` as the body.
- No separate lint or test workflow exists; the test suite must be run locally.

Trust these instructions. Only search the codebase if information here is incomplete or appears incorrect.
