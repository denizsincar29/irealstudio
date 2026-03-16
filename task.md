# Task
1. Fix the chord addition / edition dialog. in minor sevenths, there mustn't be #11, but can be 11.
2. Add transpose feature. When selected a few chords, you can transpose them. Also you can transpose whole song. Or you can paste some chords with transposition.
3. Make a compensation feature for midi in playback, because e.g. microsoft gs wavetable synth is freaking delayed. Even save the compensation selected for each midi output device. For reference, look the audio metronome compensation feature.
4. What is Fine in insert>section mark? Isn't it d.c. al fine? Needs clarification.
5. There is a feature where you select a key for the song and it recognizes flat or sharp rooted codes, like Eb or D#, but it's implementation is a big mess up. There must be instead a selector (minor or major). It's not used in ireal pro format but it helps the program to recognize it's sharpness or flatness. Fix this mess up. Now there are all keys mixed up in a strange way with 2 a's and god knows what else.
6. The volta / ending bracket feature must be revised and not marked to sections. More on that in [volta section](#volta).
7. Review all menus and code and translate untranslated strings, e.g. in autoupdator dialog or chord edition.

# Volta
1. you need to find a measure to mark the start of repeat and press a key combination. I'd like it to be left bracket.
2. Than you need to find repeat ending measure and mark it. E.g. right bracket. Now if you e.g. made measures 1 to 8 repeat, measure 5 to 16 are not accessible and hidden from the user, i mean you can view the repeated representation using down arrow.
3. Now if you need a volta in a 1-8 measure repeat on 7th measure (7 and 8 are different ending measures), you insert a volta mark using a hotkey on measure 7 beat 1, and now to navigate between repeat 1 and repeat 2, press up / down arrows, since right arrow after the first volta goes to the measure 17 as in our example.

So we have:
- measures 1-8 repeat
- Measures 7-8 are 2 different endings in both repeats.
- if you press ctrl+right, alt+right or whatever on measure 8, you go to measure 17 (after the repeat).
- To see the measures 9-16, press down arrow. It's useful e.g. when you want to insert a section mark on the repeat2 beginning. The screenreader will say: Measure 9, repeat 2. And when you go to measure 15, it will say: measure 15, ending 2.

If you edit a chord in the repeating part, not volta, it will be edited in both repeats. I mean in python way, it will not be 2 different objects. But 2 voltas are different objects.

In python representation, first 8 measures are written out with chords, on measures 1:1 and 8:4 there are repeat open and close signs, on measure 6 first volta mark. It automatically calculates that next 6 measures are the same as first, so there chords are not written out in the array, but in the view they are shown. And measures 15 and 16 are written out with volta2 chords, measure 15 has volta 2 mark.
Make a feature to make up to 4 repeats. Endings are not necessary.