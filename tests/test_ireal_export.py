"""
test_ireal_export.py - Unit tests for iReal Pro URL export correctness.

Tests cover:
  - Simple progression with a single chord per measure
  - Section marks (*A, *B, etc.) appearing in the URL
  - Volta brackets: { } N1 N2 in the URL string
  - Hidden-measure skipping (repeated body between endings)
  - Slash chords (bass note appended)
  - JSON round-trip preserving all fields
  - URL format (starts with irealbook://, contains song title)
  - Empty progression (at least produces a valid URL)
"""

import sys
import os
import unittest

# Ensure the package root is on the path regardless of where tests are run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chords import ChordProgression, TimeSignature, VoltaBracket, Position
from chords import voice_chord_midi
from urllib.parse import unquote


def make_prog(title='Test', key='C', style='Medium Swing', bpm=120,
              numerator=4, denominator=4) -> ChordProgression:
    ts = TimeSignature(numerator, denominator)
    return ChordProgression(title=title, time_signature=ts, key=key,
                            style=style, bpm=bpm)


def url_body(prog: ChordProgression) -> str:
    """Return the decoded URL body (everything after irealbook://)."""
    url = prog.to_ireal_url()
    return unquote(url)


def measures_body(prog: ChordProgression) -> str:
    """Return only the measures payload (the part inside [ ... Z)."""
    body = url_body(prog)
    # URL format: ...=n=[T44<measures>Z  – extract everything from '[' onward
    bracket = body.find('[')
    return body[bracket:] if bracket != -1 else body


class TestUrlFormat(unittest.TestCase):
    """Basic URL structure tests."""

    def test_starts_with_scheme(self):
        prog = make_prog('My Song')
        url = prog.to_ireal_url()
        self.assertTrue(url.startswith('irealbook://'), url)

    def test_contains_title(self):
        prog = make_prog('Blues In Eb')
        body = url_body(prog)
        self.assertIn('Blues In Eb', body)

    def test_empty_progression_is_valid(self):
        prog = make_prog()
        url = prog.to_ireal_url()
        self.assertTrue(url.startswith('irealbook://'))

    def test_url_ends_with_close_barline(self):
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        body = url_body(prog)
        self.assertTrue(body.endswith('Z'), body)

    def test_custom_key_in_url(self):
        prog = make_prog(key='Bb')
        body = url_body(prog)
        self.assertIn('Bb', body)

    def test_custom_style_in_url(self):
        prog = make_prog(style='Bossa Nova')
        body = url_body(prog)
        self.assertIn('Bossa Nova', body)


class TestSimpleProgression(unittest.TestCase):
    """Tests for a straightforward chord progression without special features."""

    def test_single_chord(self):
        prog = make_prog()
        prog.add_chord_by_name('C', 1, 1)
        body = url_body(prog)
        self.assertIn('C', body)

    def test_multiple_measures(self):
        prog = make_prog()
        for m in range(1, 5):
            prog.add_chord_by_name('Cmaj7', m, 1)
        url = prog.to_ireal_url()
        self.assertTrue(url.startswith('irealbook://'))

    def test_chords_across_beats(self):
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        prog.add_chord_by_name('Am7',   1, 3)
        prog.add_chord_by_name('Dm7',   2, 1)
        prog.add_chord_by_name('G7',    2, 3)
        body = url_body(prog)
        # iReal Pro canonical: maj7 → ^7, m7 → -7
        self.assertIn('C^7', body)
        self.assertIn('A-7', body)
        self.assertIn('D-7', body)
        self.assertIn('G7', body)


class TestSectionMarks(unittest.TestCase):
    """Tests that section marks appear correctly in the URL."""

    def test_section_a_mark(self):
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_chord_by_name('Cmaj7', 1, 1)
        body = url_body(prog)
        self.assertIn('*A', body)

    def test_multiple_section_marks(self):
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        body = url_body(prog)
        self.assertIn('*A', body)
        self.assertIn('*B', body)

    def test_verse_mark(self):
        prog = make_prog()
        prog.add_section_mark(1, '*V')
        prog.add_chord_by_name('G', 1, 1)
        body = url_body(prog)
        self.assertIn('*V', body)


class TestSlashChords(unittest.TestCase):
    """Tests for slash chords (bass notes)."""

    def test_slash_chord_in_url(self):
        prog = make_prog()
        prog.add_chord_by_name('G', 1, 1, bass_note='B')
        body = url_body(prog)
        self.assertIn('/B', body)

    def test_no_slash_when_no_bass_note(self):
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        body = url_body(prog)
        self.assertNotIn('/C', body)
        self.assertNotIn('/D', body)

    def test_slash_chord_name(self):
        prog = make_prog()
        prog.add_chord_by_name('G7', 1, 1, bass_note='B')
        items = prog.find_chords_in_measure(1)
        self.assertEqual(items[0].chord_name(), 'G7/B')


class TestVoltaBrackets(unittest.TestCase):
    """Tests that volta brackets emit correct iReal Pro tokens."""

    def _build_aaba_prog(self) -> ChordProgression:
        """8-bar A section + 8-bar B section, V pressed at measure 7."""
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(9, '*B')
        for m in range(1, 17):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(7)   # single press at measure 7
        return prog

    def test_repeat_open_brace(self):
        prog = self._build_aaba_prog()
        body = url_body(prog)
        self.assertIn('{', body)

    def test_repeat_close_brace(self):
        prog = self._build_aaba_prog()
        body = url_body(prog)
        self.assertIn('}', body)

    def test_ending1_marker(self):
        prog = self._build_aaba_prog()
        body = url_body(prog)
        self.assertIn('N1', body)

    def test_ending2_marker(self):
        prog = self._build_aaba_prog()
        body = url_body(prog)
        self.assertIn('N2', body)

    def test_hidden_measures_not_in_url(self):
        """Measures in the hidden range must not appear in the exported URL."""
        prog = self._build_aaba_prog()
        vb = prog.volta_brackets[0]
        hr = vb.hidden_range()
        self.assertIsNotNone(hr, "Expected a non-None hidden range")
        body = url_body(prog)

        # The hidden measures are just repeated body chords — the chords in
        # those measures should NOT be written as extra measures in the URL.
        # We count how many measures are written by counting barline separators.
        # A simpler check: count visible measures vs total measures.
        hidden_start, hidden_end = hr
        hidden_count = hidden_end - hidden_start + 1

        # Verify hidden range is populated before the test is meaningful
        self.assertGreater(hidden_count, 0)

        # Build URL without volta to know how many measures would appear normally
        prog_plain = make_prog()
        prog_plain.add_section_mark(1, '*A')
        prog_plain.add_section_mark(9, '*B')
        for m in range(1, 17):
            prog_plain.add_chord_by_name('Cmaj7', m, 1)
        body_plain = url_body(prog_plain)

        # The volta URL must be shorter (fewer measures) than the plain URL
        # because the hidden measures are skipped.
        self.assertLess(len(body), len(body_plain))

    def test_volta_bracket_is_complete_after_single_press(self):
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(4)
        self.assertTrue(prog.volta_brackets[0].is_complete())

    def test_hidden_range_correct(self):
        """Measures 5..7 should be hidden for an 8-measure AABA form."""
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(4)
        vb = prog.volta_brackets[0]
        # body_length = 4 - 1 = 3, ending_length = 5 - 4 = 1
        # ending1_end = 4, ending2_start = 5 + 3 = 8
        # hidden_range = (5, 7)
        self.assertEqual(vb.ending1_start, 4)
        self.assertEqual(vb.ending1_end, 4)
        self.assertEqual(vb.ending2_start, 8)
        self.assertEqual(vb.hidden_range(), (5, 7))

    def test_repressing_v_replaces_bracket(self):
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(4)
        prog.add_volta_start(4)  # second press at same measure
        self.assertEqual(len(prog.volta_brackets), 1)


