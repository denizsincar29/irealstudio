# task
1. In tag_release.py, use gitpython, not subprocess. I already added it to dependencies.
2. in tag_release.py you don't have to need to enter letter v before version, script should add it by it self.
3. Add selection feature to the app to be able to select bars / individual chords and copy/delete them.
4. When deleted a chord, the cursor should focus on the last chord from the position of the deleted chord, or starting points if song becomes empty.
5. When moving from one section to another, the app should speak the name of the section.
6. Make keyboard shortcuts for adding sections, the s+a s+b works badly and makes the app behave wierdly. Check all shortcut conflicts.
7. Add save dialog if something is unsaved when closing the app.
8. The user should have the option to delete a section, a repeat mark or whatever is unnavigable.