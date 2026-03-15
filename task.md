# task
Rewrite the workflow to use nuitka action instead of doing huge steps in the wf.
Here are the official guides:
```
# Build python script into a stand-alone exe
- uses: Nuitka/Nuitka-Action@main
  with:
    nuitka-version: main
    script-name: hello_world.py
```
Check out [nuitka action docs](https://github.com/Nuitka/Nuitka-Action) and rewrite the workflow that releases into github releases using nuitka action. Make sure to include steps for building the executable and uploading it to the releases section of the repository.