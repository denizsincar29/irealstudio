## v0.2.0 - 2026-03-18

New Features & Enhancements:

   Project Templates:
       The "New Project" dialog now includes a template structure picker (Blues 12/16/24, AABA, ABAC, ABAB, ABCD).
       Customize templates with per-section bar counts and optional Intro/Coda bars.
       Introducing the .ipst template file format: save any progression as a reusable template via File → Save as Template… and open it with File → Open Template.
       Bundled sample templates are included (e.g., Blues 12, Minor Blues 12, AABA/ABAC/ABCD 32, Ballad AABA 32, Waltz AABA 32).
   Transpose Dialog: Added a new transpose dialog (Ctrl+T) to transpose selections or entire songs/keys.
   MIDI Latency Compensation: Per-device MIDI latency compensation settings are now saved and restored automatically.
   Startup Behavior: The application now automatically restores the last opened project file from settings on startup. If no previous project is found, the "New Project" dialog opens immediately.
   Repeat Workflow:
       Use [+] to create normal repeats.
       Use `V` to add optional volta endings.
   Section Mark Clarity: The section mark label has been clarified to "Fine (end mark)".

Fixes:

   Selection Behavior: Fixed Shift+Right / Shift+Left selection to enter virtual (repeated) areas chord-by-chord, instead of skipping the entire virtual block.
   Chord Recognition: Fixed minor-11 chord recognition (Cm11, Cm7(11)) and prevented minor chords with an 11th from being misread as sus4.
   Copy/Cut: Corrected copy/cut functionality for selected ranges, ensuring multi-chord selections are copied/cut correctly, not just the last chord.
   Record/Play Controls: Fixed record/play menu behavior so R / Space correctly stop active recording/pre-count instead of reporting "Already active".

Localization:
*   **Russian Translations:** Added and fixed Russian translations for all new UI strings and updater messages.