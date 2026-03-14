# Task
- In settings, no title / bpm / other dialogs needed, everything is already in project settings.
- Minor 7 b5 must be detected as half diminished, not minor, automatically.
- When chord is spoken out loud, it must say the human speakable name, like "C minor 6 9" instead of "C m6 9". Sometimes i hear "caug" which is spoken like "kog", and well, UX falls apart.
- The sound playback is delayed 100-200 ms, metronome is off the beat. Try to do something with sound.py to make it more responsive, or maybe use a different library for sound playback.
- The insert section keyboard shortcut must be a press combination: press quickly S and the section letter, like A, B etc. The section keyhook is installed for 1 second after pressing S. I guess menu shortcuts make conflicts with it. The alternative would be to use like ctrl+shift+section letter, but you need to thoroughly check conflicts with other shortcuts. If you'd manage to do that, this is even better.
- Make the program save settings to a file, e.g. device names or other stuff that is not project specific. This way, when user opens the program again, they don't have to set up their devices again.


# nuitka, releases and packaging
I added nuitka to dev dependencies. Make a config file for it, if any needed.
You need to run nuitka using uv,    uv run nuitka arguments, to make it work with the virtual environment. Make sure to test the generated executable on a clean machine, to ensure that it works without any additional dependencies.
Make a github action that listens for new git tag pushes and creates a release with:
- The generated executable for Windows, Linux and MacOS. remember uv and nuitka for that. search the web if there is already a github action for that, it should be pretty common.
- The changelog entries for the new version. (news.md used for the last version, not changelog.md).

Make a git tagger python script that asks for version number and creates a tag with Vx.x.x version number and commits it to the repo. The script checks if no uncommitted changes before continueing, validates the version number, tag existance and that it's higher than the last tag. It also writes the news.md with the version number, date and multiline input for the changelog entry.
To end the multiline input, press enter 2 times quickly: `time.time()-last_enter_time<1`.

# autoupdator
Find a python library, or make yourself, that checks for new releases on github and prompts the user to download and install the new version. It should check for updates on program start and maybe also have a "check for updates" button in settings. The library should be cross-platform and work with the generated executables from nuitka.