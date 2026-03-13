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
sys.path.insert(0, os.path.dirname(__file__))

from chords import ChordProgression, TimeSignature, VoltaBracket, Position
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
        self.assertIn('Cmaj7', body)
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
        """find_chords_from_notes must succeed for C/E/G/C5 after deduplication."""
        from chords import NOTE_NAMES, find_chords_from_notes
        notes = [60, 64, 67, 72]  # C4, E4, G4, C5
        deduped = list(dict.fromkeys(NOTE_NAMES[n % 12] for n in notes))
        chords = find_chords_from_notes(deduped)
        self.assertTrue(len(chords) > 0)
        self.assertIn('C', str(chords[0]))


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


if __name__ == '__main__':
    unittest.main()
