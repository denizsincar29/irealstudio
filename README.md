# IReal Studio

A blind-accessible chord progression recorder for musicians who use screen readers.
IReal Studio lets you build chord progressions with your MIDI keyboard, navigate them
by ear, and export them directly to [iReal Pro](https://irealpro.com/).

---

## Features

- **Screen-reader friendly** – every action is announced via your system's speech output
  (NVDA, JAWS, SAPI 5, macOS VoiceOver, etc.) through `accessible-output3`.
- **MIDI recording** – play chords on any MIDI keyboard; the app detects them in real
  time and appends them to your progression, beat by beat.
- **Metronome pre-count** – a 2-measure metronome count-in before recording starts keeps
  you in time.
- **Playback** – hear your progression spoken at the recorded BPM.
- **Full editing** – move the cursor chord by chord, beat by beat, or measure by measure;
  cut / copy / paste; undo / redo; insert or delete chords and structural marks.
- **Section marks** – label sections A, B, C, D, Verse, Intro with a single shortcut.
- **Volta / ending brackets** – mark 1st, 2nd, … endings.
- **Slash chords** – add a bass note to any chord (`/` + note letter).
- **iReal Pro export** – export to an HTML file that opens the progression in iReal Pro,
  or scan a QR code to import wirelessly.
- **Native menu bar** (Windows) – accessible via `Alt`; all features are reachable without
  the keyboard shortcut layer.
- **Localization** – English and Russian included. Additional languages can be added by
  contributing a `.po` file under `locales/<lang>/LC_MESSAGES/irealstudio.po`.
- **Auto-updater** – checks GitHub Releases on startup and notifies you when a new
  version is available.

---

## Requirements

- Python 3.13+
- Windows (primary target; the app also runs on Linux/macOS in terminal-only mode)
- A MIDI keyboard or other MIDI input device (optional; chords can also be inserted
  manually from the menu)

---

## Installation

### From source (recommended for development)

```bash
# Clone the repository
git clone https://github.com/denizsincar29/irealstudio.git
cd irealstudio

# Install dependencies with uv (https://github.com/astral-sh/uv)
uv sync

# Run
uv run main.py
```

### Pre-built executable (Windows)

Download the latest `.exe` from the
[Releases page](https://github.com/denizsincar29/irealstudio/releases/latest)
and run it directly – no Python installation required.

---

## Quick Start

1. Launch IReal Studio.
2. Press **Ctrl+N** to create a new project (enter title, composer, BPM, key, style).
3. Connect your MIDI keyboard.
4. Press **R** to start recording. You will hear a 2-measure metronome count-in.
5. Play chords – each chord is captured at the beat it is held.
6. Press **R** or **Escape** to stop recording.
7. Press **Space** to hear your progression played back.
8. Navigate with **Left / Right** and edit as needed.
9. Press **Ctrl+S** to save, or **Ctrl+E** to export to iReal Pro.

---

## Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| Left / Right | Move cursor one chord |
| Alt+Left / Alt+Right | Move cursor one beat |
| Ctrl+Left / Ctrl+Right | Move cursor one measure |
| Ctrl+Home / Ctrl+End | Go to beginning / end |
| Shift+Left / Shift+Right | Extend selection |

### Playback & Recording

| Key | Action |
|-----|--------|
| R | Start / stop recording |
| Space | Play / stop |
| Ctrl+Space | Stop and jump to last position |
| Escape | Stop recording or playback |

### Editing

| Key | Action |
|-----|--------|
| Delete / Backspace | Delete chord at cursor |
| Ctrl+Delete / Ctrl+Backspace | Delete structural mark at cursor |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+X / Ctrl+C / Ctrl+V | Cut / Copy / Paste |
| Ctrl+Return | Insert chord (dialog) |
| N | Toggle No Chord (N.C.) |

### Section Marks (Ctrl+Shift+letter)

| Key | Action |
|-----|--------|
| Ctrl+Shift+A/B/C/D | Section A / B / C / D |
| Ctrl+Shift+V | Verse |
| Ctrl+Shift+I | Intro |

### Other

| Key | Action |
|-----|--------|
| V | Add volta / ending bracket |
| / + (A–G) | Add bass note (slash chord) |
| P | Speak full position |
| Ctrl+N | New project |
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+E | Export to iReal Pro |
| Ctrl+Shift+E | Show QR code |
| Ctrl+L | Speak recent log entries |
| F1 | Keyboard shortcuts |
| Ctrl+Q | Quit |

---

## File Format

IReal Studio saves progressions as `.ips` files (JSON).  
On Windows you can register the app as the default handler for `.ips` files via
**Open with** so that double-clicking a file opens it in IReal Studio.

---

## Localization

The active language is selected from **Settings → Language**.  
The choice is persisted across restarts.

To add a new language:

1. Copy `locales/ru/LC_MESSAGES/irealstudio.po` to
   `locales/<lang>/LC_MESSAGES/irealstudio.po`.
2. Translate all `msgstr` entries.
3. Compile with `msgfmt irealstudio.po -o irealstudio.mo`.
4. Add the language to `_LANGUAGES` in `main.py`.

Alternatively, the app auto-recompiles stale `.po` files on startup if
`msgfmt` is available on `PATH`.

---

## Building a Standalone Executable

The project uses [Nuitka](https://nuitka.net/) to produce a single-file Windows
executable:

```bash
uv run nuitka main.py
```

The resulting `.exe` is placed in the `dist/` folder.

---

## Running Tests

```bash
python test_ireal_export.py
```

---

## License

See the repository for license information.
