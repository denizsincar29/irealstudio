# bug
The workflow that releases the app generated errors and warnings, we need to fix them. Search the web for latest actions and ways to release python projects with nuitka and uv.
```
2 errors and 2 warnings
Build on macos-latest
Process completed with exit code 1.
Build on windows-latest
No files were found with the provided path: dist/irealstudio.exe. No artifacts will be uploaded.
Show more
 
Build on macos-latest
Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work as expected: actions/checkout@v4, actions/setup-python@v5, astral-sh/setup-uv@v6. Actions will be forced to run with Node.js 24 by default starting June 2nd, 2026. Please check if updated versions of these actions are available that support Node.js 24. To opt into Node.js 24 now, set the FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true environment variable on the runner or in your workflow file. Once Node.js 24 becomes the default, you can temporarily opt out by setting ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
```