class TestJsonRoundTrip(unittest.TestCase):
    """Tests that serialisation / deserialisation preserves all data."""

    def test_basic_roundtrip(self):
        prog = make_prog('Round Trip', key='Bb', style='Bossa Nova', bpm=95)
        prog.add_chord_by_name('Bbmaj7', 1, 1)
        prog.add_chord_by_name('Gm7',    2, 1)
        j = prog.to_json()
        p2 = ChordProgression.from_json(j)
        self.assertEqual(p2.title, 'Round Trip')
        self.assertEqual(p2.key, 'Bb')
        self.assertEqual(p2.bpm, 95)
        self.assertEqual(len(p2.items), 2)

    def test_section_marks_roundtrip(self):
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        p2 = ChordProgression.from_json(prog.to_json())
        marks = {s.measure: s.mark for s in p2.section_marks}
        self.assertEqual(marks[1], '*A')
        self.assertEqual(marks[5], '*B')

    def test_volta_bracket_roundtrip(self):
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(4)
        p2 = ChordProgression.from_json(prog.to_json())
        self.assertEqual(len(p2.volta_brackets), 1)
        vb = p2.volta_brackets[0]
        self.assertTrue(vb.is_complete())
        self.assertEqual(vb.ending1_start, 4)

    def test_slash_chord_roundtrip(self):
        prog = make_prog()
        prog.add_chord_by_name('G7', 1, 1, bass_note='B')
        p2 = ChordProgression.from_json(prog.to_json())
        self.assertEqual(p2.items[0].bass_note, 'B')

    def test_url_identical_after_roundtrip(self):
        prog = make_prog('Same URL', key='G', style='Slow Swing', bpm=60)
        prog.add_chord_by_name('Gmaj7', 1, 1)
        prog.add_chord_by_name('Em7',   2, 1)
        prog.add_section_mark(1, '*A')
        url1 = prog.to_ireal_url()
        p2 = ChordProgression.from_json(prog.to_json())
        url2 = p2.to_ireal_url()
        self.assertEqual(url1, url2)


class TestHiddenRangeNavigation(unittest.TestCase):
    """Tests for is_in_hidden_range and navigate helpers."""

    def _prog_with_volta(self) -> ChordProgression:
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(9, '*B')
        for m in range(1, 17):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(7)
        return prog

    def test_hidden_range_measures_flagged(self):
        prog = self._prog_with_volta()
        vb = prog.volta_brackets[0]
        hr = vb.hidden_range()
        self.assertIsNotNone(hr)
        for m in range(hr[0], hr[1] + 1):
            self.assertTrue(prog.is_in_hidden_range(m), f"measure {m} should be hidden")

    def test_non_hidden_measures_not_flagged(self):
        prog = self._prog_with_volta()
        vb = prog.volta_brackets[0]
        self.assertFalse(prog.is_in_hidden_range(vb.ending1_start))
        self.assertFalse(prog.is_in_hidden_range(vb.ending2_start))
        self.assertFalse(prog.is_in_hidden_range(vb.repeat_start))

    def test_navigate_right_skips_hidden(self):
        prog = self._prog_with_volta()
        vb = prog.volta_brackets[0]
        # From ending1_end, navigation should jump to ending2_start
        dest = prog.navigate_right_from_measure(vb.ending1_end)
        self.assertEqual(dest, vb.ending2_start)

    def test_navigate_left_skips_hidden(self):
        prog = self._prog_with_volta()
        vb = prog.volta_brackets[0]
        # From ending2_start, navigation should jump back to ending1_end
        dest = prog.navigate_left_from_measure(vb.ending2_start)
        self.assertEqual(dest, vb.ending1_end)


class TestNoteDeduplication(unittest.TestCase):
    """Tests for duplicate note removal before chord detection (Bug 3)."""

    def test_dedup_removes_octave_duplicates(self):
        """MIDI notes 60 and 72 both map to 'C'; only one 'C' should remain."""
        from chords import NOTE_NAMES
        notes = [60, 64, 67, 72]  # C4, E4, G4, C5
        deduped = list(dict.fromkeys(NOTE_NAMES[n % 12] for n in notes))
        self.assertEqual(deduped, ['C', 'E', 'G'])

    def test_dedup_preserves_order(self):
        """Deduplication must keep the first-seen note order."""
        from chords import NOTE_NAMES
        notes = [64, 67, 60, 72]  # E4, G4, C4, C5
        deduped = list(dict.fromkeys(NOTE_NAMES[n % 12] for n in notes))
        self.assertEqual(deduped[0], 'E')  # first seen
        self.assertEqual(deduped[-1], 'C')  # only one 'C'

    def test_chord_found_after_dedup(self):
        """Chord.from_notes must identify C major triad after deduplication."""
        from chords import NOTE_NAMES, Chord
        notes = [60, 64, 67, 72]  # C4, E4, G4, C5
        deduped = list(dict.fromkeys(NOTE_NAMES[n % 12] for n in notes))
        chord = Chord.from_notes(deduped)
        self.assertIsNotNone(chord)
        self.assertEqual('C', chord.name)


