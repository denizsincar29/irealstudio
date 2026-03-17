## v0.2.0 - 2026-03-17

- Repeat workflow: `[` + `]` creates normal repeats; `V` adds optional volta endings.
- Added transpose dialog (`Ctrl+T`) for selection or full song/key.
- Added per-device MIDI latency compensation persistence/restoration.
- Clarified section mark label to "Fine (end mark)".
- Added/fixed Russian translations for new UI and updater strings.
- Fixed minor-11 chord recognition (`Cm11`, `Cm7(11)`) and prevented minor chords with 11th from being misread as sus4.
- Fixed copy/cut from selected ranges so multi-chord selections are copied/cut correctly (not only the last chord).
- Fixed record/play menu behavior so `R` / `Space` stop active recording/pre-count instead of reporting "Already active".
- Startup now restores the last opened project file from settings; if no last project is available, the New Project dialog opens immediately.
