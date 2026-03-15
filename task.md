# Task
1. Allow the user to edit a chord via a hotkey or from menu, either via entering the chord name, or choosing the chord from list of keys and qualities and alterations.
2. Add beautiful visualization of chord progressions and playback animation. Sighted users should also be able to use the app. Make mouce selection possible...
3. Metronome playback have a huge latency! Fix it using continuous output stream and callbacks and buffer by buffer audio writing, not the whole sound at once.
4. In chord adding / editing dialog, add functions to add alterations for the 9, 11 and 13, and validate if those alterations are available for this quality in place. Thus, there must be less qualities in the list, alterating is available using checkboxes.
5. Add a feature to play metronome using midi by selecting the notes for on beat and off bit instead of sound files. This will allow users to use their own sounds for metronome and also have more control over the sound of the metronome.
6. Chord voicings are sometimes too low (not the root note though, it's perfect).

## chord voicing algorithm:
- root note is always from E1 to Bb2.
- Third and seventh are from Eb3 to Ab4. The seventh can come before the third if notes are too far from eachother, like C13 can have no 9, thus if there are 3 7 13, 7 and 13 are very far, but 3 and 13 are close because 13 is 6. You know what I mean.
- If there is a major third and flat7, the fifth is not played! Also, sus voicing is made of root note and than goes 7 9 11 and 13 in a straight row. There are no 3 and 5.