class TestChordNavigation(unittest.TestCase):
    """Tests for chord-by-chord vs beat-by-beat navigation (Bug 1)."""

    def _make_prog(self):
        ts = TimeSignature(4, 4)
        prog = ChordProgression(title='Nav', time_signature=ts,
                                key='C', style='Medium Swing', bpm=120)
        prog.add_chord_by_name('Cmaj7', 1, 1)
        prog.add_chord_by_name('Am7',   2, 1)
        prog.add_chord_by_name('Fmaj7', 3, 1)
        prog.add_chord_by_name('G7',    4, 1)
        prog.total_measures = 4
        return prog

    def test_find_next_chord_to_right(self):
        prog = self._make_prog()
        ts = prog.time_signature
        cursor = Position(1, 1, ts)
        nxt = prog.find_next_chord_to_right(cursor)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.position.measure, 2)

    def test_find_prev_chord_to_left(self):
        prog = self._make_prog()
        ts = prog.time_signature
        cursor = Position(3, 1, ts)
        prv = prog.find_last_chord_to_left(cursor)
        self.assertIsNotNone(prv)
        self.assertEqual(prv.position.measure, 2)

    def test_no_chord_to_left_returns_none(self):
        prog = self._make_prog()
        ts = prog.time_signature
        cursor = Position(1, 1, ts)
        prv = prog.find_last_chord_to_left(cursor)
        self.assertIsNone(prv)

    def test_beat_navigation_position_plus_one(self):
        """position + 1 should advance one beat."""
        ts = TimeSignature(4, 4)
        pos = Position(2, 3, ts)
        new_pos = pos + 1
        self.assertEqual(new_pos.measure, 2)
        self.assertEqual(new_pos.beat, 4)

    def test_beat_navigation_wraps_to_next_measure(self):
        ts = TimeSignature(4, 4)
        pos = Position(2, 4, ts)
        new_pos = pos + 1
        self.assertEqual(new_pos.measure, 3)
        self.assertEqual(new_pos.beat, 1)

    def test_beat_navigation_left_clamps_at_start(self):
        ts = TimeSignature(4, 4)
        pos = Position(1, 1, ts)
        new_pos = pos - 1
        self.assertEqual(new_pos.measure, 1)
        self.assertEqual(new_pos.beat, 1)


class TestIpsFileFormat(unittest.TestCase):
    """Tests for .ips file format (Bug 4)."""

    def test_ips_and_json_same_content(self):
        """IPS files use the same JSON content as .json files."""
        prog = make_prog('IPS Test', key='Bb', bpm=100)
        prog.add_chord_by_name('Bbmaj7', 1, 1)
        json_str = prog.to_json()
        # Both .ips and .json are loaded via from_json
        loaded = ChordProgression.from_json(json_str)
        self.assertEqual(loaded.title, 'IPS Test')
        self.assertEqual(loaded.key, 'Bb')
        self.assertEqual(loaded.bpm, 100)

    def test_from_json_roundtrip_with_time_sig(self):
        """Time signature survives JSON round-trip."""
        prog = make_prog(numerator=3, denominator=4)
        prog.add_chord_by_name('Cmaj7', 1, 1)
        loaded = ChordProgression.from_json(prog.to_json())
        self.assertEqual(loaded.time_signature.numerator, 3)
        self.assertEqual(loaded.time_signature.denominator, 4)


class TestChordRecognition(unittest.TestCase):
    """Tests for the _identify_chord_name() recognition algorithm.

    Covers every documented chord family and each of the three
    disambiguation rules (b3+maj3 → #9, maj7/P5+tritone → #11, 4th → sus4).
    """

    def _chord(self, notes: list[str]) -> str:
        from chords import Chord
        c = Chord.from_notes(notes)
        self.assertIsNotNone(c, f"from_notes({notes!r}) returned None")
        return c.name

    # ------------------------------------------------------------------ #
    # Basic triads                                                         #
    # ------------------------------------------------------------------ #

    def test_major_triad(self):
        self.assertEqual('C', self._chord(['C', 'E', 'G']))

    def test_minor_triad(self):
        self.assertEqual('Am', self._chord(['A', 'C', 'E']))

    def test_diminished_triad(self):
        self.assertEqual('Bdim', self._chord(['B', 'D', 'F']))

    def test_augmented_triad(self):
        self.assertEqual('Caug', self._chord(['C', 'E', 'Ab']))

    def test_sus4_triad(self):
        self.assertEqual('Csus4', self._chord(['C', 'F', 'G']))

    # ------------------------------------------------------------------ #
    # 7th chords                                                           #
    # ------------------------------------------------------------------ #

    def test_dominant_7(self):
        self.assertEqual('G7', self._chord(['G', 'B', 'D', 'F']))

    def test_major_7(self):
        self.assertEqual('Cmaj7', self._chord(['C', 'E', 'G', 'B']))

    def test_minor_7(self):
        self.assertEqual('Dm7', self._chord(['D', 'F', 'A', 'C']))

    def test_minor_major_7(self):
        self.assertEqual('AmM7', self._chord(['A', 'C', 'E', 'Ab']))

    def test_half_diminished(self):
        self.assertEqual('Bm7b5', self._chord(['B', 'D', 'F', 'A']))

    def test_diminished_7(self):
        self.assertEqual('Bdim7', self._chord(['B', 'D', 'F', 'Ab']))

    def test_sus4_dom7(self):
        self.assertEqual('G7sus4', self._chord(['G', 'C', 'D', 'F']))

    # ------------------------------------------------------------------ #
    # Added-tone / extended chords                                         #
    # ------------------------------------------------------------------ #

    def test_add9(self):
        self.assertEqual('Cadd9', self._chord(['C', 'E', 'G', 'D']))

    def test_6th(self):
        self.assertEqual('C6', self._chord(['C', 'E', 'G', 'A']))

    def test_6_9(self):
        self.assertEqual('C6/9', self._chord(['C', 'E', 'G', 'A', 'D']))

    def test_dom9(self):
        self.assertEqual('G7(9)', self._chord(['G', 'B', 'D', 'F', 'A']))

    def test_dom_13(self):
        self.assertEqual('G7(13)', self._chord(['G', 'B', 'D', 'F', 'E']))

    # ------------------------------------------------------------------ #
    # Validation rule 1: b3 + maj3 → #9                                   #
    # ------------------------------------------------------------------ #

    def test_rule1_sharp9_not_minor3(self):
        """C7(#9): C-E-G-Bb-Eb — both b3(Eb) and maj3(E) present → #9."""
        name = self._chord(['C', 'E', 'G', 'Bb', 'Eb'])
        self.assertEqual('C7(#9)', name)

    def test_rule1_b9_dominant(self):
        """C7(b9): C-E-G-Bb-Db — only b9 (semitone 1), no #9 ambiguity."""
        name = self._chord(['C', 'E', 'G', 'Bb', 'Db'])
        self.assertEqual('C7(b9)', name)

    # ------------------------------------------------------------------ #
    # Validation rule 2: (maj7 or P5) + tritone → #11                    #
    # ------------------------------------------------------------------ #

    def test_rule2_sharp11_with_5th(self):
        """G7(#11): tritone + perfect 5th → tritone is #11 not b5."""
        name = self._chord(['G', 'B', 'D', 'F', 'Db'])
        self.assertEqual('G7(#11)', name)

    def test_rule2_sharp11_with_maj7(self):
        """Cmaj7(#11): tritone + maj7 → tritone is #11 not b5."""
        name = self._chord(['C', 'E', 'G', 'B', 'Gb'])
        self.assertEqual('Cmaj7(#11)', name)

    def test_rule2_flat5_without_5th(self):
        """Bm7b5: tritone without maj7 or P5 → tritone stays b5."""
        name = self._chord(['B', 'D', 'F', 'A'])
        self.assertEqual('Bm7b5', name)

    # ------------------------------------------------------------------ #
    # Validation rule 3: perfect 4th → sus4                               #
    # ------------------------------------------------------------------ #

    def test_rule3_sus4_no_third(self):
        """Csus4: perfect 4th present, no 3rd → sus4, not minor/major."""
        name = self._chord(['C', 'F', 'G'])
        self.assertEqual('Csus4', name)

    def test_rule3_sus4_7(self):
        """G7sus4: 4th + b7 → 7sus4."""
        name = self._chord(['G', 'C', 'D', 'F'])
        self.assertEqual('G7sus4', name)


