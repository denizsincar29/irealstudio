from dataclasses import dataclass
from functools import total_ordering
from pychord import Chord, find_chords_from_notes

@dataclass
class TimeSignature:
    numerator: int
    denominator: int


    @classmethod
    def from_string(cls, time_signature_str: str):
        numerator, denominator = map(int, time_signature_str.split('/'))
        return cls(numerator, denominator)
    
    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"

@total_ordering
@dataclass
class Position:
    measure: int
    beat: int
    time_signature: TimeSignature = TimeSignature(4, 4)  # Default to 4/4 time

    def __str__(self) -> str:
        return f"{self.measure}:{self.beat}"
    
    @property
    def beat_from_start(self) -> int:
        return (self.measure - 1) * self.time_signature.numerator + self.beat

    def set_beat_from_start(self, total_beats: int):
        self.measure = (total_beats - 1) // self.time_signature.numerator + 1
        self.beat = (total_beats - 1) % self.time_signature.numerator + 1

    def new_from_beat_from_start(self, total_beats: int):
        measure = (total_beats - 1) // self.time_signature.numerator + 1
        beat = (total_beats - 1) % self.time_signature.numerator + 1
        return Position(measure, beat, self.time_signature)
    

    def __add__(self, other: int):
        # use the beat_from_start property to add beats, then convert back to measure and beat
        total_beats = self.beat_from_start + other
        return self.new_from_beat_from_start(total_beats)
    
    def __sub__(self, other: int):
        # Subtracting beats, ensuring we don't go 0 or negative
        total_beats = self.beat_from_start - other
        if total_beats < 1:
            total_beats = 1  # Prevent going before the start of the progression
        return self.new_from_beat_from_start(total_beats)
    
    
    # >> and << for adding measures
    def __rshift__(self, other: int):
        return Position(self.measure + other, self.beat, self.time_signature)
    
    def __lshift__(self, other: int):
        # Subtracting measures, ensuring we don't go 0 or negative        new_measure = self.measure - other
        if new_measure < 1:
            new_measure = 1  # Prevent going before the start of the progression
        return Position(self.measure - other, self.beat, self.time_signature)

    def __eq__(self, other):
        return (self.measure == other.measure and 
                self.beat == other.beat and 
                self.time_signature == other.time_signature)
    
    def __lt__(self, other):
        if self.measure == other.measure:
            return self.beat < other.beat
        return self.measure < other.measure
    
    def __gt__(self, other):
        if self.measure == other.measure:
            return self.beat > other.beat
        return self.measure > other.measure

@total_ordering
@dataclass
class ProgressionItem:
    chord: Chord
    position: Position

    def __str__(self) -> str:
        return f"{self.chord} at {self.position}"
    def __eq__(self, other):
        return self.position == other.position and self.chord == other.chord
    
    def __lt__(self, other):
        return self.position < other.position
    
    def __gt__(self, other):
        return self.position > other.position
    

# omg how to make type Chord progression == list of ProgressionItem
@dataclass
class ChordProgression:
    title: str
    time_signature: TimeSignature
    key: str
    style: str
    items: list[ProgressionItem]

    def __str__(self) -> str:
        return f"{self.title} in {self.key} ({self.style}) with time signature {self.time_signature}:\n" + "\n".join(str(item) for item in self.items)
    
    def add_chord_raw(self, chord: Chord, position: Position):
        self.items.append(ProgressionItem(chord, position))
        self.items.sort()  # Ensure items are sorted by position

    def add_chord(self, chord: Chord, measure: int, beat: int):
        self.add_chord_raw(chord, Position(measure, beat, self.time_signature))

    def add_chord_by_name(self, chord_name: str, measure: int, beat: int):
        chord = Chord(chord_name)
        self.add_chord(chord, measure, beat)

    def add_chord_by_notes(self, notes: list[str], measure: int, beat: int):
        chords = find_chords_from_notes(notes)
        if chords:
            self.add_chord(chords[0], measure, beat)  # Add the first matching chord

    def add_chord_by_raw_data(self, midi: list[int], timestamp: float, bpm: int):
        # when recording chords, we get a list of midi note numbers, a timestamp, and the bpm of the recording
        # we can convert the timestamp to a position in the progression using the bpm and time signature
        beats_per_second = bpm / 60
        beat_related_pos = timestamp * beats_per_second
        # now, quantize the total beats to the nearest beat in the time signature
        quantized_beat = round(beat_related_pos) % self.time_signature.numerator
        measure = int(beat_related_pos) // self.time_signature.numerator
        # now the  tricky part!
        note_names = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]  # we are jazz musicians, we use flats
        notes = [note_names[midi_note % 12] for midi_note in midi]
        self.add_chord_by_notes(notes, measure, quantized_beat)

    def find_chords_at_position(self, position: Position) -> list[ProgressionItem]:
        return [item for item in self.items if item.position == position]
    
    def find_chords_in_measure(self, measure: int) -> list[ProgressionItem]:
        return [item for item in self.items if item.position.measure == measure]
    
    def measure_is_empty(self, measure: int) -> bool:
        return all(item.position.measure != measure for item in self.items)
    
    def find_last_chord_to_left(self, position: Position) -> ProgressionItem | None:
        left_items = [item for item in self.items if item.position < position]
        return left_items[-1] if left_items else None

    def find_next_chord_to_right(self, position: Position) -> ProgressionItem | None:
        right_items = [item for item in self.items if item.position > position]
        return right_items[0] if right_items else None    

    def validate(self):
        # delete any chords that are in the same position
        unique_positions = set()
        for item in self.items:
            if item.position in unique_positions:
                self.items.remove(item)
            else:
                unique_positions.add(item.position)


    # list methods
    def __len__(self):
        return len(self.items)
    
    def __getitem__(self, index):
        return self.items[index]
    
    def __setitem__(self, index, value):
        self.items[index] = value
        self.items.sort()  # Ensure items are sorted by position

    def __delitem__(self, index):
        del self.items[index]

    # iterator
    def __iter__(self):
        return iter(self.items)
    
    def export(self):
        raise NotImplementedError("Export functionality not implemented yet")