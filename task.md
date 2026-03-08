# Task
Make a python app for blind that writes chord progressions by metronomed recording, allows to edit them and save to json and ireal pro format.

## features
- Press R to start recording. The metronome will start pre-counting 2 measures along with speech (One two...).
- The timestamp of each chord is recorded on first note-on, and the chord is identified on last note-off. It is quantized automatically in the chords.py module.
- Rehearsal marks / other metadata must be also included in the ChordProgression object, and saved to json and ireal pro format.
- Press ctrl+left/right to navigate between measures, left/right between chords.
- Adding inversion to a chord by holding slash key and pressing the note key (a-g) / typing "/"+(Gb)...
- Add section marks by holding S key and pressing A, B... and all ireal supported rehearsal marks.
- Save the chord progression to json format by pressing Ctrl+S.
- Export to ireal pro html format by pressing Ctrl+E.
- Press space to speak out the chord progression by the metronome rhythm. Ctrl+space to stop and navigate to the beat where it stopped.
- Playing and recording is done from the position of the cursor. Press ctrl+home to navigate to the beginning of the progression, ctrl+end to navigate to the end.
- repeat / ending variations. Explained in the next section.

## Repeats and endings
Let's asume we have an AABA 32 measure song, where first A is nearly the same as B, but last 2 measures are different.
Usually in IRealPro we mark that as a repeat with 2 endings. So we have something like this:
- repeat start.
- section a: first 6 measures
- ending 1: measures 7-8
- section A (refered as a2)- ending 2 without writing the first 6 measures again.

In the app, the first A section has 8 measures, and on the start of 7th measure you press V key (volta), and the 7 and 8th measures are marked as ending 1.
When you press right key from the 8th measure, you will navigate to the second ending (measure 15), and 6 measures of the second A is hidden from the user and from ireal pro export. Well, they are not hidden in the ChordProgression object, just there are no chords in the second A's first x measures, but the navigation must skip them when detected ending marks.
Ireal pro export must not write | x | x | x | x for the before ending2 measures, it must follow the pyrealpro rules / features for that.

## Technical details
Pyrealpro library is used for ireal pro export
Uv package manager is used for dependency management for python. Use uv add <dependency> to add dependencies, and uv run <script> to run the app. The app should be runnable by uv run main.py command.