class TestIRealChordTranslation(unittest.TestCase):
    """Tests that chord names are correctly translated to iReal Pro canonical form."""

    def _ireal(self, chord_name: str, bass: str = '') -> str:
        from chords import ProgressionItem, Chord, Position, TimeSignature
        pos = Position(1, 1, TimeSignature(4, 4))
        item = ProgressionItem(chord=Chord(chord_name), position=pos, bass_note=bass)
        return item.ireal_chord_name()

    def test_major_triad(self):
        self.assertEqual('C', self._ireal('C'))

    def test_major7_to_caret7(self):
        self.assertEqual('C^7', self._ireal('Cmaj7'))

    def test_minor_to_dash(self):
        self.assertEqual('A-', self._ireal('Am'))

    def test_minor7_to_dash7(self):
        self.assertEqual('A-7', self._ireal('Am7'))

    def test_minor_major7(self):
        self.assertEqual('A-^7', self._ireal('AmM7'))

    def test_half_diminished(self):
        self.assertEqual('Bh7', self._ireal('Bm7b5'))

    def test_diminished7(self):
        self.assertEqual('Bo7', self._ireal('Bdim7'))

    def test_diminished_triad(self):
        self.assertEqual('Bo', self._ireal('Bdim'))

    def test_augmented_triad(self):
        self.assertEqual('C+', self._ireal('Caug'))

    def test_six_nine_no_slash(self):
        """C6/9 must become C69 — the slash would be misread as a bass note."""
        self.assertEqual('C69', self._ireal('C6/9'))

    def test_sus4_to_sus(self):
        self.assertEqual('Csus', self._ireal('Csus4'))

    def test_7sus4_to_7sus(self):
        self.assertEqual('G7sus', self._ireal('G7sus4'))

    def test_dominant7_unchanged(self):
        self.assertEqual('G7', self._ireal('G7'))

    def test_bass_note_preserved(self):
        self.assertEqual('G7/B', self._ireal('G7', bass='B'))

    def test_bass_note_with_translation(self):
        self.assertEqual('C^7/E', self._ireal('Cmaj7', bass='E'))

    def test_six_nine_with_bass(self):
        """C6/9 with bass note D: must produce C69/D not C6/9/D."""
        self.assertEqual('C69/D', self._ireal('C6/9', bass='D'))

    def test_minor7_with_extensions_in_url(self):
        prog = make_prog()
        prog.add_chord_by_name('Am7', 1, 1)
        body = url_body(prog)
        self.assertIn('A-7', body)

    def test_maj7_in_url(self):
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        body = url_body(prog)
        self.assertIn('C^7', body)

    def test_dim7_in_url(self):
        prog = make_prog()
        prog.add_chord_by_name('Bdim7', 1, 1)
        body = url_body(prog)
        self.assertIn('Bo7', body)

    def test_aug_in_url(self):
        prog = make_prog()
        prog.add_chord_by_name('Caug', 1, 1)
        body = url_body(prog)
        self.assertIn('C+', body)

    def test_maj7_with_9(self):
        """Cmaj7(9) (major 9) must translate to C^9."""
        self.assertEqual('C^9', self._ireal('Cmaj7(9)'))

    def test_maj7_with_sharp11(self):
        """Cmaj7(#11) must translate to C^7#11."""
        self.assertEqual('C^7#11', self._ireal('Cmaj7(#11)'))

    def test_maj7_with_13(self):
        """Cmaj7(13) (major 13) must translate to C^13."""
        self.assertEqual('C^13', self._ireal('Cmaj7(13)'))

    def test_maj7_with_9_sharp11(self):
        """Cmaj7(9#11) (Lydian voicing) must translate to C^9#11."""
        self.assertEqual('C^9#11', self._ireal('Cmaj7(9#11)'))

    def test_m7b5_with_b9(self):
        """Bm7b5(b9) half-dim with b9 translates to Bh9 (closest valid iReal Pro quality)."""
        self.assertEqual('Bh9', self._ireal('Bm7b5(b9)'))

    def test_mM7_with_9(self):
        """AmM7(9) minor-major 9 must translate to A-^9."""
        self.assertEqual('A-^9', self._ireal('AmM7(9)'))


