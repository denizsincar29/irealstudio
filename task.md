# bug
The releaser action failed withe exit code 1, i guess pointing to mac os build but not sure, here is the log:

```
Run uv run nuitka \
19
Nuitka-Onefile:WARNING: Onefile mode cannot compress without 'zstandard' package installed You probably should depend on 'Nuitka[onefile]' rather than 'Nuitka' which among other things depends on it.
20
FATAL: options-nanny: Error, package 'wx' requires '--mode=app' to be used or else it cannot work.
21
Error: Process completed with exit code 1.
```
