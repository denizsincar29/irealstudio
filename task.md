# task
Implement own chord recognition system that recognizes chords from notes played on a midi keyboard, and don't use pychord because it goes bad with jazz chords.

## chord class
A chord is an object with list of notes and probable identified name.
It needs to have methods like has_degree(degree) that checks if the chord has a certain degree, and get_degree(degree) that returns the note corresponding to that degree.
Keep in mind that Everything starting from 8 is subtracted by 7 to get the degree. So 9 is 2, 11 is 4, etc.

## algorithm:
1. identify the root note of the chord
2. Identify degrees of the chord by checking the intervals between the notes and the root note, (octaveless, just on sorting from the lowest note to the highest note, and then checking the intervals between them).
3. Validate a few things that will be stated later, see [validation](#validation) section.
4. Identify the chord name by checking the degrees and the intervals between them.

## validation
1. If a chord has a minor 3rd but earlyer we detected a major 3rd, than it's a sharp ninth degree, not minor third. Otherwise it's a minor third.
2. If a chord has a major seventh or a fifth, than we detect a flat fifth, than it's a sharp eleventh. Otherwise it's a flat fifth.
3. If a chord has a fourth, it is a sus4. It can have flat ninth but not all kinds of thirds.

## chords
accidentals are marked with #, b and exclamation for natural. #b!9 is that the ninth can be one of b # and !.
1. major: 1, 3, 5 (with optional 7, 9, #11 and 13)
2. seventh chord like a dominant seventh: 1, 3, (omitable 5), b7 (with optional #b!9, #11 and 13)
3. minor: 1, b3, 5 (with optional b!7, 9, #11 and 13)
4. diminished: minor with b5 and, well, dim7.
5. half diminished: minor with b5 and b7, can have b!9.
6. augmented: major with #5. Can have 7.
7. Sus4: 1, 4, 7 (with optional b!9, and 13). We can also count 4 as 11, but it's the same in the code.

# bug
either the sound system is late, or the time in speech pre-counter is slightly 100 ms back than metronome, but try to check what's going on. Make a debug system that allowes me to press a key on metronome and offset time is spoken via the speech output, so i can identify if metronome is late.