# Tasks

Here are the prioritized tasks for refinement and correction, focusing on Virtual Area behavior and translations:

1.  **Virtual Area Functionality Anomalies:**

    *   **Context:** In the chord progression editor, virtual areas represent repeated sections (e.g., bars 9-14 as a virtual repeat of bars 1-6) that are visually displayed but not explicitly stored in the chord array. Voltas (e.g., Volta 1: bars 7-8, Volta 2: bars 15-16) are distinct sections outside the virtual area.

    *   **Navigation Issues:**
        *   **Entry Blockage:** When navigating from the last chord of Volta 1 (e.g., bar 8, beat 3) using the *modifier-less* right arrow (standard chord navigation), the cursor fails to advance into the subsequent virtual area (Repeat 2). Navigation *can* enter the virtual area using modifier keys (Ctrl/Alt + arrows for measure/beat navigation).
        *   **Directional Lock:** Once inside a virtual area (entered via modifier navigation), the *modifier-less* left arrow correctly navigates back to Volta 1, but the *modifier-less* right arrow again fails to advance, effectively blocking forward movement.
        *   **Mode Shift:** While within a virtual area, *modifier-less* left/right arrows (intended for chord-by-chord navigation) incorrectly switch to measure-by-measure navigation or skip chords that do not fall on the first beat.

    *   **In-Recording Playback Glitch:**
        *   During recording with a metronome, upon reaching a virtual area, the program plays back the previously recorded repeat. However, chords within this virtual area are *only audibly played on the first beat* during this "in-recording playback" mode.
*   **Note:** Normal, non-recording playback correctly plays all chords on their respective beats in all areas. This single playback discrepancy in virtual areas during recording is likely a core issue.

2.  **Russian Translation Corrections:**

    *   Review all Russian translations and update the following terms across the application:
        *   Change "Метка раздела" to "Метка части".
        *   Change "функция" to "тип аккорда".
```


## Release tag script
Change release_tag.py to not make a draft json, but write news.md and changelog.md and change version.py. And the script checks version.py and the last tag, and if version is greater than the last tag, it understands that it is a draft and right away publishes the release. If not, it asks for version and changelog entry and than, as now, drafts or publishes the release depending on the branch.

