# Post-merge beta-test checklist
1. **Plain repeat (no volta):** Create chords in bars 1–8, press `[` at bar 1 and `]` at bar 8, verify right-arrow from bar 8 jumps back to bar 1 and export keeps a normal repeat without N1/N2.
    My answer: this is not how it needs to work! Right arrow from bar 8 should jump to bar 17 (if there are 2 repeats from bar 1 to 8). If 3 repeats, bar 25. And up and down arrows should jump between repeats.
2. **Volta on repeat:** For the same 1–8 repeat, press `V` at bar 7 and verify bar 8 jumps to bar 17, up/down navigation reaches hidden/repeat-2 measures, and speech announces ending 1 / ending 2 correctly.
    My answer: it doesn't. beat and bar navigation should jump from repeating section out. If i'm on bar 8 beat 4, alt+right goes to bar 17 beat 1 (in our 8 bar 2 repeat example). If you press down arrow e.g. on bar 4, it goes to bar 12 because it's repeat 2's bar 4. And than using ctrl+left yor alt+left you can go to bar 9 beat 1 and it must not go to bar 8 back, because it's another repeat.
3. **Transpose:** Select a chord range and use `Ctrl+T`; then run transpose with no selection to transpose whole song and key signature. Verify enharmonic spelling and playback/export.
    My answer: it works perfectly! Nothing to add here!
4. **MIDI compensation per device:** Set different compensation values for at least two MIDI outputs, switch devices, restart app, and verify each device restores its saved value.
    My answer: will test that with my friend who has microsoft gsws.
5. **Fine label clarity:** Open Insert → Section Mark and confirm menu label is `Fine (end mark)` in English and localized text in Russian.
    My answer: comment out this menu item for now. It's rarely used and I must check what it does in ireal pro.
6. **Russian i18n coverage:** Run app in Russian and check new strings (repeat/volta feedback, transpose dialog, updater error paths, shortcut help text) are translated and not fuzzy/English.
    My answer: Not all menu items are translated. E.g. edit cord menu item... Check the whole code for that.


# Old task for reference
This task is partially done. It is kept here for reference for the above beta checklist. Carefully read volta section.
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