class TestSharpKeyRecognition(unittest.TestCase):
    """Tests sharp/flat note-name selection based on key signature."""

    def _notes_for_key(self, key: str) -> list[str]:
        from chords import get_note_names_for_key
        return get_note_names_for_key(key)

    def test_flat_key_uses_flats(self):
        notes = self._notes_for_key('F')
        self.assertIn('Bb', notes)
        self.assertNotIn('A#', notes)

    def test_sharp_key_uses_sharps(self):
        notes = self._notes_for_key('G')
        self.assertIn('F#', notes)
        self.assertNotIn('Gb', notes)

    def test_c_major_uses_sharps(self):
        """C major is a sharp key (no accidentals, but uses sharp names for raised degrees)."""
        notes = self._notes_for_key('C')
        self.assertIn('C#', notes)

    def test_d_major_uses_sharps(self):
        notes = self._notes_for_key('D')
        self.assertIn('C#', notes)
        self.assertIn('F#', notes)

    def test_bb_major_uses_flats(self):
        notes = self._notes_for_key('Bb')
        self.assertIn('Bb', notes)
        self.assertIn('Eb', notes)
        self.assertNotIn('A#', notes)
        self.assertNotIn('D#', notes)

    def test_minor_sharp_key(self):
        """A- (A minor, iReal Pro '-' suffix) is relative minor of C; uses sharp names."""
        notes = self._notes_for_key('A-')
        self.assertIn('C#', notes)

    def test_minor_flat_key(self):
        """D- (D minor) is a relative minor of F, uses flat names."""
        notes = self._notes_for_key('D-')
        self.assertIn('Bb', notes)

    # ------------------------------------------------------------------
    # Integration: chord recognition must work with sharp note names
    # ------------------------------------------------------------------

    def _chord_from_sharp_notes(self, notes: list[str]) -> str | None:
        from chords import Chord
        c = Chord.from_notes(notes)
        return c.name if c is not None else None

    def test_e7_with_sharp_major_third(self):
        """E7 uses G# (sharp major 3rd); ['E','G#','B','D'] → E7."""
        name = self._chord_from_sharp_notes(['E', 'G#', 'B', 'D'])
        self.assertEqual('E7', name)

    def test_d_major_sharp_notes(self):
        """D major triad uses F# and C#; ['D','F#','A'] → D."""
        name = self._chord_from_sharp_notes(['D', 'F#', 'A'])
        self.assertEqual('D', name)

    def test_sharp_minor7(self):
        """F#m7: ['F#','A','C#','E'] → F#m7."""
        name = self._chord_from_sharp_notes(['F#', 'A', 'C#', 'E'])
        self.assertEqual('F#m7', name)

    def test_sharp_dominant_recognized_not_none(self):
        """A7 with sharp spellings: ['A','C#','E','G'] must be recognised."""
        name = self._chord_from_sharp_notes(['A', 'C#', 'E', 'G'])
        self.assertIsNotNone(name)
        self.assertEqual('A7', name)

    def test_sharp_flat_mixed(self):
        """Mixed sharp/flat input: ['G','Bb','D'] → Gm (Bb = flat, but still recognised)."""
        name = self._chord_from_sharp_notes(['G', 'Bb', 'D'])
        self.assertEqual('Gm', name)

    # ------------------------------------------------------------------
    # Verify that invalid keys fall back to defaults in _SHARP_KEYS
    # ------------------------------------------------------------------

    def test_invalid_key_returns_flat_list(self):
        """An unrecognised key string must not raise; flat list is returned."""
        notes = self._notes_for_key('X')  # not a valid iReal Pro key
        self.assertEqual(notes, self._notes_for_key('Db'))  # falls back to flat

    def test_f_sharp_major_not_sharp_key(self):
        """F# is not a valid iReal Pro key; get_note_names_for_key returns flats."""
        notes = self._notes_for_key('F#')
        self.assertIn('Gb', notes)  # flat list, not sharp list


class TestDom7b5Recognition(unittest.TestCase):
    """Tests that dominant 7(b5) chords are recognised and exported correctly.

    Regression for bug: C7b5 was exported as C7, ignoring the flat-5.
    """

    def _chord(self, notes: list[str]) -> str:
        from chords import Chord
        c = Chord.from_notes(notes)
        self.assertIsNotNone(c, f"from_notes({notes!r}) returned None")
        return c.name

    def _ireal(self, chord_name: str) -> str:
        from chords import ProgressionItem, Chord, Position, TimeSignature
        pos = Position(1, 1, TimeSignature(4, 4))
        item = ProgressionItem(chord=Chord(chord_name), position=pos, bass_note='')
        return item.ireal_chord_name()

    def test_c7b5_recognition(self):
        """C-E-Gb-Bb → C7(b5), not C7."""
        # C major 3rd (E=4), tritone (Gb=6), b7 (Bb=10)
        name = self._chord(['C', 'E', 'Gb', 'Bb'])
        self.assertEqual('C7(b5)', name)

    def test_c7b5_ireal_export(self):
        """C7(b5) must export as C7b5, not C7."""
        self.assertEqual('C7b5', self._ireal('C7(b5)'))

    def test_c7b5_in_url(self):
        prog = make_prog()
        prog.add_chord_by_name('C7(b5)', 1, 1)
        body = url_body(prog)
        self.assertIn('C7b5', body)

    def test_g7b5_recognition(self):
        """G7b5: G-B-Db-F."""
        name = self._chord(['G', 'B', 'Db', 'F'])
        self.assertEqual('G7(b5)', name)

    def test_7b5_distinct_from_7sharp11(self):
        """7(b5) has no P5; 7(#11) has a P5 — they must be distinct."""
        no_5th       = self._chord(['C', 'E', 'Gb', 'Bb'])          # C7(b5)
        seven_sharp11 = self._chord(['C', 'E', 'G', 'Bb', 'Gb'])   # C7(#11)
        self.assertEqual('C7(b5)', no_5th)
        self.assertEqual('C7(#11)', seven_sharp11)

    def test_7b9b5_recognition(self):
        """C7(b9b5): C-E-Gb-Bb-Db."""
        name = self._chord(['C', 'E', 'Gb', 'Bb', 'Db'])
        self.assertEqual('C7(b9b5)', name)

    def test_7b9b5_ireal_export(self):
        self.assertEqual('C7b9b5', self._ireal('C7(b9b5)'))

    def test_7sharp9b5_recognition(self):
        """C7(#9b5): C-E-Gb-Bb-Eb (Eb = #9 / b3)."""
        name = self._chord(['C', 'E', 'Gb', 'Bb', 'Eb'])
        self.assertEqual('C7(#9b5)', name)

    def test_7sharp9b5_ireal_export(self):
        self.assertEqual('C7#9b5', self._ireal('C7(#9b5)'))

    def test_9b5_recognition(self):
        """C7(9b5): C-E-Gb-Bb-D."""
        name = self._chord(['C', 'E', 'Gb', 'Bb', 'D'])
        self.assertEqual('C7(9b5)', name)

    def test_9b5_ireal_export(self):
        """C7(9b5) must export as C9b5."""
        self.assertEqual('C9b5', self._ireal('C7(9b5)'))


