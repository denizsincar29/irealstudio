# Task
1. Make autoupdater download and unzip / untar files and restart the app. Maybe there are already libraries to autoupdate from github releases, search for them.
2. Fix the github action run / nuitka build. exe is not running now.

View this run on GitHub: https://github.com/denizsincar29/irealstudio/actions/runs/23134569397
Job log:
```
Build on windows-latest	Set up job	﻿2026-03-16T08:29:26.0483254Z Current runner version: '2.332.0'
Build on windows-latest	Set up job	2026-03-16T08:29:26.0533154Z ##[group]Runner Image Provisioner
Build on windows-latest	Set up job	2026-03-16T08:29:26.0534338Z Hosted Compute Agent
Build on windows-latest	Set up job	2026-03-16T08:29:26.0535065Z Version: 20260213.493
Build on windows-latest	Set up job	2026-03-16T08:29:26.0535909Z Commit: 5c115507f6dd24b8de37d8bbe0bb4509d0cc0fa3
Build on windows-latest	Set up job	2026-03-16T08:29:26.0536830Z Build Date: 2026-02-13T00:28:41Z
Build on windows-latest	Set up job	2026-03-16T08:29:26.0537823Z Worker ID: {4bef8ee4-07dd-4e86-815d-1c4b134c7720}
Build on windows-latest	Set up job	2026-03-16T08:29:26.0538794Z Azure Region: centralus
Build on windows-latest	Set up job	2026-03-16T08:29:26.0539544Z ##[endgroup]
Build on windows-latest	Set up job	2026-03-16T08:29:26.0541314Z ##[group]Operating System
Build on windows-latest	Set up job	2026-03-16T08:29:26.0542174Z Microsoft Windows Server 2025
Build on windows-latest	Set up job	2026-03-16T08:29:26.0542913Z 10.0.26100
Build on windows-latest	Set up job	2026-03-16T08:29:26.0543503Z Datacenter
Build on windows-latest	Set up job	2026-03-16T08:29:26.0544118Z ##[endgroup]
Build on windows-latest	Set up job	2026-03-16T08:29:26.0544721Z ##[group]Runner Image
Build on windows-latest	Set up job	2026-03-16T08:29:26.0545489Z Image: windows-2025
Build on windows-latest	Set up job	2026-03-16T08:29:26.0546128Z Version: 20260302.43.1
Build on windows-latest	Set up job	2026-03-16T08:29:26.0547644Z Included Software: https://github.com/actions/runner-images/blob/win25/20260302.43/images/windows/Windows2025-Readme.md
Build on windows-latest	Set up job	2026-03-16T08:29:26.0550835Z Image Release: https://github.com/actions/runner-images/releases/tag/win25%2F20260302.43
Build on windows-latest	Set up job	2026-03-16T08:29:26.0552305Z ##[endgroup]
Build on windows-latest	Set up job	2026-03-16T08:29:26.0553736Z ##[group]GITHUB_TOKEN Permissions
Build on windows-latest	Set up job	2026-03-16T08:29:26.0556545Z Contents: write
Build on windows-latest	Set up job	2026-03-16T08:29:26.0557411Z Metadata: read
Build on windows-latest	Set up job	2026-03-16T08:29:26.0558058Z ##[endgroup]
Build on windows-latest	Set up job	2026-03-16T08:29:26.0560974Z Secret source: Actions
Build on windows-latest	Set up job	2026-03-16T08:29:26.0561919Z Prepare workflow directory
Build on windows-latest	Set up job	2026-03-16T08:29:26.1047865Z Prepare all required actions
Build on windows-latest	Set up job	2026-03-16T08:29:26.1086783Z Getting action download info
Build on windows-latest	Set up job	2026-03-16T08:29:26.4691113Z Download action repository 'actions/checkout@v6' (SHA:de0fac2e4500dabe0009e67214ff5f5447ce83dd)
Build on windows-latest	Set up job	2026-03-16T08:29:26.5865721Z Download action repository 'astral-sh/setup-uv@v7' (SHA:e06108dd0aef18192324c70427afc47652e63a82)
Build on windows-latest	Set up job	2026-03-16T08:29:27.1910782Z Download action repository 'actions/setup-python@v6' (SHA:a309ff8b426b58ec0e2a45f0f869d46889d02405)
Build on windows-latest	Set up job	2026-03-16T08:29:27.3192149Z Download action repository 'Nuitka/Nuitka-Action@v1.4' (SHA:0d4e22d4b66062a13d120f6948dd90170be04b3a)
Build on windows-latest	Set up job	2026-03-16T08:29:27.7571983Z Download action repository 'actions/upload-artifact@v7' (SHA:bbbca2ddaa5d8feaa63e36b76fdaad77386f024f)
Build on windows-latest	Set up job	2026-03-16T08:29:28.4172060Z Getting action download info
Build on windows-latest	Set up job	2026-03-16T08:29:28.5525229Z Download action repository 'actions/cache@v4' (SHA:0057852bfaa89a56745cba8c7296529d2fc39830)
Build on windows-latest	Set up job	2026-03-16T08:29:28.7198011Z Complete job name: Build on windows-latest
Build on windows-latest	Checkout	﻿2026-03-16T08:29:28.8358417Z ##[group]Run actions/checkout@v6
Build on windows-latest	Checkout	2026-03-16T08:29:28.8359615Z with:
Build on windows-latest	Checkout	2026-03-16T08:29:28.8360060Z   repository: denizsincar29/irealstudio
Build on windows-latest	Checkout	2026-03-16T08:29:28.8360833Z   token: ***
Build on windows-latest	Checkout	2026-03-16T08:29:28.8361240Z   ssh-strict: true
Build on windows-latest	Checkout	2026-03-16T08:29:28.8361636Z   ssh-user: git
Build on windows-latest	Checkout	2026-03-16T08:29:28.8362063Z   persist-credentials: true
Build on windows-latest	Checkout	2026-03-16T08:29:28.8362488Z   clean: true
Build on windows-latest	Checkout	2026-03-16T08:29:28.8362941Z   sparse-checkout-cone-mode: true
Build on windows-latest	Checkout	2026-03-16T08:29:28.8363381Z   fetch-depth: 1
Build on windows-latest	Checkout	2026-03-16T08:29:28.8363819Z   fetch-tags: false
Build on windows-latest	Checkout	2026-03-16T08:29:28.8364270Z   show-progress: true
Build on windows-latest	Checkout	2026-03-16T08:29:28.8364659Z   lfs: false
Build on windows-latest	Checkout	2026-03-16T08:29:28.8365043Z   submodules: false
Build on windows-latest	Checkout	2026-03-16T08:29:28.8365458Z   set-safe-directory: true
Build on windows-latest	Checkout	2026-03-16T08:29:28.8366184Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:28.9723238Z Syncing repository: denizsincar29/irealstudio
Build on windows-latest	Checkout	2026-03-16T08:29:28.9725034Z ##[group]Getting Git version info
Build on windows-latest	Checkout	2026-03-16T08:29:28.9725620Z Working directory is 'D:\a\irealstudio\irealstudio'
Build on windows-latest	Checkout	2026-03-16T08:29:29.0622651Z [command]"C:\Program Files\Git\bin\git.exe" version
Build on windows-latest	Checkout	2026-03-16T08:29:29.3541831Z git version 2.53.0.windows.1
Build on windows-latest	Checkout	2026-03-16T08:29:29.3596732Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:29.3616345Z Temporarily overriding HOME='D:\a\_temp\e11dd8f9-18f7-41bd-85e0-62778a4a8e8e' before making global git config changes
Build on windows-latest	Checkout	2026-03-16T08:29:29.3617346Z Adding repository directory to the temporary git global config as a safe directory
Build on windows-latest	Checkout	2026-03-16T08:29:29.3625342Z [command]"C:\Program Files\Git\bin\git.exe" config --global --add safe.directory D:\a\irealstudio\irealstudio
Build on windows-latest	Checkout	2026-03-16T08:29:29.4098681Z Deleting the contents of 'D:\a\irealstudio\irealstudio'
Build on windows-latest	Checkout	2026-03-16T08:29:29.4105345Z ##[group]Initializing the repository
Build on windows-latest	Checkout	2026-03-16T08:29:29.4113729Z [command]"C:\Program Files\Git\bin\git.exe" init D:\a\irealstudio\irealstudio
Build on windows-latest	Checkout	2026-03-16T08:29:29.4826801Z Initialized empty Git repository in D:/a/irealstudio/irealstudio/.git/
Build on windows-latest	Checkout	2026-03-16T08:29:29.4879790Z [command]"C:\Program Files\Git\bin\git.exe" remote add origin https://github.com/denizsincar29/irealstudio
Build on windows-latest	Checkout	2026-03-16T08:29:29.5369177Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:29.5369989Z ##[group]Disabling automatic garbage collection
Build on windows-latest	Checkout	2026-03-16T08:29:29.5378554Z [command]"C:\Program Files\Git\bin\git.exe" config --local gc.auto 0
Build on windows-latest	Checkout	2026-03-16T08:29:29.5685699Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:29.5686783Z ##[group]Setting up auth
Build on windows-latest	Checkout	2026-03-16T08:29:29.5687561Z Removing SSH command configuration
Build on windows-latest	Checkout	2026-03-16T08:29:29.5699563Z [command]"C:\Program Files\Git\bin\git.exe" config --local --name-only --get-regexp core\.sshCommand
Build on windows-latest	Checkout	2026-03-16T08:29:29.6011818Z [command]"C:\Program Files\Git\bin\git.exe" submodule foreach --recursive "sh -c \"git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :\""
Build on windows-latest	Checkout	2026-03-16T08:29:30.8342988Z Removing HTTP extra header
Build on windows-latest	Checkout	2026-03-16T08:29:30.8354748Z [command]"C:\Program Files\Git\bin\git.exe" config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
Build on windows-latest	Checkout	2026-03-16T08:29:30.8673444Z [command]"C:\Program Files\Git\bin\git.exe" submodule foreach --recursive "sh -c \"git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :\""
Build on windows-latest	Checkout	2026-03-16T08:29:31.3994555Z Removing includeIf entries pointing to credentials config files
Build on windows-latest	Checkout	2026-03-16T08:29:31.4008632Z [command]"C:\Program Files\Git\bin\git.exe" config --local --name-only --get-regexp ^includeIf\.gitdir:
Build on windows-latest	Checkout	2026-03-16T08:29:31.4319579Z [command]"C:\Program Files\Git\bin\git.exe" submodule foreach --recursive "git config --local --show-origin --name-only --get-regexp remote.origin.url"
Build on windows-latest	Checkout	2026-03-16T08:29:31.9713770Z [command]"C:\Program Files\Git\bin\git.exe" config --file D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config http.https://github.com/.extraheader "AUTHORIZATION: basic ***"
Build on windows-latest	Checkout	2026-03-16T08:29:32.0035665Z [command]"C:\Program Files\Git\bin\git.exe" config --local includeIf.gitdir:D:/a/irealstudio/irealstudio/.git.path D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Checkout	2026-03-16T08:29:32.0340231Z [command]"C:\Program Files\Git\bin\git.exe" config --local includeIf.gitdir:D:/a/irealstudio/irealstudio/.git/worktrees/*.path D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Checkout	2026-03-16T08:29:32.0701349Z [command]"C:\Program Files\Git\bin\git.exe" config --local includeIf.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Checkout	2026-03-16T08:29:32.1020893Z [command]"C:\Program Files\Git\bin\git.exe" config --local includeIf.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Checkout	2026-03-16T08:29:32.1336743Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:32.1337502Z ##[group]Fetching the repository
Build on windows-latest	Checkout	2026-03-16T08:29:32.1352449Z [command]"C:\Program Files\Git\bin\git.exe" -c protocol.version=2 fetch --no-tags --prune --no-recurse-submodules --depth=1 origin +refs/tags/v0.1.6:refs/tags/v0.1.6
Build on windows-latest	Checkout	2026-03-16T08:29:33.1481177Z From https://github.com/denizsincar29/irealstudio
Build on windows-latest	Checkout	2026-03-16T08:29:33.1481865Z  * [new tag]         v0.1.6     -> v0.1.6
Build on windows-latest	Checkout	2026-03-16T08:29:33.1857296Z [command]"C:\Program Files\Git\bin\git.exe" tag --list v0.1.6
Build on windows-latest	Checkout	2026-03-16T08:29:33.2230988Z v0.1.6
Build on windows-latest	Checkout	2026-03-16T08:29:33.2602311Z [command]"C:\Program Files\Git\bin\git.exe" rev-parse refs/tags/v0.1.6^{commit}
Build on windows-latest	Checkout	2026-03-16T08:29:33.2603058Z 25affadeb442cf9916987af6208bb0694c23f11d
Build on windows-latest	Checkout	2026-03-16T08:29:33.2642928Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:33.2643374Z ##[group]Determining the checkout info
Build on windows-latest	Checkout	2026-03-16T08:29:33.2644475Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:33.2653625Z [command]"C:\Program Files\Git\bin\git.exe" sparse-checkout disable
Build on windows-latest	Checkout	2026-03-16T08:29:33.3047386Z [command]"C:\Program Files\Git\bin\git.exe" config --local --unset-all extensions.worktreeConfig
Build on windows-latest	Checkout	2026-03-16T08:29:33.3372493Z ##[group]Checking out the ref
Build on windows-latest	Checkout	2026-03-16T08:29:33.3381548Z [command]"C:\Program Files\Git\bin\git.exe" checkout --progress --force refs/tags/v0.1.6
Build on windows-latest	Checkout	2026-03-16T08:29:33.3984567Z Note: switching to 'refs/tags/v0.1.6'.
Build on windows-latest	Checkout	2026-03-16T08:29:33.3985075Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3985406Z You are in 'detached HEAD' state. You can look around, make experimental
Build on windows-latest	Checkout	2026-03-16T08:29:33.3985985Z changes and commit them, and you can discard any commits you make in this
Build on windows-latest	Checkout	2026-03-16T08:29:33.3986505Z state without impacting any branches by switching back to a branch.
Build on windows-latest	Checkout	2026-03-16T08:29:33.3986832Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3987047Z If you want to create a new branch to retain commits you create, you may
Build on windows-latest	Checkout	2026-03-16T08:29:33.3987485Z do so (now or later) by using -c with the switch command. Example:
Build on windows-latest	Checkout	2026-03-16T08:29:33.3987808Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3988015Z   git switch -c <new-branch-name>
Build on windows-latest	Checkout	2026-03-16T08:29:33.3988264Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3988418Z Or undo this operation with:
Build on windows-latest	Checkout	2026-03-16T08:29:33.3988587Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3988680Z   git switch -
Build on windows-latest	Checkout	2026-03-16T08:29:33.3988837Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3989058Z Turn off this advice by setting config variable advice.detachedHead to false
Build on windows-latest	Checkout	2026-03-16T08:29:33.3989417Z 
Build on windows-latest	Checkout	2026-03-16T08:29:33.3989693Z HEAD is now at 25affad Merge pull request #33 from denizsincar29/copilot/fix-error-in-task
Build on windows-latest	Checkout	2026-03-16T08:29:33.4058352Z ##[endgroup]
Build on windows-latest	Checkout	2026-03-16T08:29:33.4487376Z [command]"C:\Program Files\Git\bin\git.exe" log -1 --format=%H
Build on windows-latest	Checkout	2026-03-16T08:29:33.4754033Z 25affadeb442cf9916987af6208bb0694c23f11d
Build on windows-latest	Install uv	﻿2026-03-16T08:29:33.5355747Z ##[group]Run astral-sh/setup-uv@v7
Build on windows-latest	Install uv	2026-03-16T08:29:33.5356219Z with:
Build on windows-latest	Install uv	2026-03-16T08:29:33.5356390Z   enable-cache: true
Build on windows-latest	Install uv	2026-03-16T08:29:33.5356601Z   activate-environment: false
Build on windows-latest	Install uv	2026-03-16T08:29:33.5356844Z   working-directory: D:\a\irealstudio\irealstudio
Build on windows-latest	Install uv	2026-03-16T08:29:33.5357383Z   github-token: ***
Build on windows-latest	Install uv	2026-03-16T08:29:33.5357902Z   cache-dependency-glob: **/*requirements*.txt
Build on windows-latest	Install uv	**/*requirements*.in
Build on windows-latest	Install uv	**/*constraints*.txt
Build on windows-latest	Install uv	**/*constraints*.in
Build on windows-latest	Install uv	**/pyproject.toml
Build on windows-latest	Install uv	**/uv.lock
Build on windows-latest	Install uv	**/*.py.lock
Build on windows-latest	Install uv	
Build on windows-latest	Install uv	2026-03-16T08:29:33.5358447Z   restore-cache: true
Build on windows-latest	Install uv	2026-03-16T08:29:33.5358630Z   save-cache: true
Build on windows-latest	Install uv	2026-03-16T08:29:33.5358791Z   prune-cache: true
Build on windows-latest	Install uv	2026-03-16T08:29:33.5358964Z   cache-python: false
Build on windows-latest	Install uv	2026-03-16T08:29:33.5359147Z   ignore-nothing-to-cache: false
Build on windows-latest	Install uv	2026-03-16T08:29:33.5359375Z   ignore-empty-workdir: false
Build on windows-latest	Install uv	2026-03-16T08:29:33.5359581Z   add-problem-matchers: true
Build on windows-latest	Install uv	2026-03-16T08:29:33.5359796Z   resolution-strategy: highest
Build on windows-latest	Install uv	2026-03-16T08:29:33.5359998Z ##[endgroup]
Build on windows-latest	Install uv	2026-03-16T08:29:33.7125787Z (node:8376) [DEP0040] DeprecationWarning: The `punycode` module is deprecated. Please use a userland alternative instead.
Build on windows-latest	Install uv	2026-03-16T08:29:33.7126513Z (Use `node --trace-deprecation ...` to show where the warning was created)
Build on windows-latest	Install uv	2026-03-16T08:29:33.7131723Z Trying to find version for uv in: D:\a\irealstudio\irealstudio\uv.toml
Build on windows-latest	Install uv	2026-03-16T08:29:33.7132315Z Could not find file: D:\a\irealstudio\irealstudio\uv.toml
Build on windows-latest	Install uv	2026-03-16T08:29:33.7133523Z Trying to find version for uv in: D:\a\irealstudio\irealstudio\pyproject.toml
Build on windows-latest	Install uv	2026-03-16T08:29:33.7145367Z Could not determine uv version from uv.toml or pyproject.toml. Falling back to latest.
Build on windows-latest	Install uv	2026-03-16T08:29:33.7148769Z Fetching version data from https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson ...
Build on windows-latest	Install uv	2026-03-16T08:29:33.8354183Z Downloading uv from "https://github.com/astral-sh/uv/releases/download/0.10.10/uv-x86_64-pc-windows-msvc.zip" ...
Build on windows-latest	Install uv	2026-03-16T08:29:34.7056543Z [command]C:\Windows\system32\tar.exe x -C D:\a\_temp\09ddc725-3854-4558-a83a-a2487568eb62 -f D:\a\_temp\f083fa86-dcbf-4aa1-a70a-556c1249fb94
Build on windows-latest	Install uv	2026-03-16T08:29:34.9584104Z Set UV_TOOL_BIN_DIR to D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Install uv	2026-03-16T08:29:34.9587851Z Added D:\a\_temp\uv-tool-bin-dir to the path
Build on windows-latest	Install uv	2026-03-16T08:29:34.9597951Z Added C:\hostedtoolcache\windows\uv\0.10.10\x86_64 to the path
Build on windows-latest	Install uv	2026-03-16T08:29:34.9600670Z Set UV_TOOL_DIR to D:\a\_temp\uv-tool-dir
Build on windows-latest	Install uv	2026-03-16T08:29:34.9603789Z Set UV_PYTHON_INSTALL_DIR to D:\a\_temp\uv-python-dir
Build on windows-latest	Install uv	2026-03-16T08:29:34.9606026Z Added D:\a\_temp\uv-python-dir to the path
Build on windows-latest	Install uv	2026-03-16T08:29:34.9626848Z Set UV_CACHE_DIR to D:\a\_temp\setup-uv-cache
Build on windows-latest	Install uv	2026-03-16T08:29:34.9627198Z Successfully installed uv version 0.10.10
Build on windows-latest	Install uv	2026-03-16T08:29:37.0944714Z Searching files using cache dependency glob: D:\a\irealstudio\irealstudio\**\*requirements*.txt,D:\a\irealstudio\irealstudio\**\*requirements*.in,D:\a\irealstudio\irealstudio\**\*constraints*.txt,D:\a\irealstudio\irealstudio\**\*constraints*.in,D:\a\irealstudio\irealstudio\**\pyproject.toml,D:\a\irealstudio\irealstudio\**\uv.lock,D:\a\irealstudio\irealstudio\**\*.py.lock
Build on windows-latest	Install uv	2026-03-16T08:29:37.1394576Z D:\a\irealstudio\irealstudio\pyproject.toml
Build on windows-latest	Install uv	2026-03-16T08:29:37.1434191Z D:\a\irealstudio\irealstudio\uv.lock
Build on windows-latest	Install uv	2026-03-16T08:29:37.1444688Z Found 2 files to hash.
Build on windows-latest	Install uv	2026-03-16T08:29:37.1454582Z Trying to restore cache from GitHub Actions cache with key: setup-uv-2-x86_64-pc-windows-msvc-windows-2025-3.13.12-pruned-0be47c2d893585801c7593bdf6dd290d6a59af55cd26162ed9a76d0dbf26e2ce
Build on windows-latest	Install uv	2026-03-16T08:29:37.3618512Z No GitHub Actions cache found for key: setup-uv-2-x86_64-pc-windows-msvc-windows-2025-3.13.12-pruned-0be47c2d893585801c7593bdf6dd290d6a59af55cd26162ed9a76d0dbf26e2ce
Build on windows-latest	Set up Python	﻿2026-03-16T08:29:37.4550309Z ##[group]Run actions/setup-python@v6
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4550672Z with:
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4550838Z   python-version: 3.13
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4551019Z   check-latest: false
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4551354Z   token: ***
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4551524Z   update-environment: true
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4551718Z   allow-prereleases: false
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4551909Z   freethreaded: false
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4552081Z env:
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4552256Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4552491Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4552734Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4552982Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Set up Python	2026-03-16T08:29:37.4553192Z ##[endgroup]
Build on windows-latest	Set up Python	2026-03-16T08:29:37.6145543Z ##[group]Installed versions
Build on windows-latest	Set up Python	2026-03-16T08:29:37.6332927Z Successfully set up CPython (3.13.12)
Build on windows-latest	Set up Python	2026-03-16T08:29:37.6333616Z ##[endgroup]
Build on windows-latest	Install dependencies	﻿2026-03-16T08:29:37.6616075Z ##[group]Run uv sync --all-groups
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6616488Z [36;1muv sync --all-groups[0m
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6947023Z shell: C:\Program Files\PowerShell\7\pwsh.EXE -command ". '{0}'"
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6947376Z env:
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6947862Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6948302Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6948553Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6948839Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6949155Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6949574Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6949974Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6950330Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6950685Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Install dependencies	2026-03-16T08:29:37.6951019Z ##[endgroup]
Build on windows-latest	Install dependencies	2026-03-16T08:29:41.9637549Z Using CPython 3.13.12 interpreter at: C:\hostedtoolcache\windows\Python\3.13.12\x64\python3.exe
Build on windows-latest	Install dependencies	2026-03-16T08:29:41.9638163Z Creating virtual environment at: .venv
Build on windows-latest	Install dependencies	2026-03-16T08:29:41.9853383Z Resolved 26 packages in 2ms
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.0740783Z Downloading pywin32 (9.1MiB)
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.0747079Z Downloading wxpython (15.8MiB)
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.0754136Z Downloading numpy (11.7MiB)
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.0756377Z Downloading pillow (6.7MiB)
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.1894432Z    Building accessible-output3==0.1.2
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.3211792Z    Building python-rtmidi==1.5.8
Build on windows-latest	Install dependencies	2026-03-16T08:29:42.6487218Z  Downloaded pillow
Build on windows-latest	Install dependencies	2026-03-16T08:29:43.2445744Z  Downloaded numpy
Build on windows-latest	Install dependencies	2026-03-16T08:29:43.2513494Z  Downloaded pywin32
Build on windows-latest	Install dependencies	2026-03-16T08:29:43.4270356Z  Downloaded wxpython
Build on windows-latest	Install dependencies	2026-03-16T08:29:43.6336221Z    Building nuitka==4.0.5
Build on windows-latest	Install dependencies	2026-03-16T08:29:44.9143524Z       Built accessible-output3==0.1.2
Build on windows-latest	Install dependencies	2026-03-16T08:29:46.9932558Z       Built nuitka==4.0.5
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.1691342Z       Built python-rtmidi==1.5.8
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.1783216Z Prepared 23 packages in 22.19s
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4583949Z Installed 23 packages in 279ms
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4586259Z  + accessible-output3==0.1.2
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4587473Z  + cffi==2.0.0
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4588027Z  + colorama==0.4.6
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4589199Z  + gitdb==4.0.12
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4591327Z  + gitpython==3.1.46
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4591752Z  + libloader==1.4.3
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4593426Z  + mido==1.3.3
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4594639Z  + nuitka==4.0.5
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4595574Z  + numpy==2.4.3
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4596659Z  + packaging==26.0
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4598125Z  + pillow==12.1.1
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4598949Z  + platform-utils==1.6.2
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4600494Z  + platformdirs==4.9.4
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4600909Z  + pycparser==3.0
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4602864Z  + pyrealpro==0.2.0
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4604320Z  + python-rtmidi==1.5.8
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4604663Z  + pywin32==311
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4606834Z  + qrcode==8.2
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4607547Z  + semver==3.0.4
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4609141Z  + smmap==5.0.3
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4609706Z  + sounddevice==0.5.5
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4611258Z  + wxpython==4.2.5
Build on windows-latest	Install dependencies	2026-03-16T08:30:04.4611826Z  + zstandard==0.25.0
Build on windows-latest	Build executable	﻿2026-03-16T08:30:05.1126189Z ##[warning]Unexpected input(s) 'output-filename', 'no-progressbar', 'follow-imports', valid inputs are ['working-directory', 'nuitka-version', 'script-name', 'access-token', 'mode', 'python-flag', 'python-debug', 'enable-plugins', 'disable-plugins', 'user-plugin', 'plugin-no-detection', 'module-parameter', 'report', 'report-diffable', 'report-user-provided', 'report-template', 'quiet', 'show-scons', 'show-memory', 'include-package-data', 'include-data-files', 'include-data-dir', 'noinclude-data-files', 'include-data-files-external', 'include-raw-dir', 'include-package', 'include-module', 'include-plugin-directory', 'include-plugin-files', 'prefer-source-code', 'nofollow-import-to', 'user-package-configuration-file', 'onefile-tempdir-spec', 'onefile-child-grace-time', 'onefile-no-compression', 'warn-implicit-exceptions', 'warn-unusual-code', 'assume-yes-for-downloads', 'nowarn-mnemonic', 'deployment', 'no-deployment-flag', 'output-dir', 'output-file', 'disable-console', 'enable-console', 'company-name', 'product-name', 'file-version', 'product-version', 'file-description', 'copyright', 'trademarks', 'force-stdout-spec', 'force-stderr-spec', 'windows-console-mode', 'windows-icon-from-ico', 'windows-icon-from-exe', 'onefile-windows-splash-screen-image', 'windows-uac-admin', 'windows-uac-uiaccess', 'macos-target-arch', 'macos-app-icon', 'macos-signed-app-name', 'macos-app-name', 'macos-app-mode', 'macos-prohibit-multiple-instances', 'macos-sign-identity', 'macos-sign-notarization', 'macos-app-version', 'macos-app-protected-resource', 'macos-sign-keyring-filename', 'macos-sign-keyring-password', 'linux-icon', 'clang', 'mingw64', 'msvc', 'jobs', 'lto', 'static-libpython', 'cf-protection', 'debug', 'no-debug-immortal-assumptions', 'no-debug-c-warnings', 'unstripped', 'trace-execution', 'xml', 'experimental', 'low-memory', 'noinclude-setuptools-mode', 'noinclude-pytest-mode', 'noinclude-unittest-mode', 'noinclude-pydoc-mode', 'noinclude-IPython-mode', 'noinclude-dask-mode', 'noinclude-numba-mode', 'noinclude-default-mode', 'noinclude-custom-mode', 'include-pickle-support-module', 'include-pmw-blt', 'include-pmw-color', 'tk-library-dir', 'tcl-library-dir', 'include-qt-plugins', 'noinclude-qt-plugins', 'noinclude-qt-translations', 'upx-binary', 'upx-disable-cache', 'anti-debugger-debugging', 'auto-update-url-spec', 'auto-update-debug', 'data-hiding-salt-value', 'embed-data-files-compile-time-pattern', 'embed-data-files-run-time-pattern', 'embed-data-files-qt-resource-pattern', 'embed-debug-qt-resources', 'windows-signing-tool', 'windows-certificate-name', 'windows-certificate-sha1', 'windows-certificate-filename', 'windows-certificate-password', 'windows-signed-content-comment', 'encryption-key', 'encrypt-stdout', 'encrypt-stderr', 'encrypt-debug-init', 'encrypt-crypto-package', 'windows-service-name', 'windows-service-grace-time', 'windows-service-start-mode', 'windows-service-cli', 'disable-cache', 'caching-key']
Build on windows-latest	Build executable	2026-03-16T08:30:05.1151749Z ##[group]Run Nuitka/Nuitka-Action@v1.4
Build on windows-latest	Build executable	2026-03-16T08:30:05.1151988Z with:
Build on windows-latest	Build executable	2026-03-16T08:30:05.1152161Z   nuitka-version: 4.0.5
Build on windows-latest	Build executable	2026-03-16T08:30:05.1152348Z   script-name: main.py
Build on windows-latest	Build executable	2026-03-16T08:30:05.1152538Z   mode: standalone
Build on windows-latest	Build executable	2026-03-16T08:30:05.1152707Z   output-filename: irealstudio.exe
Build on windows-latest	Build executable	2026-03-16T08:30:05.1152919Z   output-dir: dist
Build on windows-latest	Build executable	2026-03-16T08:30:05.1153087Z   windows-console-mode: disable
Build on windows-latest	Build executable	2026-03-16T08:30:05.1153301Z   assume-yes-for-downloads: true
Build on windows-latest	Build executable	2026-03-16T08:30:05.1153511Z   no-progressbar: true
Build on windows-latest	Build executable	2026-03-16T08:30:05.1153675Z   quiet: true
Build on windows-latest	Build executable	2026-03-16T08:30:05.1153836Z   follow-imports: true
Build on windows-latest	Build executable	2026-03-16T08:30:05.1154014Z   include-data-dir: locales=locales
Build on windows-latest	Build executable	2026-03-16T08:30:05.1154233Z   working-directory: .
Build on windows-latest	Build executable	2026-03-16T08:30:05.1154421Z   caching-key: caching
Build on windows-latest	Build executable	2026-03-16T08:30:05.1154580Z env:
Build on windows-latest	Build executable	2026-03-16T08:30:05.1154753Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.1155003Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.1155257Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.1155512Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Build executable	2026-03-16T08:30:05.1157832Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1158243Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Build executable	2026-03-16T08:30:05.1158649Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1159003Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1159357Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1159640Z ##[endgroup]
Build on windows-latest	Build executable	2026-03-16T08:30:05.1396097Z ##[group]Run echo "NUITKA_CACHE_DIR=D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache" >> $GITHUB_ENV
Build on windows-latest	Build executable	2026-03-16T08:30:05.1396745Z [36;1mecho "NUITKA_CACHE_DIR=D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache" >> $GITHUB_ENV[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.1397321Z [36;1mecho "PYTHON_VERSION=$(python --version | awk '{print $2}' | cut -d '.' -f 1,2)" >> $GITHUB_ENV[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.1419825Z shell: C:\Program Files\Git\bin\bash.EXE --noprofile --norc -e -o pipefail {0}
Build on windows-latest	Build executable	2026-03-16T08:30:05.1420539Z env:
Build on windows-latest	Build executable	2026-03-16T08:30:05.1425373Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.1426203Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.1426485Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.1426769Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Build executable	2026-03-16T08:30:05.1427103Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1427512Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Build executable	2026-03-16T08:30:05.1427935Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1428303Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1428932Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.1429218Z ##[endgroup]
Build on windows-latest	Build executable	2026-03-16T08:30:05.5672201Z ##[group]Run pip install -r "D:\a\_actions\Nuitka\Nuitka-Action\v1.4/requirements.txt"
Build on windows-latest	Build executable	2026-03-16T08:30:05.5672764Z [36;1mpip install -r "D:\a\_actions\Nuitka\Nuitka-Action\v1.4/requirements.txt"[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5673272Z [36;1m[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5673631Z [36;1m# With commercial access token, use that repository.[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5674025Z [36;1mif [ "" != "" ]; then[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5674323Z [36;1m  repo_url="git+https://@github.com/Nuitka/Nuitka-commercial.git"[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5674642Z [36;1melse[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5674870Z [36;1m  repo_url="git+https://$@github.com/Nuitka/Nuitka.git"[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5675142Z [36;1mfi[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5675280Z [36;1m[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5675463Z [36;1mpip install "${repo_url}/@4.0.5#egg=nuitka"[0m
Build on windows-latest	Build executable	2026-03-16T08:30:05.5691327Z shell: C:\Program Files\Git\bin\bash.EXE --noprofile --norc -e -o pipefail {0}
Build on windows-latest	Build executable	2026-03-16T08:30:05.5691672Z env:
Build on windows-latest	Build executable	2026-03-16T08:30:05.5691859Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.5692104Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.5692367Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Build executable	2026-03-16T08:30:05.5692635Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Build executable	2026-03-16T08:30:05.5692943Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.5693350Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Build executable	2026-03-16T08:30:05.5693742Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.5694106Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.5694463Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:05.5694835Z   NUITKA_CACHE_DIR: D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache
Build on windows-latest	Build executable	2026-03-16T08:30:05.5695146Z   PYTHON_VERSION: 3.13
Build on windows-latest	Build executable	2026-03-16T08:30:05.5695313Z ##[endgroup]
Build on windows-latest	Build executable	2026-03-16T08:30:08.4161715Z Collecting ordered-set==4.1.0 (from -r D:\a\_actions\Nuitka\Nuitka-Action\v1.4/requirements.txt (line 7))
Build on windows-latest	Build executable	2026-03-16T08:30:08.6483263Z   Downloading ordered_set-4.1.0-py3-none-any.whl.metadata (5.3 kB)
Build on windows-latest	Build executable	2026-03-16T08:30:08.7427739Z Collecting wheel==0.38.4 (from -r D:\a\_actions\Nuitka\Nuitka-Action\v1.4/requirements.txt (line 9))
Build on windows-latest	Build executable	2026-03-16T08:30:08.7604203Z   Downloading wheel-0.38.4-py3-none-any.whl.metadata (2.1 kB)
Build on windows-latest	Build executable	2026-03-16T08:30:08.9038065Z Collecting zstandard==0.20.0 (from -r D:\a\_actions\Nuitka\Nuitka-Action\v1.4/requirements.txt (line 11))
Build on windows-latest	Build executable	2026-03-16T08:30:08.9212650Z   Downloading zstandard-0.20.0.tar.gz (658 kB)
Build on windows-latest	Build executable	2026-03-16T08:30:09.0511958Z      ---------------------------------------- 658.9/658.9 kB 12.2 MB/s  0:00:00
Build on windows-latest	Build executable	2026-03-16T08:30:09.1992781Z   Installing build dependencies: started
Build on windows-latest	Build executable	2026-03-16T08:30:11.6458920Z   Installing build dependencies: finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:11.6493576Z   Getting requirements to build wheel: started
Build on windows-latest	Build executable	2026-03-16T08:30:15.4604095Z   Getting requirements to build wheel: finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:15.4633949Z   Preparing metadata (pyproject.toml): started
Build on windows-latest	Build executable	2026-03-16T08:30:17.4999415Z   Preparing metadata (pyproject.toml): finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:17.5205449Z Downloading ordered_set-4.1.0-py3-none-any.whl (7.6 kB)
Build on windows-latest	Build executable	2026-03-16T08:30:17.5501779Z Downloading wheel-0.38.4-py3-none-any.whl (36 kB)
Build on windows-latest	Build executable	2026-03-16T08:30:17.5885430Z Building wheels for collected packages: zstandard
Build on windows-latest	Build executable	2026-03-16T08:30:17.5921292Z   Building wheel for zstandard (pyproject.toml): started
Build on windows-latest	Build executable	2026-03-16T08:30:32.4185828Z   Building wheel for zstandard (pyproject.toml): finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:32.4223857Z   Created wheel for zstandard: filename=zstandard-0.20.0-cp313-cp313-win_amd64.whl size=241824 sha256=7cb00926f7528e5b5fa3bd4630b44f1d7a69733534dca5570c4a3a311dc05cb5
Build on windows-latest	Build executable	2026-03-16T08:30:32.4225326Z   Stored in directory: c:\users\runneradmin\appdata\local\pip\cache\wheels\55\0c\0e\4c8c6663c5e45feeda679c9add126edbf208f37f047bd07b3b
Build on windows-latest	Build executable	2026-03-16T08:30:32.4251763Z Successfully built zstandard
Build on windows-latest	Build executable	2026-03-16T08:30:32.4314068Z Installing collected packages: zstandard, wheel, ordered-set
Build on windows-latest	Build executable	2026-03-16T08:30:32.5768489Z 
Build on windows-latest	Build executable	2026-03-16T08:30:32.5781333Z Successfully installed ordered-set-4.1.0 wheel-0.38.4 zstandard-0.20.0
Build on windows-latest	Build executable	2026-03-16T08:30:34.1910210Z Collecting nuitka
Build on windows-latest	Build executable	2026-03-16T08:30:34.1916328Z   Cloning https://github.com/Nuitka/Nuitka.git/ (to revision 4.0.5) to C:\Users\runneradmin\AppData\Local\Temp\pip-install-v72matj8\nuitka_fc1d5248b8434f66a30b8b440f07784e
Build on windows-latest	Build executable	2026-03-16T08:30:34.2091952Z   Running command git clone --filter=blob:none --quiet https://github.com/Nuitka/Nuitka.git/ 'C:\Users\runneradmin\AppData\Local\Temp\pip-install-v72matj8\nuitka_fc1d5248b8434f66a30b8b440f07784e'
Build on windows-latest	Build executable	2026-03-16T08:30:39.5803102Z   Running command git checkout -q 1860d7b214076e4d01abd36487a25d5dfb335127
Build on windows-latest	Build executable	2026-03-16T08:30:40.1574102Z   Resolved https://github.com/Nuitka/Nuitka.git/ to commit 1860d7b214076e4d01abd36487a25d5dfb335127
Build on windows-latest	Build executable	2026-03-16T08:30:40.1576343Z   Running command git submodule update --init --recursive -q
Build on windows-latest	Build executable	2026-03-16T08:30:40.7085826Z   Installing build dependencies: started
Build on windows-latest	Build executable	2026-03-16T08:30:43.1965338Z   Installing build dependencies: finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:43.1988637Z   Getting requirements to build wheel: started
Build on windows-latest	Build executable	2026-03-16T08:30:44.0001085Z   Getting requirements to build wheel: finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:44.0030013Z   Preparing metadata (pyproject.toml): started
Build on windows-latest	Build executable	2026-03-16T08:30:44.5183553Z   Preparing metadata (pyproject.toml): finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:44.5268919Z Building wheels for collected packages: nuitka
Build on windows-latest	Build executable	2026-03-16T08:30:44.5515140Z   Building wheel for nuitka (pyproject.toml): started
Build on windows-latest	Build executable	2026-03-16T08:30:50.3729361Z   Building wheel for nuitka (pyproject.toml): finished with status 'done'
Build on windows-latest	Build executable	2026-03-16T08:30:50.3801846Z   Created wheel for nuitka: filename=nuitka-4.0.5-cp313-cp313-win_amd64.whl size=3769455 sha256=161110e829530accbf98d7972ae089b9b39bad1cd27ef36d953f4998568edd32
Build on windows-latest	Build executable	2026-03-16T08:30:50.3803656Z   Stored in directory: C:\Users\runneradmin\AppData\Local\Temp\pip-ephem-wheel-cache-db2s3d9p\wheels\1a\4d\fe\15af2ba79d74f80ebdc70e94b53b00ceb9609eae8fedcaf9f4
Build on windows-latest	Build executable	2026-03-16T08:30:50.3936665Z Successfully built nuitka
Build on windows-latest	Build executable	2026-03-16T08:30:50.4079550Z Installing collected packages: nuitka
Build on windows-latest	Build executable	2026-03-16T08:30:53.8164954Z Successfully installed nuitka-4.0.5
Build on windows-latest	Build executable	2026-03-16T08:30:55.0478581Z ##[group]Run actions/cache@v4
Build on windows-latest	Build executable	2026-03-16T08:30:55.0478849Z with:
Build on windows-latest	Build executable	2026-03-16T08:30:55.0479099Z   path: D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache
Build on windows-latest	Build executable	2026-03-16T08:30:55.0479597Z   key: nuitka-caching-Windows-X64-python-3.13-nuitka-25affadeb442cf9916987af6208bb0694c23f11d
Build on windows-latest	Build executable	2026-03-16T08:30:55.0480292Z   restore-keys: nuitka-caching-Windows-X64-python-3.13-
Build on windows-latest	Build executable	nuitka-Windows-X64-python-3.13-
Build on windows-latest	Build executable	nuitka-Windows-X64-
Build on windows-latest	Build executable	
Build on windows-latest	Build executable	2026-03-16T08:30:55.0480790Z   enableCrossOsArchive: false
Build on windows-latest	Build executable	2026-03-16T08:30:55.0481023Z   fail-on-cache-miss: false
Build on windows-latest	Build executable	2026-03-16T08:30:55.0481222Z   lookup-only: false
Build on windows-latest	Build executable	2026-03-16T08:30:55.0481410Z   save-always: false
Build on windows-latest	Build executable	2026-03-16T08:30:55.0481588Z env:
Build on windows-latest	Build executable	2026-03-16T08:30:55.0481765Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Build executable	2026-03-16T08:30:55.0482043Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Build executable	2026-03-16T08:30:55.0482296Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Build executable	2026-03-16T08:30:55.0482589Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Build executable	2026-03-16T08:30:55.0482888Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:55.0483303Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Build executable	2026-03-16T08:30:55.0483725Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:55.0484085Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:55.0484446Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:55.0484815Z   NUITKA_CACHE_DIR: D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache
Build on windows-latest	Build executable	2026-03-16T08:30:55.0485143Z   PYTHON_VERSION: 3.13
Build on windows-latest	Build executable	2026-03-16T08:30:55.0485315Z ##[endgroup]
Build on windows-latest	Build executable	2026-03-16T08:30:55.4849839Z Cache hit for restore-key: nuitka-caching-Windows-X64-python-3.13-nuitka-ad6b8a8db66cf505a65736840d0d6f94c81630da
Build on windows-latest	Build executable	2026-03-16T08:30:56.0741707Z Received 6332949 of 6332949 (100.0%), 13.9 MBs/sec
Build on windows-latest	Build executable	2026-03-16T08:30:56.0744965Z Cache Size: ~6 MB (6332949 B)
Build on windows-latest	Build executable	2026-03-16T08:30:56.0775367Z [command]"C:\Program Files\Git\usr\bin\tar.exe" -xf D:/a/_temp/8c831189-bf32-402d-9741-08b4238be61d/cache.tzst -P -C D:/a/irealstudio/irealstudio --force-local --use-compress-program "zstd -d"
Build on windows-latest	Build executable	2026-03-16T08:30:56.4148604Z Cache restored successfully
Build on windows-latest	Build executable	2026-03-16T08:30:56.4286344Z Cache restored from key: nuitka-caching-Windows-X64-python-3.13-nuitka-ad6b8a8db66cf505a65736840d0d6f94c81630da
Build on windows-latest	Build executable	2026-03-16T08:30:56.4554966Z ##[group]Run set -e
Build on windows-latest	Build executable	2026-03-16T08:30:56.4555546Z [36;1mset -e[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4555699Z [36;1m[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4556029Z [36;1m# Prepare the JSON string for Nuitka, filtering out action-specific keys using Python[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4556454Z [36;1mNUITKA_WORKFLOW_INPUTS=$(echo '{[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4556700Z [36;1m  "nuitka-version": "4.0.5",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4556975Z [36;1m  "script-name": "main.py",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4557226Z [36;1m  "mode": "standalone",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4557488Z [36;1m  "output-filename": "irealstudio.exe",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4557760Z [36;1m  "output-dir": "dist",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4558008Z [36;1m  "windows-console-mode": "disable",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4558291Z [36;1m  "assume-yes-for-downloads": "true",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4558541Z [36;1m  "no-progressbar": "true",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4558764Z [36;1m  "quiet": "true",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4558983Z [36;1m  "follow-imports": "true",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4559219Z [36;1m  "include-data-dir": "locales=locales",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4559498Z [36;1m  "working-directory": ".",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4559728Z [36;1m  "access-token": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4559944Z [36;1m  "python-flag": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4560168Z [36;1m  "python-debug": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4560390Z [36;1m  "enable-plugins": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4560789Z [36;1m  "disable-plugins": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4561006Z [36;1m  "user-plugin": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4561239Z [36;1m  "plugin-no-detection": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4561491Z [36;1m  "module-parameter": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4561706Z [36;1m  "report": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4561913Z [36;1m  "report-diffable": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4562158Z [36;1m  "report-user-provided": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4562387Z [36;1m  "report-template": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4562897Z [36;1m  "show-scons": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4563124Z [36;1m  "show-memory": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4563352Z [36;1m  "include-package-data": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4563686Z [36;1m  "include-data-files": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4564067Z [36;1m  "noinclude-data-files": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4564330Z [36;1m  "include-data-files-external": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4564576Z [36;1m  "include-raw-dir": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4564802Z [36;1m  "include-package": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4565041Z [36;1m  "include-module": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4565275Z [36;1m  "include-plugin-directory": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4565533Z [36;1m  "include-plugin-files": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4565780Z [36;1m  "prefer-source-code": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4566010Z [36;1m  "nofollow-import-to": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4566259Z [36;1m  "user-package-configuration-file": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4566539Z [36;1m  "onefile-tempdir-spec": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4566800Z [36;1m  "onefile-child-grace-time": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4567049Z [36;1m  "onefile-no-compression": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4567319Z [36;1m  "warn-implicit-exceptions": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4567575Z [36;1m  "warn-unusual-code": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4567795Z [36;1m  "nowarn-mnemonic": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4568025Z [36;1m  "deployment": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4568252Z [36;1m  "no-deployment-flag": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4568491Z [36;1m  "output-file": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4568696Z [36;1m  "disable-console": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4569745Z [36;1m  "enable-console": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4569979Z [36;1m  "company-name": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4570193Z [36;1m  "product-name": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4570408Z [36;1m  "file-version": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4570633Z [36;1m  "product-version": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4570855Z [36;1m  "file-description": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4571108Z [36;1m  "copyright": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4571329Z [36;1m  "trademarks": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4571544Z [36;1m  "force-stdout-spec": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4571764Z [36;1m  "force-stderr-spec": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4572050Z [36;1m  "windows-icon-from-ico": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4572309Z [36;1m  "windows-icon-from-exe": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4572601Z [36;1m  "onefile-windows-splash-screen-image": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4572885Z [36;1m  "windows-uac-admin": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4573119Z [36;1m  "windows-uac-uiaccess": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4573364Z [36;1m  "macos-target-arch": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4573595Z [36;1m  "macos-app-icon": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4573832Z [36;1m  "macos-signed-app-name": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4574069Z [36;1m  "macos-app-name": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4574284Z [36;1m  "macos-app-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4574528Z [36;1m  "macos-prohibit-multiple-instances": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4574816Z [36;1m  "macos-sign-identity": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4575062Z [36;1m  "macos-sign-notarization": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4575302Z [36;1m  "macos-app-version": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4575570Z [36;1m  "macos-app-protected-resource": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4575858Z [36;1m  "macos-sign-keyring-filename": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4576126Z [36;1m  "macos-sign-keyring-password": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4576384Z [36;1m  "linux-icon": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4577084Z [36;1m  "clang": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4577287Z [36;1m  "mingw64": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4577481Z [36;1m  "msvc": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4577680Z [36;1m  "jobs": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4577868Z [36;1m  "lto": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4578056Z [36;1m  "static-libpython": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4578303Z [36;1m  "cf-protection": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4578527Z [36;1m  "debug": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4578753Z [36;1m  "no-debug-immortal-assumptions": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4579029Z [36;1m  "no-debug-c-warnings": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4579266Z [36;1m  "unstripped": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4579481Z [36;1m  "trace-execution": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4579699Z [36;1m  "xml": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4579900Z [36;1m  "experimental": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4580117Z [36;1m  "low-memory": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4580347Z [36;1m  "noinclude-setuptools-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4580617Z [36;1m  "noinclude-pytest-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4580869Z [36;1m  "noinclude-unittest-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4581114Z [36;1m  "noinclude-pydoc-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4581374Z [36;1m  "noinclude-IPython-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4581623Z [36;1m  "noinclude-dask-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4581860Z [36;1m  "noinclude-numba-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4582114Z [36;1m  "noinclude-default-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4582373Z [36;1m  "noinclude-custom-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4582657Z [36;1m  "include-pickle-support-module": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4583217Z [36;1m  "include-pmw-blt": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4583464Z [36;1m  "include-pmw-color": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4583743Z [36;1m  "tk-library-dir": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4584090Z [36;1m  "tcl-library-dir": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4584329Z [36;1m  "include-qt-plugins": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4584569Z [36;1m  "noinclude-qt-plugins": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4584835Z [36;1m  "noinclude-qt-translations": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4585243Z [36;1m  "upx-binary": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4585464Z [36;1m  "upx-disable-cache": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4585720Z [36;1m  "anti-debugger-debugging": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4585957Z [36;1m  "auto-update-url-spec": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4586202Z [36;1m  "auto-update-debug": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4586439Z [36;1m  "data-hiding-salt-value": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4586727Z [36;1m  "embed-data-files-compile-time-pattern": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4587104Z [36;1m  "embed-data-files-run-time-pattern": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4587440Z [36;1m  "embed-data-files-qt-resource-pattern": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4587736Z [36;1m  "embed-debug-qt-resources": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4587995Z [36;1m  "windows-signing-tool": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4588243Z [36;1m  "windows-certificate-name": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4588493Z [36;1m  "windows-certificate-sha1": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4588763Z [36;1m  "windows-certificate-filename": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4589053Z [36;1m  "windows-certificate-password": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4589328Z [36;1m  "windows-signed-content-comment": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4589594Z [36;1m  "encryption-key": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4589824Z [36;1m  "encrypt-stdout": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4590045Z [36;1m  "encrypt-stderr": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4590253Z [36;1m  "encrypt-debug-init": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4590507Z [36;1m  "encrypt-crypto-package": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4590754Z [36;1m  "windows-service-name": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4590997Z [36;1m  "windows-service-grace-time": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4591263Z [36;1m  "windows-service-start-mode": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4591516Z [36;1m  "windows-service-cli": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4591750Z [36;1m  "disable-cache": "",[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4591963Z [36;1m  "caching-key": "caching"[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4592885Z [36;1m}' | python -c "import sys, json; data = json.load(sys.stdin); [data.pop(k, None) for k in ['nuitka-version', 'working-directory', 'access-token', 'disable-cache', 'caching-key']]; json.dump(data, sys.stdout, ensure_ascii=False)")[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4593702Z [36;1m[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4593947Z [36;1m# Pass the filtered JSON to Nuitka via an environment variable[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4594283Z [36;1mexport NUITKA_WORKFLOW_INPUTS[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4594565Z [36;1mpython -m nuitka --github-workflow-options[0m
Build on windows-latest	Build executable	2026-03-16T08:30:56.4610142Z shell: C:\Program Files\Git\bin\bash.EXE --noprofile --norc -e -o pipefail {0}
Build on windows-latest	Build executable	2026-03-16T08:30:56.4610519Z env:
Build on windows-latest	Build executable	2026-03-16T08:30:56.4610704Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Build executable	2026-03-16T08:30:56.4610963Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Build executable	2026-03-16T08:30:56.4611238Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Build executable	2026-03-16T08:30:56.4611524Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Build executable	2026-03-16T08:30:56.4611851Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:56.4612278Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Build executable	2026-03-16T08:30:56.4612696Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:56.4613078Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:56.4613442Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Build executable	2026-03-16T08:30:56.4613834Z   NUITKA_CACHE_DIR: D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache
Build on windows-latest	Build executable	2026-03-16T08:30:56.4614165Z   PYTHON_VERSION: 3.13
Build on windows-latest	Build executable	2026-03-16T08:30:56.4614353Z   PYTHONUTF8: 1
Build on windows-latest	Build executable	2026-03-16T08:30:56.4614530Z ##[endgroup]
Build on windows-latest	Package artifact (Windows)	﻿2026-03-16T08:32:38.9517708Z ##[group]Run # Nuitka names the standalone output directory after the script: main.dist
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9518374Z [36;1m# Nuitka names the standalone output directory after the script: main.dist[0m
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9518891Z [36;1mRename-Item -Path "dist\main.dist" -NewName "irealstudio-windows"[0m
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9519461Z [36;1mCompress-Archive -Path "dist\irealstudio-windows" -DestinationPath "dist\irealstudio-windows.zip"[0m
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9594292Z shell: C:\Program Files\PowerShell\7\pwsh.EXE -command ". '{0}'"
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9594676Z env:
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9594959Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9595341Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9595598Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9595861Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9596166Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9596772Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9597236Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9597604Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9597966Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9598357Z   NUITKA_CACHE_DIR: D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9598667Z   PYTHON_VERSION: 3.13
Build on windows-latest	Package artifact (Windows)	2026-03-16T08:32:38.9598844Z ##[endgroup]
Build on windows-latest	Upload artifact	﻿2026-03-16T08:32:40.5613335Z ##[group]Run actions/upload-artifact@v7
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5613738Z with:
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5613942Z   name: irealstudio-windows
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5614179Z   path: dist/irealstudio-windows.zip
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5614410Z   if-no-files-found: error
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5614626Z   compression-level: 6
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5614819Z   overwrite: false
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5615007Z   include-hidden-files: false
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5615205Z   archive: true
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5615360Z env:
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5615544Z   UV_TOOL_BIN_DIR: D:\a\_temp\uv-tool-bin-dir
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5615793Z   UV_TOOL_DIR: D:\a\_temp\uv-tool-dir
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5616068Z   UV_PYTHON_INSTALL_DIR: D:\a\_temp\uv-python-dir
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5616345Z   UV_CACHE_DIR: D:\a\_temp\setup-uv-cache
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5616897Z   pythonLocation: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5617326Z   PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.13.12\x64/lib/pkgconfig
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5617797Z   Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5618354Z   Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5618733Z   Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.13.12\x64
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5619138Z   NUITKA_CACHE_DIR: D:\a\_actions\Nuitka\Nuitka-Action\v1.4/nuitka/cache
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5619454Z   PYTHON_VERSION: 3.13
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.5619654Z ##[endgroup]
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.7470961Z With the provided path, there will be 1 file uploaded
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.7476862Z Artifact name is valid!
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.7477658Z Root directory input is valid!
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.9031341Z Uploading artifact: irealstudio-windows.zip
Build on windows-latest	Upload artifact	2026-03-16T08:32:40.9075374Z Beginning upload of artifact content to blob storage
Build on windows-latest	Upload artifact	2026-03-16T08:32:41.9503643Z Uploaded bytes 8388608
Build on windows-latest	Upload artifact	2026-03-16T08:32:41.9984069Z Uploaded bytes 8587470
Build on windows-latest	Upload artifact	2026-03-16T08:32:42.0437675Z Finished uploading artifact content to blob storage!
Build on windows-latest	Upload artifact	2026-03-16T08:32:42.0439399Z SHA256 digest of uploaded artifact is 11d680b3c6882eb8227778fb9a73f3c8c05e9d921450092361c82da8b6d7f41e
Build on windows-latest	Upload artifact	2026-03-16T08:32:42.0440226Z Finalizing artifact upload
Build on windows-latest	Upload artifact	2026-03-16T08:32:42.2023790Z Artifact irealstudio-windows successfully finalized. Artifact ID 5939578256
Build on windows-latest	Upload artifact	2026-03-16T08:32:42.2027535Z Artifact irealstudio-windows has been successfully uploaded! Final size is 8587470 bytes. Artifact ID is 5939578256
Build on windows-latest	Upload artifact	2026-03-16T08:32:42.2034430Z Artifact download URL: https://github.com/denizsincar29/irealstudio/actions/runs/23134569397/artifacts/5939578256
Build on windows-latest	Post Build executable	﻿2026-03-16T08:32:42.2572901Z ##[warning]Unexpected input(s) 'output-filename', 'no-progressbar', 'follow-imports', valid inputs are ['working-directory', 'nuitka-version', 'script-name', 'access-token', 'mode', 'python-flag', 'python-debug', 'enable-plugins', 'disable-plugins', 'user-plugin', 'plugin-no-detection', 'module-parameter', 'report', 'report-diffable', 'report-user-provided', 'report-template', 'quiet', 'show-scons', 'show-memory', 'include-package-data', 'include-data-files', 'include-data-dir', 'noinclude-data-files', 'include-data-files-external', 'include-raw-dir', 'include-package', 'include-module', 'include-plugin-directory', 'include-plugin-files', 'prefer-source-code', 'nofollow-import-to', 'user-package-configuration-file', 'onefile-tempdir-spec', 'onefile-child-grace-time', 'onefile-no-compression', 'warn-implicit-exceptions', 'warn-unusual-code', 'assume-yes-for-downloads', 'nowarn-mnemonic', 'deployment', 'no-deployment-flag', 'output-dir', 'output-file', 'disable-console', 'enable-console', 'company-name', 'product-name', 'file-version', 'product-version', 'file-description', 'copyright', 'trademarks', 'force-stdout-spec', 'force-stderr-spec', 'windows-console-mode', 'windows-icon-from-ico', 'windows-icon-from-exe', 'onefile-windows-splash-screen-image', 'windows-uac-admin', 'windows-uac-uiaccess', 'macos-target-arch', 'macos-app-icon', 'macos-signed-app-name', 'macos-app-name', 'macos-app-mode', 'macos-prohibit-multiple-instances', 'macos-sign-identity', 'macos-sign-notarization', 'macos-app-version', 'macos-app-protected-resource', 'macos-sign-keyring-filename', 'macos-sign-keyring-password', 'linux-icon', 'clang', 'mingw64', 'msvc', 'jobs', 'lto', 'static-libpython', 'cf-protection', 'debug', 'no-debug-immortal-assumptions', 'no-debug-c-warnings', 'unstripped', 'trace-execution', 'xml', 'experimental', 'low-memory', 'noinclude-setuptools-mode', 'noinclude-pytest-mode', 'noinclude-unittest-mode', 'noinclude-pydoc-mode', 'noinclude-IPython-mode', 'noinclude-dask-mode', 'noinclude-numba-mode', 'noinclude-default-mode', 'noinclude-custom-mode', 'include-pickle-support-module', 'include-pmw-blt', 'include-pmw-color', 'tk-library-dir', 'tcl-library-dir', 'include-qt-plugins', 'noinclude-qt-plugins', 'noinclude-qt-translations', 'upx-binary', 'upx-disable-cache', 'anti-debugger-debugging', 'auto-update-url-spec', 'auto-update-debug', 'data-hiding-salt-value', 'embed-data-files-compile-time-pattern', 'embed-data-files-run-time-pattern', 'embed-data-files-qt-resource-pattern', 'embed-debug-qt-resources', 'windows-signing-tool', 'windows-certificate-name', 'windows-certificate-sha1', 'windows-certificate-filename', 'windows-certificate-password', 'windows-signed-content-comment', 'encryption-key', 'encrypt-stdout', 'encrypt-stderr', 'encrypt-debug-init', 'encrypt-crypto-package', 'windows-service-name', 'windows-service-grace-time', 'windows-service-start-mode', 'windows-service-cli', 'disable-cache', 'caching-key']
Build on windows-latest	Post Build executable	2026-03-16T08:32:42.2587647Z Post job cleanup.
Build on windows-latest	Post Build executable	2026-03-16T08:32:42.2725997Z Post job cleanup.
Build on windows-latest	Post Build executable	2026-03-16T08:32:42.5569602Z [command]"C:\Program Files\Git\usr\bin\tar.exe" --posix -cf cache.tzst --exclude cache.tzst -P -C D:/a/irealstudio/irealstudio --files-from manifest.txt --force-local --use-compress-program "zstd -T0"
Build on windows-latest	Post Build executable	2026-03-16T08:32:43.8858581Z Sent 12144828 of 12144828 (100.0%), 15.9 MBs/sec
Build on windows-latest	Post Build executable	2026-03-16T08:32:44.0138231Z Cache saved with key: nuitka-caching-Windows-X64-python-3.13-nuitka-25affadeb442cf9916987af6208bb0694c23f11d
Build on windows-latest	Post Set up Python	﻿2026-03-16T08:32:44.0422968Z Post job cleanup.
Build on windows-latest	Post Install uv	﻿2026-03-16T08:32:44.2131394Z Post job cleanup.
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.3724411Z UV_CACHE_DIR is already set to D:\a\_temp\setup-uv-cache
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.3732916Z UV_PYTHON_INSTALL_DIR is already set to D:\a\_temp\uv-python-dir
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.3744193Z Pruning cache...
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.3763441Z (node:3524) [DEP0040] DeprecationWarning: The `punycode` module is deprecated. Please use a userland alternative instead.
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.3764536Z (Use `node --trace-deprecation ...` to show where the warning was created)
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.3804138Z [command]C:\hostedtoolcache\windows\uv\0.10.10\x86_64\uv.exe cache prune --ci --force
Build on windows-latest	Post Install uv	2026-03-16T08:32:44.4005943Z Pruning cache at: D:\a\_temp\setup-uv-cache
Build on windows-latest	Post Install uv	2026-03-16T08:32:45.0842843Z Removed 7783 files (216.8MiB)
Build on windows-latest	Post Install uv	2026-03-16T08:32:45.0891163Z Including uv cache path: D:\a\_temp\setup-uv-cache
Build on windows-latest	Post Install uv	2026-03-16T08:32:45.1899096Z [command]"C:\Program Files\Git\usr\bin\tar.exe" --posix -cf cache.tzst --exclude cache.tzst -P -C D:/a/irealstudio/irealstudio --files-from manifest.txt --force-local --use-compress-program "zstd -T0"
Build on windows-latest	Post Install uv	2026-03-16T08:32:45.4309302Z (node:3524) [DEP0169] DeprecationWarning: `url.parse()` behavior is not standardized and prone to errors that have security implications. Use the WHATWG URL API instead. CVEs are not issued for `url.parse()` vulnerabilities.
Build on windows-latest	Post Install uv	2026-03-16T08:32:45.8979176Z Sent 5987436 of 5987436 (100.0%), 12.0 MBs/sec
Build on windows-latest	Post Install uv	2026-03-16T08:32:45.9929617Z uv cache saved with key: setup-uv-2-x86_64-pc-windows-msvc-windows-2025-3.13.12-pruned-0be47c2d893585801c7593bdf6dd290d6a59af55cd26162ed9a76d0dbf26e2ce
Build on windows-latest	Post Checkout	﻿2026-03-16T08:32:46.0776580Z Post job cleanup.
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.2596182Z [command]"C:\Program Files\Git\bin\git.exe" version
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.2866525Z git version 2.53.0.windows.1
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.2945563Z Temporarily overriding HOME='D:\a\_temp\789614bc-91c5-4839-af08-888c03384bca' before making global git config changes
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.2946816Z Adding repository directory to the temporary git global config as a safe directory
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.2957431Z [command]"C:\Program Files\Git\bin\git.exe" config --global --add safe.directory D:\a\irealstudio\irealstudio
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.3265616Z Removing SSH command configuration
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.3277149Z [command]"C:\Program Files\Git\bin\git.exe" config --local --name-only --get-regexp core\.sshCommand
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.3610955Z [command]"C:\Program Files\Git\bin\git.exe" submodule foreach --recursive "sh -c \"git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :\""
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.9112096Z Removing HTTP extra header
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.9124606Z [command]"C:\Program Files\Git\bin\git.exe" config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
Build on windows-latest	Post Checkout	2026-03-16T08:32:46.9453345Z [command]"C:\Program Files\Git\bin\git.exe" submodule foreach --recursive "sh -c \"git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :\""
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.4938686Z Removing includeIf entries pointing to credentials config files
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.4951161Z [command]"C:\Program Files\Git\bin\git.exe" config --local --name-only --get-regexp ^includeIf\.gitdir:
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5221487Z includeif.gitdir:D:/a/irealstudio/irealstudio/.git.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5222164Z includeif.gitdir:D:/a/irealstudio/irealstudio/.git/worktrees/*.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5222545Z includeif.gitdir:/github/workspace/.git.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5222886Z includeif.gitdir:/github/workspace/.git/worktrees/*.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5273580Z [command]"C:\Program Files\Git\bin\git.exe" config --local --get-all includeif.gitdir:D:/a/irealstudio/irealstudio/.git.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5558025Z D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5609918Z [command]"C:\Program Files\Git\bin\git.exe" config --local --unset includeif.gitdir:D:/a/irealstudio/irealstudio/.git.path D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.5967443Z [command]"C:\Program Files\Git\bin\git.exe" config --local --get-all includeif.gitdir:D:/a/irealstudio/irealstudio/.git/worktrees/*.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.6241736Z D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.6290177Z [command]"C:\Program Files\Git\bin\git.exe" config --local --unset includeif.gitdir:D:/a/irealstudio/irealstudio/.git/worktrees/*.path D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.6603505Z [command]"C:\Program Files\Git\bin\git.exe" config --local --get-all includeif.gitdir:/github/workspace/.git.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.6870976Z /github/runner_temp/git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.6920807Z [command]"C:\Program Files\Git\bin\git.exe" config --local --unset includeif.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.7248226Z [command]"C:\Program Files\Git\bin\git.exe" config --local --get-all includeif.gitdir:/github/workspace/.git/worktrees/*.path
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.7518475Z /github/runner_temp/git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.7568120Z [command]"C:\Program Files\Git\bin\git.exe" config --local --unset includeif.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config
Build on windows-latest	Post Checkout	2026-03-16T08:32:47.7884865Z [command]"C:\Program Files\Git\bin\git.exe" submodule foreach --recursive "git config --local --show-origin --name-only --get-regexp remote.origin.url"
Build on windows-latest	Post Checkout	2026-03-16T08:32:48.3357626Z Removing credentials config 'D:\a\_temp\git-credentials-c9a19b36-3380-4a1e-94dd-d8f2bd33a32a.config'
Build on windows-latest	Complete job	﻿2026-03-16T08:32:48.3554924Z Cleaning up orphan processes
Build on windows-latest	Complete job	2026-03-16T08:32:48.3802230Z Terminate orphan process: pid (3364) (vctip)
Build on windows-latest	Complete job	2026-03-16T08:32:48.3816541Z ##[warning]Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work as expected: actions/cache@v4. Actions will be forced to run with Node.js 24 by default starting June 2nd, 2026. Please check if updated versions of these actions are available that support Node.js 24. To opt into Node.js 24 now, set the FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true environment variable on the runner or in your workflow file. Once Node.js 24 becomes the default, you can temporarily opt out by setting ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

```