#task
1. translate the chord names: мейдж, минор, диез, бемоль, сус, уменьшённый, полууменьшённый, увеличенный...
2. translate note names for speech outputter.
3. make full navigation+selection hotkeys:
  -- left/right previous/next chord (shift for selection)
  add ctrl to navigate by bars (or select them)
  alt+left/right to navigate by beats (or select them)
  ctrl+alt+left/right to navigate by structural (sections/repeats) (or select the range between them)

4. In [ireal pro docs](https://www.irealpro.com/ireal-pro-custom-chord-chart-protocol), there are mentions of other section types, like coda and others. Read the docs and implement everything supported by ireal pro format.
5. Make the chords playback on a midi keyboard when pressed space.

## chord playback
- root note is played on range from f1 to c3 and the next root note must be close, don't make huge octave jumps.
- 3 5 and 7 are played on range from c3 to a4. Try to layout notes not to make minor seconds or other desonant intervals, e.g. you can play 7 lower than 3, if you play 13 chord and so on.
- for chords with extensions, try to play the extensions on the upper octave, e.g. for Cmaj13, play root, 3, 5, 7 in the lower octave and 9, 11, 13 in the upper octave. By next octave I mean upper than the next root note, not C.