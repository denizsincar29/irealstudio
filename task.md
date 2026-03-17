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
        *   The standard playback mode however works correctly, playing all chords in the virtual area as expected.