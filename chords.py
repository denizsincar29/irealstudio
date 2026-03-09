"""
chords.py - Data model for chord progressions, including:
- Positions, time signatures
- Section marks (*A, *B, etc.)
- Volta/ending brackets for repeats
- JSON serialization
- iReal Pro export
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from functools import total_ordering
from pychord import Chord, find_chords_from_notes

NOTE_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

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


@total_ordering
@dataclass
class ProgressionItem:
    chord: Chord
    position: Position
    bass_note: str = ''  # For slash chords, e.g. 'G/B' -> bass_note='B'

    def __str__(self) -> str:
        chord_str = str(self.chord)
        if self.bass_note:
            chord_str += f"/{self.bass_note}"
        return f"{chord_str} at {self.position}"

    def chord_name(self) -> str:
        """Return the full chord name including optional bass note."""
        name = str(self.chord)
        if self.bass_note:
            name += f"/{self.bass_note}"
        return name

    def __eq__(self, other) -> bool:
        if not isinstance(other, ProgressionItem):
            return NotImplemented
        return self.position == other.position and str(self.chord) == str(other.chord)

    def __lt__(self, other) -> bool:
        return self.position < other.position

    def __hash__(self):
        return hash((str(self.chord), self.position))

    def to_dict(self) -> dict:
        return {
            'chord': str(self.chord),
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
        chords = find_chords_from_notes(notes)
        if chords:
            self.add_chord(chords[0], measure, beat, bass_note)

    def add_chord_by_raw_data(self, midi_notes: list[int], timestamp: float, bpm: int,
                               recording_start_time: float = 0.0):
        """
        Convert a MIDI chord (recorded during playback) to a position.

        timestamp        – time in seconds when the first note was pressed
        recording_start_time – time when recording actually started (after pre-count)
        """
        beats_per_second = bpm / 60
        elapsed = timestamp - recording_start_time
        beat_pos = elapsed * beats_per_second  # 0-based float beat position from recording start
        quantized_total_beat = round(beat_pos) + 1  # 1-based
        if quantized_total_beat < 1:
            quantized_total_beat = 1
        measure = (quantized_total_beat - 1) // self.time_signature.numerator + 1
        beat = (quantized_total_beat - 1) % self.time_signature.numerator + 1
        notes = [NOTE_NAMES[n % 12] for n in midi_notes]
        self.add_chord_by_notes(notes, measure, beat)

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
        return max(measures) if measures else 1

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
                        chord_list[beat_idx] = item.chord_name()
                # Compact: if all beats after first are empty, use string shorthand
                if all(c == ' ' for c in chord_list[1:]):
                    chords_arg = chord_list[0]
                else:
                    chords_arg = chord_list
            else:
                chords_arg = ' '  # empty measure placeholder

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
