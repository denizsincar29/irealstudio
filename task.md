# Task
## workflow
Fix the error in release workflow
```
Line number, 298 FATAL: Error, malformed '--include-data-dir' value 'locales:locales' description, must specify a relative target path with '=' separating it.
```

## solution
The error is caused by the incorrect format of the `--include-data-dir` option in the release workflow. To fix this, we need to change the format to specify a relative target path with an '=' separating it.

## prepare a new fix release
run `uv run tag_release.py` and follow the instructions to prepare a new fix release. This will prepare a draft for the new release and tag. Write the release notes in the tool.