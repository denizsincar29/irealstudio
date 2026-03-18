# Task
1. Make github workflows run faster by caching dependencies by using [this action](https://github.com/actions/cache).
2. In the copilot instructions, there is a mention that copilot should run tag_release.py. Change it not to run but just write news.md without version number. The user will run it manually. Even don't touch changelog. Copilot must only edit news.md.
3. Fix bug in mac os latest build fail or don't allow the job to run on mac os latest until the bug is fixed. The bug is that it creates dist/main.app, but than chmods dist/irealstudio-macos/... which doesn't exist.
4. Autoupdator works but than it doesn't launch the bat file and if i launch it, it says: C:\Users\user\Desktop\IREALS~1\python.exe  диалог  Не удается найти "C:\Users\user\Desktop\IREALS~1\python.exe". Проверьте, правильно ли указано имя и повторите попытку.   
