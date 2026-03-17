# Tasks

Example context:
- Bars 1 to 8 are set to be repeated with volta / ending on bar 7 (bars 7-8 are ending 1, 15-16 ending2).
- Bars 9 to 14 are virtual aria where the ui shows cords that are repeated from bars 1 to 6, but in the app there are no cords at this position.

When moving left using left arrow from the repeat virtual aria bar 9, the cursor must move to the previous cord in bar 6 beat 3, but it moves to bar 6 beat 1 instead. Probably it just searches beat 1 when moving from virtual aria to the real one, but it should search for the closest cord to the current position instead. There is a method for that in CordProgression object.
The CordProgression object must support virtual arias by nature, and the find closest cord to the left method must concidder virtual arias. Than implement it's support in the app / ui.
How ever I don't know how good it works with right arrow navigation, probably since first beat comes first, it works ok.