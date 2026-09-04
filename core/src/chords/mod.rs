//! Гармония: распознавание аккордов, модели, транспонирование, вокализация
//! в MIDI. Порт `irealstudio/chords.py` (чистое ядро, без GUI и i18n).

pub mod export;
pub mod identify;
pub mod input;
pub mod ireal;
pub mod model;
pub mod notes;
pub mod persist;
pub mod progression;
pub mod spoken;
pub mod transpose;
pub mod voicing;

mod spoken_i18n; // вендоренный ru-каталог фраз озвучки (генерируется)

pub use identify::identify_chord_name;
pub use input::{normalize_bass_note, parse_chord_entry, ChordEntryError, ParsedChord};
pub use ireal::chord_name_to_ireal;
pub use model::{Chord, Position, ProgressionItem, SectionMark, TimeSignature, VoltaBracket};
pub use notes::{
    note_names_for_key, pc_of, root_pc_of_name, root_prefix, ALL_ROOTS, NOTE_NAMES,
    NOTE_NAMES_SHARP,
};
pub use progression::ChordProgression;
pub use spoken::chord_name_to_spoken;
pub use transpose::{transpose_chord_name, transpose_note_name};
pub use voicing::voice_chord_midi;
