---
name: releasing
description: instructions for making a version release draft of the project. Use this skill when you are ready to make a release draft of the project.
---

To create a version release draft of the project, follow these steps:
1. Install UV package manager for python if you haven't already.
2. Write the breaf changelog entry of the news.md file at the root of the project. This should be a brief summary of the changes made in this release, without going into technical details. It should be concise and easy to understand for users who may not be familiar with the technical aspects of the project.
3. run `uv run tag_release.py -v <version>` to create a release draft.

That's it. When the user merges your pull request, he'll run the same command on his main branch and it will publish the release.