class TestNoChordMeasure(unittest.TestCase):
    """Tests for the no-chord (N.C.) measure support."""

    def test_nc_measure_exports_n(self):
        """A measure marked as N.C. must export the 'n' symbol in the measures section."""
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        prog.add_no_chord(2)
        meas = measures_body(prog)
        # The NC marker appears as '|n,' (barline + n + beat separator)
        # or 'n,' at the very start of a measure run.
        # Either way, 'n,' must appear inside the measures payload.
        self.assertIn('n,', meas)

    def test_is_no_chord_after_add(self):
        prog = make_prog()
        prog.add_no_chord(3)
        self.assertTrue(prog.is_no_chord(3))
        self.assertFalse(prog.is_no_chord(4))

    def test_remove_no_chord(self):
        prog = make_prog()
        prog.add_no_chord(2)
        prog.remove_no_chord(2)
        self.assertFalse(prog.is_no_chord(2))

    def test_remove_nonexistent_no_chord_is_safe(self):
        prog = make_prog()
        prog.remove_no_chord(99)  # must not raise

    def test_no_chord_in_json_round_trip(self):
        prog = make_prog()
        prog.add_chord_by_name('Am7', 1, 1)
        prog.add_no_chord(2)
        json_str = prog.to_json()
        restored = ChordProgression.from_json(json_str)
        self.assertTrue(restored.is_no_chord(2))
        self.assertFalse(restored.is_no_chord(1))

    def test_nc_last_measure_counted(self):
        """A lone N.C. measure must be included in last_measure()."""
        prog = make_prog()
        prog.add_no_chord(5)
        self.assertEqual(5, prog.last_measure())

    def test_empty_measure_exports_x(self):
        """A measure with no chord and no N.C. flag exports as 'x' (iReal Pro repeat-one-measure)."""
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        # Force a second measure with no chord
        prog.total_measures = 2
        meas = measures_body(prog)
        self.assertIn('x', meas)


class TestChordSpokenName(unittest.TestCase):
    """Tests for chord_name_to_spoken() human-readable chord name conversion."""

    def _spoken(self, name: str) -> str:
        from chords import chord_name_to_spoken
        return chord_name_to_spoken(name)

    def test_major_triad(self):
        self.assertEqual('C', self._spoken('C'))

    def test_minor_triad(self):
        self.assertEqual('A minor', self._spoken('Am'))

    def test_dominant7(self):
        self.assertEqual('G 7', self._spoken('G7'))

    def test_major7(self):
        self.assertEqual('C major 7', self._spoken('Cmaj7'))

    def test_minor7(self):
        self.assertEqual('D minor 7', self._spoken('Dm7'))

    def test_m7b5_half_diminished(self):
        self.assertEqual('B half diminished', self._spoken('Bm7b5'))

    def test_dim(self):
        self.assertEqual('C diminished', self._spoken('Cdim'))

    def test_dim7(self):
        self.assertEqual('C diminished 7', self._spoken('Cdim7'))

    def test_aug(self):
        self.assertEqual('C augmented', self._spoken('Caug'))

    def test_sus4(self):
        self.assertEqual('C sus 4', self._spoken('Csus4'))

    def test_7sus4(self):
        self.assertEqual('G 7 sus 4', self._spoken('G7sus4'))

    def test_mM7(self):
        self.assertEqual('C minor major 7', self._spoken('CmM7'))

    def test_add9(self):
        self.assertEqual('C add 9', self._spoken('Cadd9'))

    def test_six_nine(self):
        self.assertEqual('C 6 9', self._spoken('C6/9'))

    def test_six(self):
        self.assertEqual('C 6', self._spoken('C6'))

    def test_minor6(self):
        self.assertEqual('A minor 6', self._spoken('Am6'))

    def test_minor6_9(self):
        self.assertEqual('C minor 6 9', self._spoken('Cm6/9'))

    def test_sharp_root(self):
        self.assertEqual('F sharp 7', self._spoken('F#7'))

    def test_flat_root(self):
        self.assertEqual('B flat major 7', self._spoken('Bbmaj7'))

    def test_slash_chord(self):
        self.assertEqual('C over E', self._spoken('C/E'))

    def test_slash_chord_with_quality(self):
        self.assertEqual('G 7 over B', self._spoken('G7/B'))

    def test_slash_chord_flat_bass(self):
        self.assertEqual('C major 7 over E flat', self._spoken('Cmaj7/Eb'))

    def test_dominant7_with_b9_extension(self):
        self.assertEqual('G 7 flat 9', self._spoken('G7(b9)'))

    def test_dominant7_with_sharp9_extension(self):
        self.assertEqual('C 7 sharp 9', self._spoken('C7(#9)'))

    def test_m7b5_with_b9(self):
        self.assertEqual('B half diminished flat 9', self._spoken('Bm7b5(b9)'))

    def test_empty_string(self):
        self.assertEqual('', self._spoken(''))

    def test_progression_item_chord_name_spoken(self):
        """ProgressionItem.chord_name_spoken() must use the spoken form."""
        from chords import ProgressionItem, Chord, Position, TimeSignature
        pos = Position(1, 1, TimeSignature(4, 4))
        item = ProgressionItem(chord=Chord('Am7b5'), position=pos, bass_note='')
        self.assertEqual('A half diminished', item.chord_name_spoken())

    def test_progression_item_spoken_with_bass(self):
        """Slash chords in ProgressionItem.chord_name_spoken() include 'over'."""
        from chords import ProgressionItem, Chord, Position, TimeSignature
        pos = Position(1, 1, TimeSignature(4, 4))
        item = ProgressionItem(chord=Chord('Cmaj7'), position=pos, bass_note='E')
        self.assertEqual('C major 7 over E', item.chord_name_spoken())

    # ------------------------------------------------------------------ #
    # Compound (non-map) quality fallback (Issue 3 fix)                   #
    # ------------------------------------------------------------------ #

    def test_mM7_sharp11_spoken(self):
        """CmM7#11 must be spoken as 'C minor major 7 sharp 11', not literal."""
        self.assertEqual('C minor major 7 sharp 11', self._spoken('CmM7#11'))

    def test_mM7_b9_spoken(self):
        """AmM7b9: minor major 7 flat 9."""
        self.assertEqual('A minor major 7 flat 9', self._spoken('AmM7b9'))

    def test_m7_sharp9_spoken(self):
        """Dm7#9: minor 7 sharp 9."""
        self.assertEqual('D minor 7 sharp 9', self._spoken('Dm7#9'))

    def test_maj7_b5_spoken(self):
        """Cmaj7b5: major 7 flat 5."""
        self.assertEqual('C major 7 flat 5', self._spoken('Cmaj7b5'))


