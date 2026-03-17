"""
pyrealpro - Tools for building iRealPro songs.

Source: https://github.com/splendidtoad/pyrealpro
This is a local copy of the pyrealpro module (v0.2.0) because the PyPI package
has a packaging issue that prevents import.
"""
from urllib.parse import quote

KEY_SIGNATURES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B', 'A-', 'Bb-', 'B-', 'C-', 'C#-',
                  'D-', 'Eb-', 'E-', 'F-', 'F#-', 'G-', 'G#-']

STYLES_JAZZ = ["Afro 12/8", "Ballad Double Time Feel", "Ballad Even", "Ballad Melodic", "Ballad Swing",
               "Blue Note", "Bossa Nova", "Doo Doo Cats", "Double Time Swing", "Even 8ths", "Even 8ths Open",
               "Even 16ths", "Guitar Trio", "Gypsy Jazz", "Latin", "Latin/Swing", "Long Notes", "Medium Swing",
               "Medium Up Swing", "Medium Up Swing 2", "New Orleans Swing", "Second Line", "Slow Swing",
               "Swing Two/Four", "Trad Jazz", "Up Tempo Swing", "Up Tempo Swing 2"]

STYLES_LATIN = ["Argentina: Tango", "Brazil: Bossa Acoustic", "Brazil: Bossa Electric", "Brazil: Samba",
                "Cuba: Bolero", "Cuba: Cha Cha Cha", "Cuba: Son Montuno 2-3", "Cuba: Son Montuno 3-2"]

STYLES_POP = ["Bluegrass", "Country", "Disco", "Funk", "Glam Funk", "House", "Reggae", "Rock", "Rock 12/8",
              "RnB", "Shuffle", "Slow Rock", "Smooth", "Soul", "Virtual Funk"]

STYLES_ALL = STYLES_JAZZ + STYLES_LATIN + STYLES_POP


class Song:
    """A class for building fake-book style chord charts that can be imported into iRealPro."""

    measures = None

    def __init__(self, **kwargs):
        self.title = kwargs.get('title', 'Untitled')

        key = kwargs.get('key', 'C')
        self.key = key if key in KEY_SIGNATURES else 'C'

        self.composer_name_first = kwargs.get('composer_name_first', 'Unknown')
        self.composer_name_last = kwargs.get('composer_name_last', 'Unknown')

        # Handle legacy 'composer' kwarg
        if 'composer' in kwargs and 'composer_name_first' not in kwargs:
            self.composer_name_first = kwargs['composer']

        style = kwargs.get('style', 'Medium Swing')
        if style not in STYLES_ALL:
            raise ValueError(f"{style} is not a valid iRealPro style.")
        self.style = style

        self.measures = kwargs.get('measures', [])

    @property
    def composer_name(self):
        if self.composer_name_first == 'Unknown' and self.composer_name_last == 'Unknown':
            return 'Unknown'
        if self.composer_name_last == 'Unknown':
            return self.composer_name_first
        return f"{self.composer_name_last} {self.composer_name_first}"

    def url(self, urlencode=True):
        if len(self.measures) == 0:
            self.measures.append(Measure(" "))
        self.measures[0].render_ts = True
        if self.measures[0].barline_open == "":
            self.measures[0].barline_open = "["
        if self.measures[-1].barline_close in ["", "|", None]:
            self.measures[-1].barline_close = "Z"

        measures_str = "".join(m.__str__() for m in self.measures)
        url = f"irealbook://{self.title}={self.composer_name}={self.style}={self.key}=n={measures_str}"

        if urlencode:
            return quote(url, safe=":/=")
        return url

    def __str__(self):
        return f"<{type(self).__name__} {id(self)}: {self.title}>"


class Measure:
    """Represents a single measure of an iRealPro song."""

    BARLINES_OPEN = ["[", "{"]
    BARLINES_CLOSE = ["|", "]", "}", "Z"]
    REHEARSAL_MARKS = ["*A", "*B", "*C", "*D", "*V", "*i", "S", "Q", "f"]
    ENDINGS = ["N1", "N2", "N3", "N0"]

    def __init__(self, chords, time_sig=None, rehearsal_marks=None, barline_open="", barline_close=None,
                 ending="", staff_text="", render_ts=False):
        if rehearsal_marks is None:
            rehearsal_marks = []
        if time_sig is None:
            time_sig = TimeSignature(4, 4)
        self.time_sig = time_sig
        if barline_open is None:
            barline_open = ""
        self.barline_open = barline_open
        self.ending = ending
        if barline_close is None or barline_close == "":
            barline_close = "|"
        self.barline_close = barline_close
        self.staff_text = staff_text
        self.render_ts = render_ts

        if type(chords) == str:
            self.chords = [chords] + [' '] * (self.time_sig.beats - 1)
        elif len(chords) == self.time_sig.beats:
            self.chords = [' ' if c is None else c for c in chords]
        elif self.time_sig.beats % len([c for c in chords if c not in ['s', 'l']]) == 0:
            pad = int((self.time_sig.beats - len(chords)) / len(chords))
            self.chords = []
            for chord in chords:
                self.chords.append(chord)
                self.chords.extend([' '] * pad)
        else:
            raise ValueError(f"Expected data for {self.time_sig.beats} beats, got {len(chords)} instead.")

        if type(rehearsal_marks) == str:
            self.rehearsal_marks = [rehearsal_marks]
        else:
            self.rehearsal_marks = list(rehearsal_marks)
        if not all(x in self.REHEARSAL_MARKS for x in self.rehearsal_marks):
            raise ValueError("Found one or more unrecognized rehearsal marks.")

    def __str__(self):
        chords_sep = "," if len(self.chords) > 1 else ""
        chords_str = chords_sep.join(self.chords)
        ts = self.time_sig if self.render_ts else ""
        staff_text = f"<{self.staff_text}>" if self.staff_text else ""
        rehearsal_marks_start = "".join(x for x in self.rehearsal_marks if x[0] not in ['Q', 'f'])
        rehearsal_marks_end = "".join(x for x in self.rehearsal_marks if x[0] in ['Q', 'f'])
        return f"{rehearsal_marks_start}{self.barline_open}{ts}{staff_text}{self.ending}{chords_str}{rehearsal_marks_end}{self.barline_close}"


class TimeSignature:
    """Represents a musical time signature."""

    VALID_TIME_SIGNATURES = ['T44', 'T34', 'T24', 'T54', 'T64', 'T74', 'T22', 'T32', 'T58', 'T68', 'T78', 'T98', 'T12']

    def __init__(self, beats=4, duration=4):
        self.beats = beats
        self.duration = duration
        if str(self) not in self.VALID_TIME_SIGNATURES:
            raise ValueError(f"{beats}/{duration} is not supported by iRealPro.")

    def __str__(self):
        if self.beats == 12:
            return "T12"
        return f"T{self.beats}{self.duration}"
