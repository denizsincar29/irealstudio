# Task
## High priority tasks
1. Make the released app compile not in one file, because windows defender freaking eats it. Ship zips / tars instead. On mac it can stay as it is.
2. In the release, the mo files for translations should also be shipped in the zip/tar.

## medium priority tasks
1. In tag_release.py use semantic versioning library instead of regex everywhere.
2. Block further execution if branch is not main, or delete the prepare/auto subcommands and make them automatic based on the branch. If not main, it prepares the release in a draft as it's now done in the prepare subcommand, but it doesn't publish it. If main, it prepares and publishes the release either from the draft or from scratch.
3. Prepare a release 0.1.5 with very small description of fixes.