class TestGetSectionAtMeasure(unittest.TestCase):
    """Tests for ChordProgression.get_section_at_measure() (Issue 4 fix)."""

    def _prog_with_sections(self) -> 'ChordProgression':
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        prog.add_chord_by_name('Dm7', 3, 1)
        prog.add_chord_by_name('G7', 5, 1)
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        return prog

    def test_exact_section_mark_measure(self):
        """get_section_at_measure returns the mark on its own measure."""
        prog = self._prog_with_sections()
        self.assertEqual('*A', prog.get_section_at_measure(1))
        self.assertEqual('*B', prog.get_section_at_measure(5))

    def test_mid_section_measure(self):
        """Measures inside section A (before *B) return '*A'."""
        prog = self._prog_with_sections()
        self.assertEqual('*A', prog.get_section_at_measure(2))
        self.assertEqual('*A', prog.get_section_at_measure(3))
        self.assertEqual('*A', prog.get_section_at_measure(4))

    def test_section_b_member(self):
        """Measures >= 5 (section B start) return '*B'."""
        prog = self._prog_with_sections()
        self.assertEqual('*B', prog.get_section_at_measure(6))
        self.assertEqual('*B', prog.get_section_at_measure(10))

    def test_before_first_section_mark(self):
        """If no section mark at or before measure, returns None."""
        prog = make_prog()
        prog.add_section_mark(3, '*A')
        self.assertIsNone(prog.get_section_at_measure(1))
        self.assertIsNone(prog.get_section_at_measure(2))

    def test_no_section_marks(self):
        """Progression with no section marks returns None for any measure."""
        prog = make_prog()
        self.assertIsNone(prog.get_section_at_measure(1))


class TestDeleteChordsInRange(unittest.TestCase):
    """Tests for ChordProgression.delete_chords_in_measure_range()."""

    def test_deletes_chords_in_range(self):
        prog = make_prog()
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        removed = prog.delete_chords_in_measure_range(3, 5)
        self.assertEqual(removed, 3)
        self.assertFalse(any(i.position.measure in (3, 4, 5) for i in prog.items))

    def test_preserves_chords_outside_range(self):
        prog = make_prog()
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.delete_chords_in_measure_range(3, 5)
        remaining = [i.position.measure for i in prog.items]
        self.assertEqual(remaining, [1, 2, 6, 7, 8])

    def test_returns_zero_when_range_empty(self):
        prog = make_prog()
        prog.add_chord_by_name('Cmaj7', 1, 1)
        removed = prog.delete_chords_in_measure_range(5, 10)
        self.assertEqual(removed, 0)

    def test_single_measure_range(self):
        prog = make_prog()
        for m in range(1, 5):
            prog.add_chord_by_name('Cmaj7', m, 1)
        removed = prog.delete_chords_in_measure_range(2, 2)
        self.assertEqual(removed, 1)
        self.assertFalse(any(i.position.measure == 2 for i in prog.items))


class TestAddVoltaClearsHiddenChords(unittest.TestCase):
    """Tests that add_volta_start() removes chords in the hidden range."""

    def test_hidden_chords_removed_after_add_volta(self):
        """Chords in measures ending1_end+1 .. ending2_start-1 must be cleared."""
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        # V at measure 4 → hidden range should be measures 5..7
        prog.add_volta_start(4)
        vb = prog.volta_brackets[0]
        hr = vb.hidden_range()
        self.assertIsNotNone(hr)
        hidden_start, hidden_end = hr
        # No chord should remain in the hidden range
        hidden_chords = [
            i for i in prog.items
            if hidden_start <= i.position.measure <= hidden_end
        ]
        self.assertEqual(hidden_chords, [])

    def test_non_hidden_chords_preserved(self):
        """Chords outside the hidden range must not be affected."""
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        prog.add_volta_start(4)
        vb = prog.volta_brackets[0]
        hr = vb.hidden_range()
        hidden_start, hidden_end = hr
        non_hidden = [
            i for i in prog.items
            if not (hidden_start <= i.position.measure <= hidden_end)
        ]
        # Should still have chords at measures 1-4 and 8
        measures = sorted(i.position.measure for i in non_hidden)
        self.assertEqual(measures, [1, 2, 3, 4, 8])

    def test_return_message_includes_cleared_count(self):
        """add_volta_start() return string mentions removed chords when any."""
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        for m in range(1, 9):
            prog.add_chord_by_name('Cmaj7', m, 1)
        msg = prog.add_volta_start(4)
        self.assertIn('removed', msg)

    def test_no_hidden_chords_no_mention_in_message(self):
        """When hidden range is already empty, message does not say removed."""
        prog = make_prog()
        prog.add_section_mark(1, '*A')
        prog.add_section_mark(5, '*B')
        # Only add chords at the non-hidden positions
        for m in [1, 2, 3, 4, 8]:
            prog.add_chord_by_name('Cmaj7', m, 1)
        msg = prog.add_volta_start(4)
        self.assertNotIn('removed', msg)


class TestLocalization(unittest.TestCase):
    """Tests for the i18n module."""

    def test_english_fallback(self):
        """With no translation loaded, _() returns the original string."""
        import i18n
        original_translation = i18n._translation
        import gettext
        i18n._translation = gettext.NullTranslations()
        try:
            self.assertEqual(i18n._('Deleted'), 'Deleted')
            self.assertEqual(i18n._('Log is empty'), 'Log is empty')
        finally:
            i18n._translation = original_translation

    def test_russian_translation_loaded(self):
        """The Russian .mo file provides correct translations."""
        import i18n
        original_translation = i18n._translation
        try:
            i18n.set_language('ru')
            self.assertEqual(i18n._('Deleted'), 'Удалено')
            self.assertEqual(i18n._('Log is empty'), 'Журнал пуст')
            self.assertEqual(i18n._('MIDI devices refreshed'), 'MIDI-устройства обновлены')
        finally:
            i18n._translation = original_translation

    def test_unknown_language_fallback(self):
        """An unknown language code silently falls back to English."""
        import i18n
        original_translation = i18n._translation
        try:
            i18n.set_language('xx')
            self.assertEqual(i18n._('Deleted'), 'Deleted')
        finally:
            i18n._translation = original_translation


