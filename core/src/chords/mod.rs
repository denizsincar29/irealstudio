//! Гармония: распознавание аккордов, модели, транспонирование, вокализация
//! в MIDI. Порт `irealstudio/chords.py` (чистое ядро, без GUI и i18n).

pub mod identify;
pub mod ireal;
pub mod model;
pub mod notes;
pub mod transpose;
pub mod voicing;

pub use identify::identify_chord_name;
pub use ireal::chord_name_to_ireal;
pub use model::{Chord, Position, ProgressionItem, SectionMark, TimeSignature, VoltaBracket};
pub use notes::{
    note_names_for_key, pc_of, root_pc_of_name, root_prefix, ALL_ROOTS, NOTE_NAMES,
    NOTE_NAMES_SHARP,
};
pub use transpose::{transpose_chord_name, transpose_note_name};
pub use voicing::voice_chord_midi;
