# task
## Menu
Menu should be reorganized.
- Add edit menu with select, copy, paste, undo redo and other things.
- Add insert menu with all the things that can be inserted: chord, rehearsals, endings, no chord symbol, repeat last chord symbol, and so on. Chord can be chosen from listboxes with root, type and alterations checkboxes or from chord enter box with strict syntax validation.
- Add record and playback menu, or shorter name.
- Add settings menu with devices submenus and project settings item. Project settings groups everything into one dialog: bpm, time, key, style and so on.

## recording
Recording should have 2 modes:
- overdub - if there is a chord on this exact place, replace it. If no chord, place it there.
- Overwrite - deletes everything from start recording position to the position where the last chord is played, not the stop recording position, so that the user could have time to run from the piano to the pc to stop recording.

Add a setting that toggles between whole measure overwrite or stop at last chord position. If the user played a chord in a measure, the whole measure will be overwritten, otherwise it will stop at the last chord position. This setting should be in record and playback menu, or in project settings, or in both.

## no chord symbol and repeat last chord
If the user didn't play any chord in the measure, ireal pro format should export it as repeat last chord. To write a no chord symbol, the user should press the left pedal on this measure or insert no chord symbol from the menu.

## qr code ireal pro url
In file menu, add export to ireal pro qr code url. It should generate a url with the current project in ireal pro url format and encode it to qr code. The user can scan this qr code with ireal pro app and import the project there. This is a very convenient way to transfer projects between this app and ireal pro app without using files.
Run `uv add qrcode` to add python qrcode library as a dependency.

## bugs in chord detection
- half diminished are recognized as minor b5. Yep, this is correct, but ireal has half diminished chord symbol, so it should be recognized as half diminished, not minor b5.
- The 7b5 chord is recognized as 7, ignoring b5. This is a bug. Btw #11 is recognized correctly where it needs to be, so it should be fixed.