class TestVoiceChordMidi(unittest.TestCase):
    """Tests for the voice_chord_midi() MIDI voicing helper."""

    def _pc_set(self, notes: list[int]) -> set[int]:
        """Return the pitch-class set of a list of MIDI notes."""
        return {n % 12 for n in notes}

    def test_dom7_omits_fifth(self):
        """Dominant 7th chord should NOT include the perfect fifth (7 semitones)."""
        notes, _ = voice_chord_midi('C7')
        # C=0, E=4, Bb=10 — no G (7)
        pcs = self._pc_set(notes)
        self.assertNotIn(7, pcs)   # G not in C7 voicing
        self.assertIn(0, pcs)      # C (root)
        self.assertIn(4, pcs)      # E (major 3rd)
        self.assertIn(10, pcs)     # Bb (minor 7th)

    def test_maj7_keeps_fifth(self):
        """Major 7th chord MUST keep the perfect fifth (only dominant chords omit it)."""
        notes, _ = voice_chord_midi('Cmaj7')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G (fifth must be present for maj7)
        self.assertIn(0, pcs)      # C
        self.assertIn(4, pcs)      # E
        self.assertIn(11, pcs)     # B (major 7th)

    def test_dom9_omits_fifth(self):
        """Dominant 9th chord should NOT include the perfect fifth."""
        notes, _ = voice_chord_midi('C9')
        pcs = self._pc_set(notes)
        self.assertNotIn(7, pcs)   # G

    def test_dom13_omits_fifth(self):
        """Dominant 13th chord should NOT include the perfect fifth."""
        notes, _ = voice_chord_midi('C13')
        pcs = self._pc_set(notes)
        self.assertNotIn(7, pcs)   # G

    def test_minor7_keeps_fifth(self):
        """Minor 7th chord MUST keep the perfect fifth."""
        notes, _ = voice_chord_midi('Cm7')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G (the fifth) should be present
        self.assertIn(3, pcs)      # Eb (minor 3rd)
        self.assertIn(10, pcs)     # Bb (minor 7th)

    def test_minor9_keeps_fifth(self):
        """Minor 9th chord MUST keep the perfect fifth."""
        notes, _ = voice_chord_midi('Cm9')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G

    def test_minor13_keeps_fifth(self):
        """Minor 13th chord MUST keep the perfect fifth."""
        notes, _ = voice_chord_midi('Cm13')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G

    def test_minor_major7_keeps_fifth(self):
        """Minor-major 7th chord MUST keep the perfect fifth."""
        notes, _ = voice_chord_midi('CmM7')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G

    def test_triad_keeps_fifth(self):
        """Plain major triad keeps the fifth (no 7th present)."""
        notes, _ = voice_chord_midi('C')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G must stay

    def test_minor_triad_keeps_fifth(self):
        """Minor triad keeps the fifth."""
        notes, _ = voice_chord_midi('Cm')
        pcs = self._pc_set(notes)
        self.assertIn(7, pcs)      # G must stay

    def test_aug7_no_perfect_fifth(self):
        """Augmented 7th has #5 instead of 5; no perfect fifth to remove."""
        notes, _ = voice_chord_midi('Caug7')
        pcs = self._pc_set(notes)
        self.assertNotIn(7, pcs)   # No perfect G (expected: C, E, G#, Bb)
        self.assertIn(8, pcs)      # G# (#5)

    def test_7b5_no_perfect_fifth(self):
        """7(b5) has b5 instead of 5; voicing should not contain perfect fifth."""
        notes, _ = voice_chord_midi('C7(b5)')
        pcs = self._pc_set(notes)
        self.assertNotIn(7, pcs)   # no perfect G
        self.assertIn(6, pcs)      # Gb/F# (b5)

    # ------------------------------------------------------------------
    # Range tests: root E1–Bb2 (28–46), core Eb3–Ab4 (51–68)
    # ------------------------------------------------------------------

    def test_root_range(self):
        """Root note must be in the range E1–Bb2 (MIDI 28–46)."""
        for name in ('C', 'Cm7', 'Cmaj7', 'C7', 'C7sus4', 'Csus4'):
            notes, root_midi = voice_chord_midi(name)
            self.assertGreaterEqual(root_midi, 28,
                f"{name}: root {root_midi} below E1 (28)")
            self.assertLessEqual(root_midi, 46,
                f"{name}: root {root_midi} above Bb2 (46)")

    def test_core_range(self):
        """Core tones (all notes except root) must be in Eb3–Ab4 (MIDI 51–68)."""
        for name in ('C', 'Cm7', 'Cmaj7', 'C7'):
            notes, root_midi = voice_chord_midi(name)
            core_notes = [n for n in notes if n != root_midi]
            for n in core_notes:
                self.assertGreaterEqual(n, 51,
                    f"{name}: core note {n} below Eb3 (51)")
                self.assertLessEqual(n, 68,
                    f"{name}: core note {n} above Ab4 (68)")

    # ------------------------------------------------------------------
    # Jazz shell voicing: for dom7 family, b7 must be lower than maj3
    # ------------------------------------------------------------------

    def test_dom7_seventh_below_third(self):
        """In dom7 jazz shell voicing the b7 should be lower than the maj3."""
        notes, root = voice_chord_midi('C7')
        # Filter out root
        core = [n for n in notes if n != root]
        # Find Bb (pc=10) and E (pc=4) among core tones
        bb = next((n for n in core if n % 12 == 10), None)
        e  = next((n for n in core if n % 12 == 4), None)
        self.assertIsNotNone(bb, "C7 voicing should contain Bb")
        self.assertIsNotNone(e,  "C7 voicing should contain E")
        self.assertLess(bb, e, "b7 (Bb) should be lower than maj3 (E) in dom7 voicing")

    def test_dom9_seventh_below_third(self):
        """Dom9 chord: b7 must be lower than maj3 (same jazz shell rule)."""
        notes, root = voice_chord_midi('C9')
        core_ext = [n for n in notes if n != root]
        bb = next((n for n in core_ext if n % 12 == 10), None)
        e  = next((n for n in core_ext if n % 12 == 4), None)
        if bb is not None and e is not None:
            self.assertLess(bb, e, "b7 (Bb) should be lower than maj3 (E) in dom9")

    # ------------------------------------------------------------------
    # Sus chord voicing: root + (b7) + 9 + 11, no maj3, no perfect 5th
    # ------------------------------------------------------------------

    def test_7sus4_no_third(self):
        """7sus4 voicing must not include a major or minor third."""
        notes, root = voice_chord_midi('C7sus4')
        pcs = self._pc_set(notes)
        self.assertNotIn(4, pcs)  # no major 3rd (E)
        self.assertNotIn(3, pcs)  # no minor 3rd (Eb)

    def test_7sus4_no_fifth(self):
        """7sus4 voicing must not include the perfect fifth."""
        notes, root = voice_chord_midi('C7sus4')
        pcs = self._pc_set(notes)
        self.assertNotIn(7, pcs)  # no G (perfect 5th)

    def test_7sus4_has_ninth_and_eleventh(self):
        """7sus4 voicing includes b7, 9th, and 11th stacked above root."""
        notes, root = voice_chord_midi('C7sus4')
        pcs = self._pc_set(notes)
        self.assertIn(10, pcs)  # Bb (b7)
        self.assertIn(2, pcs)   # D (9th)
        self.assertIn(5, pcs)   # F (11th / sus4 tone)

    def test_sus4_no_third_no_fifth(self):
        """Plain sus4 voicing drops 3rd and 5th in favour of 9th + 11th."""
        notes, root = voice_chord_midi('Csus4')
        pcs = self._pc_set(notes)
        self.assertNotIn(4, pcs)  # no major 3rd
        self.assertNotIn(7, pcs)  # no perfect 5th


if __name__ == '__main__':
    unittest.main()
