"""
chords.py - Data model for chord progressions, including:
- Positions, time signatures
- Section marks (*A, *B, etc.)
- Volta/ending brackets for repeats
- JSON serialization
- iReal Pro export
- Own chord recognition system (no pychord dependency)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import total_ordering

NOTE_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Note names used when the current key uses sharps instead of flats.
NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Unified note-name → pitch-class mapping that accepts both flat and sharp
# spellings.  This is the single source of truth used by the chord-recognition
# engine so that notes spelled with sharps (C#, F#, …) are treated identically
# to their enharmonic flat equivalents (Db, Gb, …).
_NOTE_TO_PC: dict[str, int] = {
    'C': 0,  'C#': 1,  'Db': 1,
    'D': 2,  'D#': 3,  'Eb': 3,
    'E': 4,
    'F': 5,  'F#': 6,  'Gb': 6,
    'G': 7,  'G#': 8,  'Ab': 8,
    'A': 9,  'A#': 10, 'Bb': 10,
    'B': 11,
}

# Keys that prefer sharp spellings (major and their relative minors).
# Minor keys are stored with the iReal Pro "-" suffix.
# Only keys that appear in pyrealpro.KEY_SIGNATURES are listed here to avoid
# drift between the two modules.
_SHARP_KEYS: frozenset[str] = frozenset({
    'C', 'G', 'D', 'A', 'E', 'B',          # major sharp keys in iReal Pro
    'A-', 'E-', 'B-', 'F#-', 'C#-', 'G#-', # minor sharp keys in iReal Pro
})


def get_note_names_for_key(key: str) -> list[str]:
    """Return the note-name list (flat or sharp) appropriate for *key*.

    Keys that use sharp accidentals (C, G, D, A, E, B, F# major and their
    relative minors) get ``NOTE_NAMES_SHARP``; all others get ``NOTE_NAMES``
    (flat spellings).
    """
    return NOTE_NAMES_SHARP if key in _SHARP_KEYS else NOTE_NAMES


# ---------------------------------------------------------------------------
# Chord recognition system
# ---------------------------------------------------------------------------

# Semitones from root for each simple (major-scale) degree
_DEGREE_TO_ST: dict[int, int] = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}


def _identify_chord_name(notes: list[str]) -> str | None:
    """
    Identify a chord name from pitch-class note names (root = first note).

    Accepts both flat spellings (Bb, Eb, …) and sharp spellings (A#, D#, …).
    The root of the returned name uses the same spelling as the first element
    of *notes* so that the caller's preferred enharmonic is preserved.

    Algorithm (see task.md):
    1. Root is the lowest (first) note.
    2. Calculate semitone intervals from root (mod 12).
    3. Apply validation rules to disambiguate enharmonic spellings.
    4. Return the chord name string.
    """
    # Deduplicate while preserving order; accept all known note spellings.
    seen: set[str] = set()
    clean: list[str] = []
    for n in notes:
        if n in _NOTE_TO_PC and n not in seen:
            seen.add(n)
            clean.append(n)
    if not clean:
        return None

    root = clean[0]
    root_pc = _NOTE_TO_PC[root]

    # Semitone interval set (mod 12, excluding 0 = root)
    ivals: set[int] = set()
    for n in clean[1:]:
        st = (_NOTE_TO_PC[n] - root_pc) % 12
        if st != 0:
            ivals.add(st)

    # Raw interval flags
    has_min3    = 3  in ivals   # semitone 3: minor 3rd or #9
    has_maj3    = 4  in ivals   # semitone 4: major 3rd
    has_4th     = 5  in ivals   # semitone 5: perfect 4th (sus4)
    has_tritone = 6  in ivals   # semitone 6: tritone (b5 or #11)
    has_5th     = 7  in ivals   # semitone 7: perfect 5th
    has_aug5    = 8  in ivals   # semitone 8: augmented 5th
    has_6th     = 9  in ivals   # semitone 9: major 6th / dim7
    has_b7      = 10 in ivals   # semitone 10: dominant/minor 7th
    has_maj7    = 11 in ivals   # semitone 11: major 7th
    has_b9      = 1  in ivals   # semitone 1: b9
    has_nat9    = 2  in ivals   # semitone 2: natural 9

    # --- Validation rule 1 ---
    # If both b3 (3 st) and maj3 (4 st) present → the 3-st interval is #9
    sharp9 = has_min3 and has_maj3
    min3   = has_min3 and not has_maj3   # genuine minor third

    # --- Validation rule 2 ---
    # If (maj7 or perfect 5th) present along with tritone → tritone is #11
    sharp11 = has_tritone and (has_maj7 or has_5th)
    flat5   = has_tritone and not sharp11

    # --- Validation rule 3 ---
    # If perfect 4th is present, chord is sus4 (no thirds in sus4)
    sus4 = has_4th

    # ================================================================
    # Chord-type identification
    # ================================================================

    def exts_str(parts: list[str]) -> str:
        return f"({''.join(parts)})" if parts else ''

    if sus4:
        if has_b7:
            base = root + '7sus4'
        elif has_maj7:
            base = root + 'maj7sus4'
        else:
            base = root + 'sus4'
        exts: list[str] = []
        if has_b9:
            exts.append('b9')
        if has_6th:
            exts.append('13')
        return base + exts_str(exts)

    if min3 and flat5:
        # Diminished family
        if has_b7:
            # Half-diminished (m7b5)
            base = root + 'm7b5'
            exts = []
            if has_b9:
                exts.append('b9')
            elif has_nat9:
                exts.append('9')
            return base + exts_str(exts)
        if has_6th:
            # Diminished seventh (bb7 = 9 semitones = major 6th)
            return root + 'dim7'
        return root + 'dim'

    if min3:
        # Minor family
        if has_maj7:
            base = root + 'mM7'
        elif has_b7:
            base = root + 'm7'
        elif has_aug5:
            return root + 'm#5'
        else:
            base = root + 'm'
        exts = []
        if has_nat9:
            exts.append('9')
        if sharp11:
            exts.append('#11')
        if has_6th:
            exts.append('13')
        return base + exts_str(exts)

    if has_maj3 and has_aug5 and not has_5th:
        # Augmented family
        if has_b7:
            return root + 'aug7'
        if has_maj7:
            return root + 'augM7'
        return root + 'aug'

    if has_maj3:
        # Major family
        if has_b7:
            base = root + '7'
            exts = []
            if has_b9:
                exts.append('b9')
            elif sharp9:
                exts.append('#9')
            elif has_nat9:
                exts.append('9')
            if flat5:
                exts.append('b5')
            if sharp11:
                exts.append('#11')
            if has_6th:
                exts.append('13')
            return base + exts_str(exts)
        if has_maj7:
            base = root + 'maj7'
            exts = []
            if has_nat9:
                exts.append('9')
            if sharp11:
                exts.append('#11')
            if has_6th:
                exts.append('13')
            return base + exts_str(exts)
        # Major triad with optional added tones
        if has_nat9 and has_6th:
            return root + '6/9'
        if has_6th:
            return root + '6'
        if has_nat9:
            return root + 'add9'
        return root

    # No recognizable third — return root (power chord / single note)
    return root


class Chord:
    """
    A chord with a name and optionally its constituent notes.

    The chord name is the canonical string representation (e.g. 'Cmaj7', 'Am7').
    When constructed from MIDI notes, the notes are stored and enable
    has_degree() / get_degree() queries.
    """

    def __init__(self, name: str, notes: list[str] | None = None) -> None:
        """
        Parameters
        ----------
        name  : Chord name string, e.g. 'Cmaj7', 'Am7', 'G7'.
        notes : Optional pitch-class note names ordered lowest to highest.
                Enables has_degree() / get_degree() when provided.
        """
        self._name = name
        self._notes: list[str] = list(notes) if notes else []
        if self._notes and self._notes[0] in _NOTE_TO_PC:
            self._root_pc: int = _NOTE_TO_PC[self._notes[0]]
            self._ivals: frozenset[int] = frozenset(
                (_NOTE_TO_PC[n] - self._root_pc) % 12
                for n in self._notes
                if n in _NOTE_TO_PC
            )
        else:
            self._root_pc = -1
            self._ivals = frozenset()

    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """The canonical chord name, e.g. 'Cmaj7', 'Am7'."""
        return self._name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"Chord({self._name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Chord):
            return self._name == other._name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)

    # ------------------------------------------------------------------
    # Degree helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_degree(degree: int) -> int:
        """Fold extended octave degrees to simple ones (9→2, 11→4, 13→6)."""
        return degree - 7 if degree >= 8 else degree

    def has_degree(self, degree: int) -> bool:
        """Return True if the chord contains a note at *degree* (1-based)."""
        if not self._ivals:
            return False
        st = _DEGREE_TO_ST.get(self._norm_degree(degree))
        return st is not None and st in self._ivals

    def get_degree(self, degree: int) -> str | None:
        """Return the note name for *degree*, or None if absent."""
        if self._root_pc < 0:
            return None
        st = _DEGREE_TO_ST.get(self._norm_degree(degree))
        if st is None:
            return None
        for note in self._notes:
            if note in _NOTE_TO_PC and (_NOTE_TO_PC[note] - self._root_pc) % 12 == st:
                return note
        return None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_notes(cls, notes: list[str]) -> Chord | None:
        """Identify a chord from pitch-class note names (root = first/lowest)."""
        name = _identify_chord_name(notes)
        return cls(name, notes) if name else None

# iReal Pro rehearsal marks supported by the app (S key + letter)
SECTION_KEYS = {
    'a': '*A',
    'b': '*B',
    'c': '*C',
    'd': '*D',
    'v': '*V',
    'i': '*i',
}


@dataclass
class TimeSignature:
    numerator: int
    denominator: int

    @classmethod
    def from_string(cls, time_signature_str: str) -> TimeSignature:
        numerator, denominator = map(int, time_signature_str.split('/'))
        return cls(numerator, denominator)

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"


@total_ordering
@dataclass
class Position:
    measure: int
    beat: int
    time_signature: TimeSignature = field(default_factory=lambda: TimeSignature(4, 4))

    def __str__(self) -> str:
        return f"{self.measure}:{self.beat}"

    @property
    def beat_from_start(self) -> int:
        return (self.measure - 1) * self.time_signature.numerator + self.beat

    def set_beat_from_start(self, total_beats: int):
        self.measure = (total_beats - 1) // self.time_signature.numerator + 1
        self.beat = (total_beats - 1) % self.time_signature.numerator + 1

    def new_from_beat_from_start(self, total_beats: int) -> Position:
        measure = (total_beats - 1) // self.time_signature.numerator + 1
        beat = (total_beats - 1) % self.time_signature.numerator + 1
        return Position(measure, beat, self.time_signature)

    def __add__(self, other: int) -> Position:
        total_beats = self.beat_from_start + other
        return self.new_from_beat_from_start(total_beats)

    def __sub__(self, other: int) -> Position:
        total_beats = self.beat_from_start - other
        if total_beats < 1:
            total_beats = 1
        return self.new_from_beat_from_start(total_beats)

    def __rshift__(self, other: int) -> Position:
        return Position(self.measure + other, self.beat, self.time_signature)

    def __lshift__(self, other: int) -> Position:
        new_measure = self.measure - other
        if new_measure < 1:
            new_measure = 1
        return Position(new_measure, self.beat, self.time_signature)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return (self.measure == other.measure and
                self.beat == other.beat and
                self.time_signature == other.time_signature)

    def __lt__(self, other) -> bool:
        if self.measure == other.measure:
            return self.beat < other.beat
        return self.measure < other.measure

    def __hash__(self):
        return hash((self.measure, self.beat))


@dataclass
class SectionMark:
    """A rehearsal / section mark at a specific measure (e.g. *A, *B, *i, *V)."""
    measure: int
    mark: str  # iReal Pro mark string, e.g. '*A', '*B', '*i'

    def to_dict(self) -> dict:
        return {'measure': self.measure, 'mark': self.mark}

    @classmethod
    def from_dict(cls, d: dict) -> SectionMark:
        return cls(d['measure'], d['mark'])


@dataclass
class VoltaBracket:
    """
    Represents a first/second-ending repeat bracket.

    Layout in the progression:
      [ repeat_start ... ending1_start-1 | N1 ending1_start ... ending1_end }
        N2 ending2_start ... ]

    Measures ending1_end+1 .. ending2_start-1 are 'hidden' (empty in the
    ChordProgression object) – they represent the body of the repeated section
    and are NOT written to iReal Pro output.
    """
    repeat_start: int       # first measure of the repeated section (where { goes)
    ending1_start: int      # first measure of ending 1  (N1)
    ending1_end: int = 0    # last measure of ending 1   (where } goes); 0 = not set
    ending2_start: int = 0  # first measure of ending 2  (N2); 0 = not set

    def is_complete(self) -> bool:
        return self.ending1_end > 0 and self.ending2_start > 0

    def hidden_range(self) -> tuple[int, int] | None:
        """Return the (start, end) measure range that is hidden between endings."""
        if not self.is_complete():
            return None
        # measures between end of ending 1 and start of ending 2
        hidden_start = self.ending1_end + 1
        hidden_end = self.ending2_start - 1
        if hidden_start > hidden_end:
            return None
        return hidden_start, hidden_end

    def to_dict(self) -> dict:
        return {
            'repeat_start': self.repeat_start,
            'ending1_start': self.ending1_start,
            'ending1_end': self.ending1_end,
            'ending2_start': self.ending2_start,
        }

    @classmethod
    def from_dict(cls, d: dict) -> VoltaBracket:
        return cls(
            d['repeat_start'],
            d['ending1_start'],
            d.get('ending1_end', 0),
            d.get('ending2_start', 0),
        )


# ---------------------------------------------------------------------------
# iReal Pro chord-name translation
# ---------------------------------------------------------------------------

# All valid pitch-class roots in both flat and sharp spellings, ordered
# longest-first so the prefix scan always tries two-char roots before one-char.
_ALL_ROOTS: list[str] = [
    'C#', 'Db', 'D#', 'Eb', 'F#', 'Gb', 'G#', 'Ab', 'A#', 'Bb',
    'C', 'D', 'E', 'F', 'G', 'A', 'B',
]

# Quality translations: (our_quality, ireal_quality)
# Longer / more specific patterns must come BEFORE shorter ones so that
# e.g. "mM7" is matched before "m".
_IREAL_QUALITY_MAP: list[tuple[str, str]] = [
    # Minor-major 7th / minor extended
    ('mM7',     '-^7'),
    ('mM7(9)',  '-^9'),
    ('m7b5',    'h7'),
    ('m7(b5)',  'h7'),
    ('m7b5(b9)', 'h9'),   # closest valid: half-dim 9; b9 not representable in iReal Pro
    ('m7b5(9)', 'h9'),
    ('m7(9)',   '-9'),
    ('m7(#11)', '-11'),
    ('m7(13)',  'min13'),   # iReal Pro uses 'min13' consistently (same as m13)
    ('m7',      '-7'),
    ('m6/9',    '-69'),
    ('m6',      '-6'),
    ('m9',      '-9'),
    ('m11',     '-11'),
    ('m13',     'min13'),   # iReal Pro uses 'min13', not '-13'
    ('m#5',     '-#5'),
    ('m',       '-'),      # minor triad — must follow all 'm…' patterns
    # Major-7th family — parenthesized extensions unfolded for iReal Pro
    ('maj13',    '^13'),
    ('maj9',     '^9'),
    ('maj7(9#11)', '^9#11'),
    ('maj7(9)',  '^9'),
    ('maj7(#11)', '^7#11'),
    ('maj7(13)', '^13'),
    ('maj7',     '^7'),
    # Dominant with extensions in parentheses → unfold
    ('7(b9#11)', '7b9#11'),
    ('7(#9#11)', '7#9#11'),
    ('7(b9b5)',  '7b9b5'),
    ('7(#9b5)',  '7#9b5'),
    ('7(9b5)',   '9b5'),
    ('7(b5)',    '7b5'),
    ('7(#9#5)',  '7#9#5'),
    ('7(b9#5)',  '7b9#5'),
    ('7(b9)',   '7b9'),
    ('7(#9)',   '7#9'),
    ('7(9)',    '9'),
    ('7(#11)',  '7#11'),
    ('7(b13)',  '7b13'),
    ('7(13)',   '13'),
    # 6/9 chord — slash would be misread as bass-note separator in iReal Pro
    ('6/9',    '69'),
    # Diminished / augmented
    ('dim7',   'o7'),
    ('dim',    'o'),
    ('aug7',   '7#5'),
    ('augM7',  '^7#5'),
    ('aug',    '+'),
    # Sus chords
    ('7sus4',  '7sus'),
    ('sus4',   'sus'),
]


def _chord_name_to_ireal(name: str) -> str:
    """Translate *name* from our canonical form to iReal Pro notation.

    Example::

        _chord_name_to_ireal('Cmaj7')    → 'C^7'
        _chord_name_to_ireal('Am7b5')    → 'Ah7'
        _chord_name_to_ireal('Bdim7')    → 'Bo7'
        _chord_name_to_ireal('C6/9')     → 'C69'
        _chord_name_to_ireal('Daug')     → 'D+'
        _chord_name_to_ireal('EmM7')     → 'E-^7'
        _chord_name_to_ireal('G7(b9)')   → 'G7b9'
    """
    # Find the root prefix
    root = ''
    for r in _ALL_ROOTS:
        if name.startswith(r):
            root = r
            break
    quality = name[len(root):]
    for src, dst in _IREAL_QUALITY_MAP:
        if quality == src:
            return root + dst
    return name  # unchanged — already canonical or unknown


# ---------------------------------------------------------------------------
# Human-readable spoken chord names
# ---------------------------------------------------------------------------

# Spoken quality map: (quality_string, spoken_text).
# Each entry is matched with strict equality against the quality portion of the
# chord name, so ordering within this list does not affect which entry matches.
# Entries that share a prefix (e.g. 'm7' and 'm7b5') are still distinct because
# the comparison is exact.
_SPOKEN_QUALITY_MAP: list[tuple[str, str]] = [
    ('mM7',          'minor major 7'),
    ('mM7(9)',        'minor major 9'),
    ('m7b5',          'half diminished'),
    ('m7(b5)',        'half diminished'),
    ('m7b5(b9)',      'half diminished flat 9'),
    ('m7b5(9)',       'half diminished 9'),
    ('m7(9)',         'minor 9'),
    ('m7(#11)',       'minor 7 sharp 11'),
    ('m7(13)',        'minor 13'),
    ('m7',            'minor 7'),
    ('m6/9',          'minor 6 9'),
    ('m6',            'minor 6'),
    ('m9',            'minor 9'),
    ('m11',           'minor 11'),
    ('m13',           'minor 13'),
    ('m#5',           'minor sharp 5'),
    ('m',             'minor'),
    ('maj13',         'major 13'),
    ('maj9',          'major 9'),
    ('maj7(9#11)',    'major 9 sharp 11'),
    ('maj7(9)',       'major 9'),
    ('maj7(#11)',     'major 7 sharp 11'),
    ('maj7(13)',      'major 13'),
    ('maj7',          'major 7'),
    ('7(b9#11)',      '7 flat 9 sharp 11'),
    ('7(#9#11)',      '7 sharp 9 sharp 11'),
    ('7(b9b5)',       '7 flat 9 flat 5'),
    ('7(#9b5)',       '7 sharp 9 flat 5'),
    ('7(9b5)',        '9 flat 5'),
    ('7(b5)',         '7 flat 5'),
    ('7(#9#5)',       '7 sharp 9 sharp 5'),
    ('7(b9#5)',       '7 flat 9 sharp 5'),
    ('7(b9)',         '7 flat 9'),
    ('7(#9)',         '7 sharp 9'),
    ('7(9)',          '9'),
    ('7(#11)',        '7 sharp 11'),
    ('7(b13)',        '7 flat 13'),
    ('7(13)',         '13'),
    ('6/9',           '6 9'),
    ('dim7',          'diminished 7'),
    ('dim',           'diminished'),
    ('aug7',          'augmented 7'),
    ('augM7',         'augmented major 7'),
    ('aug',           'augmented'),
    ('7sus4',         '7 sus 4'),
    ('sus4',          'sus 4'),
    ('7sus',          '7 sus 4'),
    ('sus',           'sus 4'),
    ('add9',          'add 9'),
    ('13',            '13'),
    ('11',            '11'),
    ('9',             '9'),
    ('7',             '7'),
    ('6',             '6'),
]


def _spoken_root(root: str) -> str:
    """Convert a note name (``C#``, ``Bb``, etc.) to its spoken form.

    Example::

        _spoken_root('C#')  → 'C sharp'
        _spoken_root('Bb')  → 'B flat'
        _spoken_root('G')   → 'G'
    """
    if root.endswith('#'):
        return root[:-1] + ' sharp'
    if len(root) == 2 and root[1] == 'b':
        return root[0] + ' flat'
    return root


def chord_name_to_spoken(name: str, bass_note: str = '') -> str:
    """Convert a chord name to a human-readable spoken string.

    Parameters
    ----------
    name:
        Chord name in canonical form (e.g. ``'Cmaj7'``, ``'Am7b5'``,
        ``'C/E'``).  A slash followed by an upper-case letter is treated as a
        bass-note inversion; ``'Cm6/9'`` is treated as a quality (the ``/``
        precedes a digit).
    bass_note:
        Optional bass note supplied separately (e.g. from
        ``ProgressionItem.bass_note``).  When provided it overrides any
        slash-note embedded in *name*.

    Example::

        chord_name_to_spoken('Cmaj7')        → 'C major 7'
        chord_name_to_spoken('Am7b5')        → 'A half diminished'
        chord_name_to_spoken('Caug')         → 'C augmented'
        chord_name_to_spoken('Csus4')        → 'C sus 4'
        chord_name_to_spoken('G7(b9)')       → 'G 7 flat 9'
        chord_name_to_spoken('C/E')          → 'C over E'
        chord_name_to_spoken('Cm6/9')        → 'C minor 6 9'
        chord_name_to_spoken('Cmaj7', 'E')   → 'C major 7 over E'
    """
    if not name:
        return ''

    # Parse root (try two-char roots first, then one-char)
    root = ''
    for r in _ALL_ROOTS:
        if name.startswith(r):
            root = r
            break

    quality_and_ext = name[len(root):]

    # Detect slash-chord bass note embedded in *name*: a '/' not followed by a
    # digit distinguishes 'C/E' (inversion) from 'Cm6/9' (quality).
    # An explicit *bass_note* argument takes precedence.
    embedded_bass = ''
    for idx in range(len(quality_and_ext) - 1, -1, -1):
        if quality_and_ext[idx] == '/':
            after = quality_and_ext[idx + 1:]
            if after and after[0].isupper():
                embedded_bass = after
                quality_and_ext = quality_and_ext[:idx]
                break

    resolved_bass = bass_note or embedded_bass

    # Look up quality in the spoken map (empty quality → major triad, no suffix)
    quality_spoken = ''
    for src, dst in _SPOKEN_QUALITY_MAP:
        if quality_and_ext == src:
            quality_spoken = dst
            break
    # Unrecognized non-empty quality: use as-is
    if not quality_spoken and quality_and_ext:
        quality_spoken = quality_and_ext

    parts: list[str] = [_spoken_root(root)]
    if quality_spoken:
        parts.append(quality_spoken)
    result = ' '.join(parts)
    if resolved_bass:
        result += ' over ' + _spoken_root(resolved_bass)
    return result


@total_ordering
@dataclass
class ProgressionItem:
    chord: Chord
    position: Position
    bass_note: str = ''  # For slash chords, e.g. 'G/B' -> bass_note='B'

    def __str__(self) -> str:
        chord_str = self.chord.name
        if self.bass_note:
            chord_str += f"/{self.bass_note}"
        return f"{chord_str} at {self.position}"

    def chord_name(self) -> str:
        """Return the full chord name including optional bass note."""
        name = self.chord.name
        if self.bass_note:
            name += f"/{self.bass_note}"
        return name

    def chord_name_spoken(self) -> str:
        """Return the full chord name as a human-readable spoken string."""
        return chord_name_to_spoken(self.chord.name, self.bass_note)

    def ireal_chord_name(self) -> str:
        """Return the chord name translated to iReal Pro canonical format.

        iReal Pro uses:  ``-`` for minor,  ``^7`` for major 7th,
        ``h7`` for half-diminished,  ``o`` / ``o7`` for diminished,
        ``+`` for augmented, ``69`` (no slash) for the 6/9 chord, etc.
        Extensions in parentheses (e.g. ``7(b9)``) are unfolded
        (``7b9``) because iReal Pro doesn't use the parenthesised form.
        Bass-note inversions are preserved.
        """
        name = _chord_name_to_ireal(self.chord.name)
        if self.bass_note:
            name += f"/{self.bass_note}"
        return name

    def __eq__(self, other) -> bool:
        if not isinstance(other, ProgressionItem):
            return NotImplemented
        return self.position == other.position and self.chord.name == other.chord.name

    def __lt__(self, other) -> bool:
        return self.position < other.position

    def __hash__(self):
        return hash((self.chord.name, self.position))

    def to_dict(self) -> dict:
        return {
            'chord': self.chord.name,
            'measure': self.position.measure,
            'beat': self.position.beat,
            'bass_note': self.bass_note,
        }

    @classmethod
    def from_dict(cls, d: dict, ts: TimeSignature) -> ProgressionItem:
        chord = Chord(d['chord'])
        pos = Position(d['measure'], d['beat'], ts)
        return cls(chord, pos, d.get('bass_note', ''))


@dataclass
class ChordProgression:
    title: str
    time_signature: TimeSignature
    key: str
    style: str
    items: list[ProgressionItem] = field(default_factory=list)
    section_marks: list[SectionMark] = field(default_factory=list)
    volta_brackets: list[VoltaBracket] = field(default_factory=list)
    bpm: int = 120
    composer: str = 'Unknown'
    total_measures: int = 0  # track how many measures have been used
    no_chord_measures: set[int] = field(default_factory=set)  # measures marked as N.C.

    def __str__(self) -> str:
        lines = [f"{self.title} in {self.key} ({self.style}) @ {self.bpm} BPM, "
                 f"time: {self.time_signature}"]
        for item in self.items:
            lines.append(f"  {item}")
        return '\n'.join(lines)

    # -----------------------------------------------------------------------
    # Chord management
    # -----------------------------------------------------------------------

    def add_chord_raw(self, chord: Chord, position: Position, bass_note: str = ''):
        # Remove any existing chord at the same position first
        self.items = [i for i in self.items if i.position != position]
        self.items.append(ProgressionItem(chord, position, bass_note))
        self.items.sort()
        if position.measure > self.total_measures:
            self.total_measures = position.measure

    def add_chord(self, chord: Chord, measure: int, beat: int, bass_note: str = ''):
        self.add_chord_raw(chord, Position(measure, beat, self.time_signature), bass_note)

    def add_chord_by_name(self, chord_name: str, measure: int, beat: int, bass_note: str = ''):
        chord = Chord(chord_name)
        self.add_chord(chord, measure, beat, bass_note)

    def add_chord_by_notes(self, notes: list[str], measure: int, beat: int, bass_note: str = ''):
        chord = Chord.from_notes(notes)
        if chord is not None:
            self.add_chord(chord, measure, beat, bass_note)

    def delete_chord_at(self, position: Position):
        self.items = [i for i in self.items if i.position != position]

    def find_chords_at_position(self, position: Position) -> list[ProgressionItem]:
        return [item for item in self.items if item.position == position]

    def find_chords_in_measure(self, measure: int) -> list[ProgressionItem]:
        return [item for item in self.items if item.position.measure == measure]

    def measure_is_empty(self, measure: int) -> bool:
        return not any(item.position.measure == measure for item in self.items)

    def find_last_chord_to_left(self, position: Position) -> ProgressionItem | None:
        left = [i for i in self.items if i.position < position]
        return left[-1] if left else None

    def find_next_chord_to_right(self, position: Position) -> ProgressionItem | None:
        right = [i for i in self.items if i.position > position]
        return right[0] if right else None

    def validate(self):
        seen = set()
        unique = []
        for item in self.items:
            key = (item.position.measure, item.position.beat)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        self.items = unique

    # -----------------------------------------------------------------------
    # Section marks
    # -----------------------------------------------------------------------

    def add_section_mark(self, measure: int, mark: str):
        """Add or replace a section mark at a given measure."""
        self.section_marks = [s for s in self.section_marks if s.measure != measure]
        self.section_marks.append(SectionMark(measure, mark))
        self.section_marks.sort(key=lambda s: s.measure)

    def remove_section_mark(self, measure: int):
        self.section_marks = [s for s in self.section_marks if s.measure != measure]

    def get_section_mark(self, measure: int) -> str | None:
        for s in self.section_marks:
            if s.measure == measure:
                return s.mark
        return None

    # -----------------------------------------------------------------------
    # Volta / repeat brackets
    # -----------------------------------------------------------------------

    def add_volta_start(self, measure: int) -> str:
        """
        Press V once at the first measure of ending 1.

        All bracket coordinates are computed automatically from the section marks:
          - repeat_start  = last section mark at or before `measure`
          - next_section  = first section mark after `measure` (or end-of-content + 1)
          - body_length   = measure - repeat_start
          - ending_length = next_section - measure  (≥ 1)
          - ending1_end   = measure + ending_length - 1
          - ending2_start = next_section + body_length

        If a bracket already exists for the same repeat_start it is replaced.
        """
        repeat_start = self._find_section_start(measure)
        next_section = self._find_next_section_start(measure)

        body_length = measure - repeat_start
        ending_length = max(1, next_section - measure)
        ending1_end = measure + ending_length - 1
        ending2_start = next_section + body_length

        # Replace any existing bracket that starts at the same repeat_start
        self.volta_brackets = [vb for vb in self.volta_brackets
                                if vb.repeat_start != repeat_start]

        vb = VoltaBracket(
            repeat_start=repeat_start,
            ending1_start=measure,
            ending1_end=ending1_end,
            ending2_start=ending2_start,
        )
        self.volta_brackets.append(vb)
        return (f"Repeat from measure {repeat_start}, "
                f"ending 1: {measure}–{ending1_end}, "
                f"ending 2 starts at measure {ending2_start}")

    def _find_section_start(self, measure: int) -> int:
        """Find the measure where the current section starts (for repeat bracket placement)."""
        marks_before = [s.measure for s in self.section_marks if s.measure <= measure]
        return marks_before[-1] if marks_before else 1

    def _find_next_section_start(self, from_measure: int) -> int:
        """
        Return the first measure of the next section after `from_measure`.
        Falls back to max(total_measures, from_measure) + 1 when no section
        mark exists beyond `from_measure` (yielding a 1-measure ending when
        total_measures equals from_measure, or a longer one when more content
        exists).
        """
        marks_after = sorted(s.measure for s in self.section_marks
                             if s.measure > from_measure)
        if marks_after:
            return marks_after[0]
        # Use end-of-known-content + 1, or a safe 2-measure default
        return max(self.total_measures, from_measure) + 1

    def get_volta_bracket_for_measure(self, measure: int) -> VoltaBracket | None:
        """Return the VoltaBracket that contains the given measure."""
        for vb in self.volta_brackets:
            if vb.repeat_start <= measure:
                if vb.is_complete() and measure <= max(vb.ending1_end, vb.ending2_start):
                    return vb
                if not vb.is_complete() and measure >= vb.ending1_start:
                    return vb
        return None

    def is_in_hidden_range(self, measure: int) -> bool:
        """Return True if this measure is in the 'hidden' (repeated-body) region."""
        for vb in self.volta_brackets:
            hr = vb.hidden_range()
            if hr and hr[0] <= measure <= hr[1]:
                return True
        return False

    # -----------------------------------------------------------------------
    # Navigation helpers
    # -----------------------------------------------------------------------

    def navigate_right_from_measure(self, measure: int) -> int:
        """
        Given a measure, return the next measure to navigate to.
        Skips hidden ranges; at end of ending 1 jumps to ending 2.
        """
        for vb in self.volta_brackets:
            if vb.is_complete() and measure == vb.ending1_end:
                return vb.ending2_start
        # Skip hidden ranges
        next_m = measure + 1
        while self.is_in_hidden_range(next_m):
            next_m += 1
        return next_m

    def navigate_left_from_measure(self, measure: int) -> int:
        """
        Given a measure, return the previous measure to navigate to.
        At ending2_start jumps back to ending1_end.
        """
        for vb in self.volta_brackets:
            if vb.is_complete() and measure == vb.ending2_start:
                return vb.ending1_end
        prev_m = measure - 1
        if prev_m < 1:
            return 1
        while self.is_in_hidden_range(prev_m):
            prev_m -= 1
        return max(1, prev_m)

    def last_measure(self) -> int:
        """Return the last measure that has content (chords or section marks)."""
        measures = [item.position.measure for item in self.items]
        measures += [s.measure for s in self.section_marks]
        measures += list(self.no_chord_measures)
        return max(measures) if measures else 1

    def add_no_chord(self, measure: int) -> None:
        """Mark *measure* as a 'no chord' (N.C.) measure for iReal Pro export."""
        self.no_chord_measures.add(measure)
        if measure > self.total_measures:
            self.total_measures = measure

    def remove_no_chord(self, measure: int) -> None:
        """Remove the no-chord mark from *measure* (if set)."""
        self.no_chord_measures.discard(measure)

    def is_no_chord(self, measure: int) -> bool:
        """Return True if *measure* is marked as N.C."""
        return measure in self.no_chord_measures

    # -----------------------------------------------------------------------
    # JSON serialisation
    # -----------------------------------------------------------------------

    def to_json(self) -> str:
        data = {
            'title': self.title,
            'key': self.key,
            'style': self.style,
            'bpm': self.bpm,
            'composer': self.composer,
            'time_signature': str(self.time_signature),
            'total_measures': self.total_measures,
            'items': [item.to_dict() for item in self.items],
            'section_marks': [s.to_dict() for s in self.section_marks],
            'volta_brackets': [vb.to_dict() for vb in self.volta_brackets],
            'no_chord_measures': sorted(self.no_chord_measures),
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ChordProgression:
        data = json.loads(json_str)
        ts = TimeSignature.from_string(data['time_signature'])
        prog = cls(
            title=data['title'],
            time_signature=ts,
            key=data['key'],
            style=data['style'],
            bpm=data.get('bpm', 120),
            composer=data.get('composer', 'Unknown'),
            total_measures=data.get('total_measures', 0),
        )
        prog.items = [ProgressionItem.from_dict(d, ts) for d in data.get('items', [])]
        prog.section_marks = [SectionMark.from_dict(d) for d in data.get('section_marks', [])]
        prog.volta_brackets = [VoltaBracket.from_dict(d) for d in data.get('volta_brackets', [])]
        prog.no_chord_measures = set(data.get('no_chord_measures', []))
        return prog

    # -----------------------------------------------------------------------
    # iReal Pro export
    # -----------------------------------------------------------------------

    def to_ireal_url(self) -> str:
        """Export to an iRealPro URL string."""
        from pyrealpro import Song, Measure as IrMeasure, TimeSignature as IrTS

        # Map our time signature to iReal Pro TimeSignature
        try:
            ir_ts = IrTS(self.time_signature.numerator, self.time_signature.denominator)
        except ValueError:
            ir_ts = IrTS(4, 4)  # fallback

        # Map our style to an iReal Pro style (use closest or default)
        from pyrealpro import STYLES_ALL
        style = self.style if self.style in STYLES_ALL else 'Medium Swing'

        # Find the valid iReal Pro key
        from pyrealpro import KEY_SIGNATURES
        key = self.key if self.key in KEY_SIGNATURES else 'C'

        song = Song(title=self.title, composer_name_first=self.composer,
                    key=key, style=style)

        last_m = self.last_measure()
        total_m = max(last_m, self.total_measures)

        # Build a list of measures (1-indexed), skipping hidden ones
        measures_to_write = []
        m = 1
        while m <= total_m:
            if self.is_in_hidden_range(m):
                m += 1
                continue
            measures_to_write.append(m)
            m += 1

        # Build iReal Pro measures
        for idx, measure_num in enumerate(measures_to_write):
            chords_in_measure = self.find_chords_in_measure(measure_num)
            beats = self.time_signature.numerator

            if chords_in_measure:
                # Build chord list for the measure
                chord_list = [' '] * beats
                for item in chords_in_measure:
                    beat_idx = item.position.beat - 1  # 0-based
                    if 0 <= beat_idx < beats:
                        chord_list[beat_idx] = item.ireal_chord_name()
                # Compact: if all beats after first are empty, use string shorthand
                if all(c == ' ' for c in chord_list[1:]):
                    chords_arg = chord_list[0]
                else:
                    chords_arg = chord_list
            elif self.is_no_chord(measure_num):
                # Explicitly marked as "no chord" (N.C.)
                chords_arg = 'n'
            else:
                # No chord played → "repeat one measure" symbol (iReal Pro: x)
                chords_arg = 'x'

            # Determine barline_open
            barline_open = ''
            for vb in self.volta_brackets:
                if measure_num == vb.repeat_start:
                    barline_open = '{'
                    break

            # Determine barline_close
            barline_close = None
            for vb in self.volta_brackets:
                if vb.is_complete() and measure_num == vb.ending1_end:
                    barline_close = '}'
                    break

            # Determine ending marker
            ending = ''
            for vb in self.volta_brackets:
                if measure_num == vb.ending1_start:
                    ending = 'N1'
                    break
                if vb.is_complete() and measure_num == vb.ending2_start:
                    ending = 'N2'
                    break

            # Determine rehearsal marks
            rehearsal_marks = []
            sm = self.get_section_mark(measure_num)
            if sm:
                if sm in IrMeasure.REHEARSAL_MARKS:
                    rehearsal_marks = [sm]

            # Whether to render time signature (first measure or after time sig change)
            render_ts = (idx == 0)

            try:
                ir_measure = IrMeasure(
                    chords=chords_arg,
                    time_sig=ir_ts,
                    rehearsal_marks=rehearsal_marks,
                    barline_open=barline_open,
                    barline_close=barline_close,
                    ending=ending,
                    render_ts=render_ts,
                )
                song.measures.append(ir_measure)
            except ValueError:
                # Fallback: write as single chord
                ir_measure = IrMeasure(
                    chords=' ',
                    time_sig=ir_ts,
                    rehearsal_marks=rehearsal_marks,
                    barline_open=barline_open,
                    barline_close=barline_close,
                    ending=ending,
                    render_ts=render_ts,
                )
                song.measures.append(ir_measure)

        return song.url()

    # -----------------------------------------------------------------------
    # List-like interface
    # -----------------------------------------------------------------------

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __setitem__(self, index, value):
        self.items[index] = value
        self.items.sort()

    def __delitem__(self, index):
        del self.items[index]

    def __iter__(self):
        return iter(self.items)
