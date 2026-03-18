## v0.2.1 - 2026-03-18

- Fixed Shift+Right / Shift+Left selection so it enters virtual (repeated) areas chord-by-chord instead of jumping past the entire virtual block in one press.
- New Project dialog now offers a template structure picker (Blues 12/16/24, AABA, ABAC, ABAB, ABCD) with per-section bar counts and optional Intro/Coda bars.
- Added `.ipst` template file format: save any progression as a reusable template via *File → Save as Template…* and reopen it via *File → Open Template*.  Bundled sample templates included (Blues 12, Minor Blues 12, AABA/ABAC/ABCD 32, Ballad AABA 32, Waltz AABA 32).
- Added Russian translations for all new UI strings.

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
