# task
1. Fix the hyperlatency (200 ms) of the metronome sound. Make a sound.py that opens the stream in a thread and sends metronome sound data to the stream in a loop.
2. when not recording, playing a chord must speak the chord name just to make sure it recognizes it. When recording, also only the chord name without bars and beats must be spoken, because it's too verbose.
3. If the time signature is 4/4, make precounting more jazzy: first measure must say "one", and "two" on third beat, than next measure one two three four. Use english words instead of digits in pre-counting.
4. Make midi-out device submenu, for the future it will play the chords. Make the sound output submenu for metronome.
5. Make sure the ireal pro format exports correctly. Check out [IReal pro file format](https://www.irealpro.com/ireal-pro-custom-chord-chart-protocol) and thoroughly review the code for correct chords and whatever.
6. Make jazz style selection listbox instead of edit box. Styles are in the above link. Make sure the style is correctly applied to the generated chord progressions.
7. A key signature should be selected with minor or major to detect if the chord is in flat or sharp keys. Chord recognition must folow this and recognize Db7 as C#7 if the key uses sharps. Keep in mind that ireal pro format doesn't specify major / minor key signatures, only the root note.